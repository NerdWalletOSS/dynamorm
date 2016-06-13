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

*This package is a work in progress -- Feedback / Suggestions / Etc welcomed!*

Two awesome things, better together!

Dynamallow is a Python library that provides integration between the `Boto v3 DynamoDB API`_ and `Marshmallow`_.
Together they provide a simple, ORM inspired, interface to the `DynamoDB`_ service with a fully defined, strongly typed
schema.

.. code-block:: python

    from dynamallow import MarshModel
    from marshmallow import fields

    class Book(MarshModel):
        class Table:
            name = 'prod-books'
            hash_key = 'isbn'
            read = 25
            write = 5

        class Schema:
            isbn = fields.String(validate=validate_isbn)
            title = fields.String()
            author = fields.String()
            publisher = fields.String()
            year = fields.Number()


    # Store new documents directly from dictionaries
    Book.put({
        "isbn": "12345678910",
        "title": "Foo",
        "author": "Mr. Bar",
        "publisher": "Publishorama"
    })

    # Work with the classes as objects
    # You can pass attributes from the schema to the constructor
    foo = Book(isbn="12345678910", title="Foo", author="Mr. Bar",
               publisher="Publishorama")
    foo.save()

    # Or assign attributes
    foo = Book()
    foo.isbn = "12345678910"
    foo.title = "Foo"
    foo.author = "Mr. Bar"
    foo.publisher = "Publishorama"
    foo.save()

    # In all cases they go through Schema validation, calls to
    # .put or .save can result in ValidationError being raised.

    # You can then fetch, query and scan your tables.

    # Get on the hash key, and/or range key
    Book.get(isbn="12345678910")

    # Query based on the keys
    Book.query(isbn__begins_with="12345")

    # Scan based on attributes
    Book.scan(author="Mr. Bar")
    Book.scan(author__ne="Mr. Bar")


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
