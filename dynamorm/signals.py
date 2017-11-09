from blinker import signal


model_prepared = signal('dynamorm.model_prepared', doc='''
This signal is sent when a model has been prepared by the metaclass and is ready for use.
''')

pre_init = signal('dynamorm.pre_init', doc='''
''')
post_init = signal('dynamorm.post_init', doc='''
''')

pre_save = signal('dynamorm.pre_save')
post_save = signal('dynamorm.post_save')

pre_update = signal('dynamorm.pre_update')
post_update = signal('dynamorm.post_update')

pre_delete = signal('dynamorm.pre_delete')
post_delete = signal('dynamorm.post_delete')
