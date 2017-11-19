"""Relationships leverage the native tables & indexes in DynamoDB to allow more concise definition and access of related
objects in your Python code.

You define relationships along side your Schema and Indexes on your model, and must provide the query used to map the
related models together.  You can also supply a "back reference" query to have the other side of the relationship also
have a relationship back to the defining model.

DynamORM provides the following relationship types:

* :py:class:`dynamorm.relationships.OneToOne` - Useful when you have a large number of attributes to store and you want
  to break them up over multiple tables for performance in querying.

* :py:class:`dynamorm.relationships.OneToMany` / :py:class:`dynamorm.relationships.ManyToOne` - Useful when you have an
  instance of one model that has a collection of related instances of another model.  You use ``OneToMany`` or
  ``ManyToOne`` depending on which side of the relationship you are defining the attribute on.  You'll to use both
  interchangeably based on how your models are laid out since you need to pass a reference to the other model into the
  relationship.


Here's an example of how you could model the `Forum Application`_ from the DynamoDB Examples:

.. _Forum Application: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/SampleData.CreateTables.html#SampleData.CreateTables2

.. code-block:: python

    class Reply(DynaModel):
        class Table:
            name = 'replies'
            hash_key = 'forum_thread'
            range_key = 'created'
            read = 1
            write = 1

        class ByUser(GlobalIndex):
            name = 'replies-by-user'
            hash_key = 'user_name'
            range_key = 'message'
            projection = ProjectKeys()
            read = 1
            write = 1

        class Schema:
            forum_thread = String(required=True)
            created = String(required=True)
            user_name = String(required=True)
            message = String()

    class User(DynaModel):
        class Table:
            name = 'users'
            hash_key = 'name'
            read = 1
            write = 1

        class Schema:
            name = String(required=True)

        replies = OneToMany(
            Reply,
            index='ByUser',
            query=lambda user: dict(user_name=user.name),
            back_query=lambda reply: dict(name=reply.user_name)
        )

    class Thread(DynaModel):
        class Table:
            name = 'threads'
            hash_key = 'forum_name'
            range_key = 'subject'
            read = 1
            write = 1

        class ByUser(GlobalIndex):
            name = 'threads-by-user'
            hash_key = 'user_name'
            range_key = 'subject'
            projection = ProjectKeys()
            read = 1
            write = 1

        class Schema:
            forum_name = String(required=True)
            user_name = String(required=True)
            subject = String(required=True)

        user = ManyToOne(
            User,
            query=lambda thread: dict(name=thread.user_name),
            back_index='ByUser',
            back_query=lambda user: dict(user_name=user.name)
        )
        replies = OneToMany(
            Reply,
            query=lambda thread: dict(forum_thread='{0}\\n{1}'.format(thread.forum_name, thread.subject)),
            back_query=lambda reply: dict(
                forum_name=reply.forum_thread.split('\\n')[0],
                subject=reply.forum_thread.split('\\n')[1]
            )
        )

    class Forum(DynaModel):
        class Table:
            name = 'forums'
            hash_key = 'name'
            read = 1
            write = 1

        class Schema:
            name = String(required=True)

        threads = OneToMany(
            Thread,
            query=lambda forum: dict(forum_name=forum.name),
            back_query=lambda thread: dict(name=thread.forum_name)
        )
"""

import six

from .signals import pre_save, post_save, pre_update, post_update


@six.python_2_unicode_compatible
class DefaultBackReference(object):
    """When given a relationship the string representation of this will be a "python" string name of the model the
    relationship exists on.

    For example, if there's a relationship defined on a model named ``OrderItem`` this would render ``order_item``.
    """
    def __init__(self, relationship):
        self.relationship = relationship

    def __str__(self):
        return ''.join([
            x if x.islower() else '_{0}'.format(x.lower())
            for x in self.relationship.this.__name__
        ]).strip('_')


class Relationship(object):
    BackReferenceClass = None
    BackReferenceTemplate = None

    def __init__(self, other, query, index=None, back_query=None, back_index=None, back_reference=DefaultBackReference):
        self.this = None
        self.other = other
        self.query = query
        self.index = index
        self.back_query = back_query
        self.back_index = back_index
        self.back_reference = back_reference
        self.back_reference_relationship = None

        self.accessor = self.other if index is None else getattr(self.other, index)

    def __repr__(self):
        return '{0}({1}, {2})'.format(self.__class__.__name__, self.this, self.other)

    def set_this_model(self, model):
        """Called from the metaclass once the model the relationship is being placed on has been initialized"""
        self.this = model

        if self.back_query is not None:
            if callable(self.back_reference):
                self.back_reference = self.back_reference(self)

            if self.back_reference is not None:
                self.set_back_reference()

    def set_back_reference(self):
        """Sets up a back reference to this model on the other model"""
        assert self.this is not None, "This model must be set prior to setting up a back reference!"

        if self.BackReferenceClass == 'self':
            back_ref_cls = self.__class__
        else:
            back_ref_cls = self.BackReferenceClass

        self.back_reference_relationship = back_ref_cls(
            self.this,
            query=self.back_query,
            index=self.back_index,
            back_query=self.query,
            back_reference=None
        )
        self.back_reference_relationship.set_this_model(self.other)

        ref_name = self.BackReferenceTemplate.format(back_reference=self.back_reference)
        setattr(self.other, ref_name, self.back_reference_relationship)
        self.other.relationships[ref_name] = self.back_reference_relationship

    def assign(self, value):
        """ """
        pass


class OneToOne(Relationship):
    """A One-to-One relationship is where two models (tables) have items that have a relation to exactly one instance in
    the other model.

    It is a useful pattern when you wish to split up large tables with many attributes where your "main" table is
    queried frequently and having all of the attributes included in the query results would increase your required
    throughput.  By splitting the data into two tables you can have lower throughput on the "secondary" table as the
    items will be lazily fetched only as they are accessed.
    """
    BackReferenceClass = 'self'
    BackReferenceTemplate = '{back_reference}'

    def __init__(self, other, query, index=None, back_query=None, back_index=None, back_reference=DefaultBackReference,
                 auto_create=True):
        super(OneToOne, self).__init__(other=other, query=query, index=index, back_query=back_query,
                                       back_index=back_index, back_reference=back_reference)
        self.other_inst = None
        self.auto_create = auto_create

    def __get__(self, obj, owner):
        if self.other_inst is None:
            self.get_other_inst(obj, create_missing=self.auto_create)
        return self.other_inst

    def __set__(self, obj, new_instance):
        if not isinstance(new_instance, self.other):
            raise TypeError("%s is not an instance of %s", new_instance, self.other)

        query = self.query(obj)
        for key, val in six.iteritems(query):
            setattr(new_instance, key, val)

        self.other_inst = new_instance

    def __delete__(self, obj):
        if self.other_inst is None:
            self.get_other_inst(obj, create_missing=False)

        if not self.other_inst:
            raise AttributeError("No other instance to delete")

        self.other_inst.delete()
        self.other_inst = None

    def set_this_model(self, model):
        super(OneToOne, self).set_this_model(model)

        if self.back_reference:
            pre_save.connect(self.pre_save, sender=model)
            post_save.connect(self.post_save, sender=model)
            pre_update.connect(self.pre_update, sender=model)
            post_update.connect(self.post_update, sender=model)

    def get_other_inst(self, obj, create_missing=False):
        query = self.query(obj)
        results = self.accessor.query(**query)

        try:
            self.other_inst = next(results)
        except StopIteration:
            if create_missing:
                query['partial'] = True
                self.other_inst = self.other(**query)

    def assign(self, value):
        return self.back_query(value)

    def pre_save(self, sender, instance, put_kwargs):
        if self.other_inst:
            self.other_inst.validate()

    def post_save(self, sender, instance, put_kwargs):
        if self.other_inst:
            self.other_inst.save(partial=False)

    def pre_update(self, sender, instance, conditions, update_item_kwargs, updates):
        if self.other_inst:
            self.other_inst.validate()

    def post_update(self, sender, instance, conditions, update_item_kwargs, updates):
        if self.other_inst:
            self.other_inst.save(partial=True)


class OneToMany(Relationship):
    """A One to Many relationship is defined on the "parent" model, where each instance has many related "child"
    instances of another model.
    """
    BackReferenceClass = OneToOne
    BackReferenceTemplate = '{back_reference}'

    def __get__(self, obj, owner):
        return QuerySet(self.other, self.query(obj), self.accessor if self.index else None)


class ManyToOne(OneToOne):
    """A Many To One relationship is defined on the "child" model, where many child models have one parent model."""
    BackReferenceClass = OneToMany
    BackReferenceTemplate = '{back_reference}s'


# XXX TODO: ManyToMany

class QuerySet(object):
    # XXX TODO: QuerySet should be moved to it's own namespace and should also be leveraged by the model classes so that
    # when you query on a Table or Index you get back one of these.  This will allow you to call .count() and .filter()
    # on existing queries to further refine them.
    def __init__(self, model, query, index=None):
        self.model = model
        self.query = query
        self.index = index

    def __iter__(self):
        if self.index:
            return self.index.query(**self.query)
        return self.model.query(**self.query)

    def __len__(self):
        return self.count()

    def count(self):
        query = self.query.copy()
        query['query_kwargs'] = dict(Select='COUNT')
        if self.index:
            query['query_kwargs']['IndexName'] = self.index.name
        resp = self.model.Table.query(**query)
        return resp['Count']

    def filter(self, **kwargs):
        new_query = self.query.copy()
        new_query.update(kwargs)
        return QuerySet(model=self.model, query=new_query, index=self.index)
