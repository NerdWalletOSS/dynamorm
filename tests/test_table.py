"""These tests require dynamo local running"""
import datetime
import dateutil.tz
import os

from decimal import Decimal

import pytest

from dynamorm import Q

from dynamorm.exceptions import HashKeyExists, InvalidSchemaField, ValidationError, ConditionFailed


def is_marshmallow():
    return os.environ.get('SERIALIZATION_PKG', '').startswith('marshmallow')


def test_table_creation_deletion(TestModel, dynamo_local):
    """Creating, detecting and deleting tables should work"""
    assert not TestModel.Table.exists
    assert TestModel.Table.create_table()
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

    TestModel.put({'foo': 'first', 'bar': 'one', 'baz': 'baz'})

    TestModel.Table.__class__._table.put_item.assert_called_with(
        Item={'foo': 'first', 'bar': 'one', 'baz': 'baz'},
    )


def test_schema_change(TestModel, TestModel_table, dynamo_local):
    """Simulate a schema change and make sure we get the record correctly"""
    data = {'foo': '1', 'bar': '2', 'bad_key': 10, 'baz': 'baz'}
    TestModel.Table.put(data)
    item = TestModel.get(foo='1', bar='2')
    assert item._raw == data
    assert item.foo == '1'
    assert item.bar == '2'
    assert not hasattr(item, 'bad_key')


def test_put_invalid_schema(TestModel, TestModel_table, dynamo_local):
    """Putting an invalid schema should raise a ``ValidationError``."""
    if is_marshmallow():
        pytest.skip('Marshmallow does marshalling and not validation when serializing')

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


def test_get_batch(TestModel, TestModel_entries, dynamo_local):
    items = TestModel.get_batch(
        keys=(
            {'foo': 'first', 'bar': 'one'},
            {'foo': 'first', 'bar': 'three'},
        ),
        attrs='bar'
    )

    item_bars = [item.bar for item in items]
    assert 'one' in item_bars
    assert 'two' not in item_bars
    assert 'three' in item_bars


def test_get_batch_invalid_field(TestModel):
    """Calling .get_batch on an invalid field should result in an exception"""
    with pytest.raises(InvalidSchemaField):
        list(TestModel.get_batch(keys=(
            {'invalid': 'nope'},
        )))


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


def test_query_filter(TestModel, TestModel_entries, dynamo_local):
    """Querying with non PK kwargs should return the expected values"""
    results = list(TestModel.query(foo="first", count__gt=200))
    assert len(results) == 2
    assert results[0].count == 333
    assert results[1].count == 222

    # This is *ugly* since in py2 you need to pass the positional args first (for the non-PK filters)
    # and then the keyword args for the PK query.
    results = list(TestModel.query(
        Q(count__gt=222) | Q(count__lt=222), ~Q(count=111),
        foo="first"
    ))
    assert len(results) == 1


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

    TestModel.put({"foo": "no_child", "bar": "omg", "baz": "baz"})
    results = list(TestModel.scan(child__not_exists=True))
    assert len(results) == 1
    assert results[0].foo == "no_child"

    with pytest.raises(TypeError):
        # Make sure we reject if the value isn't True
        list(TestModel.scan(baz__not_exists=False))


def test_scan_q(TestModel, TestModel_entries, dynamo_local):
    results = list(TestModel.scan(Q(count__gt=222) | Q(count__lt=222)))
    assert len(results) == 2

    results = list(TestModel.scan(Q(count__gt=222) | Q(count__lt=222), ~Q(count=111)))
    assert len(results) == 1


def test_update(TestModel, TestModel_entries, dynamo_local):
    two = TestModel.get(foo="first", bar="two")
    assert two.baz == 'wtf'
    two.update(baz='yay')
    assert two.baz == 'yay'

    two = TestModel.get(foo="first", bar="two", consistent=True)
    assert two.baz == 'yay'


def test_query_instead_of_get(TestModel, TestModel_entries, dynamo_local):
    two_results = list(TestModel.query(foo="first", bar="two"))
    assert len(two_results) == 1
    two = two_results[0]
    assert two.baz == 'wtf'


def test_update_no_range(TestModelTwo, TestModelTwo_table, dynamo_local):
    TestModelTwo.put({'foo': 'foo', 'bar': 'bar'})
    thing = TestModelTwo.get(foo='foo')
    thing.update(baz='illion')

    new = TestModelTwo.get(foo='foo', consistent=True)
    assert new.baz == 'illion'


def test_update_conditions(TestModel, TestModel_entries, dynamo_local):
    def update_should_fail_with_condition(conditions):
        with pytest.raises(ConditionFailed):
            TestModel.update_item(
                # our hash & range key -- matches current
                foo='first',
                bar='two',

                # things to update
                baz='yay',

                # things to check
                conditions=conditions
            )

    # all of these should fail
    update_should_fail_with_condition(dict(baz='nope'))
    update_should_fail_with_condition(dict(count__ne=222))
    update_should_fail_with_condition(dict(count__gt=300))
    update_should_fail_with_condition(dict(count__gte=300))
    update_should_fail_with_condition(dict(count__lt=200))
    update_should_fail_with_condition(dict(count__lte=200))
    update_should_fail_with_condition(dict(count__between=[10, 20]))
    update_should_fail_with_condition(dict(count__in=[221, 223]))
    update_should_fail_with_condition(dict(count__not_exists=True))
    update_should_fail_with_condition(dict(things__exists=True))
    update_should_fail_with_condition(dict(count__type='S'))
    update_should_fail_with_condition(dict(baz__begins_with='nope'))
    update_should_fail_with_condition(dict(baz__contains='nope'))

    update_should_fail_with_condition(Q(count__gt=300) | Q(count__lt=200))
    update_should_fail_with_condition(Q(count__gt=200) & ~Q(count=222))
    update_should_fail_with_condition([Q(count__gt=200), ~Q(count=222)])


def test_update_validation(TestModel, TestModel_entries, dynamo_local):
    if is_marshmallow():
        pytest.skip('Marshmallow does marshalling and not validation when serializing')

    with pytest.raises(ValidationError):
        TestModel.update_item(
            # our hash & range key -- matches current
            foo='first',
            bar='two',

            # things to update
            baz=['not a list']
        )


def test_update_invalid_fields(TestModel, TestModel_entries, dynamo_local):
    with pytest.raises(InvalidSchemaField):
        TestModel.update_item(
            # our hash & range key -- matches current
            foo='first',
            bar='two',

            # things to update
            unknown_attr='foo'
        )

    with pytest.raises(ConditionFailed):
        TestModel.update_item(
            # our hash & range key -- matches current
            foo='first',
            bar='two',

            # things to update
            baz='foo',

            conditions=dict(
                unknown_attr='foo'
            )
        )


def test_update_expressions(TestModel, TestModel_entries, dynamo_local):
    two = TestModel.get(foo='first', bar='two')
    assert two.child == {'sub': 'two'}
    two.update(child={'foo': 'bar'})
    assert two.child == {'foo': 'bar'}

    if is_marshmallow():
        with pytest.raises(AttributeError):
            assert two.things is None
    else:
        assert two.things is None

    two.update(things=['foo'])
    assert two.things == ['foo']
    two.update(things__append=[1])
    assert two.things == ['foo', 1]

    assert two.count == 222
    two.update(count__plus=10)
    assert two.count == 232
    two.update(count__minus=2)
    assert two.count == 230

    two.update(count__if_not_exists=1)
    assert two.count == 230

    six = TestModel(foo='sixth', bar='six', baz='baz')
    six.save()

    if is_marshmallow():
        with pytest.raises(AttributeError):
            assert six.count is None
    else:
        assert six.count is None
    six.update(count__if_not_exists=6)
    assert six.count == 6

    # XXX TODO
    # XXX two.update(child__foo__bar='thing')
    # http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html#Expressions.UpdateExpressions.SET.AddingNestedMapAttributes
    # XXX support REMOVE in a different function


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


def test_yield_items_xlarge(TestModel, TestModel_entries_xlarge, dynamo_local, mocker):
    try:
        mocker.spy(TestModel.Table.__class__, 'scan')
    except TypeError:
        # pypy doesn't allow us to spy on the dynamic class, so we need to spy on the instance
        mocker.spy(TestModel.Table, 'scan')
    results = list(TestModel._yield_items('scan'))

    assert TestModel.Table.scan.call_count == 2
    assert len(results) == 4000


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
    test_model = TestModel(foo='a', bar='b', baz='c', count=100)
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
    test_model = TestModel(foo='a', bar='b', baz='c', count=100)
    test_model.save()

    test_model = TestModel.get(foo='a', bar='b')
    assert test_model.count == 100

    TestModel(foo='a', bar='b', baz='c', count=200).save()

    test_model = TestModel.get(foo='a', bar='b', consistent=True)
    assert test_model.count == 200


def test_delete_with_hash_and_sort(TestModel, TestModel_table, dynamo_local):
    test_model = TestModel(foo='d', bar='e', baz='f')
    test_model.save()

    get_result = TestModel.get(foo='d', bar='e')
    assert get_result is not None
    test_model.delete()

    result = TestModel.get(foo='d', bar='e')
    assert result is None


def test_delete_with_hash(TestModelTwo, TestModelTwo_table, dynamo_local):
    test_model = TestModelTwo(foo='q')
    test_model.save()

    get_result = TestModelTwo.get(foo='q')
    assert get_result is not None
    test_model.delete()

    result = TestModelTwo.get(foo='q')
    assert result is None


def test_native_types(TestModel, TestModel_table, dynamo_local):
    DT = datetime.datetime(2017, 7, 28, 16, 18, 15, 48, tzinfo=dateutil.tz.tzutc())

    TestModel.put({"foo": "first", "bar": "one", "baz": "lol", "count": 123, "when": DT, "created": DT})
    model = TestModel.get(foo='first', bar='one')
    assert model.when == DT

    with pytest.raises(ValidationError):
        TestModel.put({"foo": "first", "bar": "one", "baz": "lol", "count": 123, "when": DT, "created": {'foo': 1}})


def test_indexes_query(TestModel, TestModel_entries, dynamo_local):
    results = list(TestModel.ByBaz.query(baz='bbq'))
    assert len(results) == 2

    results = list(TestModel.ByBaz.query(baz='bbq', bar='one'))
    assert len(results) == 1

    # we project count into the ByBaz index, but not when
    assert results[0].count == 111

    if is_marshmallow():
        assert not hasattr(results[0], 'when')
    else:
        assert results[0].when is None

    # ByBar only has a hash_key not a range key
    results = list(TestModel.ByBar.query(bar='three'))
    assert len(results) == 1


def test_indexes_scan(TestModel, TestModel_entries, dynamo_local):
    results = list(TestModel.ByBaz.scan())
    assert len(results) == 3

    results = list(TestModel.ByBar.scan())
    assert len(results) == 3
