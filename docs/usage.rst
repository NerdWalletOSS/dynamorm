Usage
=====

Using DynamORM is straight forward.  Simply define your models with some specific meta data to represent the DynamoDB
Table structure as well as the document schema.  You can then use class level methods to query for and get items,
represented as instances of the class, as well as class level methods to interact with specific documents in the table.

.. note::

    Not all functionality is covered in this documentation yet.  See `the tests`_ for all "supported" functionality
    (like: batch puts, unique puts, etc).

.. _the tests: https://github.com/NerdWalletOSS/DynamORM/tree/master/tests


Setting up Boto3
-----------------

Make sure you have `configured boto3`_ and can access DynamoDB from the Python console.

.. code-block:: python

    import boto3
    dynamodb = boto3.resource('dynamodb')
    list(dynamodb.tables.all())  # --> ['table1', 'table2', 'etc...']

.. _configured boto3: https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration


Configuring the Boto3 resource
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The above example is relying on the files ``~/.aws/credentials`` & ``~/.aws/config`` to provide access information and
region selection.  You can provide explicit configuration for `boto3 sessions`_ and `boto3 resources`_ as part of your
``Table`` definition.

For example, if you develop against a local dynamo service your models may look something like:

.. code-block:: python


    class MyModel(DynaModel):
        class Table:
            session_kwargs = {
                'region_name': 'us-east-2'
            }
            resource_kwargs = {
                'endpoint_url': 'http://localhost:33333'
            }


You would obviously want the session and resource configuration to come from some sort of configuration provider that
could provide the correct options depending on where your application is being run.

.. _boto3 sessions: http://boto3.readthedocs.io/en/latest/reference/core/session.html
.. _boto3 resources: http://boto3.readthedocs.io/en/latest/reference/services/dynamodb.html#service-resource
.. _Flask: http://flask.pocoo.org/


Using Dynamo Local
~~~~~~~~~~~~~~~~~~

If you're using `Dynamo Local`_ for development you can use the following config for the table resource:

.. code-block:: python

    MyModel.Table.get_resource(
        aws_access_key_id="-",
        aws_secret_access_key="-",
        region_name="us-west-2",
        endpoint_url="http://localhost:8000"
    )

.. _Dynamo Local: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html


Defining your Models -- Tables & Schemas
----------------------------------------

.. automodule:: dynamorm.model
    :noindex:

.. autoclass:: dynamorm.model.DynaModel
    :noindex:


Table Data Model
----------------

.. automodule:: dynamorm.table
    :noindex:


.. _creating-new-documents:

Creating new documents
----------------------

Using objects:

.. code-block:: python

    thing = Thing(id="thing1", name="Thing One", color="purple")
    thing.save()

.. code-block:: python

    thing = Thing()
    thing.id = "thing1"
    thing.name = "Thing One"
    thing.color = "purple"
    thing.save()


Using raw documents:

.. code-block:: python

    Thing.put({
        "id": "thing1",
        "name": "Thing One",
        "color": "purple"
    })

In all cases, the attributes go through validation against the Schema.

.. code-block:: python

    thing = Thing(id="thing1", name="Thing One", color="orange")

    # the call to save will result in a ValidationError because orange is an invalid choice.
    thing.save()

.. note::

    Remember, if you have a ``String`` field it will use ``unicode`` (py2) or ``str`` (py3) on any value assigned to it,
    which means that if you assign a ``list``, ``dict``, ``int``, etc then the validation will succeed and what will be
    stored is the representative string value.


Fetching existing documents
---------------------------

Get based on primary key
~~~~~~~~~~~~~~~~~~~~~~~~

To fetch an existing document based on its primary key you use the ``.get`` class method on your models:

.. code-block:: python

    thing1 = Thing.get(id="thing1")
    assert thing1.color == 'purple'

To do a `Consistent Read`_ just pass ``consistent=True``:

.. code-block:: python

    thing1 = Thing.get(id="thing1", consistent=True)
    assert thing1.color == 'purple'

.. _Consistent Read: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html

Querying
~~~~~~~~

.. epigraph::

    A Query operation uses the primary key of a table or a secondary index to directly access items from that table or index.

    -- `Table query docs`_

.. _Table query docs: https://boto3.readthedocs.io/en/latest/reference/services/dynamodb.html#DynamoDB.Table.query


Like a ``get`` operation this takes arguments that map to the key names, but you can also specify a comparison operator
for that key using the "double-under" syntax (``<field>__<operator>``).  For example to query a ``Book`` model for all
entries with the ``isbn`` field that start with a specific value you would use the ``begins_with`` comparison operator:

.. code-block:: python

    books = Book.query(isbn__begins_with="12345")

You can find the full list of supported comparison operators in the `DynamoDB Condition docs`_.

.. _DynamoDB Condition docs: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/customizations/dynamodb.html#dynamodb-conditions

Scanning
~~~~~~~~

.. epigraph::

    The Scan operation returns one or more items and item attributes **by accessing every item** in a table or a
    secondary index.

    -- `Table scan docs`_

.. _Table scan docs: https://boto3.readthedocs.io/en/latest/reference/services/dynamodb.html#DynamoDB.Table.scan

Scanning works exactly the same as querying.

.. code-block:: python

    # Scan based on attributes
    Book.scan(author="Mr. Bar")
    Book.scan(author__ne="Mr. Bar")


.. _read-iterators:

Read Iterator object
~~~~~~~~~~~~~~~~~~~~

Calling ``.query`` or ``.scan`` will return a ``ReadIterator`` object that will not actually send the API call to
DynamoDB until you try to access an item in the object by iterating (``for book in books:``, ``list(books)``, etc...).

The iterator objects have a number of methods on them that can be used to influence their behavior.  All of the methods
described here (except ``.count()``) are "chained methods", meaning that they return the iterator object such that you
can chain them together.

.. code-block:: python

    next_10_books = Book.query(hash_key=the_hash_key).start(previous_last).limit(10)


Returning the Count (``.count()``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Unlike the rest of the methods in this section, ``.count()`` is the only one that does not return the iterator object.
Instead it changes the SELECT_ parameter to ``COUNT`` and immediately sends the request, returning the count.

.. code-block:: python

    books_matching_hash_key = Books.query(hash_key=the_hash_key).count()


.. _SELECT: https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_Query.html#DDB-Query-request-Select


Requesting consistent results (``.consistent()``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Queries & scans return eventually consistent results by default.  You can use ``.consistent()`` to return results that
ensure all in-flight writes finished and no new writes were launched.

.. code-block:: python

    Books.query(hash_key=the_hash_key).consistent()


Changing the returned attributes (``.specific_attributes()``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, query & scan operations will return ALL attributes from the table or index.  If you'd like to change the
attributes to only return subset of the attributes you can pass a list to ``.specific_attributes([...])``.  Each
attribute passed in should match the syntax from `Specifying Item Attributes`_ in the docs.

.. code-block:: python

    Books.query(hash_key=the_hash_key).specific_attributes(['isbn', 'title', 'publisher.name'])

.. _Specifying Item Attributes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.Attributes.html


Paging (``.last``, ``.start()`` & ``.again()``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. epigraph::

    A single Query operation will read up to the maximum number of items set (if using the Limit parameter) or a maximum
    of 1 MB of data and then apply any filtering to the results

    -- `Table query docs`_

When you query a table with many items, or with a limit, the iterator object will set its ``.last`` attribute to the key
of the last item it received.  You can pass that item into a subsequent query via the ``start()`` method, or if you have
the existing iterator object simply call ``.again()``.

.. code-block:: python

    books = Book.scan()
    print(list(books))

    if books.last:
        print("The last book seen was: {}".format(books.last))
        print(list(books.again()))


.. code-block:: python

    last = get_last_from_request()
    books = Book.scan().start(last)


Limiting (``.limit()``)
^^^^^^^^^^^^^^^^^^^^^^^

.. epigraph::

    The maximum number of items to evaluate (not necessarily the number of matching items). If DynamoDB processes the
    number of items up to the limit while processing the results, it stops the operation and returns the matching values
    up to that point.

    -- `Table query docs`_

You can also use the ``.limit()`` method on the iterator object to apply a Limit to your query.

.. code-block:: python

    books = Book.scan().limit(1)
    assert len(books) == 1


Reversing (``.reverse()`` - Queries Only)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To have the indexed scanned in reverse for your query, use ``.reverse()``

.. note::

    Scanning does not support reversing.

.. code-block:: python

    books = Book.query(hash_key=the_hash_key).reverse()


Recursion (``.recursive()``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you wish to get ALL items from a query or scan without having to deal with paging your self, then you can use the
``recursive()`` method to have the iterator handle the paging for you.

.. code-block:: python

    books = Book.scan().recursive()


.. _q-objects:

``Q`` objects
~~~~~~~~~~~~~

.. autofunction:: dynamorm.table.Q
    :noindex:

See the :py:func:`dynamorm.model.DynaModel.scan` docs for more examples.


Indexes
~~~~~~~

By default the hash & range keys of your table make up the "Primary Index".  `Secondary Indexes`_ provide different ways
to query & scan your data.  They are defined on your Model alongside the main Table definition as inner classes
inheriting from either the ``GlobalIndex`` or ``LocalIndex`` classes.

.. _Secondary Indexes: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/SecondaryIndexes.html

Here's an excerpt from the model used in the readme:

.. code-block:: python

    class Book(DynaModel):
        # Define our DynamoDB properties
        class Table:
            name = 'prod-books'
            hash_key = 'isbn'
            read = 25
            write = 5

        class ByAuthor(GlobalIndex):
            name = 'by-author'
            hash_key = 'author'
            read = 25
            write = 5
            projection = ProjectAll()

With the index defined we can now call ``Book.ByAuthor.query`` or ``Book.ByAuthor.scan`` to query or scan the index.
The query & scan semantics on the Index are the same as on the main table.

.. code-block:: python

    Book.ByAuthor.query(author='Some Author')
    Book.ByAuthor.query(author__ne='Some Author')

Indexes uses "projection" to determine which attributes of your documents are available in the index.  The
``ProjectAll`` projection puts ALL attributes from your Table into the Index.  The ``ProjectKeys`` projection puts just
the keys from the table (and also the keys from the index themselves) into the index.  The ``ProjectInclude('attr1',
'attr2')`` projection allows you to specify which attributes you wish to project.

Using the ``ProjectKeys`` or ``ProjectInclude`` projection will result in partially validated documents, since we won't
have all of the require attributes.

A common pattern is to define a "sparse index" with just the keys (``ProjectKeys``), load the keys of the documents you
want from the index and then do a batch get to fetch them all from the main table.


Updating documents
------------------

There are a number of ways to send updates back to the Table from your Model classes and indexes.  The
:ref:`creating-new-documents` section already showed you the :py:func:`dynamorm.model.DynaModel.save` methods for
creating new documents.  ``save`` can also be used to update existing documents:

.. code-block:: python

    # Our book is no longer in print
    book = Book.get(isbn='1234567890')
    book.in_print = False
    book.save()

When you call ``.save()`` on an instance the WHOLE document is put back into the table as save simply invokes the
:py:func:`dynamorm.model.DynaModel.put` function.  This means that if you have large models it may cost you more in
Write Capacity Units to put the whole document back.

You can also do a "partial save" by passing ``partial=True`` when calling save, in which case the
:py:func:`dynamorm.model.DynaModel.update` function will be used to only send the attributes that have been modified
since the document was loaded.  The following two code blocks will result in the same operations:

.. code-block:: python

    # Our book is no longer in print
    book = Book.get(isbn='1234567890')
    book.in_print = False
    book.save(partial=True)

.. code-block:: python

    # Our book is no longer in print
    book = Book.get(isbn='1234567890')
    book.update(in_print=False)

Doing partial saves (``.save(partial=True)``) is a very convenient way to work with existing instances, but using the
:py:func:`dynamorm.model.DynaModel.update` directly allows for you to also send `Update Expressions`_ and `Condition
Expressions`_ with the update.  Combined with consistent reads, this allows you to do things like acquire locks that
ensure race conditions cannot happen:

.. code-block:: python

    class Lock(DynaModel):
        class Table:
            name = 'locks'
            hash_key = 'name'
            read = 1
            write = 1

        class Schema:
            name = String(required=True)
            updated = Integer(required=True, default=0)
            key = String()
            is_locked = Boolean(default=False)

        @classmethod
        def lock(self, name, key):
            inst = cls.get(name=name, consistent=True)

            if inst is None:
                inst = Lock(name=name)
                inst.save()

            if not inst.is_locked:
                inst.update(
                    is_locked=True,
                    key=key,
                    updated=time.time(),
                    conditions=dict(
                        updated=inst.updated,
                    )
                )
            return inst

        @classmethod
        def unlock(cls, name, key):
            inst = cls.get(name=name, consistent=True)

            if key == inst.key:
                inst.update(
                    is_locked=False,
                    key=None,
                    updated=time.time(),
                    conditions=dict(
                        updated=inst.updated,
                    )
                )

            return inst

    lock = Lock.lock('my-lock', 'my-key')
    if lock.key != 'my-key':
        print("Failed to lock!")
    else:
        print("Lock acquired!")


Just like Scanning or Querying a table, you can use :ref:`q-objects` for your update expressions.

.. _Update Expressions: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html
.. _Condition Expressions: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html


Relationships
-------------

.. automodule:: dynamorm.relationships
    :noindex:
