import os

from dynamorm.model import DynaModel
from dynamorm.signals import model_prepared

if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
    from marshmallow.fields import String
else:
    from schematics.types import StringType as String


def test_model_prepared():
    def receiver(model):
        receiver.calls.append(model)
    receiver.calls = []

    model_prepared.connect(receiver)

    assert len(receiver.calls) == 0

    class SillyModel(DynaModel):
        class Table:
            name = 'silly'
            hash_key = 'silly'
            read = 1
            write = 1

        class Schema:
            silly = String(required=True)

    assert receiver.calls == [SillyModel]
