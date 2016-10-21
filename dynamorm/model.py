"""Models represent tables in DynamoDB and define the characteristics of the Dynamo service as well as the Marshmallow
schema that is used for validating and marshalling your data.

.. autoclass:: DynaModel
    :noindex:

"""

import inspect
import logging

try:
    import simplejson as json
except ImportError:
    import json

import six

from .table import DynamoTable3
from .types import Model
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

        for inner_class in ('Table', 'Schema'):
            if inner_class not in attrs or not inspect.isclass(attrs[inner_class]):
                raise DynaModelException("You must define an inner '{inner}' class on your '{name}' class".format(
                    inner=inner_class,
                    name=name
                ))

        # transform the Schema
        SchemaClass = type(
            '{name}Schema'.format(name=name),
            (Model,),
            dict(attrs['Schema'].__dict__),
        )
        attrs['Schema'] = SchemaClass

        # transform the Table
        TableClass = type(
            '{name}Table'.format(name=name),
            (DynamoTable3,),
            dict(attrs['Table'].__dict__)
        )
        attrs['Table'] = TableClass(schema=attrs['Schema'])

        # call our parent to get the new instance
        model = super(DynaModelMeta, cls).__new__(cls, name, parents, attrs)

        # give the Schema and Table objects a reference back to the model
        model.Schema._model = model
        model.Table._model = model

        return model


@six.add_metaclass(DynaModelMeta)
class DynaModel(object):
    """``DynaModel`` is the base class all of your models will extend from.  This model definition encapsulates the
    parameters used to create and manage the table as well as the schema for validating and marshalling data into object
    attributes.  It will also hold any custom business logic you need for your objects.

    Your class must define two inner classes that specify the Dynamo Table options and the Schema, respectively.

    The Dynamo Table options are defined in a class named ``Table``.  See the :mod:`dynamorm.table` module for
    more information.

    The document schema is defined in a class named ``Schema``, which should be filled out exactly as you would fill
    out any other Marshmallow :class:`~marshmallow.Schema` or Schematics :class:`~schematics.Model`.

    For example:

    .. code-block:: python

        # Marshmallow example
        import os

        from dynamorm import DynaModel

        from marshmallow import fields, validate, validates, ValidationError

        class Thing(DynaModel):
            class Table:
                name = '{env}-things'.format(env=os.environ.get('ENVIRONMENT', 'dev'))
                hash_key = 'id'
                read = 5
                write = 1

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

    .. code-block:: python

        # Schematics example
        import os

        from dynamorm import DynaModel

        from schematics import types

        class Thing(DynaModel):
            class Table:
                name = '{env}-things'.format(env=os.environ.get('ENVIRONMENT', 'dev'))
                hash_key = 'id'
                read = 5
                write = 1

            class Schema:
                id = types.StringType(required=True, max_length=10)
                name = types.StringType()
                color = types.StringType()
                compound = types.DictType(types.IntType, required=True)

            def say_hello(self):
                print("Hello.  {name} here.  My ID is {id} and I'm colored {color}".format(
                    id=self.id,
                    name=self.name,
                    color=self.color
                ))
    """

    def __init__(self, **raw):
        """Create a new instance of a DynaModel

        :param \*\*raw: The raw data as pulled out of dynamo. This will be validated and the sanitized
        input will be put onto ``self`` as attributes.
        """
        self._raw = raw
        data = self.Schema.dynamorm_validate(raw)
        for k, v in six.iteritems(data):
            setattr(self, k, v)

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
    def new_from_raw(cls, raw):
        """Return a new instance of this model from a raw (dict) of data that is loaded by our Schema

        :param dict raw: The attributes to use when creating the instance
        """
        if raw is None:
            return None
        return cls(**raw)

    @classmethod
    def get(cls, consistent=False, **kwargs):
        """Get an item from the table

        Example::

            Thing.get(hash_key="three")

        :param bool consistent: If set to True the get will be a consistent read
        :param \*\*kwargs: You must supply your hash key, and range key if used, with the values to get
        """
        item = cls.Table.get(consistent=consistent, **kwargs)
        return cls.new_from_raw(item)

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
        resp = cls.Table.query(query_kwargs=query_kwargs, **kwargs)
        return [
            cls.new_from_raw(raw)
            for raw in resp['Items']
            if raw is not None
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
        resp = cls.Table.scan(scan_kwargs=scan_kwargs, **kwargs)
        return [
            cls.new_from_raw(raw)
            for raw in resp['Items']
            if raw is not None
        ]

    def to_dict(self):
        obj = {}
        for k in self.Schema.dynamorm_fields():
            if hasattr(self, k):
                obj[k] = getattr(self, k)
        return obj

    def save(self, **kwargs):
        """Save this instance to the table

        The attributes on the item go through validation, so this may raise :class:`ValidationError`.
        """
        # XXX TODO: do partial updates if we know the item already exists, right now we just blindly put the whole
        # XXX TODO: item on every save
        return self.put(self.to_dict(), **kwargs)
