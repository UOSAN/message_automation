# this exists because I found stdout to be inconsistently recorded

logfile = '/home/LogFiles/progress.log'

printLog = True


def print_progress(*args, **kwargs):
    print(*args, **kwargs)

    if printLog:
        with open(logfile, 'a') as f:
            print(*args, **dict(kwargs, file=f))
