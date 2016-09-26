import logging
import os

try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve

import pytest

from dynamallow import MarshModel  # , LocalIndex, GlobalIndex
from dynamallow import local

log = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def TestModel():
    """Provides a test model"""

    if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
        from marshmallow import fields

        class TestModel(MarshModel):
            class Table:
                name = 'peanut-butter'
                hash_key = 'foo'
                range_key = 'bar'
                read = 5
                write = 5

                """
                class Bazillions(LocalIndex):
                    read = 5
                    write = 5
                """

            class Schema:
                foo = fields.String(required=True)
                bar = fields.String(required=True)
                baz = fields.String()
                count = fields.Integer()
                child = fields.Dict()

            def business_logic(self):
                return 'http://art.lawver.net/funny/internet.jpg?foo={foo}&bar={bar}'.format(
                    foo=self.foo,
                    bar=self.bar
                )
    else:
        from schematics import types
        from schematics.types import compound

        class TestModel(MarshModel):
            class Table:
                name = 'peanut-butter'
                hash_key = 'foo'
                range_key = 'bar'
                read = 5
                write = 5

                """
                class Bazillions(LocalIndex):
                    read = 5
                    write = 5
                """

            class Schema:
                foo = types.StringType(required=True)
                bar = types.StringType(required=True)
                baz = types.StringType()
                count = types.IntType()
                child = compound.DictType(types.StringType)

            def business_logic(self):
                return 'http://art.lawver.net/funny/internet.jpg?foo={foo}&bar={bar}'.format(
                    foo=self.foo,
                    bar=self.bar
                )

    return TestModel

@pytest.fixture(scope='function')
def TestModel_table(request, TestModel, dynamo_local):
    """Used with TestModel, creates and deletes the table around the test"""
    TestModel.Table.create()
    request.addfinalizer(TestModel.Table.delete)


@pytest.fixture(scope='function')
def TestModel_entries(TestModel, TestModel_table):
    """Used with TestModel, creates and deletes the table and populates entries"""
    TestModel.put_batch(
        {"foo": "first", "bar": "one", "baz": "bbq", "count": 111, "child": {"sub": "one"}},
        {"foo": "first", "bar": "two", "baz": "wtf", "count": 222, "child": {"sub": "two"}},
        {"foo": "first", "bar": "three", "baz": "bbq", "count": 333, "child": {"sub": "three"}},
    )


@pytest.fixture(scope='session')
def dynamo_local(request, TestModel):
    """Connect to a local dynamo instance"""
    dynamo_local_dir = os.environ.get('DYNAMO_LOCAL', 'build/dynamo-local')
    dynamo_local_ = local.DynamoLocal(dynamo_local_dir)
    TestModel.Table.get_resource(
        aws_access_key_id="anything",
        aws_secret_access_key="anything",
        region_name="us-west-2",
        endpoint_url="http://localhost:{port}".format(port=dynamo_local_.port)
    )
    return dynamo_local_.port
