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


"""

import logging

import boto3
import botocore
import six

from boto3.dynamodb.conditions import Key, Attr
from dynamorm.exceptions import MissingTableAttribute, InvalidSchemaField, HashKeyExists, ConditionFailed

log = logging.getLogger(__name__)


class DynamoTable3(object):
    """Represents a Table object in the Boto3 DynamoDB API

    This is built in such a way that in the future, when Amazon releases future boto versions, a new DynamoTable class
    can be authored that implements the same methods but maps through to the new semantics.
    """

    _resource = None
    _table = None

    def __init__(self, schema):
        self.schema = schema

        required_attrs = ('name', 'hash_key')
        optional_attrs = ('range_key', 'read', 'write')

        for attr in required_attrs:
            if not hasattr(self, attr):
                raise MissingTableAttribute("Missing required Table attribute: {0}".format(attr))

        for attr in optional_attrs:
            if not hasattr(self, attr):
                setattr(self, attr, None)

        if self.hash_key not in self.schema.dynamorm_fields():
            raise InvalidSchemaField("The hash key '{0}' does not exist in the schema".format(self.hash_key))

        if self.range_key and self.range_key not in self.schema.dynamorm_fields():
            raise InvalidSchemaField("The range key '{0}' does not exist in the schema".format(self.range_key))

    @classmethod
    def get_resource(cls, **kwargs):
        """Return the boto3 dynamodb resource, create it if it doesn't exist

        The resource is stored globally on the ``DynamoTable3`` class and is shared between all models. To influence
        the connection parameters you just need to call ``get_resource`` on any model with the correct kwargs BEFORE you
        use any of the models.
        """
        if DynamoTable3._resource is None:
            DynamoTable3._resource = boto3.resource('dynamodb', **kwargs)
        return DynamoTable3._resource

    @classmethod
    def get_table(cls, name):
        """Return the boto3 Table object for this model, create it if it doesn't exist

        The Table is stored on the class for each model, so it is shared between all instances of a given model.
        """
        if cls._table is None:
            cls._table = cls.get_resource().Table(name)
        return cls._table

    @property
    def resource(self):
        """Return the boto3 resource"""
        return self.get_resource()

    @property
    def table(self):
        """Return the boto3 table"""
        return self.get_table(self.name)

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
    def attribute_definitions(self):
        """Return an appropriate AttributeDefinitions, based on our key attributes and the schema object"""
        def as_def(name, field):
            return {
                'AttributeName': name,
                'AttributeType': self.schema.field_to_dynamo_type(field)
            }
        defs = [as_def(self.hash_key, self.schema.dynamorm_fields()[self.hash_key])]
        if self.range_key:
            defs.append(as_def(self.range_key, self.schema.dynamorm_fields()[self.range_key]))
        return defs

    @property
    def provisioned_throughput(self):
        """Return an appropriate ProvisionedThroughput, based on our attributes"""
        return {
            'ReadCapacityUnits': self.read,
            'WriteCapacityUnits': self.write
        }

    @property
    def exists(self):
        """Return True or False based on the existance of this tables name in our resource"""
        return any(
            table.name == self.name
            for table in self.resource.tables.all()
        )

    def create(self, wait=True):
        """Create a new table based on our attributes

        :param bool wait: If set to True, the default, this call will block until the table is created
        """
        if not self.read or not self.write:
            raise MissingTableAttribute("The read/write attributes are required to create a table")

        table = self.resource.create_table(
            TableName=self.name,
            KeySchema=self.key_schema,
            AttributeDefinitions=self.attribute_definitions,
            ProvisionedThroughput=self.provisioned_throughput
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

    def update(self, conditions=None, update_item_kwargs=None, **kwargs):
        update_item_kwargs = update_item_kwargs or {}
        conditions = conditions or {}

        update_function_templates = {
            'append': '#uk_{0} = list_append(#uk_{0}, :uv_{0})',
            'plus': '#uk_{0} = #uk_{0} + :uv_{0}',
            'minus': '#uk_{0} = #uk_{0} - :uv_{0}',
            'if_not_exists': '#uk_{0} = if_not_exists(#uk_{0}, :uv_{0})',
            None: '#uk_{0} = :uv_{0}'
        }

        condition_function_templates = {
            'ne': '#ck_{0} <> :cv_{0}',
            'lt': '#ck_{0} < :cv_{0}',
            'lte': '#ck_{0} <= :cv_{0}',
            'gt': '#ck_{0} > :cv_{0}',
            'gte': '#ck_{0} >= :cv_{0}',
            # XXX TODO support these later
            # 'between': '#ck_{0} BETWEEN :cv_{0[0]} AND :cv_{0[1]}',
            # 'in': '#ck_{0} IN :cv_{0}',
            # 'exists': 'attribute_exists(#ck_{0})',
            # 'not_exists': 'attribute_not_exists (#ck_{0})',
            # 'type': 'attribute_type(#ck_{0}, :cv_{0})',
            # 'begins_with': 'begins_with(#ck_{0}, :cv_{0})',
            # 'contains': 'contains(#ck_{0}, :cv_{0})',
            # XXX TODO 'size' ??
            None: '#ck_{0} = :cv_{0}'
        }

        update_key = {}
        update_fields = []
        condition_fields = []
        expr_names = {}
        expr_vals = {}
        for k, v in six.iteritems(kwargs):
            try:
                k, function = k.split('__', 1)
            except ValueError:
                function = None

            # make sure the field (k) exists
            if k not in self.schema.dynamorm_fields():
                raise InvalidSchemaField("{0} does not exist in the schema fields".format(k))

            # if the field is in our hash/range key use it for the Key value in our query
            # you can't modify the primary key once an item has been set
            if k in (self.hash_key, self.range_key):
                update_key[k] = v
            else:
                # handle function
                update_fields.append(update_function_templates[function].format(k))
                expr_names['#uk_{0}'.format(k)] = k
                expr_vals[':uv_{0}'.format(k)] = v

        for k, v in six.iteritems(conditions):
            try:
                k, function = k.split('__', 1)
            except ValueError:
                function = None

            if k not in self.schema.dynamorm_fields():
                raise InvalidSchemaField("{0} does not exist in the schema fields".format(k))

            condition_fields.append(condition_function_templates[function].format(k))
            expr_names['#ck_{0}'.format(k)] = k
            expr_vals[':cv_{0}'.format(k)] = v

        update_item_kwargs['Key'] = update_key
        update_item_kwargs['UpdateExpression'] = 'SET {0}'.format(', '.join(update_fields))
        if condition_fields:
            update_item_kwargs['ConditionExpression'] = ' AND '.join(condition_fields)
        update_item_kwargs['ExpressionAttributeNames'] = expr_names
        update_item_kwargs['ExpressionAttributeValues'] = expr_vals

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

            if key not in (self.hash_key, self.range_key):
                raise InvalidSchemaField("{0} is not our hash or range key".format(key))

            key = Key(key)
            op = getattr(key, op)

            if 'KeyConditionExpression' in query_kwargs:
                query_kwargs['KeyConditionExpression'] = query_kwargs['KeyConditionExpression'] & op(value)
            else:
                query_kwargs['KeyConditionExpression'] = op(value)

        log.debug("Query: %s", query_kwargs)
        return self.table.query(**query_kwargs)

    def scan(self, scan_kwargs=None, **kwargs):
        if scan_kwargs is None:
            scan_kwargs = {}

        while len(kwargs):
            attr, value = kwargs.popitem()

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
                filter_expression = op(value)
            except TypeError:
                # A TypeError calling our attr op likely means we're invoking exists, not_exists or another op that
                # doesn't take an arg. If our value is True then we try to re-call the op function without any
                # arguments, otherwise we bubble it up.
                if value is True:
                    filter_expression = op()
                else:
                    raise

            if 'FilterExpression' in scan_kwargs:
                # XXX TODO: support | (or) and ~ (not)
                scan_kwargs['FilterExpression'] = scan_kwargs['FilterExpression'] & filter_expression
            else:
                scan_kwargs['FilterExpression'] = filter_expression

        return self.table.scan(**scan_kwargs)


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
