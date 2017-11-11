from blinker import signal

# XXX TODO: finish docs, including parameters

model_prepared = signal(
    'dynamorm.model_prepared',
    doc='''This signal is sent when a model has been prepared by the metaclass and is ready for use.'''
)

pre_init = signal(
    'dynamorm.pre_init',
    doc='''This signal is sent right before an instance of a model is going to initialize.'''
)
post_init = signal(
    'dynamorm.post_init',
    doc='''This signal is sent right after an instance of a model has been initialized.'''
)

pre_save = signal('dynamorm.pre_save')
post_save = signal('dynamorm.post_save')

pre_update = signal('dynamorm.pre_update')
post_update = signal('dynamorm.post_update')

pre_delete = signal('dynamorm.pre_delete')
post_delete = signal('dynamorm.post_delete')
