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
def xml_to_unicode(raw, verbose=False):
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
    match = re.compile(r'<[^<>]+encoding=[\'"](.*?)[\'"][^<>]*>', re.IGNORECASE).search(raw)
    if match is None:
        match = re.compile(r'<meta.*?content=[\'"].*?charset=([^\s\'"]+).*?[\'"]', re.IGNORECASE).search(raw)
    if match is not None:
        encoding = match.group(1) 
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
    return raw.decode(encoding, 'ignore'), encoding 
