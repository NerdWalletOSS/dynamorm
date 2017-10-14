"""The inner ``Table`` class on ``DynaModel`` definitions becomes an instance of our
:class:`dynamorm.table.DynamoTable3` class.

The attributes you define on your inner ``Table`` class map to underlying boto data structures.  This mapping is
expressed through the following data model:

=========  ========  ====  ===========
Attribute  Required  Type  Description
=========  ========  ====  ===========
name       True      str   The name of the table, as stored in Dynamo.

hash_key   True      str   The name of the field to use as the hash key.
                           It must exist in the schema.

range_key  False     str   The name of the field to use as the range_key, if one is used.
                           It must exist in the schema.

read       True      int   The provisioned read throughput.

write      True      int   The provisioned write throughput.

=========  ========  ====  ===========


Indexes
-------

Like the ``Table`` definition, Indexes are also inner classes on ``DynaModel`` definitions, and they require the same
data model with one extra field.

==========  ========  ======  ===========
Attribute   Required  Type    Description
==========  ========  ======  ===========
projection  True      object  An instance of of :class:`dynamorm.model.ProjectAll`, :class:`dynamorm.model.ProjectKeys`,
                              or :class:`dynamorm.model.ProjectInclude`

==========  ========  ======  ===========

"""

import collections
import logging
import warnings

import boto3
import botocore
import six

from boto3.dynamodb.conditions import Key, Attr
from dynamorm.exceptions import MissingTableAttribute, InvalidSchemaField, HashKeyExists, ConditionFailed

log = logging.getLogger(__name__)


class DynamoCommon3(object):
    """Common properties & functions of Boto3 DynamORM objects -- i.e. Tables & Indexes"""
    REQUIRED_ATTRS = ('name', 'hash_key')
    OPTIONAL_ATTRS = ('range_key', 'read', 'write')

    def validate_attrs(self):
        for attr in self.REQUIRED_ATTRS:
            if not hasattr(self, attr):
                raise MissingTableAttribute("Missing required Table attribute: {0}".format(attr))

        for attr in self.OPTIONAL_ATTRS:
            if not hasattr(self, attr):
                setattr(self, attr, None)

        if self.hash_key not in self.schema.dynamorm_fields():
            raise InvalidSchemaField("The hash key '{0}' does not exist in the schema".format(self.hash_key))

        if self.range_key and self.range_key not in self.schema.dynamorm_fields():
            raise InvalidSchemaField("The range key '{0}' does not exist in the schema".format(self.range_key))

    @staticmethod
    def get_resource(**kwargs):
        """Return the boto3 dynamodb resource, create it if it doesn't exist

        The resource is stored globally on the ``DynamoCommon3`` class and is shared between all models. To influence
        the connection parameters you just need to call ``get_resource`` on any model with the correct kwargs BEFORE you
        use any of the models.
        """
        try:
            return DynamoCommon3._resource
        except AttributeError:
            DynamoCommon3._resource = boto3.resource('dynamodb', **kwargs)
            return DynamoCommon3._resource

    @property
    def resource(self):
        """Return the boto3 resource"""
        return self.get_resource()

    @property
    def key_schema(self):
        """Return an appropriate KeySchema, based on our key attributes and the schema object"""
        def as_schema(name, key_type):
            return {
                'AttributeName': name,
                'KeyType': key_type
            }
        schema = [as_schema(self.hash_key, 'HASH')]
        if self.range_key:
            schema.append(as_schema(self.range_key, 'RANGE'))
        return schema

    @property
    def provisioned_throughput(self):
        """Return an appropriate ProvisionedThroughput, based on our attributes"""
        return {
            'ReadCapacityUnits': self.read,
            'WriteCapacityUnits': self.write
        }


class DynamoIndex3(DynamoCommon3):
    REQUIRED_ATTRS = DynamoCommon3.REQUIRED_ATTRS + ('projection',)
    ARG_KEY = None

    def __init__(self, table, schema):
        self.table = table
        self.schema = schema
        self.validate_attrs()

    @property
    def index_args(self):
        if self.projection.__class__.__name__ == 'ProjectAll':
            projection = {
                'ProjectionType': 'ALL',
            }
        elif self.projection.__class__.__name__ == 'ProjectKeys':
            projection = {
                'ProjectionType': 'KEYS_ONLY',
            }
        elif self.projection.__class__.__name__ == 'ProjectInclude':
            projection = {
                'ProjectionType': 'INCLUDE',
                'NonKeyAttributes': self.projection.include
            }
        else:
            raise RuntimeError("Unknown projection mode!")

        return {
            'IndexName': self.name,
            'KeySchema': self.key_schema,
            'Projection': projection,
        }


class DynamoLocalIndex3(DynamoIndex3):
    ARG_KEY = 'LocalSecondaryIndexes'


class DynamoGlobalIndex3(DynamoIndex3):
    ARG_KEY = 'GlobalSecondaryIndexes'

    @property
    def index_args(self):
        args = super(DynamoGlobalIndex3, self).index_args
        args['ProvisionedThroughput'] = self.provisioned_throughput
        return args


class DynamoTable3(DynamoCommon3):
    """Represents a Table object in the Boto3 DynamoDB API

    This is built in such a way that in the future, when Amazon releases future boto versions, a new DynamoTable class
    can be authored that implements the same methods but maps through to the new semantics.
    """
    def __init__(self, schema, indexes=None):
        self.schema = schema
        self.validate_attrs()

        self.indexes = {}
        if indexes:
            for name, klass in six.iteritems(indexes):
                # Our indexes are just uninstantiated classes, but what we are interested in is what their parent class
                # name is.  We can reach into the MRO to find that out, and then determine our own index type.
                index_type = klass.__mro__[1].__name__
                if index_type == 'GlobalIndex':
                    index_class = DynamoGlobalIndex3
                elif index_type == 'LocalIndex':
                    index_class = DynamoLocalIndex3
                else:
                    raise RuntimeError('Unknown index type!')

                # Now that we know which of our classes we want to use, we create a new class on the fly that uses our
                # class with the attributes of the original class
                new_class = type(name, (index_class,), dict(
                    (k, v)
                    for k, v in six.iteritems(klass.__dict__)
                    if k[0] != '_'
                ))

                self.indexes[name] = new_class(self, schema)

    @classmethod
    def get_table(cls, name):
        """Return the boto3 Table object for this model, create it if it doesn't exist

        The Table is stored on the class for each model, so it is shared between all instances of a given model.
        """
        try:
            return cls._table
        except AttributeError:
            cls._table = cls.get_resource().Table(name)
            return cls._table

    @property
    def table(self):
        """Return the boto3 table"""
        return self.get_table(self.name)

    @property
    def exists(self):
        """Return True or False based on the existance of this tables name in our resource"""
        return any(
            table.name == self.name
            for table in self.resource.tables.all()
        )

    @property
    def table_attribute_fields(self):
        """Returns a list with the names of the table attribute fields (hash or range key)"""
        fields = set([self.hash_key])
        if self.range_key:
            fields.add(self.range_key)

        return fields

    @property
    def all_attribute_fields(self):
        """Returns a list with the names of all the attribute fields (hash or range key on the table or indexes)"""
        return self.table_attribute_fields.union(self.index_attribute_fields())

    def index_attribute_fields(self, index_name=None):
        """Return the attribute fields for a given index, or all indexes if omitted"""
        fields = set()

        for index in six.itervalues(self.indexes):
            if index_name and index.name != index_name:
                continue

            fields.add(index.hash_key)
            if index.range_key:
                fields.add(index.range_key)

        return fields

    @property
    def attribute_definitions(self):
        """Return an appropriate AttributeDefinitions, based on our key attributes and the schema object"""
        defs = []

        for name in self.all_attribute_fields:
            dynamorm_field = self.schema.dynamorm_fields()[name]
            field_type = self.schema.field_to_dynamo_type(dynamorm_field)

            defs.append({
                'AttributeName': name,
                'AttributeType': field_type,
            })

        return defs

    def create(self, wait=True):
        """DEPRECATED -- shim"""
        warnings.warn("DynamoTable3.create has been deprecated, please use DynamoTable3.create_table",
                      DeprecationWarning)
        return self.create_table(wait=wait)

    def create_table(self, wait=True):
        """Create a new table based on our attributes

        :param bool wait: If set to True, the default, this call will block until the table is created
        """
        if not self.read or not self.write:
            raise MissingTableAttribute("The read/write attributes are required to create a table")

        index_args = collections.defaultdict(list)
        for index in six.itervalues(self.indexes):
            index_args[index.ARG_KEY].append(index.index_args)

        table = self.resource.create_table(
            TableName=self.name,
            KeySchema=self.key_schema,
            AttributeDefinitions=self.attribute_definitions,
            ProvisionedThroughput=self.provisioned_throughput,
            **index_args
        )
        if wait:
            table.meta.client.get_waiter('table_exists').wait(TableName=self.name)
        return table

    def delete(self, wait=True):
        """Delete this existing table

        :param bool wait: If set to True, the default, this call will block until the table is deleted
        """
        self.table.delete()
        if wait:
            self.table.meta.client.get_waiter('table_not_exists').wait(TableName=self.name)
        return True

    def put(self, item, **kwargs):
        """Put a singular item into the table

        :param dict item: The data to put into the table
        :param \*\*kwargs: All other keyword arguments are passed through to the `DynamoDB Table put_item`_ function.

        .. _DynamoDB Table put_item: http://boto3.readthedocs.io/en/latest/reference/services/dynamodb.html#DynamoDB.Table.put_item
        """  # noqa
        return self.table.put_item(Item=remove_nones(item), **kwargs)

    def put_unique(self, item, **kwargs):
        try:
            kwargs['ConditionExpression'] = 'attribute_not_exists({0})'.format(self.hash_key)
            return self.put(item, **kwargs)
        except botocore.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise HashKeyExists
            raise

    def put_batch(self, *items, **batch_kwargs):
        with self.table.batch_writer(**batch_kwargs) as writer:
            for item in items:
                writer.put_item(Item=remove_nones(item))

    def update(self, update_item_kwargs=None, conditions=None, **kwargs):
        update_item_kwargs = update_item_kwargs or {}
        conditions = conditions or {}
        update_key = {}
        update_fields = []
        expr_names = {}
        expr_vals = {}

        UPDATE_FUNCTION_TEMPLATES = {
            'append': '#uk_{0} = list_append(#uk_{0}, :uv_{0})',
            'plus': '#uk_{0} = #uk_{0} + :uv_{0}',
            'minus': '#uk_{0} = #uk_{0} - :uv_{0}',
            'if_not_exists': '#uk_{0} = if_not_exists(#uk_{0}, :uv_{0})',
            None: '#uk_{0} = :uv_{0}'
        }

        for key, value in six.iteritems(kwargs):
            try:
                key, function = key.split('__', 1)
            except ValueError:
                function = None

            # make sure the field (key) exists
            if key not in self.schema.dynamorm_fields():
                raise InvalidSchemaField("{0} does not exist in the schema fields".format(key))

            if key in (self.hash_key, self.range_key):
                update_key[key] = value
            else:
                update_fields.append(UPDATE_FUNCTION_TEMPLATES[function].format(key))
                expr_names['#uk_{0}'.format(key)] = key
                expr_vals[':uv_{0}'.format(key)] = value

        update_item_kwargs['Key'] = update_key
        update_item_kwargs['UpdateExpression'] = 'SET {0}'.format(', '.join(update_fields))
        update_item_kwargs['ExpressionAttributeNames'] = expr_names
        update_item_kwargs['ExpressionAttributeValues'] = expr_vals

        if isinstance(conditions, collections.Mapping):
            condition_expression = Q(**conditions)
        elif isinstance(conditions, collections.Iterable):
            condition_expression = None
            for condition in conditions:
                try:
                    condition_expression = condition_expression & condition
                except TypeError:
                    condition_expression = condition
        else:
            condition_expression = conditions

        if condition_expression:
            update_item_kwargs['ConditionExpression'] = condition_expression

        try:
            return self.table.update_item(**update_item_kwargs)
        except botocore.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ConditionFailed(exc)
            raise

    def get_batch(self, keys, consistent=False, attrs=None, batch_get_kwargs=None):
        batch_get_kwargs = batch_get_kwargs or {}

        batch_get_kwargs['Keys'] = []
        for kwargs in keys:
            for k, v in six.iteritems(kwargs):
                if k not in self.schema.dynamorm_fields():
                    raise InvalidSchemaField("{0} does not exist in the schema fields".format(k))

            batch_get_kwargs['Keys'].append(kwargs)

        if consistent:
            batch_get_kwargs['ConsistentRead'] = True

        if attrs:
            batch_get_kwargs['ProjectionExpression'] = attrs

        while True:
            response = self.resource.batch_get_item(RequestItems={
                self.name: batch_get_kwargs
            })

            for item in response['Responses'][self.name]:
                yield item

            try:
                batch_get_kwargs = response['UnprocessedKeys'][self.name]
            except KeyError:
                # once our table is no longer listed in UnprocessedKeys we're done our while True loop
                break

    def get(self, consistent=False, get_item_kwargs=None, **kwargs):
        get_item_kwargs = get_item_kwargs or {}

        for k, v in six.iteritems(kwargs):
            if k not in self.schema.dynamorm_fields():
                raise InvalidSchemaField("{0} does not exist in the schema fields".format(k))

        get_item_kwargs['Key'] = kwargs
        if consistent:
            get_item_kwargs['ConsistentRead'] = True

        response = self.table.get_item(**get_item_kwargs)

        if 'Item' in response:
            return response['Item']

    def query(self, query_kwargs=None, **kwargs):
        assert len(kwargs) in (1, 2), "Query only takes 1 or 2 keyword arguments"

        if query_kwargs is None:
            query_kwargs = {}

        while len(kwargs):
            key, value = kwargs.popitem()

            try:
                key, op = key.split('__')
            except ValueError:
                op = 'eq'

            if 'IndexName' in query_kwargs:
                attr_fields = self.index_attribute_fields(index_name=query_kwargs['IndexName'])
            else:
                attr_fields = self.table_attribute_fields

            if key not in attr_fields:
                raise InvalidSchemaField("{0} is not a valid hash or range key".format(key))

            key = Key(key)
            op = getattr(key, op)

            if 'KeyConditionExpression' in query_kwargs:
                query_kwargs['KeyConditionExpression'] = query_kwargs['KeyConditionExpression'] & op(value)
            else:
                query_kwargs['KeyConditionExpression'] = op(value)

        log.debug("Query: %s", query_kwargs)
        return self.table.query(**query_kwargs)

    def scan(self, *args, **kwargs):
        scan_kwargs = kwargs.pop('scan_kwargs', None) or {}

        filter_expression = Q(**kwargs)
        for arg in args:
            try:
                filter_expression = filter_expression & arg
            except TypeError:
                filter_expression = arg

        if filter_expression:
            scan_kwargs['FilterExpression'] = filter_expression

        return self.table.scan(**scan_kwargs)

    def delete_item(self, **kwargs):
        return self.table.delete_item(Key=kwargs)


def remove_nones(in_dict):
    """
    Recursively remove keys with a value of ``None`` from the ``in_dict`` collection
    """
    try:
        return dict(
            (key, remove_nones(val))
            for key, val in six.iteritems(in_dict)
            if val is not None
        )
    except (ValueError, AttributeError):
        return in_dict


def Q(**mapping):
    """A Q object represents an AND'd together query using boto3's Attr object, based on a set of keyword arguments that
    support the full access to the operations (eq, ne, between, etc) as well as nested attributes.

    It can be used input to both scan operations as well as update conditions.
    """
    expression = None

    while len(mapping):
        attr, value = mapping.popitem()

        parts = attr.split('__')
        attr = Attr(parts.pop(0))
        op = 'eq'

        while len(parts):
            if not hasattr(attr, parts[0]):
                # this is a nested field, extend the attr
                attr = Attr('.'.join([attr.name, parts.pop(0)]))
            else:
                op = parts.pop(0)
                break

        assert len(parts) == 0, "Left over parts after parsing query attr"

        op = getattr(attr, op)
        try:
            attr_expression = op(value)
        except TypeError:
            # A TypeError calling our attr op likely means we're invoking exists, not_exists or another op that
            # doesn't take an arg or takes multiple args. If our value is True then we try to re-call the op
            # function without any arguments, if our value is a list we use it as the arguments for the function,
            # otherwise we bubble it up.
            if value is True:
                attr_expression = op()
            elif isinstance(value, collections.Iterable):
                attr_expression = op(*value)
            else:
                raise

        try:
            expression = expression & attr_expression
        except TypeError:
            expression = attr_expression

    return expression
