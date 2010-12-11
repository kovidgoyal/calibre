from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import re

_ascii_pat = None

def clean_ascii_chars(txt, charlist=None):
    'remove ASCII invalid chars : 0 to 8 and 11-14 to 24-26-27 by default'
    global _ascii_pat
    if _ascii_pat is None:
        chars = list(range(8)) + [0x0B, 0x0E, 0x0F] + list(range(0x10, 0x19)) \
            + [0x1A, 0x1B]
        _ascii_pat = re.compile(u'|'.join(map(unichr, chars)))

    if charlist is None:
        pat = _ascii_pat
    else:
        pat = re.compile(u'|'.join(map(unichr, charlist)))
    return pat.sub('', txt)

