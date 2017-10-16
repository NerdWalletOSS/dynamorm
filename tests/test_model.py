import os
import pytest

from dynamorm.model import DynaModel, GlobalIndex, LocalIndex, ProjectAll
from dynamorm.exceptions import InvalidSchemaField, MissingTableAttribute, DynaModelException
if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
    from marshmallow.fields import String, Number
else:
    from schematics.types import StringType as String, IntType as Number


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


def test_number_hash_key():
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

    model = Model(foo=1, baz='foo')
    assert model.Table.attribute_definitions == [{'AttributeName': 'foo', 'AttributeType': 'N'}]


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

    assert 'Index' in model.Table.indexes
    assert model.Index.index is model.Table.indexes['Index']
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
