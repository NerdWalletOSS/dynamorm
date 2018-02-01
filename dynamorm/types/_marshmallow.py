import six

from marshmallow import Schema as MarshmallowSchema
from marshmallow import fields

from .base import DynamORMSchema
from ..exceptions import ValidationError


class Schema(MarshmallowSchema, DynamORMSchema):
    """This is the base class for marshmallow based schemas"""

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
        return cls().fields

    @classmethod
    def dynamorm_validate(cls, obj, partial=False, native=False):
        if native:
            data, errors = cls().load(obj, partial=partial)
        else:
            data, errors = cls(partial=partial).dump(obj)
        if errors:
            raise ValidationError(obj, cls.__name__, errors)

        # When asking for partial native objects (during model init) we want to return None values
        # This ensures our object has all attributes and we can track partial saves properly
        if partial and native:
            for name in six.iterkeys(cls().fields):
                if name not in data:
                    data[name] = None

        return data

    @staticmethod
    def base_field_type():
        return fields.Field
