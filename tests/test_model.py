import pytest

from marshmallow import fields

from dynamallow.model import MarshModel, MarshModelException
from dynamallow.table import InvalidSchemaField, MissingTableAttribute


def test_missing_inner_classes():
    """Classes must define the correct inner class structure"""
    with pytest.raises(MarshModelException):
        class Model(MarshModel):
            pass

    with pytest.raises(MarshModelException):
        class Model(MarshModel):
            class Table:
                pass

    with pytest.raises(MarshModelException):
        class Model(MarshModel):
            class Schema:
                pass


def test_table_validation():
    """Defining a model with missing table attributes should raise exceptions"""
    with pytest.raises(MissingTableAttribute):
        class Model(MarshModel):
            class Table:
                name = 'table'
                hash_key = 'foo'

            class Schema:
                foo = fields.String(required=True)


def test_invalid_hash_key():
    with pytest.raises(InvalidSchemaField):
        class Model(MarshModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                read = 1
                write = 1

            class Schema:
                bar = fields.String(required=True)


def test_invalid_range_key():
    with pytest.raises(InvalidSchemaField):
        class Model(MarshModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                range_key = 'bar'
                read = 1
                write = 1

            class Schema:
                foo = fields.String(required=True)
                baz = fields.String(required=True)
