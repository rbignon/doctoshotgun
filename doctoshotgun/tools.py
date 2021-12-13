import datetime
from termcolor import colored

def log(text, *args, **kwargs):

    args = (colored(arg, 'yellow') for arg in args)
    if 'color' in kwargs:
        text = colored(text, kwargs.pop('color'))
    text = text % tuple(args)
    print(text, **kwargs)


def log_ts(text=None, *args, **kwargs):
    ''' Log with timestamp'''
    now = datetime.datetime.now()
    print("[%s]" % now.isoformat(" ", "seconds"))
    if text:
        log(text, *args, **kwargs)
