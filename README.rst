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

This package is still very much a work in progress, but has basic working functional tests.


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
