from marshmallow import Schema as MarshmallowModel
from marshmallow import fields

from .base import BaseModel as BaseModel
from ..exceptions import ValidationError as ValidationError


class Model(MarshmallowModel, BaseModel):
    """``Model`` is the base class for marshmallow based schemas """
    _dynamallow_fields = None

    @staticmethod
    def field_to_dynamo_type(field):
        """Given a marshmallow field object return the appropriate Dynamo type character"""
        if isinstance(field, fields.Raw):
            return 'B'
        if isinstance(field, fields.Number):
            return 'N'
        return 'S'

    @classmethod
    def dynamallow_fields(cls):
        if cls._dynamallow_fields is None:
            cls._dynamallow_fields = cls().fields
        return cls._dynamallow_fields

    @classmethod
    def dynamallow_validate(cls, obj):
        data, errors = cls().load(obj)
        if errors:
            raise ValidationError(obj, cls.__name__, errors)
        return data
