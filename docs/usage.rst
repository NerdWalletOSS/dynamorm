Usage
=====

Using Dynamallow is straight forward.  Simply define your models with some specific meta data to represent the DynamoDB
Table structure as well as the document schema.  You can then use class level methods to query for and get items,
represented as instances of the class, as well as class level methods to interact with specific documents in the table.

.. note::

    Not all functionality is covered in this documentation yet.  See `the tests`_ for all "supported" functionality
    (like: batch puts, unique puts, etc).


Setting up Boto3
-----------------

Make sure you have `configured boto3`_ and can access DynamoDB from the Python console.

.. code-block:: python

    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    list(dynamodb.tables.all())  # --> ['table1', 'table2', 'etc...']


Using Dynamo Local
~~~~~~~~~~~~~~~~~~

If you're using `Dynamo Local`_ for development you will need to configure Dynamallow appropriately by manually calling
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

.. automodule:: dynamallow.model
    :noindex:


Table Data Model
----------------

.. automodule:: dynamallow.table
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

To fetch an existing document you use the ``.get`` class method on your models:

.. code-block:: python

    thing1 = Thing.get(id="thing1")
    assert thing1.color == 'purple'


.. _configured boto3: https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration
.. _the tests: https://github.com/borgstrom/dynamallow/tree/master/tests
