from marshmallow import Schema
from marshmallow import fields

from .base import BaseModel
from ..exceptions import ValidationError


class Model(Schema, BaseModel):
    """``Model`` is the base class for marshmallow based schemas """
    _dynamorm_fields = None

    @staticmethod
    def field_to_dynamo_type(field):
        """Given a marshmallow field object return the appropriate Dynamo type character"""
        if isinstance(field, fields.Raw):
            return 'B'
        if isinstance(field, fields.Number):
            return 'N'
        return 'S'

    @classmethod
    def dynamorm_fields(cls):
        if cls._dynamorm_fields is None:
            cls._dynamorm_fields = cls().fields
        return cls._dynamorm_fields

    @classmethod
    def dynamorm_validate(cls, obj):
        data, errors = cls().load(obj)
        if errors:
            raise ValidationError(obj, cls.__name__, errors)
        return data
