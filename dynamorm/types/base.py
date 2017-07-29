class BaseModel(object):
    """``BaseModel`` is the base class for ``types.Model``. It must define ``dynamallow_validate`` which runs validation
    in your desired serialization library, ``dynamallow_fields`` which returns a dictionary of key value pairs
    where keys are attributes and values are the type of the attribute, and ``field_to_dynamo_type`` which returns
    the dynamo type character for the input type (we currently implement schematics_ and marshmallow_).

    .. _schematics: https://schematics.readthedocs.io/en/latest/
    .. _marshmallow: https://marshmallow.readthedocs.io/en/latest/
    """
    @staticmethod
    def field_to_dynamo_type(field):
        """ Returns the dynamo type character given the field. """
        raise NotImplementedError('Child class must implement field_to_dynamo_type')

    @classmethod
    def dynamallow_fields(cls):
        """ Returns a dictionary of key value pairs where keys are attributes and values are type classes """
        raise NotImplementedError('{0} class must implement dynamallow_fields'.format(cls.__name__))

    @classmethod
    def dynamallow_validate(cls, obj, partial=False, native=False):
        """
        Given a dictionary representing a blob from dynamo, this method will validate the blob
        given the desired validation library.

        If partial is true then the underlying validation library should allow for partial objects.

        If native is true then the underlying validation library should return a dictionary of native python values
        (i.e. datetime.datetime), otherwise it should return a dictionary of primitive values (i.e. a string
        representation of a date time value).

        On validation failure, this should raise ``dynamallow.exc.ValidationError``.
        """
        raise NotImplementedError('{0} class must implement dynamallow_validate'.format(cls.__name__))
