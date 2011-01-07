######################## BEGIN LICENSE BLOCK ########################
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA
######################### END LICENSE BLOCK #########################


__version__ = "1.0"

import re, codecs

def detect(aBuf):
    import calibre.ebooks.chardet.universaldetector as universaldetector
    u = universaldetector.UniversalDetector()
    u.reset()
    u.feed(aBuf)
    u.close()
    return u.result

# Added by Kovid
ENCODING_PATS = [
                 re.compile(r'<\?[^<>]+encoding\s*=\s*[\'"](.*?)[\'"][^<>]*>',
                            re.IGNORECASE),
                 re.compile(r'''<meta\s+?[^<>]*?content\s*=\s*['"][^'"]*?charset=([-a-z0-9]+)[^'"]*?['"][^<>]*>''',
                            re.IGNORECASE)
                 ]
ENTITY_PATTERN = re.compile(r'&(\S+?);')

def strip_encoding_declarations(raw):
    for pat in ENCODING_PATS:
        raw = pat.sub('', raw)
    return raw

def substitute_entites(raw):
    from calibre import xml_entity_to_unicode
    return ENTITY_PATTERN.sub(xml_entity_to_unicode, raw)

_CHARSET_ALIASES = { "macintosh" : "mac-roman",
                        "x-sjis" : "shift-jis" }


def force_encoding(raw, verbose, assume_utf8=False):
    from calibre.constants import preferred_encoding
    try:
        chardet = detect(raw)
    except:
        chardet = {'encoding':preferred_encoding, 'confidence':0}
    encoding = chardet['encoding']
    if chardet['confidence'] < 1 and assume_utf8:
        encoding = 'utf-8'
    if chardet['confidence'] < 1 and verbose:
        print 'WARNING: Encoding detection confidence %d%%'%(chardet['confidence']*100)
    if not encoding:
        encoding = preferred_encoding
    encoding = encoding.lower()
    if _CHARSET_ALIASES.has_key(encoding):
        encoding = _CHARSET_ALIASES[encoding]
    if encoding == 'ascii':
        encoding = 'utf-8'
    return encoding


def xml_to_unicode(raw, verbose=False, strip_encoding_pats=False,
                   resolve_entities=False, assume_utf8=False):
    '''
    Force conversion of byte string to unicode. Tries to look for XML/HTML
    encoding declaration first, if not found uses the chardet library and
    prints a warning if detection confidence is < 100%
    @return: (unicode, encoding used)
    '''
    encoding = None
    if not raw:
        return u'', encoding
    if not isinstance(raw, unicode):
        if raw.startswith(codecs.BOM_UTF8):
            raw, encoding = raw.decode('utf-8')[1:], 'utf-8'
        elif raw.startswith(codecs.BOM_UTF16_LE):
            raw, encoding = raw.decode('utf-16-le')[1:], 'utf-16-le'
        elif raw.startswith(codecs.BOM_UTF16_BE):
            raw, encoding = raw.decode('utf-16-be')[1:], 'utf-16-be'
    if not isinstance(raw, unicode):
        for pat in ENCODING_PATS:
            match = pat.search(raw)
            if match:
                encoding = match.group(1)
                break
        if encoding is None:
            encoding = force_encoding(raw, verbose, assume_utf8=assume_utf8)
        try:
            if encoding.lower().strip() == 'macintosh':
                encoding = 'mac-roman'
            raw = raw.decode(encoding, 'replace')
        except LookupError:
            encoding = 'utf-8'
            raw = raw.decode(encoding, 'replace')

    if strip_encoding_pats:
        raw = strip_encoding_declarations(raw)
    if resolve_entities:
        raw = substitute_entites(raw)

    return raw, encoding
