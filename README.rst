DynamoDB + Marshmallow == Dynamallow
====================================

Two awesome things, better together!

.. image:: https://img.shields.io/travis/borgstrom/dynamallow.svg
           :target: https://travis-ci.org/borgstrom/dynamallow

.. image:: https://img.shields.io/codecov/c/github/borgstrom/dynamallow.svg
           :target: https://codecov.io/github/borgstrom/dynamallow

.. image:: https://img.shields.io/pypi/v/dynamallow.svg
           :target: https://pypi.python.org/pypi/dynamallow
           :alt: Latest PyPI version

.. image:: https://img.shields.io/pypi/dm/dynamallow.svg
           :target: https://pypi.python.org/pypi/dynamallow
           :alt: Number of PyPI downloads

Dynamallow provides integration between the `Boto v3 DynamoDB API`_ and `Marshmallow`_.  Together they provide an ORM
inspired interface to the `DynamoDB`_ service with a fully defined, strongly typed schema.

*This package is still very much a work in progress -- Feedback / Suggestions / Etc welcomed*

Usage
-----

Using Dynamallow is straight forward.  Simply define your models with some specific meta data to represent the DynamoDB
Table structure as well as the document schema.  You can then use class level methods to query for and get items,
represented as instances of the class, as well as class level methods to interact with specific documents in the table.

.. note::

    Not all functionality is covered in this documentation yet.  See the tests for all "supported" functionality (like:
    batch puts, unique puts, etc).


Setting up Boto3
~~~~~~~~~~~~~~~~~

Make sure you have `configured boto3`_ and can access DynamoDB from the Python console.

.. code-block:: python

    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    list(dynamodb.tables.all())  # --> ['table1', 'table2', 'etc...']


Defining the MarshModels
~~~~~~~~~~~~~~~~~~~~~~~~

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
            hash_key = id
            read = 5
            write = 1

        class Schema:
            id = fields.String(required=True)
            name = fields.String()
            color = fields.String(validate=validate.OneOf(('purple', 'red', 'yellow')))

        def some_function(self):
            ...


Creating new documents
~~~~~~~~~~~~~~~~~~~~~~

Using objects:

.. code-block:: python

    thing = Thing(id="thing1", name="Thing One", color="purple")
    thing.save()

.. code-block:: python

    thing = Thing()
    thing.id = "thing1"
    thing.name="Thing One"
    thing.color="purple"
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To fetch an existing document you use the ``.get`` class method on your models:

.. code-block:: python

    thing1 = Thing.get(id="thing1")
    assert thing1.color == 'purple'


Developing
----------

To create a virtualenv and pull in the required dependencies:

.. code-block:: bash
    
    virtualenv ~/.virtualenvs/dynamallow
    source ~/.virtualenvs/dynamallow/bin/activate
    pip install -e .


Running the tests
~~~~~~~~~~~~~~~~~

From the activated virtualenv:

.. code-block:: bash

    python setup.py test

The tests will pull down the latest copy of DynamoDB Local from S3 and place it in ``build/dynamo-local``.  A copy will
be started on a random high port, running with ``-inMemory``, at the start of the test run and shutdown after the run.


.. _Boto v3 DynamoDB API: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
.. _Marshmallow: https://marshmallow.readthedocs.io/en/latest/
.. _DynamoDB: http://aws.amazon.com/dynamodb/
.. _configured boto3: https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration
