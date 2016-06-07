Developing
==========

To create a virtualenv and pull in the required dependencies:

.. code-block:: bash
    
    virtualenv ~/.virtualenvs/dynamallow
    source ~/.virtualenvs/dynamallow/bin/activate
    pip install -e .


Running the tests
-----------------

From the activated virtualenv:

.. code-block:: bash

    python setup.py test

The tests will pull down the latest copy of DynamoDB Local from S3 and place it in ``build/dynamo-local``.  A copy will
be started on a random high port, running with ``-inMemory``, at the start of the test run and shutdown after the run.
