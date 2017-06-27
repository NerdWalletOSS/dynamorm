import logging
import os

import pytest

from dynamorm import DynaModel  # , LocalIndex, GlobalIndex
from dynamorm import local

log = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def TestModel():
    """Provides a test model"""

    if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
        from marshmallow import fields

        class TestModel(DynaModel):
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
                baz = fields.String(required=True)
                count = fields.Integer()
                child = fields.Dict()
                things = fields.List(fields.String())

            def business_logic(self):
                return 'http://art.lawver.net/funny/internet.jpg?foo={foo}&bar={bar}'.format(
                    foo=self.foo,
                    bar=self.bar
                )
    else:
        from schematics import types
        from schematics.types import compound

        class TestModel(DynaModel):
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
                baz = types.StringType(required=True)
                count = types.IntType()
                child = compound.DictType(types.StringType)
                things = compound.ListType(types.BaseType)

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


@pytest.fixture(scope='function')
def TestModel_entries_xlarge(TestModel, TestModel_table):
    """Used with TestModel, creates and deletes the table and populates multiple pages of entries"""
    TestModel.put_batch(*[
        {"foo": str(i), "bar": "baz", "baz": "bat" * 100}
        for i in range(4000)  # 1mb page is roughly 3300 items, so 4000 will be two pages.
    ])


@pytest.fixture(scope='session')
def TestModelTwo():
    """Provides a test model without a range key"""

    if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
        from marshmallow import fields

        class TestModelTwo(DynaModel):
            class Table:
                name = 'peanut-butter'
                hash_key = 'foo'
                read = 5
                write = 5

            class Schema:
                foo = fields.String(required=True)
                bar = fields.String()
                baz = fields.String()
    else:
        from schematics import types

        class TestModelTwo(DynaModel):
            class Table:
                name = 'peanut-butter'
                hash_key = 'foo'
                read = 5
                write = 5

            class Schema:
                foo = types.StringType(required=True)
                bar = types.StringType()
                baz = types.StringType()

    return TestModelTwo


@pytest.fixture(scope='function')
def TestModelTwo_table(request, TestModelTwo, dynamo_local):
    """Used with TestModel, creates and deletes the table around the test"""
    TestModelTwo.Table.create()
    request.addfinalizer(TestModelTwo.Table.delete)


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
