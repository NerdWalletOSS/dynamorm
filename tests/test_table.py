"""These tests require dynamo local running"""
from decimal import Decimal
import pytest

from dynamorm.exceptions import HashKeyExists, InvalidSchemaField, ValidationError


def test_table_creation_deletion(TestModel, dynamo_local):
    """Creating, detecting and deleting tables should work"""
    assert not TestModel.Table.exists
    assert TestModel.Table.create()
    assert TestModel.Table.exists
    assert TestModel.Table.delete()
    assert not TestModel.Table.exists


def test_put_get(TestModel, TestModel_table, dynamo_local):
    """Putting and getting an item should work"""
    TestModel.put({"foo": "first", "bar": "one", "baz": "lol", "count": 123})
    first_one = TestModel.get(foo="first", bar="one")
    assert isinstance(first_one, TestModel)
    assert first_one.baz == 'lol' and first_one.count == 123


def test_put_remove_nones(TestModel, TestModel_table, dynamo_local, mocker):
    # mock out the underlying table resource, we have to reach deep in to find it...
    mocker.patch.object(TestModel.Table.__class__, '_table')

    TestModel.put({'foo': 'first', 'bar': 'one'})

    TestModel.Table.__class__._table.put_item.assert_called_with(
        Item={'foo': 'first', 'bar': 'one'}
    )


def test_schema_change(TestModel, TestModel_table, dynamo_local):
    """Simulate a schema change and make sure we get the record correctly"""
    data = {'foo': '1', 'bar': '2', 'bad_key': 10}
    TestModel.Table.put(data)
    item = TestModel.get(foo='1', bar='2')
    assert item._raw == data
    assert item.foo == '1'
    assert item.bar == '2'
    assert not hasattr(item, 'bad_key')


def test_put_invalid_schema(TestModel, TestModel_table, dynamo_local):
    """Putting an invalid schema should raise a ``ValidationError``."""
    with pytest.raises(ValidationError):
        TestModel.put({"foo": [1], "bar": '10'})


def test_put_batch(TestModel, TestModel_table, dynamo_local):
    """Batch putting items should work"""
    TestModel.put_batch(
        {"foo": "first", "bar": "two", "baz": "wtf", "count": 321},
        {"foo": "second", "bar": "one", "baz": "bbq", "count": 456},
    )
    second_one = TestModel.get(foo="second", bar="one")
    assert isinstance(second_one, TestModel)
    assert second_one.baz == 'bbq' and second_one.count == 456


def test_get_non_existant(TestModel, TestModel_table, dynamo_local):
    """Getting a non-existant item should return None"""
    assert TestModel.get(foo="fifth", bar="derp") is None


def test_object_syntax(TestModel, TestModel_table, dynamo_local):
    """Putting (saving) an item using the object syntax should work"""
    third_three = TestModel(foo="third", bar="three", baz="idk", count=7)
    third_three.save()

    assert TestModel.get(foo="third", bar="three").baz == "idk"


def test_put_unique(TestModel, TestModel_table, dynamo_local):
    """Putting an item with a unique constraint should work"""
    TestModel.put({"foo": "third", "bar": "three", "baz": "fuu", "count": 8})

    assert TestModel.get(foo="third", bar="three").baz == "fuu"

    with pytest.raises(HashKeyExists):
        TestModel.put_unique({"foo": "third", "bar": "three", "baz": "waa", "count": 9})


def test_get_invalid_field(TestModel):
    """Calling .get on an invalid field should result in an exception"""
    with pytest.raises(InvalidSchemaField):
        TestModel.get(bbq="wtf")


def test_count(TestModel, TestModel_entries, dynamo_local):
    """Test the raw query/scan functions to allow things like Counting"""
    resp = TestModel.Table.query(foo="first", query_kwargs=dict(Select='COUNT'))
    assert resp['Count'] == 3

    resp = TestModel.Table.scan(count__lt=250, scan_kwargs=dict(Select='COUNT'))
    assert resp['Count'] == 2


def test_query(TestModel, TestModel_entries, dynamo_local):
    """Querying should return the expected values"""
    results = list(TestModel.query(foo="first"))
    assert len(results) == 3

    # our table has a hash and range key, so our results are ordered based on the range key
    assert results[0].count == 111
    assert results[1].count == 333
    assert results[2].count == 222

    # get the results in the opposite order
    # XXX TODO: should this be eaiser?
    results = list(TestModel.query(foo="first", query_kwargs={'ScanIndexForward': False}))
    assert results[0].count == 222

    with pytest.raises(InvalidSchemaField):
        results = list(TestModel.query(baz="bbq"))

    results = list(TestModel.query(foo="first", bar="two"))
    assert len(results) == 1
    assert results[0].count == 222

    results = list(TestModel.query(foo="first", bar__begins_with="t"))
    assert len(results) == 2

    results = list(TestModel.query(query_kwargs={"Limit": 2}, foo="first"))
    assert len(results) == 2
    assert results[0].count == 111
    assert results[1].count == 333


def test_scan(TestModel, TestModel_entries, dynamo_local):
    """Scanning should return the expected values"""
    results = list(TestModel.scan(count__gt=200))
    assert len(results) == 2

    # our table has a hash and range key, so our results are ordered based on the range key
    assert results[0].count == 333
    assert results[1].count == 222

    results = list(TestModel.scan(child__sub="two"))
    assert len(results) == 1
    assert results[0].count == 222

    results = list(TestModel.scan(child__sub__begins_with="t"))
    assert len(results) == 2
    assert results[0].count == 333
    assert results[1].count == 222

    results = list(TestModel.scan(scan_kwargs={"Limit": 2}, count__gt=0))
    assert len(results) == 2
    assert results[0].count == 111
    assert results[1].count == 333

    TestModel.put({"foo": "no_baz", "bar": "omg"})
    results = list(TestModel.scan(baz__not_exists=True))
    assert len(results) == 1
    assert results[0].foo == "no_baz"

    with pytest.raises(TypeError):
        # Make sure we reject if the value isn't True
        list(TestModel.scan(baz__not_exists=False))


def test_yield_items(TestModel, mocker):
    # Mock out Dynamo responses as each having only one item to test auto-paging
    side_effects = [{
        'Items': [{'bar': 'one', 'baz': 'bbq', 'child': {'sub': 'one'}, 'count': Decimal('111'), 'foo': 'first'}],
        'LastEvaluatedKey': {'cookie_id': 'ec477c69-8bc5-4e14-995d-37a73e8eb185', 'created_at': Decimal('1490000000')},
        'ScannedCount': 1
        }, {
        'Items': [{'bar': 'two', 'baz': 'bbq', 'child': {'sub': 'one'}, 'count': Decimal('222'), 'foo': 'second'}],
        'ScannedCount': 1
    }]
    mocker.patch.object(TestModel.Table.__class__, 'scan', side_effect=side_effects)
    results = list(TestModel._yield_items('scan', dynamo_kwargs={"Limit": 2}))

    assert TestModel.Table.scan.call_count == 2
    assert len(results) == 2
    assert results[0].count == 111
    assert results[1].count == 222

    mocker.patch.object(TestModel.Table.__class__, 'query', side_effect=side_effects)
    results = list(TestModel._yield_items('query', dynamo_kwargs={"Limit": 2}))

    assert TestModel.Table.query.call_count == 2
    assert len(results) == 2
    assert results[0].count == 111
    assert results[1].count == 222


def test_overwrite(TestModel, TestModel_entries, dynamo_local):
    """Putting an existing hash+range should replace the old entry"""
    TestModel.put(
        {"foo": "first", "bar": "one", "baz": "omg", "count": 999, "child": {"sub": "zero"}},
    )

    resp = TestModel.Table.query(foo="first", query_kwargs=dict(Select='COUNT'))
    assert resp['Count'] == 3

    first_one = TestModel.get(foo="first", bar="one")
    assert first_one.count == 999


def test_save(TestModel, TestModel_table, dynamo_local):
    test_model = TestModel(foo='a', bar='b', count=100)
    test_model.save()
    result = TestModel.get(foo='a', bar='b')
    assert result.foo == 'a'
    assert result.bar == 'b'
    assert result.count == 100

    test_model.count += 1
    test_model.baz = 'hello_world'
    test_model.save()
    result = TestModel.get(foo='a', bar='b')
    assert result.foo == 'a'
    assert result.bar == 'b'
    assert result.count == 101
    assert result.baz == 'hello_world'


def test_save_update(TestModel, TestModel_entries, dynamo_local):
    result = TestModel.get(foo='first', bar='one')
    assert result.baz == 'bbq'
    result.baz = 'changed'
    result.save()

    result = TestModel.get(foo='first', bar='one')
    assert result.baz == 'changed'


def test_consistent_read(TestModel, TestModel_entries, dynamo_local):
    test_model = TestModel(foo='a', bar='b', count=100)
    test_model.save()

    test_model = TestModel.get(foo='a', bar='b')
    assert test_model.count == 100

    TestModel(foo='a', bar='b', count=200).save()

    test_model = TestModel.get(foo='a', bar='b', consistent=True)
    assert test_model.count == 200
