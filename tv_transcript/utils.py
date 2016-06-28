import re


def remove_special(s):
    """Remove all special characters from the given string"""
    return re.sub(r"[?|:*/\\<>\"]+", '', s)


def flatten(lst):
    """Shallow flatten *lst*"""
    return [a for b in lst for a in b]


def word_count(s):
    """Stupidly simple function that counts the number of words in a string."""
    return s.count(' ') + s.count('\n') + 1
