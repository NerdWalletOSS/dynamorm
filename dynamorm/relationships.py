"""Relationships leverage the native tables & indexes in DynamoDB to allow more concise definition and access of related
objects.

When you define a relationship you set the other model in the relationship as well as the "accessor", which defaults to
the ``Table`` but can be changed to a ``GlobalIndex`` if your relationship is based on a secondary index.
"""
import six

from .signals import post_save, post_update


class DefaultBackReference(object):
    pass


class Relationship(object):
    def __init__(self):
        self.this = None

    def set_this_model(self, model):
        self.this = model


class OneToOne(Relationship):
    """A One-to-One relationship is where two models (tables) have items that have a relation to exactly one model in
    the other model.

    It is a useful pattern when you wish to split up large tables with many attributes where your "main" table is
    queried frequently and having all of the attributes included in the query results would increase your required
    throughput.  By splitting the data into two tables you can have lower throughput on the "secondary" table as the
    items will be lazily fetched only as they are accessed.
    """
    def __init__(self, other, accessor='Table', query=None, back_reference=DefaultBackReference, auto_create=True):
        super(OneToOne, self).__init__()

        self.other = other
        self.other_inst = None
        self.accessor = getattr(other, accessor)
        self.query = query or OneToOne.default_query(self.accessor)
        self.back_reference = back_reference
        self.auto_create = auto_create

        # XXX TODO: handle back_reference

    def __get__(self, obj, owner):
        self.get_other_inst(obj, create_missing=self.auto_create)
        return self.other_inst

    def __set__(self, obj, new_instance):
        if not isinstance(new_instance, self.other):
            raise TypeError("%s is not an instance of %s", new_instance, self.other)

        query_kwargs = self.query(obj)
        for key, val in six.iteritems(query_kwargs):
            setattr(new_instance, key, val)

        self.other_inst = new_instance

    def __delete__(self, obj):
        if self.other_inst is None:
            self.get_other_inst(obj, create_missing=False)

        if self.other_inst:
            self.other_inst.delete()
            self.other_inst = None

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

    def set_this_model(self, model):
        super(OneToOne, self).set_this_model(model)

        post_save.connect(self.post_save, sender=model)
        post_update.connect(self.post_update, sender=model)

    def get_other_inst(self, obj, create_missing=False):
        query_kwargs = self.query(obj)
        results = self.other.query(**query_kwargs)

        try:
            self.other_inst = next(results)
        except StopIteration:
            if create_missing:
                query_kwargs['partial'] = True
                self.other_inst = self.other(**query_kwargs)

    def post_save(self, sender, instance, put_kwargs):
        if self.other_inst:
            self.other_inst.save(partial=False)

    def post_update(self, sender, instance, conditions, update_item_kwargs, updates):
        if self.other_inst:
            self.other_inst.save(partial=True)


class OneToMany(Relationship):
    """XXX TODO"""
    pass


class ManyToMany(Relationship):
    """XXX TODO"""
    pass