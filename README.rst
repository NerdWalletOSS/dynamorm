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

    import datetime

    from dynamorm import DynaModel, GlobalIndex, ProjectAll

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

        class ByAuthor(GlobalIndex):
            name = 'by-author'
            hash_key = 'author'
            read = 25
            write = 5
            projection = ProjectAll()

        # Define our data schema, each property here will become a property on instances of the Book class
        class Schema:
            isbn = fields.String(validate=validate_isbn)
            title = fields.String()
            author = fields.String()
            publisher = fields.String()

            # NOTE: Marshmallow uses the `missing` keyword during deserialization, which occurs when we save
            # an object to Dynamo and the attr has no value, versus the `default` keyword, which is used when
            # we load a document from Dynamo and the value doesn't exist or is null.
            year = fields.Number(missing=lambda: datetime.datetime.utcnow().year)


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

    # Query based on indexes
    Book.ByAuthor.query(author="Mr. Bar")


Documentation
=============

Full documentation is built from the sources each build and can be found online at:

https://nerdwalletoss.github.io/dynamorm/


The ``tests/`` also contain the most complete documentation on how to actually use the library, so you are encouraged to
read through them to really familiarize yourself with some of the more advanced concepts and use cases.
