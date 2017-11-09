import collections
import functools

import six

from dynamorm.exceptions import InvalidOtherModel


class RelationshipResolver(object):
    """This works like a property that is backed by a relationship proxy and resolves string model names into classes"""
    def __init__(self, relationship, model_registry):
        self.relationship = relationship
        self.model_registry = model_registry
        self.proxy_cache = {}

    def _get_proxy(self, instance):
        try:
            return self.proxy_cache[instance]
        except KeyError:
            # If other_model is a string, resolve it to an actual model by looking in the registry we were provided
            if isinstance(self.relationship.other_model, six.string_types):
                try:
                    self.relationship.other_model = self.model_registry[self.relationship.other_model]
                except KeyError:
                    raise InvalidOtherModel("{0} is not a valid other model".format(self.relationship.other_model))

            self.proxy_cache[instance] = self.relationship.PROXY(self.relationship, instance)
            return self.proxy_cache[instance]

    def __get__(self, instance, owner):
        return self._get_proxy(instance)

    def __set__(self, instance, value):
        proxy = self._get_proxy(instance)
        return proxy.assign(value)

    def __delete__(self, instance):
        proxy = self._get_proxy(instance)
        return proxy.delete()


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

        if self.relationship.get_mode == OneToMany.Batch:
            for inst in self.relationship.other_model.get_batch([keys for keys in other_keys]):
                yield inst
        else:
            for keys in other_keys:
                yield self.relationship.other_model.get(**keys)

    def assign(self, value):
        if not isinstance(value, collections.Mapping):
            raise ValueError("{0} must be set with a mapping", self.attr)

        new_value = []
        for inst in value:
            if not isinstance(inst, self.relationship.other_model):
                raise ValueError("{0} is not an instance of {1}".format(inst, self.relationship.other_model))

            new_value.append(inst.primary_key)

        setattr(self.instance, self.relationship.attr, new_value)

    def __len__(self):
        return len(getattr(self.instance, self.relationship.attr))

    def count(self):
        return len(getattr(self.instance, self.relationship.attr))

    def append(self, inst):
        if not isinstance(inst, self.relationship.other_model):
            raise ValueError("{0} is not an instance of {1}".format(inst, self.relationship.other_model))

        return getattr(self.instance, self.relationship.attr).append(inst.primary_key)

class BaseRelationship(object):
    PROXY = None

    def __init__(self, other_model, attr=None, required=False):
        self.other_model = other_model
        self.attr = attr
        self.required = required

    def schema_field(self, schema):
        raise NotImplementedError


class ManyToMany(BaseRelationship):
    PROXY = None


class OneToOne(BaseRelationship):
    """One to one relationship between two models"""
    PROXY = OneToOneProxy

    def schema_field(self, schema):
        return schema.key_field(required=self.required)


class OneToMany(BaseRelationship):
    """One to many relationship between a parent and children models"""
    PROXY = OneToManyProxy

    Individual = 1
    Batch = 2

    def __init__(self, other_model, attr=None, required=False, get_mode=Individual):
        super(OneToMany, self).__init__(other_model, attr=attr, required=required)
        self.get_mode = get_mode

    def schema_field(self, schema):
        return schema.keys_field(required=self.required)
