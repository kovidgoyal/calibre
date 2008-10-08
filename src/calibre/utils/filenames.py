# -*- coding: utf-8 -*-
'''
Make strings safe for use as ASCII filenames, while trying to preserve as much 
meaning as possible.
'''

import re, string

MAP = {
        u"‘" : "'",
        u"’" : "'",
        u"«" : '"',
        u"»" : '"',
        u"…" : "...",
        u"№" : "#",
        u"Щ" : "Shh",
        u"Ё" : "Jo",
        u"Ж" : "Zh",
        u"Ц" : "C",
        u"Ч" : "Ch",
        u"Ш" : "Sh",
        u"Ы" : "Y",
        u"Ю" : "Ju",
        u"Я" : "Ja",
        u"Б" : "B",
        u"Г" : "G",
        u"Д" : "D",
        u"И" : "I",
        u"Й" : "J",
        u"К" : "K",
        u"Л" : "L",
        u"П" : "P",
        u"Ф" : "F",
        u"Э" : "E",
        u"Ъ" : "`",
        u"Ь" : "'",
        u"щ" : "shh",
        u"ё" : "jo",
        u"ж" : "zh",
        u"ц" : "c",
        u"ч" : "ch",
        u"ш" : "sh",
        u"ы" : "y",
        u"ю" : "ju",
        u"я" : "ja",
        u"б" : "b",
        u"в" : "v",
        u"г" : "g",
        u"д" : "d",
        u"з" : "z",
        u"и" : "i",
        u"й" : "j",
        u"к" : "k",
        u"л" : "l",
        u"м" : "m",
        u"н" : "n",
        u"о" : "o",
        u"п" : "p",
        u"т" : "t",
        u"ф" : "f",
        u"э" : "e",
        u"ъ" : "`",
        u"ь" : "'",
        u"А" : "A",
        u"В" : "V",
        u"Е" : "Je",
        u"З" : "Z",
        u"М" : "M",
        u"Н" : "N",
        u"О" : "O",
        u"Р" : "R",
        u"С" : "S",
        u"Т" : "T",
        u"У" : "U",
        u"Х" : "Kh",
        u"Є" : "Je",
        u"Ї" : "Ji",
        u"а" : "a",
        u"е" : "je",
        u"р" : "r",
        u"с" : "s",
        u"у" : "u",
        u"х" : "kh",
        u"є" : "je",
}  #: Translation table

for c in string.whitespace:
    MAP[c] = ' '
PAT = re.compile('['+u''.join(MAP.keys())+']')

def ascii_filename(orig):
    orig =  PAT.sub(lambda m:MAP[m.group()], orig)
    buf = []
    for i in range(len(orig)):
        val = ord(orig[i])
        buf.append('_' if val < 33 or val > 126 else orig[i])
    return (''.join(buf)).encode('ascii')
