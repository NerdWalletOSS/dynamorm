"""Models represent tables in DynamoDB and define the characteristics of the Dynamo service as well as the Marshmallow
schema that is used for validating and marshalling your data.

.. autoclass:: MarshModel
    :noindex:

"""

import inspect
import logging
import sys

try:
    import simplejson as json
except ImportError:
    import json

import six

from marshmallow import Schema

from .table import DynamoTable3

log = logging.getLogger(__name__)


class MarshModelException(Exception):
    """Base exception for MarshModel problems"""


class ValidationError(MarshModelException):
    """Schema validation failed"""
    # XXX TODO: this needs to be improved so that it actually shows the errors

    def __init__(self, errors, *args, **kwargs):
        super(ValidationError, self).__init__(*args, **kwargs)
        self.errors = errors


class MarshModelMeta(type):
    """MarshModelMeta is a metaclass for the MarshModel class that transforms our Table and Schema classes

    Since we can inspect the data we need to build the full data structures needed for working with tables and indexes
    users can define for more concise and readable table definitions that we transform into the final To allow for a
    more concise definition of MarshModel's we do not require that users define their inner Schema class as extending
    from the :class:`~marshmallow.Schema`.  Instead, when the class is being defined we take the inner Schema and
    transform it into a new class named <Name>Schema, extending from :class:`~marshmallow.Schema`.  For example, on a
    model named ``Foo`` the resulting ``Foo.Schema`` object would be an instance of a class named ``FooSchema``, rather
    than a class named ``Schema``
    """
    def __new__(cls, name, parents, attrs):
        if name in ('MarshModel', 'MarshModelMeta'):
            return super(MarshModelMeta, cls).__new__(cls, name, parents, attrs)

        for inner_class in ('Table', 'Schema'):
            if inner_class not in attrs or not inspect.isclass(attrs[inner_class]):
                raise MarshModelException("You must define an inner '{inner}' class on your '{name}' class".format(
                    inner=inner_class,
                    name=name
                ))

        # transform the Schema
        SchemaClass = type(
            '{name}Schema'.format(name=name),
            (Schema,),
            dict(attrs['Schema'].__dict__)
        )
        attrs['Schema'] = SchemaClass(strict=True)

        # transform the Table
        TableClass = type(
            '{name}Table'.format(name=name),
            (DynamoTable3,),
            dict(attrs['Table'].__dict__)
        )
        attrs['Table'] = TableClass(schema=attrs['Schema'])

        return super(MarshModelMeta, cls).__new__(cls, name, parents, attrs)



@six.add_metaclass(MarshModelMeta)
class MarshModel(object):
    """``MarshModel`` is the base class all of your models will extend from.  This model definition encapsulates the
    parameters used to create and manage the table as well as the schema for validating and marshalling data into object
    attributes.  It will also hold any custom business logic you need for your objects.
    
    Your class must define two inner classes that specify the Dynamo Table options and the Marshmallow Schema,
    respectively.

    The Dynamo Table options are defined in a class named ``Table``.  See the :mod:`dynamallow.table` module for
    more information.

    The Marshmallow Schema is defined in a class named ``Schema``, which should be filled out exactly as you would fill
    out any other :class:`~marshmallow.Schema`.
    
    .. note::
    
        You do not need to have Schema extend from the marshmallow :class:`~marshmallow.Schema` class as we
        automatically do that for you, to make model definition more concise.

        The same is true for the Table class.  We will automatically transform it so that it extends from the
        :class:`dynamallow.table.DynamoTable3`.

        In either case you're free to define them as extending from the actual base classes if you prefer to be explicit.

    For example:

    .. code-block:: python

        import os

        from dynamallow import MarshModel

        from marshmallow import fields, validate


        class Thing(MarshModel):
            class Table:
                name = '{env}-things'.format(env=os.environ.get('ENVIRONMENT', 'dev'))
                hash_key = 'id'
                read = 5
                write = 1

            class Schema:
                id = fields.String(required=True)
                name = fields.String()
                color = fields.String(validate=validate.OneOf(('purple', 'red', 'yellow')))

            def say_hello(self):
                print("Hello.  {name} here.  My ID is {id} and I'm colored {color}".format(
                    id=self.id,
                    name=self.name,
                    color=self.color
                ))
    """

    def __init__(self, raw=None, **kwargs):
        """Create a new instance of a MarshModel

        :param dict raw: The raw data that is being using to populate this model instance
        :param \*\*kwargs: Any other keywords passed through to the constructor become attributes on the instance
        """
        self._raw = raw

        for k, v in six.iteritems(kwargs):
            setattr(self, k, v)

    @classmethod
    def put(cls, item, **kwargs):
        """Put a single item into the table for this model
        
        The attributes on the item go through validation, so this may raise :class:`ValidationError`.

        :param dict item: The item to put into the table
        :param \*\*kwargs: All other kwargs are passed through to the put method on the table
        """
        data, errors = cls.Schema.load(item)
        if errors:
            raise ValidationError("Failed to put item", errors=errors)
        return cls.Table.put(data, **kwargs)

    @classmethod
    def put_unique(cls, item, **kwargs):
        """Put a single item into the table for this model, with a unique attribute constraint on the hash key

        :param dict item: The item to put into the table
        :param \*\*kwargs: All other kwargs are passed through to the put_unique method on the table
        """
        data, errors = cls.Schema.load(item)
        if errors:
            raise ValidationError("Failed to put unique item", errors=errors)
        return cls.Table.put_unique(data, **kwargs)

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
        data, errors = cls.Schema.load(items, many=True)
        if errors:
            raise ValidationError("Failed to put batch items", errors=errors)
        return cls.Table.put_batch(*data, **batch_kwargs)

    @classmethod
    def new_from_raw(cls, raw):
        data, errors = cls.Schema.load(raw)
        if errors:
            raise ValidationError("Failed to load data from Dynamo via our Schema", errors=errors)
        if data:
            return cls(raw=raw, **data)

    @classmethod
    def get(cls, consistent=False, **kwargs):
        """Get an item from the table

        Example::

            Thing.get(hash_key="three")

        :param bool consistent: If set to True the get will be a consistent read
        :param \*\*kwargs: You must supply your hash key, and range key if used, with the values to get
        """
        return cls.new_from_raw(cls.Table.get(consistent=consistent, **kwargs))

    @classmethod
    def query(cls, query_kwargs=None, **kwargs):
        """Execute a query on our table based on our keys

        You supply the key(s) to query based on as keyword arguments::

            Thing.query(foo="Mr. Foo")

        By default the ``eq`` condition is used.  If you wish to use any of the other `valid conditions for keys`_ use
        a double underscore syntax following the key name.  For example::

            Thing.query(foo__begins_with="Mr.")

        .. _valid conditions for keys: http://boto3.readthedocs.io/en/latest/reference/customizations/dynamodb.html#boto3.dynamodb.conditions.Key

        :param dict query_kwargs: Extra parameters that should be passed through to the Table query function
        :param \*\*kwargs: The key(s) and value(s) to query based on
        """
        return [
            cls.new_from_raw(raw)
            for raw in cls.Table.query(query_kwargs=query_kwargs, **kwargs)
        ]

    @classmethod
    def scan(cls, scan_kwargs=None, **kwargs):
        """Execute a scan on our table

        You supply the attr(s) to query based on as keyword arguments::

            Thing.scan(age=10)

        By default the ``eq`` condition is used.  If you wish to use any of the other `valid conditions for attrs`_ use
        a double underscore syntax following the key name.  For example::

            Thing.scan(age__lte=10)

        .. _valid conditions for attrs: http://boto3.readthedocs.io/en/latest/reference/customizations/dynamodb.html#boto3.dynamodb.conditions.Attr

        Accessing nested attributes also uses the double underscore syntax::

            Thing.scan(address__state="CA")
            Thing.scan(address__state__begins_with="C")

        :param dict scan_kwargs: Extra parameters that should be passed through to the Table scan function
        :param \*\*kwargs: The key(s) and value(s) to filter based on
        """
        return [
            cls.new_from_raw(raw)
            for raw in cls.Table.scan(scan_kwargs=scan_kwargs, **kwargs)
        ]

    def save(self):
        """Save this instance to the table
        
        The attributes on the item go through validation, so this may raise :class:`ValidationError`.
        """
        # XXX TODO: do partial updates if we know the item already exists, right now we just blindly put the whole
        # XXX TODO: item on every save
        data, errors = self.Schema.dump(self)
        if errors:
            raise ValidationError("Failed to dump {0} via our Schema".format(self.__class__.__name__), errors=errors)
        return self.Table.put(data)
