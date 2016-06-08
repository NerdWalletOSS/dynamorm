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


Defining the MarshModels
------------------------

``MarshModel`` is the base class all of your models will extend from.  Each ``MarshModel`` represents a DynamoDB table.
This model definition encapsulates the parameters used to create and manage the table as well as the schema used to
validate and encode/decode data into object attributes.  It also holds any custom business logic you need for your
objects.

.. code-block:: python

    import os

    from dynamallow import MarshModel

    from marshmallow import fields, validate


    class Thing(MarshModel):

        class Table:
            name = '{env}-things'.format(env=os.environ.get('ENVIRONMENT', 'dev'))
            hash_key = 'id'
            read = 5
            write = 1

        class Schema:
            id = fields.String(required=True)
            name = fields.String()
            color = fields.String(validate=validate.OneOf(('purple', 'red', 'yellow')))

        def say_hello(self):
            print("Hello.  {name} here.  My ID is {id} and I'm colored {color}".format(
                id=self.id,
                name=self.name,
                color=self.color
            ))


Table Data Model
~~~~~~~~~~~~~~~~

.. automodule:: dynamallow.table


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
