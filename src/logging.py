DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        '': {
            'level': 'INFO',
            'handlers': ['rotating_file'],
        },
        'console': {
            'level': 'INFO',
            'handlers': ['console']
        },
        'src.apptoto': {
            'level': 'INFO',
            'handlers': ['console']
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
        'rotating_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'info',
            'filename': '/home/LogFiles/message_app.log',
            'mode': 'a',
            'maxBytes': 1000,
            'backupCount': 1
        },
    },
    'formatters': {
        'info': {
            'format': '%(asctime)s  %(message)s'
        },
    },
}
