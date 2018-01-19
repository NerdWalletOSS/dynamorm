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

    Book.query(isbn__begins_with="12345")

You can find the full list of supported comparison operators in the `Table query docs`_.


Scanning
~~~~~~~~

.. epigraph::

    The Scan operation returns one or more items and item attributes **by accessing every item** in a table or a
    secondary index.

    -- `Table scan docs`_

.. _Table scan docs: https://boto3.readthedocs.io/en/latest/reference/services/dynamodb.html#DynamoDB.Table.scan

Scanning works exactly the same as querying: comparison operators are specified using the "double-under" syntax
(``<field>__<operator>``).

.. code-block:: python

    # Scan based on attributes
    Book.scan(author="Mr. Bar")
    Book.scan(author__ne="Mr. Bar")


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
