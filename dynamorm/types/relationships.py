class BaseRelationship(object):
    def __init__(self, other, attr, reference=None):
        # XXX TODO: support other as a string
        self.other = other
        self.attr = attr
        self.reference = reference

    def prepare(self, schema):
        # XXX TODO: return the correct field type for our document and setup other
        return 'foo'


class OneToMany(BaseRelationship):
    """A One To Many relationship is defined on parent schema, and is a list of primary keys on the child schema.

    It is represented as a list in the parent document and a string in the child document.
    """


class OneToOne(BaseRelationship):
    pass


class ManyToMany(BaseRelationship):
    pass


class ManyToOne(BaseRelationship):
    """A Many To One relationship is an inverse One To Many relationship, which can be used when the semantics of the
    relationship are better expressed on the child rather than the parent.
    """
    pass
