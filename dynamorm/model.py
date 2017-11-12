"""Models represent tables in DynamoDB and define the characteristics of the Dynamo service as well as the Marshmallow
or Schematics schema that is used for validating and marshalling your data.

.. autoclass:: DynaModel
    :noindex:

"""

import inspect
import logging

import six

from .signals import (
    model_prepared,
    pre_init, post_init,
    pre_save, post_save,
    pre_update, post_update,
    pre_delete, post_delete
)
from .table import DynamoTable3
from .exceptions import DynaModelException

log = logging.getLogger(__name__)


class DynaModelMeta(type):
    """DynaModelMeta is a metaclass for the DynaModel class that transforms our Table and Schema classes

    Since we can inspect the data we need to build the full data structures needed for working with tables and indexes
    users can define for more concise and readable table definitions that we transform into the final. To allow for a
    more concise definition of DynaModels we do not require that users define their inner Schema class as extending
    from the :class:`~marshmallow.Schema`.  Instead, when the class is being defined we take the inner Schema and
    transform it into a new class named <Name>Schema, extending from :class:`~marshmallow.Schema`.  For example, on a
    model named ``Foo`` the resulting ``Foo.Schema`` object would be an instance of a class named ``FooSchema``, rather
    than a class named ``Schema``
    """
    def __new__(cls, name, parents, attrs):
        if name in ('DynaModel', 'DynaModelMeta'):
            return super(DynaModelMeta, cls).__new__(cls, name, parents, attrs)

        def should_transform(inner_class):
            """Closure to determine if we should transfer an inner class (Schema or Table)"""
            # if the inner class exists in our own attributes we use that
            if inner_class in attrs:
                return True

            # if any of our parent classes have the class then we use that
            for parent in parents:
                try:
                    getattr(parent, inner_class)
                    return False
                except AttributeError:
                    pass

            raise DynaModelException("You must define an inner '{inner}' class on your '{name}' class".format(
                inner=inner_class,
                name=name
            ))

        # transform the Schema
        # to allow both schematics and marshmallow to be installed and select the correct model we peek inside of the
        # dict and see if the item comes from either of them and lazily import our local Model implementation
        if should_transform('Schema'):
            for schema_item in six.itervalues(attrs['Schema'].__dict__):
                try:
                    module_name = schema_item.__module__
                except AttributeError:
                    continue

                if module_name.startswith('marshmallow.'):
                    from .types._marshmallow import Schema
                    break
                elif module_name.startswith('schematics.'):
                    from .types._schematics import Schema
                    break
            else:
                raise DynaModelException("Unknown Schema definitions, we couldn't find any supported fields/types")

            SchemaClass = type(
                '{name}Schema'.format(name=name),
                (Schema,) + attrs['Schema'].__bases__,
                dict(attrs['Schema'].__dict__),
            )
            attrs['Schema'] = SchemaClass

        indexes = {}

        # transform the Table
        if should_transform('Table'):
            # collect our indexes
            indexes = dict(
                (name, val)
                for name, val in six.iteritems(attrs)
                if inspect.isclass(val) and issubclass(val, Index)
            )

            TableClass = type(
                '{name}Table'.format(name=name),
                (DynamoTable3,),
                dict(attrs['Table'].__dict__)
            )
            attrs['Table'] = TableClass(schema=attrs['Schema'], indexes=indexes)

        # call our parent to get the new instance
        model = super(DynaModelMeta, cls).__new__(cls, name, parents, attrs)

        # Put the instantiated indexes back into our attrs.  We instantiate the Index class that's in the attrs and
        # provide the actual Index object from our table as the parameter.
        for name, klass in six.iteritems(indexes):
            index = klass(model, model.Table.indexes[klass.name])
            setattr(model, name, index)

        # give the Schema and Table objects a reference back to the model
        model.Schema._model = model
        model.Table._model = model

        model_prepared.send(model)

        return model


@six.add_metaclass(DynaModelMeta)
class DynaModel(object):
    """``DynaModel`` is the base class all of your models will extend from.  This model definition encapsulates the
    parameters used to create and manage the table as well as the schema for validating and marshalling data into object
    attributes.  It will also hold any custom business logic you need for your objects.

    Your class must define two inner classes that specify the Dynamo Table options and the Schema, respectively.

    The Dynamo Table options are defined in a class named ``Table``.  See the :mod:`dynamorm.table` module for
    more information.

    Any Local or Global Secondary Indexes you wish to create are defined as inner tables that extend from either the
    :class:`~LocalIndex` or :class:`~GlobalIndex` classes.  See the :mod:`dynamorm.table` module for more information.

    The document schema is defined in a class named ``Schema``, which should be filled out exactly as you would fill
    out any other Marshmallow :class:`~marshmallow.Schema` or Schematics :class:`~schematics.Model`.

    For example:

    .. code-block:: python

        # Marshmallow example
        import os

        from dynamorm import DynaModel, GlobalIndex, ProjectAll

        from marshmallow import fields, validate, validates, ValidationError

        class Thing(DynaModel):
            class Table:
                name = 'things'
                hash_key = 'id'
                read = 5
                write = 1

            class ByColor(GlobalIndex):
                name = 'by-color'
                hash_key = 'color'
                read = 5
                write = 1
                projection = ProjectAll()

            class Schema:
                id = fields.String(required=True)
                name = fields.String()
                color = fields.String(validate=validate.OneOf(('purple', 'red', 'yellow')))
                compound = fields.Dict(required=True)

                @validates('name')
                def validate_name(self, value):
                    # this is a very silly example just to illustrate that you can fill out the
                    # inner Schema class just like any other Marshmallow class
                    if name.lower() == 'evan':
                        raise ValidationError("No Evan's allowed")

            def say_hello(self):
                print("Hello.  {name} here.  My ID is {id} and I'm colored {color}".format(
                    id=self.id,
                    name=self.name,
                    color=self.color
                ))
    """

    def __init__(self, partial=False, **raw):
        """Create a new instance of a DynaModel

        :param \*\*raw: The raw data as pulled out of dynamo. This will be validated and the sanitized
        input will be put onto ``self`` as attributes.
        """
        pre_init.send(self.__class__, instance=self, partial=partial, raw=raw)

        self._raw = raw
        self._validated_data = self.Schema.dynamorm_validate(raw, partial=partial, native=True)
        for k, v in six.iteritems(self._validated_data):
            setattr(self, k, v)

        post_init.send(self.__class__, instance=self, partial=partial, raw=raw)

    @classmethod
    def _normalize_keys_in_kwargs(cls, kwargs):
        """Helper method to pass kwargs that will be used as Key arguments in Table operations so that they are
        validated against the Schema.  This is done so that if a field does transformation during validation or
        marshalling we can accept the untransformed value and pass the transformed value through to the Dyanmo
        operation.
        """
        def normalize(key):
            try:
                validated = cls.Schema.dynamorm_validate({key: kwargs[key]}, partial=True)
                kwargs[key] = validated[key]
            except KeyError:
                pass
        normalize(cls.Table.hash_key)
        normalize(cls.Table.range_key)
        return kwargs

    @classmethod
    def put(cls, item, **kwargs):
        """Put a single item into the table for this model

        The attributes on the item go through validation, so this may raise :class:`ValidationError`.

        :param dict item: The item to put into the table
        :param \*\*kwargs: All other kwargs are passed through to the put method on the table
        """
        return cls.Table.put(cls.Schema.dynamorm_validate(item), **kwargs)

    @classmethod
    def put_unique(cls, item, **kwargs):
        """Put a single item into the table for this model, with a unique attribute constraint on the hash key

        :param dict item: The item to put into the table
        :param \*\*kwargs: All other kwargs are passed through to the put_unique method on the table
        """
        return cls.Table.put_unique(cls.Schema.dynamorm_validate(item), **kwargs)

    @classmethod
    def put_batch(cls, *items, **batch_kwargs):
        """Put one or more items into the table

        :param \*items: The items to put into the table
        :param \*\*kwargs: All other kwargs are passed through to the put_batch method on the table

        Example::

            Thing.put_batch(
                {"hash_key": "one"},
                {"hash_key": "two"},
                {"hash_key": "three"},
            )
        """
        return cls.Table.put_batch(*[
            cls.Schema.dynamorm_validate(item) for item in items
        ], **batch_kwargs)

    @classmethod
    def update_item(cls, conditions=None, update_item_kwargs=None, **kwargs):
        """Update a item in the table

        :params conditions: A dict of key/val pairs that should be applied as a condition to the update
        :params update_item_kwargs: A dict of other kwargs that are passed through to update_item
        :params \*\*kwargs: Includes your hash/range key/val to match on as well as any keys to update
        """
        cls.Schema.dynamorm_validate(kwargs, partial=True)
        kwargs = cls._normalize_keys_in_kwargs(kwargs)
        return cls.Table.update(conditions=conditions, update_item_kwargs=update_item_kwargs, **kwargs)

    @classmethod
    def new_from_raw(cls, raw, partial=False):
        """Return a new instance of this model from a raw (dict) of data that is loaded by our Schema

        :param dict raw: The attributes to use when creating the instance
        """
        if raw is None:
            return None
        return cls(partial=partial, **raw)

    @classmethod
    def get(cls, consistent=False, **kwargs):
        """Get an item from the table

        Example::

            Thing.get(hash_key="three")

        :param bool consistent: If set to True the get will be a consistent read
        :param \*\*kwargs: You must supply your hash key, and range key if used
        """
        kwargs = cls._normalize_keys_in_kwargs(kwargs)
        item = cls.Table.get(consistent=consistent, **kwargs)
        return cls.new_from_raw(item)

    @classmethod
    def get_batch(cls, keys, consistent=False, attrs=None):
        """Generator to get more than one item from the table.

        :param keys: One or more dicts containing the hash key, and range key if used
        :param bool consistent: If set to True then get_batch will be a consistent read
        :param str attrs: The projection expression of which attrs to fetch, if None all attrs will be fetched
        """
        keys = (
            cls._normalize_keys_in_kwargs(key)
            for key in keys
        )
        items = cls.Table.get_batch(keys, consistent=consistent, attrs=attrs)
        for item in items:
            yield cls.new_from_raw(item, partial=attrs is not None)

    @classmethod
    def query(cls, **kwargs):
        """Execute a query on our table based on our keys

        You supply the key(s) to query based on as keyword arguments::

            Thing.query(foo="Mr. Foo")

        By default the ``eq`` condition is used.  If you wish to use any of the other `valid conditions for keys`_ use
        a double underscore syntax following the key name.  For example::

            Thing.query(foo__begins_with="Mr.")

        .. _valid conditions for keys: http://boto3.readthedocs.io/en/latest/reference/customizations/dynamodb.html#boto3.dynamodb.conditions.Key

        :param dict query_kwargs: Extra parameters that should be passed through to the Table query function
        :param \*\*kwargs: The key(s) and value(s) to query based on
        """  # noqa
        kwargs = cls._normalize_keys_in_kwargs(kwargs)
        return cls._yield_items('query', **kwargs)

    @classmethod
    def scan(cls, *args, **kwargs):
        """Execute a scan on our table

        You supply the attr(s) to query based on as keyword arguments::

            Thing.scan(age=10)

        By default the ``eq`` condition is used.  If you wish to use any of the other `valid conditions for attrs`_ use
        a double underscore syntax following the key name.  For example:

        * ``<>``: ``Thing.scan(foo__ne='bar')``
        * ``<``: ``Thing.scan(count__lt=10)``
        * ``<=``: ``Thing.scan(count__lte=10)``
        * ``>``: ``Thing.scan(count__gt=10)``
        * ``>=``: ``Thing.scan(count__gte=10)``
        * ``BETWEEN``: ``Thing.scan(count__between=[10, 20])``
        * ``IN``: ``Thing.scan(count__in=[11, 12, 13])``
        * ``attribute_exists``: ``Thing.scan(foo__exists=True)``
        * ``attribute_not_exists``: ``Thing.scan(foo__not_exists=True)``
        * ``attribute_type``: ``Thing.scan(foo__type='S')``
        * ``begins_with``: ``Thing.scan(foo__begins_with='f')``
        * ``contains``: ``Thing.scan(foo__contains='oo')``

        .. _valid conditions for attrs: http://boto3.readthedocs.io/en/latest/reference/customizations/dynamodb.html#boto3.dynamodb.conditions.Attr

        Accessing nested attributes also uses the double underscore syntax::

            Thing.scan(address__state="CA")
            Thing.scan(address__state__begins_with="C")

        Multiple attrs are combined with the AND (&) operator::

            Thing.scan(address__state="CA", address__zip__begins_with="9")

        If you want to combine them with the OR (|) operator, or negate them (~), then you can use the Q function and
        pass them as arguments into scan where each argument is combined with AND::

            from dynamorm import Q

            Thing.scan(Q(address__state="CA") | Q(address__state="NY"), ~Q(address__zip__contains="5"))

        The above would scan for all things with an address.state of (CA OR NY) AND address.zip does not contain 5.

        This returns a generator, which will continue to yield items until all matching the scan are produced,
        abstracting away pagination. More information on scan pagination: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Scan.html#Scan.Pagination

        :param dict scan_kwargs: Extra parameters that should be passed through to the Table scan function
        :param \*args: An optional list of Q objects that can be combined with or superseded the \*\*kwargs values
        :param \*\*kwargs: The key(s) and value(s) to filter based on
        """  # noqa
        kwargs = cls._normalize_keys_in_kwargs(kwargs)
        return cls._yield_items('scan', *args, **kwargs)

    @classmethod
    def _yield_items(cls, method_name, *args, **kwargs):
        """Private helper method to yield items from a scan or query response

        :param method_name: The cls.Table.<method_name> that should be called (one of: 'scan','query'))
        :param dict dynamo_kwargs: Extra parameters that should be passed through from query_kwargs or scan_kwargs
        :param \*\*kwargs: The key(s) and value(s) to filter based on
        """
        partial = kwargs.pop('partial', False)
        method = getattr(cls.Table, method_name)
        dynamo_kwargs_key = '_'.join([method_name, 'kwargs'])

        while True:
            # Fetch and yield values
            resp = method(*args, **kwargs)
            for raw in resp['Items']:
                if raw is not None:
                    yield cls.new_from_raw(raw, partial=partial)

            # Stop if no further pages
            if 'LastEvaluatedKey' not in resp:
                break

            try:
                # Reduce limit by amount scanned for subsequent calls
                kwargs[dynamo_kwargs_key]['Limit'] -= resp['ScannedCount']

                # Stop if we've reached the limit set by the caller
                if kwargs[dynamo_kwargs_key]['Limit'] <= 0:
                    break
            except KeyError:
                pass

            # Update calling kwargs with offset key
            try:
                kwargs[dynamo_kwargs_key]['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            except KeyError:
                kwargs[dynamo_kwargs_key] = {'ExclusiveStartKey': resp['LastEvaluatedKey']}

    def to_dict(self, native=False):
        obj = {}
        for k in self.Schema.dynamorm_fields():
            try:
                obj[k] = getattr(self, k)
            except AttributeError:
                pass
        return self.Schema.dynamorm_validate(obj, native=native)

    def save(self, partial=False, **kwargs):
        """Save this instance to the table

        :param bool partial: When False the whole document will be ``.put`` to the table.  When True only values that
                             have changed since the document was loaded will sent to the table via an ``.update``.
        :param \*\*kwargs: When partial is False these are passed through to the put method on the table.  When partial
                           is True these become the kwargs for update_item.  See ``.put`` & ``.update`` for more
                           details.

        The attributes on the item go through validation, so this may raise :class:`ValidationError`.
        """
        if not partial:
            pre_save.send(self.__class__, instance=self, put_kwargs=kwargs)
            resp = self.put(self.to_dict(), **kwargs)
            post_save.send(self.__class__, instance=self, put_kwargs=kwargs)
            return resp

        # Collect the fields to updated based on what's changed
        # XXX: Deeply nested data will still put the whole top-most object that has changed
        # TODO: Support the __ syntax to do deeply nested updates
        updates = dict(
            (k, v)
            for k, v in six.iteritems(self._validated_data)
            if getattr(self, k) != v
        )

        if not updates:
            log.warn("Partial save on %s produced nothing to update", self)
            return

        return self.update(update_item_kwargs=kwargs, **updates)

    def _add_hash_key_values(self, hash_dict):
        """Mutate a dicitonary to add key: value pair for a hash and (if specified) sort key.
        """
        hash_dict[self.Table.hash_key] = getattr(self, self.Table.hash_key)
        try:
            hash_dict[self.Table.range_key] = getattr(self, self.Table.range_key)
        except (AttributeError, TypeError):
            pass

    def update(self, conditions=None, update_item_kwargs=None, **kwargs):
        """Update this instance in the table

        New values are set via kwargs to this function:

        .. code-block:: python

            thing.update(foo='bar')

        This would set the ``foo`` attribute of the thing object to ``'bar'``.  You cannot change the Hash or Range key
        via an update operation -- this is a property of DynamoDB.

        You can supply a dictionary of conditions that influence the update.  In their simpliest form Conditions are
        supplied as a direct match (eq)::

            thing.update(foo='bar', conditions=dict(foo='foo'))

        This update would only succeed if foo was set to 'foo' at the time of the update.  If you wish to use any of the
        other `valid conditions for attrs`_ use a double underscore syntax following the key name.  You can also access
        nested attributes using the double underscore syntac.  See the scan method for examples of both.

        You can also pass Q objects to conditions as either a complete expression, or a list of expressions that will be
        AND'd together::

            thing.update(foo='bar', conditions=Q(foo='foo'))

            thing.update(foo='bar', conditions=Q(foo='foo') | Q(bar='bar'))

            # the following two statements are equivalent
            thing.update(foo='bar', conditions=Q(foo='foo') & ~Q(bar='bar'))
            thing.update(foo='bar', conditions=[Q(foo='foo'), ~Q(bar='bar')])

        If your update conditions do not match then a dynamorm.exceptions.ConditionFailed exception will be raised.

        As long as the update succeeds the attrs on this instance will be updated to match their new values.

        .. expressions supported by Dynamo: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.OperatorsAndFunctions.html
        """
        self._add_hash_key_values(kwargs)

        try:
            update_item_kwargs['ReturnValues'] = 'UPDATED_NEW'
        except TypeError:
            update_item_kwargs = {'ReturnValues': 'UPDATED_NEW'}

        pre_update.send(self.__class__, instance=self, conditions=conditions, update_item_kwargs=update_item_kwargs,
                        updates=kwargs)

        resp = self.update_item(conditions=conditions, update_item_kwargs=update_item_kwargs, **kwargs)

        # update our local attrs to match what we updated
        for key, val in six.iteritems(resp['Attributes']):
            setattr(self, key, val)

        post_update.send(self.__class__, instance=self, conditions=conditions, update_item_kwargs=update_item_kwargs,
                         updates=kwargs)
        return resp

    def delete(self):
        """Delete this record in the table."""
        delete_item_kwargs = {}
        self._add_hash_key_values(delete_item_kwargs)

        pre_delete.send(self.__class__, instance=self)
        resp = self.Table.delete_item(**delete_item_kwargs)
        post_delete.send(self.__class__, instance=self)
        return resp


class Index(object):
    def __init__(self, model, index):
        self.model = model
        self.index = index

    def query(self, query_kwargs=None, **kwargs):
        """Execute a query on this index

        See DynaModel.query for documentation on how to pass query arguments.
        """
        try:
            query_kwargs['IndexName'] = self.index.name
        except TypeError:
            query_kwargs = {'IndexName': self.index.name}

        return self.model.query(query_kwargs=query_kwargs, partial=self.projection.partial, **kwargs)

    def scan(self, scan_kwargs=None, **kwargs):
        """Execute a scan on this index

        See DynaModel.scan for documentation on how to pass scan arguments.
        """
        try:
            scan_kwargs['IndexName'] = self.index.name
        except TypeError:
            scan_kwargs = {'IndexName': self.index.name}

        return self.model.scan(scan_kwargs=scan_kwargs, partial=self.projection.partial, **kwargs)


class LocalIndex(Index):
    """Represents a Local Secondary Index on your table"""
    pass


class GlobalIndex(Index):
    """Represents a Local Secondary Index on your table"""
    pass


class Projection(object):
    pass


class ProjectAll(Projection):
    """Project all attributes from the Table into the Index

    Documents loaded using this projection will be fully validated by the schema.
    """
    partial = False


class ProjectKeys(Projection):
    """Project the keys from the Table into the Index.

    Documents loaded using this projection will be partially validated by the schema.
    """
    partial = True


class ProjectInclude(Projection):
    """Project the specified attributes into the Index.

    Documents loaded using this projection will be partially validated by the schema.

    .. code-block:: python

        class ByAuthor(GlobalIndex):
            ...
            projection = ProjectInclude('some_attr', 'other_attr')
    """
    partial = True

    def __init__(self, *include):
        self.include = include
