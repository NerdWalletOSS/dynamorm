import collections

import six

from dynamorm.exceptions import InvalidOtherModel
from dynamorm.signals import model_prepared, post_save


class BaseRelationshipProxy(object):
    _local_attrs = ('relationship', 'instance')

    def __init__(self, relationship, instance):
        self.relationship = relationship
        self.instance = instance

    def assign(self, value):
        raise AttributeError("Can't assign {0} relationship {1}".format(self.relationship, self.instance))

    def delete(self):
        raise AttributeError("Can't delete {0} relationship {1}".format(self.relationship, self.instance))


class OneToOneProxy(BaseRelationshipProxy):
    """TODO"""
    _local_attrs = BaseRelationshipProxy._local_attrs + ('other',)

    def get_other(self):
        other_keys = getattr(self.instance, self.relationship.attr)
        self.other = self.relationship.other_model.get(**other_keys)

    def assign(self, new_instance):
        if not isinstance(new_instance, self.relationship.other_model):
            raise AttributeError("You cannot assign {0}, it is not an instance of {1}".format(
                new_instance,
                self.relationship.other_model
            ))
        return setattr(self.instance, self.relationship.attr, new_instance.primary_key)

    def delete(self):
        return delattr(self.instance, self.relationship.attr)

    def with_lazy_other(self, func, *args, **kwargs):
        try:
            return func(self.other, *args, **kwargs)
        except AttributeError:
            if self.other is None:
                self.get_other()
                return func(self.other, *args, **kwargs)
            raise

    def __getattr__(self, name):
        if name in self._local_attrs:
            return self.__dict__.get(name)

        return self.with_lazy_other(getattr, name)

    def __setattr__(self, name, value):
        if name in self._local_attrs:
            self.__dict__[name] = value
            return

        return self.with_lazy_other(setattr, name, value)

    def __delattr__(self, name):
        if name in self._local_attrs:
            raise AttributeError("Cannot delete {0}".format(name))

        return self.with_lazy_other(delattr, name)


class OneToManyProxy(BaseRelationshipProxy):
    def __iter__(self):
        other_keys = getattr(self.instance, self.relationship.attr)

        if self.relationship.get_mode == OneToMany.GetBatch:
            for inst in self.relationship.other_model.get_batch(other_keys):
                yield inst
        else:
            for keys in other_keys:
                yield self.relationship.other_model.get(**keys)

    def __len__(self):
        return len(getattr(self.instance, self.relationship.attr))

    def count(self):
        return len(self)

    def append(self, inst):
        if not isinstance(inst, self.relationship.other_model):
            raise ValueError("{0} is not an instance of {1}".format(inst, self.relationship.other_model))

        attrs = getattr(self.instance, self.relationship.attr)
        attrs.append(inst.primary_key)

        if self.relationship.reference_setup:
            setattr(inst, self.relationship.reference_relationship.attr, self.instance.primary_key)

    def assign(self, value):
        if not isinstance(value, collections.Mapping):
            raise ValueError("{0} must be set with a mapping", self.attr)

        new_value = []
        for inst in value:
            if not isinstance(inst, self.relationship.other_model):
                raise ValueError("{0} is not an instance of {1}".format(inst, self.relationship.other_model))

            new_value.append(inst.primary_key)

            if self.relationship.reference_setup:
                setattr(inst, self.relationship.reference_relationship.attr, self.instance.primary_key)

        setattr(self.instance, self.relationship.attr, new_value)

    def delete(self):
        setattr(self.instance, self.relationship.attr, [])


@six.python_2_unicode_compatible
class AutomaticReference(object):
    def __init__(self, relationship):
        self.relationship = relationship

    def __str__(self):
        return self.relationship.this_model.__name__.lower()


class BaseRelationship(object):
    ProxyClass = None

    def __init__(self, other_model, reference=AutomaticReference, attr=None, required=False):
        self.this_model = None
        self.other_model = other_model
        self.attr = attr
        self.required = required
        self.proxy_cache = {}
        self.reference = reference
        self.reference_setup = False
        self.reference_name = None
        self.reference_relationship = None

        model_prepared.connect(self.resolve_models)

        if isinstance(self.other_model, six.string_types):
            from dynamorm.model import DynaModel  # noqa -- decoupling is hard...

            def find_in_subclasses(parent):
                for cls in parent.__subclasses__():
                    if self.other_model == cls.__name__:
                        return cls

                    cls = find_in_subclasses(cls)
                    if cls:
                        return cls

            # If our other model is a string then we need to see if it's already been definied.  If we can't find it
            # then we'll (hopefully) resolve it via a model_prepared signal.
            cls = find_in_subclasses(DynaModel)
            if cls:
                self.set_other(cls)

    def set_other(self, model):
        self.other_model = model

        if self.this_model is not None:
            self.set_reference()

    def set_this(self, model):
        self.this_model = model

        if self.other_model is not None:
            self.set_reference()

    def set_reference(self):
        if self.reference is None or self.reference_setup:
            return

        if callable(self.reference):
            self.reference = self.reference(self)

        reference_name = str(self.reference)
        self.reference_relationship = self.get_reference_relationship()

        self.other_model.relationships[reference_name] = self.reference_relationship
        setattr(self.other_model, reference_name, self.reference_relationship.proxy)

        reference_field = self.reference_relationship.schema_field(self.other_model.Schema)
        if reference_field:
            if self.reference_relationship.attr is None:
                self.reference_relationship.attr = '{0}_id'.format(reference_name)

            self.other_model.Schema.add_field(self.reference_relationship.attr, reference_field)

        self.reference_setup = True

    def get_reference_relationship(self):
        raise NotImplementedError

    def resolve_models(self, model):
        if self.other_model == model.__name__:
            self.set_other(model)

        if self.this_model is None and self in model.relationships.values():
            self.set_this(model)

        if self.this_model and not isinstance(self.other_model, six.string_types):
            # since we've resolved we can disconnect our receiver now
            model_prepared.disconnect(self.resolve_models)

    @property
    def proxy(self):
        """Returns another property to be used as a proxy in model attributes"""
        def get(instance):
            return self.proxy_for(instance)

        def assign(instance, value):
            proxy = self.proxy_for(instance)
            return proxy.assign(value)

        def delete(instance):
            proxy = self.proxy_for(instance)
            return proxy.delete()

        return property(get, assign, delete)

    def proxy_for(self, instance):
        try:
            return self.proxy_cache[instance]
        except KeyError:
            self.proxy_cache[instance] = self.ProxyClass(self, instance)
            return self.proxy_cache[instance]

    def schema_field(self, schema):
        pass


class OneToOne(BaseRelationship):
    """One to one relationship between two models"""
    ProxyClass = OneToOneProxy

    def schema_field(self, schema):
        return schema.key_field(required=self.required)

    def get_reference_relationship(self):
        return OneToOne(self.this_model, reference=None, required=self.required)


class OneToMany(BaseRelationship):
    """One to many relationship between a parent and children models"""
    ProxyClass = OneToManyProxy

    GetIndividual = 1
    GetBatch = 2

    def __init__(self, other_model, reference=AutomaticReference, attr=None, required=False, get_mode=GetIndividual):
        super(OneToMany, self).__init__(other_model, reference=reference, attr=attr, required=required)
        self.get_mode = get_mode

    def schema_field(self, schema):
        return schema.keys_field(required=self.required)

    def get_reference_relationship(self):
        return OneToOne(self.this_model, reference=None, required=self.required)


class ManyToMany(BaseRelationship):
    ProxyClass = None
