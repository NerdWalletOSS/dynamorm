import inspect
import logging
import sys

try:
    import simplejson as json
except ImportError:
    import json

import boto3
import botocore
import six

from marshmallow import Schema

from .table import DynamoTable3

log = logging.getLogger(__name__)


class MarshModelException(Exception):
    """Base exception for MarshModel problems"""


class HashKeyExists(MarshModelException):
    """A operating requesting a unique hash key failed"""


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
    """MarshModel is the base class that is used for defining your objects
    
    Your class must define two inner classes that specify the Dynamo Table options and the Marshmallow Schema,
    respectively.

    The Dynamo Table options are defined in a class named ``Table``.  TODO

    The Marshmallow Schema is defined in a class named ``Schema``, which should be filled out exactly as you would fill
    out any other :class:`~marshmallow.Schema`.  You do not need to have Schema extend from the marshmallow Schema class
    as we automatically do that for you, to make model definition more concise.

    .. code-block:: python

        class MyThing(MarshModel):
            class Table:
                name 'prod-things'
                hash_key = 'id'
                read = 1
                write = 1

            class Schema:
                id = fields.Str()
                ...

            def functionality(self)
                ...
    """
    _resource = None

    def __init__(self, raw=None, **kwargs):
        self._raw = raw

        for k, v in six.iteritems(kwargs):
            setattr(self, k, v)

    @classmethod
    def get_resource(cls, **kwargs):
        """Return the boto3 dynamodb resource, create it if it doesn't exist

        The resource is stored globally on the ``MarshModel`` class, so to influence the connection parameters you
        just need to call ``get_connection`` on any model with the correct kwargs BEFORE you use any of the models.
        """
        if MarshModel._resource is None:
            MarshModel._resource = boto3.resource('dynamodb', **kwargs)
        return MarshModel._resource

    @classmethod
    def table_exists(cls):
        return cls.Table.exists(cls.get_resource())

    @classmethod
    def create_table(cls):
        return cls.Table.create(cls.get_resource())

    @classmethod
    def delete_table(cls):
        return cls.Table.delete(cls.get_resource())

    @classmethod
    def put(cls, item, **kwargs):
        return cls.Table.put(cls.get_resource(), item, **kwargs)

    @classmethod
    def put_unique(cls, item, **kwargs):
        try:
            return cls.Table.put_unique(cls.get_resource(), item, **kwargs)
        except botocore.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise HashKeyExists
            raise

    @classmethod
    def put_batch(cls, *items, **batch_kwargs):
        """Put one or more items into the table"""
        return cls.Table.put_batch(cls.get_resource(), *items, **batch_kwargs)

    @classmethod
    def get(cls, **kwargs):
        raw = cls.Table.get(cls.get_resource(), **kwargs)
        data, errors = cls.Schema.load(raw)
        if errors:
            # XXX TODO: the data loaded from dynamo doesn't match our expected schema, what to do?
            # XXX TODO: some of our data will likely still have loaded, so for now just log an error and continue
            log.error("Data from dynamo failed schema validation! -> {0}".format(errors))
        if data:
            return cls(raw=raw, **data)

    def save(self):
        # XXX TODO: do partial updates if we know the item already exists, right now we just blindly put the whole
        # XXX TODO: item on every save
        data, errors = self.Schema.dump(self)
        if errors:
            raise ValueError("Failed to dump ourselves!? -> {0}".format(errors))
        return self.put(data)
