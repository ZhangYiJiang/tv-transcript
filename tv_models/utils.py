import re


def remove_special(s):
    """Remove all special characters from """
    return re.sub(r"[?|:*/\\<>\"]+", '', s)


def flatten(lst):
    return [a for b in lst for a in b]


def word_count(s):
    return s.count(' ') + s.count('\n') + 1


def identity(*args):
    if len(args) == 1:
        return args[0]
    return args
