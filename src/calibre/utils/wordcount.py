#!/usr/bin/env python


"""
Get word, character, and Asian character counts

1. Get a word count as a dictionary:
    wc = get_wordcount(text)
    words = wc['words'] # etc.

2. Get a word count as an object
    wc = get_wordcount_obj(text)
    words = wc.words # etc.

properties counted:
    * characters
    * chars_no_spaces
    * asian_chars
    * non_asian_words
    * words

Sourced from:
http://ginstrom.com/scribbles/2008/05/17/counting-words-etc-in-an-html-file-with-python/
http://ginstrom.com/scribbles/2007/10/06/counting-words-characters-and-asian-characters-with-python/
"""
__version__ = 0.1
__author__ = "Ryan Ginstrom"

IDEOGRAPHIC_SPACE = 0x3000


def is_asian(char):
    """Is the character Asian?"""

    # 0x3000 is ideographic space (i.e. double-byte space)
    # Anything over is an Asian character
    return ord(char) > IDEOGRAPHIC_SPACE


def filter_jchars(c):
    """Filters Asian characters to spaces"""
    if is_asian(c):
        return ' '
    return c


def nonj_len(word):
    """Returns number of non-Asian words in {word}
    - 日本語AアジアンB -> 2
    - hello -> 1
    @param word: A word, possibly containing Asian characters
    """
    # Here are the steps:
    # 本spam日eggs
    # -> [' ', 's', 'p', 'a', 'm', ' ', 'e', 'g', 'g', 's']
    # -> ' spam eggs'
    # -> ['spam', 'eggs']
    # The length of which is 2!
    chars = [filter_jchars(c) for c in word]
    return len(''.join(chars).split())


def get_wordcount(text):
    """Get the word/character count for text

    @param text: The text of the segment
    """

    characters = len(text)
    chars_no_spaces = sum(not x.isspace() for x in text)
    asian_chars =  sum(is_asian(x) for x in text)
    non_asian_words = nonj_len(text)
    words = non_asian_words + asian_chars

    return dict(characters=characters,
                chars_no_spaces=chars_no_spaces,
                asian_chars=asian_chars,
                non_asian_words=non_asian_words,
                words=words)


def dict2obj(dictionary):
    """Transform a dictionary into an object"""
    class Obj:

        def __init__(self, dictionary):
            self.__dict__.update(dictionary)
    return Obj(dictionary)


def get_wordcount_obj(text):
    """Get the wordcount as an object rather than a dictionary"""
    return dict2obj(get_wordcount(text))
