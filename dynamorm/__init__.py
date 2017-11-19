"""The base module namespace simply imports the most frequently used objects to simplify imports in clients:

.. code-block:: python

    from dynamorm import DynaModel

"""
from .model import DynaModel  # noqa
from .indexes import GlobalIndex, LocalIndex, ProjectAll, ProjectKeys, ProjectInclude  # noqa
from .relationships import ManyToOne, OneToMany, OneToOne  # noqa
from .table import Q  # noqa
