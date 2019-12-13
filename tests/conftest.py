import datetime
import logging
import os
import time

import pytest
from dateutil import tz

from dynamorm import (
    DynaModel,
    GlobalIndex,
    LocalIndex,
    ProjectAll,
    ProjectKeys,
    ProjectInclude,
)
from dynamorm import local
from dynamorm.table import DynamoTable3

log = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    logging.basicConfig(level=logging.INFO)


@pytest.fixture(scope="session")
def TestModel():
    """Provides a test model"""

    if os.environ.get("SERIALIZATION_PKG", "").startswith("marshmallow"):
        from marshmallow import fields

        class DynamoTimestamp(fields.DateTime):
            default_error_messages = {"invalid": "Not a valid timestamp"}

            def _serialize(self, value, attr, obj, **kwargs):
                try:
                    value = time.mktime(value.timetuple())
                    return int(value * 1000000)
                except (ValueError, AttributeError):
                    self.fail("invalid")

            def _deserialize(self, value, attr, data, **kwargs):
                try:
                    return datetime.datetime.fromtimestamp(
                        float(value) / 1000000, tz=tz.tzutc()
                    )
                except TypeError:
                    if isinstance(value, datetime.datetime):
                        return value
                    self.fail("invalid")

        class TestModel(DynaModel):
            class Table:
                name = "peanut-butter"
                hash_key = "foo"
                range_key = "bar"
                read = 5
                write = 5

            class ByDate(LocalIndex):
                name = "by_date"
                hash_key = "foo"
                range_key = "when"
                projection = ProjectKeys()

            class ByBar(GlobalIndex):
                name = "bar"
                hash_key = "bar"
                read = 5
                write = 5
                projection = ProjectAll()

            class ByBaz(GlobalIndex):
                name = "baz"
                hash_key = "baz"
                range_key = "bar"
                read = 5
                write = 5
                projection = ProjectInclude("count")

            class Schema:
                foo = fields.String(required=True)
                bar = fields.String(required=True)
                baz = fields.String(required=True)
                count = fields.Integer()
                child = fields.Dict()
                things = fields.List(fields.String())
                when = fields.DateTime()
                created = DynamoTimestamp()

            def business_logic(self):
                return "http://art.lawver.net/funny/internet.jpg?foo={foo}&bar={bar}".format(
                    foo=self.foo, bar=self.bar
                )

    else:
        from schematics import types
        from schematics.types import compound
        from schematics.exceptions import ConversionError

        class DynamoTimestampType(types.TimestampType, types.NumberType):
            primitive_type = int
            native_type = datetime.datetime

            def to_primitive(self, value, context=None):
                value = time.mktime(value.timetuple())
                return self.primitive_type(value * 1000000)

            def to_native(self, value, context=None):
                try:
                    return datetime.datetime.fromtimestamp(
                        float(value) / 1000000, tz=tz.tzutc()
                    )
                except TypeError:
                    if isinstance(value, datetime.datetime):
                        return value
                    raise ConversionError("Not a valid timestamp")

        class TestModel(DynaModel):
            class Table:
                name = "peanut-butter"
                hash_key = "foo"
                range_key = "bar"
                read = 5
                write = 5

            class ByDate(LocalIndex):
                name = "by_date"
                hash_key = "foo"
                range_key = "when"
                projection = ProjectKeys()

            class ByBar(GlobalIndex):
                name = "bar"
                hash_key = "bar"
                read = 5
                write = 5
                projection = ProjectAll()

            class ByBaz(GlobalIndex):
                name = "baz"
                hash_key = "baz"
                range_key = "bar"
                read = 5
                write = 5
                projection = ProjectInclude("count")

            class Schema:
                foo = types.StringType(required=True)
                bar = types.StringType(required=True)
                baz = types.StringType(required=True)
                count = types.IntType()
                child = compound.DictType(types.StringType)
                things = compound.ListType(types.BaseType)
                when = types.DateTimeType()
                created = DynamoTimestampType()

            def business_logic(self):
                return "http://art.lawver.net/funny/internet.jpg?foo={foo}&bar={bar}".format(
                    foo=self.foo, bar=self.bar
                )

    return TestModel


@pytest.fixture(scope="function")
def TestModel_table(request, TestModel, dynamo_local):
    """Used with TestModel, creates and deletes the table around the test"""
    TestModel.Table.create_table()
    request.addfinalizer(TestModel.Table.delete)


@pytest.fixture(scope="function")
def TestModel_entries(TestModel, TestModel_table):
    """Used with TestModel, creates and deletes the table and populates entries"""
    TestModel.put_batch(
        {
            "foo": "first",
            "bar": "one",
            "baz": "bbq",
            "count": 111,
            "child": {"sub": "one"},
        },
        {
            "foo": "first",
            "bar": "two",
            "baz": "wtf",
            "count": 222,
            "child": {"sub": "two"},
        },
        {
            "foo": "first",
            "bar": "three",
            "baz": "bbq",
            "count": 333,
            "child": {"sub": "three"},
        },
    )


@pytest.fixture(scope="function")
def TestModel_entries_xlarge(TestModel, TestModel_table):
    """Used with TestModel, creates and deletes the table and populates multiple pages of entries"""
    TestModel.put_batch(
        *[
            {"foo": "first", "bar": str(i), "baz": "bat" * 100}
            for i in range(
                4000
            )  # 1mb page is roughly 3300 items, so 4000 will be two pages.
        ]
    )


@pytest.fixture(scope="session")
def TestModelTwo():
    """Provides a test model without a range key"""

    if "marshmallow" in (os.getenv("SERIALIZATION_PKG") or ""):
        from marshmallow import fields

        class TestModelTwo(DynaModel):
            class Table:
                name = "peanut-butter"
                hash_key = "foo"
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
                name = "peanut-butter"
                hash_key = "foo"
                read = 5
                write = 5

            class Schema:
                foo = types.StringType(required=True)
                bar = types.StringType()
                baz = types.StringType()

    return TestModelTwo


@pytest.fixture(scope="function")
def TestModelTwo_table(request, TestModelTwo, dynamo_local):
    """Used with TestModel, creates and deletes the table around the test"""
    TestModelTwo.Table.create_table()
    request.addfinalizer(TestModelTwo.Table.delete)


@pytest.fixture(scope="session")
def dynamo_local(request):
    """Connect to a local dynamo instance"""
    dynamo_local_dir = os.environ.get("DYNAMO_LOCAL", "build/dynamo-local")
    dynamo_local_ = local.DynamoLocal(dynamo_local_dir)
    DynamoTable3.get_resource(
        aws_access_key_id="anything",
        aws_secret_access_key="anything",
        region_name="us-west-2",
        endpoint_url="http://localhost:{port}".format(port=dynamo_local_.port),
    )
    return dynamo_local_
