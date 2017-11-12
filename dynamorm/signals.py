"""Signals provide a way for applications to loosely couple themselves and respond to different life cycle events.

The `blinker`_ library provides the low-level signal implementation.

To use the signals you ``connect`` a receiver function to the signals you're interested in:

.. code-block:: python

    from dynamorm.signals import post_save

    def post_save_receiver(sender, instance, partial, put_kwargs):
        log.info("Received post_save signal from model %s for instance %s", sender, instance)

    post_save.connect(post_save_receiver)

See the `blinker`_ documentation for more details.

.. _blinker: https://pythonhosted.org/blinker/
"""

from blinker import signal

model_prepared = signal(
    'dynamorm.model_prepared',
    doc='''Sent whenever a model class has been prepared by the metaclass.

    :param: sender: The model class that is now prepared for use.
    '''
)

pre_init = signal(
    'dynamorm.pre_init',
    doc='''Sent during model instantiation, before processing the raw data.

    :param: sender: The model class.
    :param: instance: The model instance.
    :param: bool partial: True if this is a partial instantiation, not all data may be present.
    :param: dict raw: The raw data to be processed by the model schema.
    '''
)

post_init = signal(
    'dynamorm.post_init',
    doc='''Sent once model instantiation is complete and all raw data has been processed.

    :param: sender: The model class.
    :param: instance: The model instance.
    :param: bool partial: True if this is a partial instantiation, not all data may be present.
    :param: dict raw: The raw data to be processed by the model schema.
    '''
)

pre_save = signal(
    'dynamorm.pre_save',
    doc='''Sent before saving (via put) model instances.

    :param: sender: The model class.
    :param: instance: The model instance.
    :param: dict put_kwargs: A dict of the kwargs being sent to the table put method.
    '''
)

post_save = signal(
    'dynamorm.post_save',
    doc='''Sent after saving (via put) model instances.

    :param: sender: The model class.
    :param: instance: The model instance.
    :param: dict put_kwargs: A dict of the kwargs being sent to the table put method.
    '''
)

pre_update = signal(
    'dynamorm.pre_update',
    doc='''Sent before saving (via update) model instances.

    :param: sender: The model class.
    :param: instance: The model instance.
    :param: dict conditions: The conditions for the update to succeed.
    :param: dict update_item_kwargs: A dict of the kwargs being sent to the table put method.
    :param: dict updates: The fields to update.
    '''
)

post_update = signal(
    'dynamorm.post_update',
    doc='''Sent after saving (via update) model instances.

    :param: sender: The model class.
    :param: instance: The model instance.
    :param: dict conditions: The conditions for the update to succeed.
    :param: dict update_item_kwargs: A dict of the kwargs being sent to the table put method.
    :param: dict updates: The fields to update.
    '''
)

pre_delete = signal(
    'dynamorm.pre_delete',
    doc='''Sent before deleting model instances.

    :param: sender: The model class.
    :param: instance: The model instance.
    '''
)

post_delete = signal(
    'dynamorm.post_delete',
    doc='''Sent after deleting model instances.

    :param: sender: The model class.
    :param: instance: The deleted model instance.
    '''
)
