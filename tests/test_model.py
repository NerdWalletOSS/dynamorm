import os
import pytest

from dynamallow.model import MarshModel
from dynamallow.exceptions import InvalidSchemaField, MissingTableAttribute, MarshModelException
if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
    from marshmallow.fields import String
else:
    from schematics.types import StringType as String


def test_missing_inner_classes():
    """Classes must have both a Table and Schema inner class"""
    with pytest.raises(MarshModelException):
        class Model(MarshModel):
            pass


def test_missing_inner_schema_class():
    """Classes must have an inner Schema class"""
    with pytest.raises(MarshModelException):
        class Model(MarshModel):
            class Table:
                pass


def test_missing_inner_table_class():
    """Classes must have an inner Table class"""
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
                foo = String(required=True)


def test_invalid_hash_key():
    """Defining a model where ``hash_key`` in Table points to an invalid field should raise InvalidSchemaField"""
    with pytest.raises(InvalidSchemaField):
        class Model(MarshModel):
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
        class Model(MarshModel):
            class Table:
                name = 'table'
                hash_key = 'foo'
                range_key = 'bar'
                read = 1
                write = 1

            class Schema:
                foo = String(required=True)
                baz = String(required=True)
