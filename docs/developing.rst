Developing
==========

To create a virtualenv and activate it.

.. code-block:: bash

    virtualenv ~/.virtualenvs/dynamorm
    source ~/.virtualenvs/dynamorm/bin/activate


Running the tests
-----------------

From the activated virtualenv:

.. code-block:: bash

    ./test.sh

The tests will pull down the latest copy of DynamoDB Local from S3 and place it in ``build/dynamo-local``.  A copy will be started on a random high port, running with ``-inMemory``, at the start of the test run and shutdown after the run.

By default the tests will run against both marshmallow and schematics.  You can manually set the ``SERIALIZATION_PKG`` environment variable to a desired package, and optional version, if you want to run against just one of them.

See the source for ``test.sh`` for full details.
