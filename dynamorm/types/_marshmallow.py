import six
from pkg_resources import parse_version

from marshmallow import Schema as MarshmallowSchema
from marshmallow.exceptions import MarshmallowError
from marshmallow import fields, __version__ as marshmallow_version

from .base import DynamORMSchema
from ..exceptions import ValidationError

# Define different validation logic depending on the version of marshmallow we're using
if parse_version(marshmallow_version) >= parse_version('3.0.0a1'):
    def _validate(cls, obj, partial=False, native=False):
        """Validate using a Marshmallow v3+ schema"""
        try:
            if native:
                data = cls().load(obj, partial=partial, unknown="EXCLUDE")
            else:
                data = cls(partial=partial, unknown="EXCLUDE").dump(obj)
        except MarshmallowError as e:
            raise ValidationError(obj, cls.__name__, e)
        return data
else:
    def _validate(cls, obj, partial=False, native=False):
        """Validate using a Marshmallow 2.x schema"""
        if native:
            data, errors = cls().load(obj, partial=partial)
        else:
            data, errors = cls(partial=partial).dump(obj)
        if errors:
            raise ValidationError(obj, cls.__name__, errors)
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
        # Call out to our _validate to get the correct logic for the version of marshmallow we're using
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
