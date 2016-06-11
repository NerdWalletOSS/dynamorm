DynamoDB + Marshmallow == Dynamallow
====================================

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

----

Two awesome things, better together!

Dynamallow provides integration between the `Boto v3 DynamoDB API`_ and `Marshmallow`_.  Together they provide a simple,
ORM inspired, interface to the `DynamoDB`_ service with a fully defined, strongly typed schema.

*This package is still very much a work in progress -- Feedback / Suggestions / Etc welcomed*


Documentation
=============

Full documentation can be found online at:

http://borgstrom.github.io/dynamallow/


TODO
====

* Indexes -- Currently there is no support for indexes.
* Schema Migrations
* Partial updates on ``save()``


.. _Boto v3 DynamoDB API: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
.. _Marshmallow: https://marshmallow.readthedocs.io/en/latest/
.. _DynamoDB: http://aws.amazon.com/dynamodb/
