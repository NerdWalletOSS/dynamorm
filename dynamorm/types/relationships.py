class BaseRelationship(object):
    def __init__(self, other, attr):
        self.other = other
        self.attr = attr

    def load_relations(self, model):
        raise NotImplementedError

    def get_kwargs(self, value):
        """Return a dict suitable for ``**`` use when calling ``.get`` to load the other side of a relationship"""
        if self.other.Table.range_key:
            hash_key, range_key = value.split()
            return {
                self.other.Table.hash_key: hash_key,
                self.other.Table.range_key: range_key
            }

        return {
            self.other.Table.hash_key: value
        }


class ManyToMany(BaseRelationship):
    pass


class OneToOne(BaseRelationship):
    def load_relations(self, model):
        attr_value = getattr(model, self.attr)
        get_kwargs = self.get_kwargs(attr_value)
        return self.other.get(**get_kwargs)


class OneToMany(BaseRelationship):
    """A One To Many relationship is defined on parent schema, and is a list of primary keys on the child schema.

    It is represented as a list in the parent document and a string in the child document.
    """
    def load_relations(self, model):
        attr_values = getattr(model, self.attr)
        for attr_value in attr_values:
            get_kwargs = self.get_kwargs(attr_value)
            yield self.other.get(**get_kwargs)
