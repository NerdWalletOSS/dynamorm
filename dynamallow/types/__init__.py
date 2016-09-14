from .base import BaseModel
try:
    from ._schematics import Model
except ImportError:
    try:
        from ._marshmallow import Model
    except ImportError:
        raise ImportError('One of marshmallow or schematics is required to use this library.')
