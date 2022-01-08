#!/usr/bin/env python


__author__ = "stackoverflow community"
__docformat__ = 'restructuredtext en'
"""
Takes english numeric words and converts them to integers.
Returns False if the word isn't a number.

implementation courtesy of the stackoverflow community:
http://stackoverflow.com/questions/493174/is-there-a-way-to-convert-number-words-to-integers-python
"""

import re

numwords = {}


def text2int(textnum):
    if not numwords:

        units = ["zero", "one", "two", "three", "four", "five", "six",
                "seven", "eight", "nine", "ten", "eleven", "twelve",
                "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
                "eighteen", "nineteen"]

        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty",
                "seventy", "eighty", "ninety"]

        scales = ["hundred", "thousand", "million", "billion", "trillion",
                'quadrillion', 'quintillion', 'sexillion', 'septillion',
                'octillion', 'nonillion', 'decillion']

        numwords["and"] = (1, 0)
        for idx, word in enumerate(units):
            numwords[word] = (1, idx)
        for idx, word in enumerate(tens):
            numwords[word] = (1, idx * 10)
        for idx, word in enumerate(scales):
            numwords[word] = (10 ** (idx * 3 or 2), 0)

    ordinal_words = {'first':1, 'second':2, 'third':3, 'fifth':5,
            'eighth':8, 'ninth':9, 'twelfth':12}
    ordinal_endings = [('ieth', 'y'), ('th', '')]
    current = result = 0
    tokens = re.split(r"[\s-]+", textnum)
    for word in tokens:
        if word in ordinal_words:
            scale, increment = (1, ordinal_words[word])
        else:
            for ending, replacement in ordinal_endings:
                if word.endswith(ending):
                    word = f"{word[:-len(ending)]}{replacement}"

            if word not in numwords:
                # raise Exception("Illegal word: " + word)
                return False

            scale, increment = numwords[word]

        if scale > 1:
            current = max(1, current)

        current = current * scale + increment
        if scale > 100:
            result += current
            current = 0

    return result + current
