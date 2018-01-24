import os
import pytest

from dynamorm.model import DynaModel
from dynamorm.indexes import GlobalIndex, LocalIndex, ProjectAll, ProjectInclude
from dynamorm.exceptions import (
    DynaModelException,
    HashKeyExists,
    InvalidSchemaField,
    MissingTableAttribute,
    ValidationError,
)

if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
    from marshmallow.fields import String, Integer as Number
    from marshmallow import validates, ValidationError as SchemaValidationError
else:
    from schematics.types import StringType as String, IntType as Number
    from schematics.exceptions import ValidationError as SchemaValidationError

try:
    from unittest.mock import MagicMock, call
except ImportError:
    from mock import MagicMock, call


def test_missing_inner_classes():
    """Classes must have both a Table and Schema inner class"""
    with pytest.raises(DynaModelException):
        class Model(DynaModel):
            pass


def test_missing_inner_schema_class():
    """Classes must have an inner Schema class"""
    with pytest.raises(DynaModelException):
        class Model(DynaModel):
            class Table:
                pass


def test_missing_inner_table_class():
    """Classes must have an inner Table class"""
    with pytest.raises(DynaModelException):
        class Model(DynaModel):
            class Schema:
                pass


def test_parent_inner_classes():
    class Parent(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            read = 1
            write = 1

        class Schema:
            foo = String(required=True)

    class Child(Parent):
        pass

    assert Child.Table is Parent.Table


def test_table_validation():
    """Defining a model with missing table attributes should raise exceptions"""
    with pytest.raises(MissingTableAttribute):
        class Model(DynaModel):
            class Table:
                name = 'table'

            class Schema:
                foo = String(required=True)


def test_table_create_validation():
    """You cannot create a table that is missing read/write attrs"""
    with pytest.raises(MissingTableAttribute):
        class Model(DynaModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                read = 5

            class Schema:
                foo = String(required=True)

        Model.Table.create_table()

    with pytest.raises(MissingTableAttribute):
        class Model(DynaModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                write = 5

            class Schema:
                foo = String(required=True)

        Model.Table.create_table()

    with pytest.raises(MissingTableAttribute):
        class Model(DynaModel):
            class Table:
                name = 'table'
                hash_key = 'foo'

            class Schema:
                foo = String(required=True)

        Model.Table.create_table()


def test_invalid_hash_key():
    """Defining a model where ``hash_key`` in Table points to an invalid field should raise InvalidSchemaField"""
    with pytest.raises(InvalidSchemaField):
        class Model(DynaModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                read = 1
                write = 1

            class Schema:
                bar = String(required=True)


def test_invalid_range_key():
    """Defining a model where ``range_key`` in Table points to an invalid field should raise InvalidSchemaField"""
    with pytest.raises(InvalidSchemaField):
        class Model(DynaModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                range_key = 'bar'
                read = 1
                write = 1

            class Schema:
                foo = String(required=True)
                baz = String(required=True)


def test_number_hash_key(dynamo_local, request):
    """Test a number hash key and ensure the dynamo type gets set correctly"""
    class Model(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            read = 1
            write = 1

        class Schema:
            foo = Number(required=True)
            baz = String(required=True)

    Model.Table.create()
    request.addfinalizer(Model.Table.delete)

    model = Model(foo=1, baz='foo')
    assert model.Table.attribute_definitions == [{'AttributeName': 'foo', 'AttributeType': 'N'}]

    model.save()


def test_missing_field_validation():
    class Model(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            read = 1
            write = 1

        class Schema:
            foo = String(required=True)
            baz = String(required=True)

    model = Model(foo='foo', partial=True)
    with pytest.raises(ValidationError):
        model.validate()

    try:
        model.validate()
    except ValidationError as exc:
        assert str(exc).startswith("Validation failed for schema ModelSchema. Errors: {'baz'")


def test_index_setup():
    """Ensure our index objects are setup & transformed correctly by our meta class"""
    class Model(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            range_key = 'bar'
            read = 1
            write = 1

        class Index(GlobalIndex):
            name = 'test-idx'
            hash_key = 'foo'
            range_key = 'bar'
            projection = ProjectAll()

        class Schema:
            foo = String(required=True)
            bar = String(required=True)

    model = Model(foo='hi', bar='there')

    assert 'test-idx' in model.Table.indexes
    assert model.Index.index is model.Table.indexes['test-idx']
    assert model.Index.index.table is model.Table

    assert model.Index.index.schema is model.Schema

    # this gets automatically set during initialization, since read is an optional parameter
    assert model.Index.index.read is None


def test_invalid_indexes():
    """Ensure validation happens for indexes"""
    for idx in (GlobalIndex, LocalIndex):
        with pytest.raises(MissingTableAttribute):
            class Model1(DynaModel):
                class Table:
                    name = 'table'
                    hash_key = 'foo'
                    range_key = 'bar'
                    read = 1
                    write = 1

                class Index(idx):
                    name = 'test-idx'
                    # missing hash_key
                    range_key = 'bar'
                    projection = ProjectAll()

                class Schema:
                    foo = String(required=True)
                    bar = String(required=True)

        with pytest.raises(MissingTableAttribute):
            class Model2(DynaModel):
                class Table:
                    name = 'table'
                    hash_key = 'foo'
                    range_key = 'bar'
                    read = 1
                    write = 1

                class Index(idx):
                    name = 'test-idx'
                    hash_key = 'foo'
                    range_key = 'bar'
                    # no projection

                class Schema:
                    foo = String(required=True)
                    bar = String(required=True)

        with pytest.raises(InvalidSchemaField):
            class Model3(DynaModel):
                class Table:
                    name = 'table'
                    hash_key = 'foo'
                    range_key = 'bar'
                    read = 1
                    write = 1

                class Index(idx):
                    name = 'test-idx'
                    hash_key = 'foo'
                    # no key named baz
                    range_key = 'baz'
                    projection = ProjectAll()

                class Schema:
                    foo = String(required=True)
                    bar = String(required=True)

        with pytest.raises(InvalidSchemaField):
            class Model4(DynaModel):
                class Table:
                    name = 'table'
                    hash_key = 'foo'
                    range_key = 'bar'
                    read = 1
                    write = 1

                class Index(idx):
                    name = 'test-idx'
                    # no key named baz
                    hash_key = 'baz'
                    range_key = 'bar'
                    projection = ProjectAll()

                class Schema:
                    foo = String(required=True)
                    bar = String(required=True)


def test_update_table(dynamo_local):
    class TableV1(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            range_key = 'bar'
            read = 5
            write = 5

        class Schema:
            foo = String(required=True)
            bar = String(required=True)
            baz = String(required=True)
            bbq = String(required=True)

    class TableV2(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            range_key = 'bar'
            read = 10
            write = 10

        class Index1(GlobalIndex):
            name = 'index1'
            hash_key = 'baz'
            range_key = 'bar'
            projection = ProjectAll()
            read = 5
            write = 5

        class Index2(GlobalIndex):
            name = 'index2'
            hash_key = 'bbq'
            range_key = 'bar'
            projection = ProjectAll()
            read = 5
            write = 5

        class Schema:
            foo = String(required=True)
            bar = String(required=True)
            baz = String(required=True)
            bbq = String(required=True)

    class TableV3(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            range_key = 'bar'
            read = 10
            write = 10

        class Index2(GlobalIndex):
            name = 'index2'
            hash_key = 'bbq'
            range_key = 'bar'
            projection = ProjectAll()
            read = 5
            write = 5

        class Schema:
            foo = String(required=True)
            bar = String(required=True)
            baz = String(required=True)
            bbq = String(required=True)

    TableV1.Table.create_table()

    # updating to v2 should result in 3 changes
    # * changing throughput
    # * adding index1
    # * adding index2
    assert TableV2.Table.update_table() == 3

    # updating to v2 result in 1 change
    # * deleting index 1
    assert TableV3.Table.update_table() == 1

    # should now be a no-op
    assert TableV3.Table.update_table() == 0


def test_sparse_indexes(dynamo_local):
    class MyModel(DynaModel):
        class Table:
            name = 'mymodel'
            hash_key = 'foo'
            read = 10
            write = 10

        class Index1(GlobalIndex):
            name = 'index1'
            hash_key = 'bar'
            read = 10
            write = 10
            projection = ProjectInclude('foo', 'bar')

        class Schema:
            foo = String(required=True)
            bar = String(required=True)
            baz = String(required=True)
            bbq = String(required=True)

    MyModel.Table.create_table()
    MyModel.put_batch(
        {'foo': '1', 'bar': '1', 'baz': '1', 'bbq': '1'},
        {'foo': '2', 'bar': '2', 'baz': '2', 'bbq': '2'},
    )

    items = list(MyModel.Index1.query(bar='2'))
    assert len(items) == 1
    assert items[0].foo == '2'


def test_partial_save(TestModel, TestModel_entries, dynamo_local):
    def get_first():
        first = TestModel.get(foo='first', bar='one')
        first.put = MagicMock()
        first.update_item = MagicMock()
        return first

    # the first time to a non-partial save and put should be called
    first = get_first()
    first.save()
    first.update_item.assert_not_called()

    # next do a partial save without any changed and again with a change
    # put should not be called, and update should only be called once dispite save being called twice
    first = get_first()
    first.save(partial=True)

    first.baz = 'changed'
    first.update_item.return_value = {'Attributes': {'baz': 'changed'}}
    first.save(partial=True)
    first.put.assert_not_called()

    baz_update_call = call(
        # no conditions should we set
        conditions=None,
        # our ReturnValues should be set to return updates values
        update_item_kwargs={'ReturnValues': 'UPDATED_NEW'},
        # the the we changed should be included
        baz='changed',
        # and so should the primary key
        foo='first',
        bar='one',
    )
    first.update_item.assert_has_calls([baz_update_call])

    # do it again, and just count should be sent
    first.count = 999
    first.update_item.return_value = {'Attributes': {'count': 999}}
    first.save(partial=True)
    first.put.assert_not_called()

    count_update_call = call(
        conditions=None,
        update_item_kwargs={'ReturnValues': 'UPDATED_NEW'},
        count=999,
        foo='first',
        bar='one',
    )
    first.update_item.assert_has_calls([baz_update_call, count_update_call])


def test_unique_save(TestModel, TestModel_entries, dynamo_local):
    first = TestModel(foo='first', bar='one', baz='uno')
    first.save()

    second = TestModel(foo='first', bar='one', baz='uno')
    with pytest.raises(HashKeyExists):
        second.save(unique=True)
    second.save()


def test_explicit_schema_parents():
    """Inner Schema classes should be able to have explicit parents"""
    class SuperMixin(object):
        bbq = String()

    if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
        class Mixin(SuperMixin):
            is_mixin = True
            bar = String()

            @validates('bar')
            def validate_bar(self, value):
                if value != 'bar':
                    raise SchemaValidationError('bar must be bar')
    else:
        class Mixin(SuperMixin):
            is_mixin = True
            bar = String()

            def validate_bar(self, data, value):
                if value != 'bar':
                    raise SchemaValidationError('bar must be bar')

    class Model(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            read = 1
            write = 1

        class Schema(Mixin):
            foo = Number(required=True)
            baz = String(required=True)

    assert Model.Schema.is_mixin is True
    assert list(sorted(Model.Schema.dynamorm_fields().keys())) == ['bar', 'baz', 'bbq', 'foo']

    with pytest.raises(ValidationError):
        Model(foo='foo', baz='baz', bar='not bar')


def test_schema_parents_mro():
    """Inner Schema classes should obey MRO (to test our schematics field pull up)"""
    class MixinTwo(object):
        bar = Number()

    class MixinOne(object):
        bar = String()

    class Model(DynaModel):
        class Table:
            name = 'table'
            hash_key = 'foo'
            read = 1
            write = 1

        class Schema(MixinOne, MixinTwo):
            foo = Number(required=True)
            baz = String(required=True)

    assert 'bar' in Model.Schema.dynamorm_fields()
    assert isinstance(Model.Schema.dynamorm_fields()['bar'], String)


def test_table_config(TestModel, dynamo_local):
    class MyModel(DynaModel):
        class Table:
            name = 'mymodel'
            hash_key = 'foo'
            read = 10
            write = 10

            resource_kwargs = {
                'region_name': 'us-east-2'
            }

        class Schema:
            foo = String(required=True)

    class OtherModel(DynaModel):
        class Table:
            name = 'othermodel'
            hash_key = 'foo'
            read = 10
            write = 10

        class Schema:
            foo = String(required=True)

    # dynamo_local sets up the default table config to point to us-west-2
    # So any models, like TestModel, that don't specify a config end up pointing there
    assert TestModel.Table.resource.meta.client.meta.region_name == 'us-west-2'

    # Our first model above has explicit resource kwargs, as such it should get a different resource with our explicitly
    # configured region name
    assert MyModel.Table.resource.meta.client.meta.region_name == 'us-east-2'

    # Tables that share the same resource kwargs share the same resources
    assert MyModel.Table.resource is not TestModel.Table.resource
    assert OtherModel.Table.resource is TestModel.Table.resource


def test_field_subclassing():
    class SubclassedString(String):
        pass

    class SubSubclassedString(SubclassedString):
        pass

    class MyModel(DynaModel):
        class Table:
            name = 'mymodel'
            hash_key = 'foo'
            read = 10
            write = 10

        class Schema:
            foo = SubSubclassedString(required=True)

    assert isinstance(MyModel.Schema.dynamorm_fields()['foo'], String)
