Usage
=====

Using DynamORM is straight forward.  Simply define your models with some specific meta data to represent the DynamoDB
Table structure as well as the document schema.  You can then use class level methods to query for and get items,
represented as instances of the class, as well as class level methods to interact with specific documents in the table.

.. note::

    Not all functionality is covered in this documentation yet.  See `the tests`_ for all "supported" functionality
    (like: batch puts, unique puts, etc).

.. _the tests: https://github.com/NerdWallet/DynamORM/tree/master/tests


Setting up Boto3
-----------------

Make sure you have `configured boto3`_ and can access DynamoDB from the Python console.

.. code-block:: python

    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    list(dynamodb.tables.all())  # --> ['table1', 'table2', 'etc...']

.. _configured boto3: https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration


Using Dynamo Local
~~~~~~~~~~~~~~~~~~

If you're using `Dynamo Local`_ for development you will need to configure DynamORM appropriately by manually calling
``get_resource`` on any model's ``Table`` object, which takes the same parameters as ``boto3.resource``.  The
``dynamodb`` boto resource is shared globally by all models, so it only needs to be done once.  For example:

.. code-block:: python

    MyModel.Table.get_resource(
        aws_access_key_id="anything",
        aws_secret_access_key="anything",
        region_name="us-west-2",
        endpoint_url="http://localhost:8000"
    )

.. _Dynamo Local: http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html


Defining your Models -- Tables & Schemas
----------------------------------------

.. automodule:: dynamorm.model
    :noindex:


Table Data Model
----------------

.. automodule:: dynamorm.table
    :noindex:


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
