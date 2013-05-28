__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import re, htmlentitydefs
from future_builtins import map

_ascii_pat = None

def clean_ascii_chars(txt, charlist=None):
    r'''
    Remove ASCII control chars.
    This is all control chars except \t, \n and \r
    '''
    if not txt:
        return ''
    global _ascii_pat
    if _ascii_pat is None:
        chars = set(xrange(32))
        chars.add(127)
        for x in (9, 10, 13):
            chars.remove(x)
        _ascii_pat = re.compile(u'|'.join(map(unichr, chars)))

    if charlist is None:
        pat = _ascii_pat
    else:
        pat = re.compile(u'|'.join(map(unichr, charlist)))
    return pat.sub('', txt)

def allowed(x):
    x = ord(x)
    return (x != 127 and (31 < x < 0xd7ff or x in (9, 10, 13))) or (0xe000 < x < 0xfffd) or (0x10000 < x < 0x10ffff)

def clean_xml_chars(unicode_string):
    return u''.join(filter(allowed, unicode_string))


# Fredrik Lundh: http://effbot.org/zone/re-sub.htm#unescape-html
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text, rm=False, rchar=u''):
    def fixup(m, rm=rm, rchar=rchar):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        if rm:
            return rchar  # replace by char
        return text  # leave as is
    return re.sub("&#?\w+;", fixup, text)

