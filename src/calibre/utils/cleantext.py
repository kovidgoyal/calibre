from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import re

def clean_ascii_char(txt, charlist = None):
    #remove ASCII invalid chars : 0 to 8 and 11-14 to 24-26-27 by default
    chars = list(range(8)) + [0x0B, 0x0E, 0x0F] + list(range(0x10, 0x19)) \
        + [0x1A, 0x1B]
    if charlist is not None:
        chars = charlist
    illegal_chars = re.compile(u'|'.join(map(unichr, chars)))
    return illegal_chars.sub('', txt)