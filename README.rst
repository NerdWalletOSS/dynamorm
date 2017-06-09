DynamORM
========

.. image:: https://img.shields.io/travis/NerdWalletOSS/dynamorm.svg
           :target: https://travis-ci.org/NerdWalletOSS/dynamorm

.. image:: https://img.shields.io/codecov/c/github/NerdWalletOSS/dynamorm.svg
           :target: https://codecov.io/github/NerdWalletOSS/dynamorm

.. image:: https://img.shields.io/pypi/v/dynamorm.svg
           :target: https://pypi.python.org/pypi/dynamorm
           :alt: Latest PyPI version

----

*This package is a work in progress -- Feedback / Suggestions / Etc welcomed!*

DynamORM (pronounced *Dynamo-R-M*) is a Python object relation mapping library for Amazon's `DynamoDB`_ service.

The project has two goals:

1. **Abstract away the interaction with the underlying DynamoDB libraries**.  Python access to the DynamoDB service has
   evolved quickly, from `Dynamo v1 in boto to Dynamo v2 in boto`_ and then the `new resource model in boto3`_.  By
   providing a consistent interface that will feel familiar to users of other Python ORMs (SQLAlchemy, Django, Peewee,
   etc) means that we can always provide best-practices for queries and take advantages of new features without needing
   to refactor any application logic.

2. **Delegate schema validation and serialization to more focused libraries**.  Building ORM semantics is "easy", doing
   data validation and serialization is not.  We support both `Marshmallow`_ and `Schematics`_ for building your object
   schemas.  You can take advantage of the full power of these libraries as they are transparently exposed in your code.

.. _DynamoDB: http://aws.amazon.com/dynamodb/
.. _Dynamo v1 in boto to Dynamo v2 in boto: http://boto.cloudhackers.com/en/latest/migrations/dynamodb_v1_to_v2.html
.. _new resource model in boto3: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
.. _Marshmallow: https://marshmallow.readthedocs.io/en/latest/
.. _Schematics: https://schematics.readthedocs.io/en/latest/


Supported Versions
------------------

* Schematics >= 2.0
* Marshmallow >= 2.0

Example
-------

.. code-block:: python

    from dynamorm import DynaModel

    # In this example we'll use Marshmallow, but you can also use Schematics too!
    # You can see that you have to import the schema library yourself, it is not abstracted at all
    from marshmallow import fields

    # Our objects are defined as DynaModel classes
    class Book(DynaModel):
        # Define our DynamoDB properties
        class Table:
            name = 'prod-books'
            hash_key = 'isbn'
            read = 25
            write = 5

        # Define our data schema, each property here will become a property on instances of the Book class
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

    # Work with the classes as objects.  You can pass attributes from the schema to the constructor
    foo = Book(isbn="12345678910", title="Foo", author="Mr. Bar",
               publisher="Publishorama")
    foo.save()

    # Or assign attributes
    foo = Book()
    foo.isbn = "12345678910"
    foo.title = "Foo"
    foo.author = "Mr. Bar"
    foo.publisher = "Publishorama"

    # In all cases they go through Schema validation, calls to .put or .save can result in ValidationError
    foo.save()

    # You can then fetch, query and scan your tables.
    # Get on the hash key, and/or range key
    book = Book.get(isbn="12345678910")

    # Update items, with conditions
    # Here our condition ensures we don't have a race condition where someone else updates the title first
    book.update(title='Corrected Foo', conditions=(title=book.title,))

    # Query based on the keys
    Book.query(isbn__begins_with="12345")

    # Scan based on attributes
    Book.scan(author="Mr. Bar")
    Book.scan(author__ne="Mr. Bar")


Documentation
=============

Full documentation can be found online at:

https://nerdwalletoss.github.io/dynamorm/


TODO
====

These are broken down by milestone release.

0.2.0
-----
* Partial updates on ``save()``

0.3.0
-----
* Indexes -- Currently there is no support for indexes.

1.0.0
-----
* Schema Migrations
