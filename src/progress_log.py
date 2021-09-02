logfile = '/home/LogFiles/progress.log'

def print_progress(*args, **kwargs):
    print(*args, **kwargs)
    with open(logfile, 'a') as f:
        print(*args, **dict(kwargs, file = f))

