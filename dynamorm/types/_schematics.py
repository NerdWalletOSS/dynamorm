from schematics.models import Model as SchematicsModel
from schematics.exceptions import ValidationError as SchematicsValidationError, ModelConversionError
from schematics import types

from .base import DynamORMSchema
from ..exceptions import ValidationError


class Schema(SchematicsModel, DynamORMSchema):
    """This is the base class for schematics based schemas"""

    @staticmethod
    def field_to_dynamo_type(field):
        """Given a schematics field object return the appropriate Dynamo type character"""
        # XXX: Schematics does not currently have a "raw" type that would map to Dynamo's 'B' (binary) type.
        if isinstance(field, types.NumberType):
            return 'N'
        return 'S'

    @classmethod
    def dynamorm_fields(cls):
        return cls.fields

    @classmethod
    def dynamorm_validate(cls, obj, partial=False, native=False):
        try:
            inst = cls(obj, strict=False, partial=partial)
        except (SchematicsValidationError, ModelConversionError) as e:
            raise ValidationError(obj, cls.__name__, e.messages)

        if native:
            return inst.to_native()
        else:
            return inst.to_primitive()
