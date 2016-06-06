import six

from marshmallow import fields


def _field_to_dynamo_type(field):
    """Given a marshmallow field object return the appropriate Dynamo type character"""
    if isinstance(field, fields.Raw):
        return 'B'
    if isinstance(field, fields.Number):
        return 'N'
    return 'S'


class DynaTableException(Exception):
    """Base exception class for all DynaTable errors"""


class InvalidSchemaField(DynaTableException):
    """A field provided does not exist in the schema"""


class DynaTable(object):
    """ """
    def __init__(self, schema):
        self.schema = schema
        self._table = None

        required_attrs = ('name', 'hash_key', 'read', 'write')
        optional_attrs = ('range_key',)

        for attr in required_attrs:
            if not hasattr(self, attr):
                raise DynaTableException("Missing required Table attribute: {0}".format(attr))

        for attr in optional_attrs:
            if not hasattr(self, attr):
                setattr(self, attr, None)

        if self.hash_key not in self.schema.fields:
            raise InvalidSchemaField("The hash key '{0}' does not exist in the schema".format(self.hash_key))

        if self.range_key and self.range_key not in self.schema.fields:
            raise InvalidSchemaField("The range key '{0}' does not exist in the schema".format(self.range_key))

    def get_table(self, resource):
        if self._table is None:
            self._table = resource.Table(self.name)
        return self._table

    def exists(self, resource):
        tables = resource.tables.all()
        return any(
            table.name == self.name
            for table in tables
        )

    def create(self, resource):
        table = resource.create_table(
            TableName=self.name,
            KeySchema=self.key_schema,
            AttributeDefinitions=self.attribute_definitions,
            ProvisionedThroughput=self.provisioned_throughput
        )
        table.meta.client.get_waiter('table_exists').wait(TableName=self.name)
        return table

    @property
    def key_schema(self):
        as_schema = lambda name, key_type: {'AttributeName': name, 'KeyType': key_type}
        schema = [as_schema(self.hash_key, 'HASH')]
        if self.range_key:
            schema.append(as_schema(self.range_key, 'RANGE'))
        return schema

    @property
    def attribute_definitions(self):
        as_def = lambda name, field: {'AttributeName': name, 'AttributeType': _field_to_dynamo_type(field)}
        defs = [as_def(self.hash_key, self.schema.fields[self.hash_key])]
        if self.range_key:
            defs.append(as_def(self.range_key, self.schema.fields[self.range_key]))
        return defs

    @property
    def provisioned_throughput(self):
        return {
            'ReadCapacityUnits': self.read,
            'WriteCapacityUnits': self.write
        }

    def delete(self, resource):
        table = self.get_table(resource)
        table.delete()
        table.meta.client.get_waiter('table_not_exists').wait(TableName=self.name)
        return True

    def put(self, resource, item, **kwargs):
        table = self.get_table(resource)
        return table.put_item(Item=item, **kwargs)

    def put_unique(self, resource, item, **kwargs):
        kwargs['ConditionExpression'] = 'attribute_not_exists({0})'.format(self.hash_key)
        return self.put(resource, item, **kwargs)

    def put_batch(self, resource, *items, **batch_kwargs):
        table = self.get_table(resource)
        with table.batch_writer(**batch_kwargs) as writer:
            for item in items:
                writer.put_item(Item=item)

    def get(self, resource, **kwargs):
        table = self.get_table(resource)
        for k, v in six.iteritems(kwargs):
            if k not in self.schema.fields:
                raise InvalidSchemaField("{0} does not exist in the schema fields".format(k))
        response = table.get_item(Key=kwargs)
        if 'Item' in response:
            return response['Item']
