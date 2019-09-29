Developing
==========

DynamORM is designed to work with Python2.7, Python3.5, Python3.6, and Python3.7 as well as with both Marshmallow and Schematics for serialization.  When you open a Pull Request on GitHub tests will be against a full matrix of these options to guarantee compatibility.

Locally we use tox_ to provide a similar test matrix.  By default when you run ``tox`` the tests will run against ``python2`` and ``python3`` for both Marshmallow and Schematics.

The tests will pull down the latest copy of DynamoDB Local from S3 and place it in ``build/dynamo-local``.  A copy will be started on a random high port, running with ``-inMemory``, at the start of the test run and shutdown after the run.


Testing with tox_
-----------------

tox_ can be installed with ``pip``, or with your local package manager (i.e. on OSX ``brew install tox``).

Once installed simply run ``tox``::

    tox

This will create virtualenvs for the full matrix of ``python2`` and ``python3`` with both schematics and marshmallow.

.. _tox: https://tox.readthedocs.io/en/latest/


Formatting with black_
----------------------

DynamORM uses black_ for formatting so that we don't spend time worrying about formatting.

When you run ``tox`` it will check all files before running tests, and will fail if any of them are not formatted to black's standards.  To re-format those files you can run ``tox -e black -- .``

.. _black: https://github.com/psf/black
