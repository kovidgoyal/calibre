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

import re

def detect(aBuf):
    import calibre.ebooks.chardet.universaldetector as universaldetector
    u = universaldetector.UniversalDetector()
    u.reset()
    u.feed(aBuf)
    u.close()
    return u.result

# Added by Kovid
ENCODING_PATS = [
                 re.compile(r'<\?[^<>]+encoding=[\'"](.*?)[\'"][^<>]*>', re.IGNORECASE),
                 re.compile(r'<meta.*?content=[\'"].*?charset=([^\s\'"]+).*?[\'"].*?>', re.IGNORECASE)
                 ]
ENTITY_PATTERN = re.compile(r'&(\S+?);')

def xml_to_unicode(raw, verbose=False, strip_encoding_pats=False, resolve_entities=False):
    '''
    Force conversion of byte string to unicode. Tries to look for XML/HTML 
    encoding declaration first, if not found uses the chardet library and
    prints a warning if detection confidence is < 100%
    @return: (unicode, encoding used) 
    '''
    encoding = None
    if not raw:
        return u'', encoding    
    if isinstance(raw, unicode):
        return raw, encoding
    for pat in ENCODING_PATS:
        match = pat.search(raw)
        if match:
            encoding = match.group(1)
            break
    if strip_encoding_pats:
        for pat in ENCODING_PATS:
            raw = pat.sub('', raw)
    if encoding is None:
        try:
            chardet = detect(raw)
        except:
            chardet = {'encoding':'utf-8', 'confidence':0}
        encoding = chardet['encoding']
        if chardet['confidence'] < 1 and verbose:
            print 'WARNING: Encoding detection confidence %d%%'%(chardet['confidence']*100)
    CHARSET_ALIASES = { "macintosh" : "mac-roman",
                        "x-sjis" : "shift-jis" }
    if not encoding:
        from calibre import preferred_encoding
        encoding = preferred_encoding
    if encoding:
        encoding = encoding.lower()
    if CHARSET_ALIASES.has_key(encoding):
        encoding = CHARSET_ALIASES[encoding]
    if encoding == 'ascii':
        encoding = 'utf-8'
    
    try:
        raw = raw.decode(encoding, 'replace')
    except LookupError:
        raw = raw.decode('utf-8', 'replace')
    if resolve_entities:
        from calibre import entity_to_unicode
        from functools import partial
        f = partial(entity_to_unicode, exceptions=['amp', 'apos', 'quot', 'lt', 'gt'])
        raw = ENTITY_PATTERN.sub(f, raw)
    
    return raw, encoding 
