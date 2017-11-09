class DynamORMSchema(object):
    """This is the base class for the inner ``Schema`` class on Tables"""

    @staticmethod
    def field_to_dynamo_type(field):
        """Returns the dynamo type character given the field."""
        raise NotImplementedError('Child class must implement field_to_dynamo_type')

    @classmethod
    def dynamorm_fields(cls):
        """Returns a dictionary of key value pairs where keys are attributes and values are type classes"""
        raise NotImplementedError('{0} class must implement dyanmorm_fields'.format(cls.__name__))

    @classmethod
    def dynamorm_validate(cls, obj, partial=False, native=False):
        """Given a dictionary representing a blob from dynamo, this method will validate the blob given the desired
        validation library.

        If partial is true then the underlying validation library should allow for partial objects.

        If native is true then the underlying validation library should return a dictionary of native python values
        (i.e. datetime.datetime), otherwise it should return a dictionary of primitive values (i.e. a string
        representation of a date time value).

        On validation failure, this should raise ``dynamorm.exc.ValidationError``.
        """
        raise NotImplementedError('{0} class must implement dyanmorm_validate'.format(cls.__name__))

    @classmethod
    def key_field(cls, required=False):
        """Returns a schema field for storing primary keys"""
        raise NotImplementedError('{0} class must implement key_field'.format(cls.__name__))

    @classmethod
    def keys_field(cls, required=False):
        """Returns a schema field for storing a list of primary keys"""
        raise NotImplementedError('{0} class must implement keys_field'.format(cls.__name__))
