"""Relationships leverage the native tables & indexes in DynamoDB to allow more concise definition and access of related
objects.
"""

from .signals import post_save, post_update


class DefaultBackReference(object):
    pass


class Relationship(object):
    def __init__(self):
        self.this = None

    def set_this_model(self, model):
        self.this = model


class OneToOne(Relationship):
    def __init__(self, other, accessor='Table', query=None, back_reference=DefaultBackReference, auto_create=True):
        super(OneToOne, self).__init__()

        self.other = other
        self.other_inst = None
        self.accessor = getattr(other, accessor)
        self.query = query or OneToOne.default_query(self.accessor)
        self.back_reference = back_reference
        self.auto_create = auto_create

    def set_this_model(self, model):
        super(OneToOne, self).set_this_model(model)

        post_save.connect(self.post_save, sender=model)
        post_update.connect(self.post_update, sender=model)

    def __get__(self, instance, owner):
        query_kwargs = self.query(instance)
        results = self.other.query(**query_kwargs)

        try:
            self.other_inst = next(results)
        except StopIteration:
            if not self.auto_create:
                return

            query_kwargs['partial'] = True
            self.other_inst = self.other(**query_kwargs)

        return self.other_inst

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

    def post_save(self, sender, instance, put_kwargs):
        if self.other_inst:
            self.other_inst.save()

    def post_update(self, sender, instance, conditions, update_item_kwargs, updates):
        pass
