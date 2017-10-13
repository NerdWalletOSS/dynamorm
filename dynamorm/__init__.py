"""The base module namespace simply imports the most frequently used objects to simplify imports in clients:

.. code-block:: python

    from dynamorm import DynaModel

"""
from .model import DynaModel, GlobalIndex, LocalIndex, ProjectAll, ProjectKeys, ProjectInclude  # noqa
from .table import Q  # noqa
