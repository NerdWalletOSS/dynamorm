from schematics.models import Model as SchematicsModel
from schematics.exceptions import ValidationError as SchematicsValidationError, ModelConversionError
from schematics import types

from .base import BaseModel as _BaseModel
from ..exceptions import ValidationError as _ValidationError


class Model(SchematicsModel, _BaseModel):
    """``Model`` is the base class for schematics_ based schemas """
    @staticmethod
    def field_to_dynamo_type(field):
        """Given a schematics field object return the appropriate Dynamo type character"""
        # XXX: Schematics does not currently have a "raw" type that would map to Dynamo's 'B' (binary) type.
        if isinstance(field, types.NumberType):
            return 'N'
        return 'S'

    @classmethod
    def dynamallow_fields(cls):
        return cls.fields

    @classmethod
    def dynamallow_validate(cls, obj):
        try:
            return cls(obj, strict=False).to_primitive()
        except (SchematicsValidationError, ModelConversionError) as e:
            raise _ValidationError(obj, cls.__name__, e.messages)
