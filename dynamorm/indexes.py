

class Index(object):
    def __init__(self, model, index):
        self.model = model
        self.index = index

    def query(self, query_kwargs=None, **kwargs):
        """Execute a query on this index

        See DynaModel.query for documentation on how to pass query arguments.
        """
        try:
            query_kwargs['IndexName'] = self.index.name
        except TypeError:
            query_kwargs = {'IndexName': self.index.name}

        return self.model.query(query_kwargs=query_kwargs, partial=self.projection.partial, **kwargs)

    def scan(self, scan_kwargs=None, **kwargs):
        """Execute a scan on this index

        See DynaModel.scan for documentation on how to pass scan arguments.
        """
        try:
            scan_kwargs['IndexName'] = self.index.name
        except TypeError:
            scan_kwargs = {'IndexName': self.index.name}

        return self.model.scan(scan_kwargs=scan_kwargs, partial=self.projection.partial, **kwargs)


class LocalIndex(Index):
    """Represents a Local Secondary Index on your table"""
    pass


class GlobalIndex(Index):
    """Represents a Local Secondary Index on your table"""
    pass


class Projection(object):
    pass


class ProjectAll(Projection):
    """Project all attributes from the Table into the Index

    Documents loaded using this projection will be fully validated by the schema.
    """
    partial = False


class ProjectKeys(Projection):
    """Project the keys from the Table into the Index.

    Documents loaded using this projection will be partially validated by the schema.
    """
    partial = True


class ProjectInclude(Projection):
    """Project the specified attributes into the Index.

    Documents loaded using this projection will be partially validated by the schema.

    .. code-block:: python

        class ByAuthor(GlobalIndex):
            ...
            projection = ProjectInclude('some_attr', 'other_attr')
    """
    partial = True

    def __init__(self, *include):
        self.include = include
