# -*- coding: utf-8 -*-
'''
Make strings safe for use as ASCII filenames, while trying to preserve as much 
meaning as possible.
'''

import re, string
    
    
MAP = {
        u"‘" : u"'",
        u"’" : u"'",
        u"«" : u'"',
        u"»" : u'"',
        u"…" : u"...",
        u"№" : u"#",
        u"Щ" : u"Sch",
        u"Щ" : u"SCH",
        u"Ё" : u"Yo",
        u"Ё" : u"YO",
        u"Ж" : u"Zh",
        u"Ж" : u"ZH",
        u"Ц" : u"Ts",
        u"Ц" : u"TS",
        u"Ч" : u"Ch",
        u"Ч" : u"CH",
        u"Ш" : u"Sh",
        u"Ш" : u"SH",
        u"Ы" : u"Yi",
        u"Ы" : u"YI",
        u"Ю" : u"Yu",
        u"Ю" : u"YU",
        u"Я" : u"Ya",
        u"Я" : u"YA",
        u"Б" : u"B",
        u"Г" : u"G",
        u"Д" : u"D",
        u"И" : u"I",
        u"Й" : u"J",
        u"К" : u"K",
        u"Л" : u"L",
        u"П" : u"P",
        u"Ф" : u"F",
        u"Э" : u"E",
        u"Ъ" : u"`",
        u"Ь" : u"'",
        u"щ" : u"sch",
        u"ё" : u"yo",
        u"ж" : u"zh",
        u"ц" : u"ts",
        u"ч" : u"ch",
        u"ш" : u"sh",
        u"ы" : u"yi",
        u"ю" : u"yu",
        u"я" : u"ya",
        u"б" : u"b",
        u"в" : u"v",
        u"г" : u"g",
        u"д" : u"d",
        u"з" : u"z",
        u"и" : u"i",
        u"й" : u"j",
        u"к" : u"k",
        u"л" : u"l",
        u"м" : u"m",
        u"н" : u"n",
        u"о" : u"o",
        u"п" : u"p",
        u"т" : u"t",
        u"ф" : u"f",
        u"э" : u"e",
        u"ъ" : u"`",
        u"ь" : u"'",
        }  #: Translation table

def ascii_filename(orig):
    orig =  PAT.sub(lambda m:MAP[m.group()], orig)
    buf = []
    for i in range(len(orig)):
        val = ord(orig[i])
        buf.append('_' if val < 33 or val > 126 else orig[i])
    return (''.join(buf)).encode('ascii')

