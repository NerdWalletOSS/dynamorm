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

    with pytest.raises(InvalidSchemaField):
        class Model(MarshModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                read = 1
                write = 1

            class Schema:
                bar = fields.String(required=True)
