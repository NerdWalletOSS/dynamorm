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
projection  True      object  An instance of of :class:`dynamorm.model.ProjectAll`,
                              :class:`dynamorm.model.ProjectKeys`, or :class:`dynamorm.model.ProjectInclude`

==========  ========  ======  ===========

"""

import collections
import logging
import time
import warnings

import boto3
import botocore
import six

from boto3.dynamodb.conditions import Key, Attr
from dynamorm.exceptions import (
    MissingTableAttribute, TableNotActive,
    InvalidSchemaField, HashKeyExists, ConditionFailed,
)

log = logging.getLogger(__name__)


class DynamoCommon3(object):
    """Common properties & functions of Boto3 DynamORM objects -- i.e. Tables & Indexes"""
    REQUIRED_ATTRS = ('name', 'hash_key')

    name = None
    hash_key = None
    range_key = None
    read = None
    write = None

    def __init__(self):
        for attr in self.REQUIRED_ATTRS:
            if getattr(self, attr) is None:
                raise MissingTableAttribute("Missing required Table attribute: {0}".format(attr))

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
    INDEX_TYPE = None

    projection = None

    @classmethod
    def lookup_by_type(cls, index_type):
        for klass in cls.__subclasses__():
            if klass.INDEX_TYPE == index_type:
                return klass
        raise RuntimeError("Unknown index type: %s" % index_type)

    def __init__(self, table, schema):
        self.table = table
        self.schema = schema

        super(DynamoIndex3, self).__init__()

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
    INDEX_TYPE = 'LocalIndex'
    ARG_KEY = 'LocalSecondaryIndexes'


class DynamoGlobalIndex3(DynamoIndex3):
    INDEX_TYPE = 'GlobalIndex'
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

        super(DynamoTable3, self).__init__()

        self.indexes = {}
        if indexes:
            for name, klass in six.iteritems(indexes):
                # Our indexes are just uninstantiated classes, but what we are interested in is what their parent class
                # name is.  We can reach into the MRO to find that out, and then determine our own index type.
                index_type = klass.__mro__[1].__name__
                index_class = DynamoIndex3.lookup_by_type(index_type)

                # Now that we know which of our classes we want to use, we create a new class on the fly that uses our
                # class with the attributes of the original class
                new_class = type(name, (index_class,), dict(
                    (k, v)
                    for k, v in six.iteritems(klass.__dict__)
                    if k[0] != '_'
                ))

                self.indexes[klass.name] = new_class(self, schema)

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

        log.info("Creating table %s", self.name)
        table = self.resource.create_table(
            TableName=self.name,
            KeySchema=self.key_schema,
            AttributeDefinitions=self.attribute_definitions,
            ProvisionedThroughput=self.provisioned_throughput,
            **index_args
        )
        if wait:
            log.info("Waiting for table creation...")
            table.meta.client.get_waiter('table_exists').wait(TableName=self.name)
        return table

    _update_table_ops = None

    def update_table(self):
        """Updates an existing table

        Per the AWS documentation:

        You can only perform one of the following operations at once:

         * Modify the provisioned throughput settings of the table.
         * Enable or disable Streams on the table.
         * Remove a global secondary index from the table.
         * Create a new global secondary index on the table.

        Thus, this will recursively call itself to perform each of these operations in turn, waiting for the table to
        return to 'ACTIVE' status before performing the next.

        This returns the number of update operations performed.
        """
        try:
            self._update_table_ops += 1
        except TypeError:
            self._update_table_ops = 0

        table = self.resource.Table(self.name)

        def wait_for_active():
            def _wait(thing_type, thing_name, thing_status_callback):
                wait_duration = 0.5
                if thing_status_callback(table) != 'ACTIVE':
                    log.info("Waiting for %s %s to become active before performing update...", thing_type, thing_name)

                    while thing_status_callback(table) != 'ACTIVE':
                        if thing_type == 'index':
                            if thing_status_callback(table) is None:
                                # once the index status is None then the index is gone
                                break

                            ok_statuses = ('CREATING', 'UPDATING', 'DELETING')
                        else:
                            ok_statuses = ('CREATING', 'UPDATING')

                        thing_status = thing_status_callback(table)
                        if thing_status in ok_statuses:
                            time.sleep(wait_duration)
                            if wait_duration < 20:
                                wait_duration = min(20, wait_duration * 2)
                            table.load()
                            continue

                        raise TableNotActive("{0} {1} is {2}".format(thing_type, thing_name, thing_status))

            def _index_status(table, index_name):
                for index in (table.global_secondary_indexes or []):
                    if index['IndexName'] == index_name:
                        return index['IndexStatus']

            _wait('table', table.table_name, lambda table: table.table_status)
            for index in (table.global_secondary_indexes or []):
                _wait('index', index['IndexName'], lambda table: _index_status(table, index['IndexName']))

        def do_update(**kwargs):
            kwargs.update(dict(
                AttributeDefinitions=self.attribute_definitions,
            ))
            return table.update(**kwargs)

        wait_for_active()

        # check if we're going to change our capacity
        if (self.read and self.write) and \
                (self.read != table.provisioned_throughput['ReadCapacityUnits'] or
                 self.write != table.provisioned_throughput['WriteCapacityUnits']):

            log.info("Updating capacity on table %s (%s -> %s)",
                     self.name,
                     dict(
                         (k, v)
                         for k, v in six.iteritems(table.provisioned_throughput)
                         if k.endswith('Units')
                     ),
                     self.provisioned_throughput)
            do_update(ProvisionedThroughput=self.provisioned_throughput)
            return self.update_table()

        # Now for the global indexes, turn the data strucutre into a real dictionary so we can look things up by name
        # Along the way we'll delete any indexes that are no longer defined
        existing_indexes = {}
        for index in (table.global_secondary_indexes or []):
            if index['IndexName'] not in self.indexes:
                log.info("Deleting global secondary index %s on table %s", index['IndexName'], self.name)
                do_update(GlobalSecondaryIndexUpdates=[{
                    'Delete': {
                        'IndexName': index['IndexName']
                    }
                }])
                return self.update_table()

            existing_indexes[index['IndexName']] = index

        for index in six.itervalues(self.indexes):
            if index.name in existing_indexes:
                current_capacity = existing_indexes[index.name]['ProvisionedThroughput']
                if (index.read and index.write) and \
                        (index.read != current_capacity['ReadCapacityUnits'] or
                         index.write != current_capacity['WriteCapacityUnits']):

                    log.info("Updating capacity on global secondary index %s on table %s (%s)", index.name, self.name,
                             index.provisioned_throughput)

                    do_update(GlobalSecondaryIndexUpdates=[{
                        'Update': {
                            'IndexName': index['IndexName'],
                            'ProvisionedThroughput': index.provisioned_throughput
                        }
                    }])
                    return self.update_table()
            else:
                # create the index
                log.info("Creating global secondary index %s on table %s", index.name, self.name)
                do_update(
                    AttributeDefinitions=self.attribute_definitions,
                    GlobalSecondaryIndexUpdates=[{
                        'Create': index.index_args
                    }]
                )
                return self.update_table()

        update_ops = self._update_table_ops
        self._update_table_ops = None
        return update_ops

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
