"""Relationships leverage the native tables & indexes in DynamoDB to allow more concise definition and access of related
objects.
"""


class DefaultBackReference(object):
    pass


class Relationship(object):
    pass


class OneToOne(Relationship):
    def __init__(self, other, accessor='Table', query=None, back_reference=DefaultBackReference, auto_create=True):
        self.other = other
        self.accessor = getattr(other, accessor)
        self.query = query or OneToOne.default_query(self.accessor)
        self.back_reference = back_reference
        self.auto_create = auto_create

    @staticmethod
    def default_query(accessor):
        if accessor.range_key:
            return lambda instance: {
                accessor.hash_key: getattr(instance, accessor.hash_key),
                accessor.range_key: getattr(instance, accessor.range_key)
            }
        else:
            return lambda instance: {
                accessor.hash_key: getattr(instance, accessor.hash_key),
            }

    def __get__(self, instance, owner):
        results = self.other.query(**self.query(instance))

        try:
            return next(results)
        except StopIteration:
            if not self.auto_create:
                return None

            query_func = self.default_query(owner.Table)
            kwargs = query_func(instance)
            kwargs['partial'] = True
            return self.other(**kwargs)
