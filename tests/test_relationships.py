import datetime
import os

import pytest

from dynamorm.exceptions import ValidationError
from dynamorm.model import DynaModel
from dynamorm.indexes import GlobalIndex, ProjectKeys
from dynamorm.relationships import OneToOne, OneToMany, ManyToOne

if 'marshmallow' in (os.getenv('SERIALIZATION_PKG') or ''):
    from marshmallow.fields import String, Integer as Number
else:
    from schematics.types import StringType as String, IntType as Number

try:
    from unittest.mock import MagicMock, call
except ImportError:
    from mock import MagicMock, call


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
            attr2 = Number(required=True)
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
            query=lambda sparse: dict(thing_version='{0}:{1}'.format(sparse.thing, sparse.version)),
            back_query=lambda details: dict(
                thing=details.thing_version.split(':')[0],
                version=details.thing_version.split(':')[1]
            )
        )

    Details.Table.create()
    request.addfinalizer(Details.Table.delete)

    Sparse.Table.create()
    request.addfinalizer(Sparse.Table.delete)

    item = Sparse(thing='foo', version=1)

    # when accessing a one-to-one relationship that doesn't exist it will be automatically created
    item.details.attr1 = 'this is attr1'

    # when saving an object with a one-to-one relationship both sides will be saved
    # when we call .save we should get a validation error from the pre_save signal since we're missing attr2
    with pytest.raises(ValidationError):
        item.save()

    assert Details.get(thing_version='foo:1', consistent=True) is None

    # set it, and the save should succeed
    item.details.attr2 = 1
    item.save()

    details = Details.get(thing_version='foo:1', consistent=True)
    assert details.attr1 == 'this is attr1'

    # test replacing the details
    item.details = Details(attr1='new attr1', attr2=2, partial=True)
    item.save()

    details = Details.get(thing_version='foo:1')
    assert details.attr1 == 'new attr1'
    assert details.attr2 == 2
    assert details.sparse.thing == 'foo'

    # trying to set a value to the relationship that's not the type of our other model should raise a TypeError
    with pytest.raises(TypeError):
        item.details = 1

    # test deleting the details
    # reload the item first to ensure that the __delete__ method can successfully fetch not yet loaded relationships
    item = Sparse.get(thing='foo', version=1)
    del item.details
    assert Details.get(thing_version='foo:1', consistent=True) is None

    # also ensure that trying to delete a non-existent related object raises an error
    item = Sparse.get(thing='foo', version=1)
    with pytest.raises(AttributeError):
        del item.details

    # reload the item
    item = Sparse.get(thing='foo', version=1)
    item.details.attr1 = 'this is attr1'
    item.details.attr2 = 1
    item.save()

    # change something on the details
    item.details.attr2 = 10

    # do a partial save on the item, and the details should use update_item to update themselves
    item.details.put = MagicMock()
    item.details.update_item = MagicMock()
    item.save(partial=True)
    item.details.put.assert_not_called()
    item.details.update_item.assert_has_calls([
        call(
            conditions=None,
            update_item_kwargs={'ReturnValues': 'UPDATED_NEW'},
            attr2=10,
            thing_version='foo:1'
        )
    ])


def test_one_to_many(dynamo_local, request):
    class Reply(DynaModel):
        class Table:
            name = 'replies'
            hash_key = 'forum_thread'
            range_key = 'created'
            read = 1
            write = 1

        class ByUser(GlobalIndex):
            name = 'replies-by-user'
            hash_key = 'user_name'
            range_key = 'message'
            projection = ProjectKeys()
            read = 1
            write = 1

        class Schema:
            forum_thread = String(required=True)
            created = String(required=True)
            user_name = String(required=True)
            message = String()

    class User(DynaModel):
        class Table:
            name = 'users'
            hash_key = 'name'
            read = 1
            write = 1

        class Schema:
            name = String(required=True)

        replies = OneToMany(
            Reply,
            index='ByUser',
            query=lambda user: dict(user_name=user.name),
            back_query=lambda reply: dict(name=reply.user_name)
        )

    class Thread(DynaModel):
        class Table:
            name = 'threads'
            hash_key = 'forum_name'
            range_key = 'subject'
            read = 1
            write = 1

        class ByUser(GlobalIndex):
            name = 'threads-by-user'
            hash_key = 'user_name'
            range_key = 'subject'
            projection = ProjectKeys()
            read = 1
            write = 1

        class Schema:
            forum_name = String(required=True)
            user_name = String(required=True)
            subject = String(required=True)

        user = ManyToOne(
            User,
            query=lambda thread: dict(name=thread.user_name),
            back_index='ByUser',
            back_query=lambda user: dict(user_name=user.name)
        )
        replies = OneToMany(
            Reply,
            query=lambda thread: dict(forum_thread='{0}\n{1}'.format(thread.forum_name, thread.subject)),
            back_query=lambda reply: dict(
                forum_name=reply.forum_thread.split('\n')[0],
                subject=reply.forum_thread.split('\n')[1]
            )
        )

    class Forum(DynaModel):
        class Table:
            name = 'forums'
            hash_key = 'name'
            read = 1
            write = 1

        class Schema:
            name = String(required=True)

        threads = OneToMany(
            Thread,
            query=lambda forum: dict(forum_name=forum.name),
            back_query=lambda thread: dict(name=thread.forum_name)
        )

    User.Table.create()
    request.addfinalizer(User.Table.delete)

    Reply.Table.create()
    request.addfinalizer(Reply.Table.delete)

    Thread.Table.create()
    request.addfinalizer(Thread.Table.delete)

    Forum.Table.create()
    request.addfinalizer(Forum.Table.delete)

    alice = User(name='alice')
    alice.save()

    bob = User(name='bob')
    bob.save()

    general = Forum(name='general')
    general.save()
    assert len(general.threads) == 0

    topic1 = Thread(forum=general, user=bob, subject='Topic #1')
    assert topic1.forum_name == 'general'
    assert topic1.user_name == 'bob'
    topic1.save()

    assert len(general.threads) == 1
    assert len(bob.threads) == 1

    assert [t.subject for t in bob.threads] == ['Topic #1']

    assert len(bob.replies) == 0
    assert len(alice.replies) == 0

    reply1 = Reply(thread=topic1, user=bob, created=str(datetime.datetime.utcnow()), message='Reply #1')
    reply1.save()

    reply2 = Reply(thread=topic1, user=alice, created=str(datetime.datetime.utcnow()), message='Reply #2')
    reply2.save()

    assert [r.forum_thread for r in bob.replies] == ['general\nTopic #1']
    assert [r.forum_thread for r in alice.replies] == ['general\nTopic #1']
