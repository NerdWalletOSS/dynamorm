import collections

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

    def value_to_keys(self, inst, value):
        """Return a dict of the Table keys suitable for ``**`` use when calling model operations"""
        if inst.Table.range_key:
            # XXX This assumes that both the hash & range are strings since we store them as a string
            # XXX This may cause problems if a complex decimal is used as a key
            hash_key, range_key = value.split()
            return {
                inst.Table.hash_key: hash_key,
                inst.Table.range_key: range_key
            }

        return {
            inst.Table.hash_key: value
        }

    def inst_to_value(self, inst):
        """Return a string value representing the Table keys in the given instance"""
        if inst.Table.range_key:
            # XXX See the note in value_to_keys
            return '{0} {1}'.format(
                getattr(inst, inst.Table.hash_key),
                getattr(inst, inst.Table.range_key)
            )
        return getattr(inst, inst.Table.hash_key)


class OneToOneProxy(BaseRelationshipProxy):
    """TODO"""
    _local_attrs = BaseRelationshipProxy._local_attrs + ('other', 'other_model')

    def get_other(self):
        other_value = getattr(self.instance, self.relationship.attr)
        keys = self.value_to_keys(self.relationship.other_model, other_value)
        self.other = self.relationship.other_model.get(**keys)

    def assign(self, new_instance):
        if not isinstance(new_instance, self.relationship.other_model):
            raise AttributeError("You cannot assign {0}, it is not an instance of {1}".format(
                value,
                self.relationship.other_model
            ))
        return setattr(self.instance, self.relationship.attr, self.inst_to_value(new_instance))

    def delete(self):
        return delattr(self.instance, self.relationship.attr)

    def __getattr__(self, name):
        if name in self._local_attrs:
            return self.__dict__.get(name)

        try:
            return getattr(self.other, name)
        except AttributeError:
            if self.other is None:
                self.get_other()
                return getattr(self.other, name)
            raise

    def __setattr__(self, name, value):
        if name in self._local_attrs:
            self.__dict__[name] = value
            return

        return setattr(self.other, name, value)

    def __delattr__(self, name):
        if name in self._local_attrs:
            raise AttributeError("Cannot delete {0}".format(name))

        return delattr(self.other, name)


class BaseRelationship(object):
    PROXY = None

    def __init__(self, other_model, attr):
        self.other_model = other_model
        self.attr = attr


class ManyToMany(BaseRelationship):
    pass


class OneToOne(BaseRelationship):
    """One to one relationship between two models"""
    PROXY = OneToOneProxy


class OneToMany(BaseRelationship):
    Individual = 1
    Batch = 2

    def __init__(self, other_model, attr, get_mode=Individual):
        super(OneToMany, self).__init__(other_model, attr)
        self.get_mode = get_mode

    def get_relations(self, model):
        attr_values = getattr(model, self.attr)

        if self.get_mode == OneToMany.Individual:
            return self.get_individual(model, attr_values)

        elif self.get_mode == OneToMany.Batch:
            return self.get_batch(model, attr_values)

    def get_individual(self, model, attr_values):
        for attr_value in attr_values:
            keys = self.value_to_keys(self.other_model, attr_value)
            yield self.other_model.get(**keys)

    def get_batch(self, model, attr_values):
        return self.other_model.get_batch([
            self.value_to_keys(attr_value)
            for attr_value in attr_values
        ])

    def set_relations(self, model, value):
        if not isinstance(value, collections.Mapping):
            raise ValueError("{0} must be set with a mapping", self.attr)

        new_value = []
        for inst in value:
            if not isinstance(inst, self.other_model):
                raise ValueError("{0} is not an instance of {1}".format(inst, self.other_model))

            new_value.append(self.inst_to_value(inst))

        setattr(model, self.attr, new_value)
