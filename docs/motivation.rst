Motivation for creating DynamORM
================================

*This was written Q2 2016*

* Both `PynamoDB`_ and `dynamodb-mapper`_ provide their own implementation of a "schema", neither of which have strong
  validation.  Also, getting the schema implementation right is the much harder problem to solve than the actual
  interaction with the DynamoDB service.  After using `Marshmallow`_ with other NoSQL systems it was clear that the
  library providing the abstraction of the data service should simply defer to a far more mature schema implementation
  that is specifically built to be agnostic.

* `dynamodb-mapper`_ uses the v1 of DynamoDB API via the ``boto`` library.  `PynamoDB`_ uses v2 via ``botocore``
  directly.  The preference was to maintain parity with the officially supported library and implement functionality
  based on ``boto3``, and v3 of the API.  The implementation is done in such a way that when v4 rolls around the
  abstraction can be added without the end user implementation needing to be changed.

* There was a desire for an explicit declaration where the table properties and the schema properties were defined on
  their own, while still making sense semantically. For example, instead of annotating a schema field that it is the
  hash key, the name of the hash key should be defined on the table and the properties of the field should be defined on
  the schema.  When the table needs information about the hash key it can simply reference it from the schema by name.

.. _PynamoDB: https://github.com/jlafon/PynamoDB
.. _dynamodb-mapper: https://bitbucket.org/Ludia/dynamodb-mapper/overview
.. _Marshmallow: https://github.com/marshmallow-code/marshmallow
