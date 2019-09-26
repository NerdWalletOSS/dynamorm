import six
from pkg_resources import parse_version

from marshmallow import Schema as MarshmallowSchema
from marshmallow.exceptions import MarshmallowError
from marshmallow import fields, __version__

from .base import DynamORMSchema
from ..exceptions import ValidationError

marshmallow_version = parse_version(__version__)
v3 = parse_version('3.0.0')

def _validate(cls, obj, partial=False, native=False):
    if native:
        data, errors = cls().load(obj, partial=partial)
    else:
        data, errors = cls(partial=partial).dump(obj)
    if errors:
        raise ValidationError(obj, cls.__name__, errors)
    return data


def _v3_validate(cls, obj, partial=False, native=False):
    try:
        if native:
            data = cls().load(obj, partial=partial)
        else:
            data = cls(partial=partial).dump(obj)
    except MarshmallowError as e:
        raise ValidationError(obj, cls.__name__, e)
    return data


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
        if marshmallow_version >= v3:
            data = _v3_validate(cls, obj, partial, native)
        else:
            data = _validate(cls, obj, partial, native)

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
