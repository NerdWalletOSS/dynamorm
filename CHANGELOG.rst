0.10.0 - 2019.12.18
###################

* Enable support for updating nested paths in ``Table.update``. Like functions (like ``minus`` or ``if_not_exists``) nested paths are also separated using the double-underscore syntax. For example, given an attribute ``foo`` of an item ``i``:::

    "foo": {
        "bar": {
            "a": 1
        },
        "baz": 10
    }

    i.update(foo__bar__a=42)
    "foo": {
        "bar": {
            "a": 42
        },
        "baz": 10
    }

    i.update(foo__baz__plus=32)
    "foo": {
        "bar": {
            "a": 42
        },
        "baz": 42
    }

  This works because DynamoDB allows updating of nested attributes, using something like JSON path. From the `DynamoDB Developer Guide`_::

    aws dynamodb update-item \
        --table-name ProductCatalog \
        --key '{"Id":{"N":"789"}}' \
        --update-expression "SET #pr.#5star[1] = :r5, #pr.#3star = :r3" \
        --expression-attribute-names '{
            "#pr": "ProductReviews",
            "#5star": "FiveStar",
            "#3star": "ThreeStar"
        }' \
        --expression-attribute-values '{
            ":r5": { "S": "Very happy with my purchase" },
            ":r3": {
                "L": [
                    { "S": "Just OK - not that great" }
                ]
            }
        }' \
        --return-values ALL_NEW

  Note that the attribute names along the nested path are broken up - this helps distinguish a nested update from a flat key like ``my.flat.key`` that contains a period.

.. _`DynamoDB Developer Guide`: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html#Expressions.UpdateExpressions.SET.AddingNestedMapAttributes

0.9.14 - 2019.12.13
###################

* Ensure that ``dynamorm_validate`` actually calls ``schematics`` validation.

0.9.13 - 2019.12.12
###################

* Check that recursive mode is enabled before warning about trying to use both limit and recursive.

0.9.12 - 2019.09.30
###################

* Ensure GitHub pages serves our static documentation content
* No functional library changes

0.9.11 - 2019.09.30
###################

* Bug fix: Don't mutate dictionaries passed to table methods.

  This caused problems with ``ReadIterator`` objects that called ``.again()`` because the underlying Table object would end up mutating state on the iterator object.

0.9.10 - 2019.09.30
###################

* Bug fix: Ensure keys are normalized when calling ``.delete()`` on a model.

0.9.9 - 2019.09.30
##################

* Performance: Avoid validating twice when calling ``.save()`` on a model.

0.9.8 - 2019.09.29
##################

* Fix documentation deployment (broken since 0.9.6)

0.9.7 - 2019.09.29
##################

* Use Black (https://github.com/psf/black) for formatting code
* No functional library changes

0.9.6 - 2019.09.26
##################

* Switch to ``tox`` for running tests
* Documentation improvements
* No functional library changes

0.9.5 - 2019.09.26
##################

* Add support for Marshmallow version 3

0.9.4 - 2019.09.28
##################

* Bump minimum schematics version to 2.10
* Ignore schematics warnings during test

0.9.3 - 2019.04.30
##################

* Add extras_require to setup.py to specify minimum versions of schematics & marshmallow

0.9.2
#####

* Documentation update

0.9.1 - 2018.09.07
##################

https://github.com/NerdWalletOSS/dynamorm/pull/61

* **BACKWARDS INCOMPATIBLE CHANGE!**

  ``Model.query`` and ``Model.scan`` no longer return ALL available items.
  Instead they stop at each 1Mb page.  You can keep the existing behavior by
  adding a ``.recursive()`` call to the return value.

  Before::

      books = Books.scan()

  After::

      books = Books.scan().recursive()

* This version introduces the ``ReadIterator`` object which is returned from
  query and scan operations.  This object exposes functions that allow for
  better control over how a query/scan is executed.  See the usage docs for full
  details.
