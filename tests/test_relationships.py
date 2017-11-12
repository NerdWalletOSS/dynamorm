import os

from dynamorm.model import DynaModel
from dynamorm.relationships import OneToOne

if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
    from marshmallow.fields import String, Number
else:
    from schematics.types import StringType as String, IntType as Number


def test_one_to_one(dynamo_local, request):
    class Details(DynaModel):
        class Table:
            name = 'details'
            hash_key = 'thing_version'
            read = 1
            write = 1

        class Schema:
            thing_version = String(required=True)
            attr1 = String()
            attr2 = Number()
            # ... lots more attrs ...

    class Sparse(DynaModel):
        class Table:
            name = 'sparse'
            hash_key = 'thing'
            range_key = 'version'
            read = 1
            write = 1

        class Schema:
            thing = String(required=True)
            version = Number(required=True)
            details = OneToOne(
                Details,
                query=lambda instance: dict(thing_version='{0}:{1}'.format(instance.thing, instance.version))
            )

    Details.Table.create()
    request.addfinalizer(Details.Table.delete)

    Sparse.Table.create()
    request.addfinalizer(Sparse.Table.delete)

    item = Sparse(thing='foo', version=1)

    # when accessing a one-to-one relationship that doesn't exist it will be automatically created
    item.details.attr1 = 'this is attr1'

    # when saving an object with a one-to-one relationship both sides will be saved
    item.save()

    details = Details.get(thing_version='foo:1')
    assert details.attr1 == 'this is attr1'

    # test replacing the details
    item.details = Details(attr1='new attr1', partial=True)
    item.save()

    details = Details.get(thing_version='foo:1')
    assert details.attr1 == 'new attr1'

    # test deleting the details
    del item.details
    assert Details.get(thing_version='foo:1') is None
