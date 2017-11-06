class BaseRelationship(object):
    def __init__(self, other, attr):
        self.other = other
        self.attr = attr

    def load_relations(self, model):
        raise NotImplementedError


class ManyToMany(BaseRelationship):
    pass


class OneToOne(BaseRelationship):
    def load_relations(self, model):
        if self.other.Table.range_key:
            hash_key, range_key = getattr(model, self.attr).split()
            get_kwargs = {
                self.other.Table.hash_key: hash_key,
                self.other.Table.range_key: range_key
            }
        else:
            get_kwargs = {
                self.other.Table.hash_key: getattr(model, self.attr)
            }

        return self.other.get(**get_kwargs)


class OneToMany(BaseRelationship):
    """A One To Many relationship is defined on parent schema, and is a list of primary keys on the child schema.

    It is represented as a list in the parent document and a string in the child document.
    """


class ManyToOne(BaseRelationship):
    """A Many To One relationship is an inverse One To Many relationship, which can be used when the semantics of the
    relationship are better expressed on the child rather than the parent.
    """
