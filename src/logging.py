DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
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
        'src.event_generator': {
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
            'formatter': 'timestamped',
            'filename': '/home/LogFiles/message_app.log',
            'mode': 'a',
            'maxBytes': 100000,
            'backupCount': 1
        },
    },
    'formatters': {
        'timestamped': {
            'format': '%(asctime)s  %(message)s'
        },
    },
}
