#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, codecs

ENCODING_PATS = [
                # XML declaration
                 re.compile(r'<\?[^<>]+encoding\s*=\s*[\'"](.*?)[\'"][^<>]*>',
                            re.IGNORECASE),
                 # HTML 4 Pragma directive
                 re.compile(r'''<meta\s+?[^<>]*?content\s*=\s*['"][^'"]*?charset=([-_a-z0-9]+)[^'"]*?['"][^<>]*>''',
                            re.IGNORECASE),
                 # HTML 5 charset
                 re.compile(r'''<meta\s+charset=['"]([-_a-z0-9]+)['"][^<>]*>''',
                     re.IGNORECASE),
                 ]
ENTITY_PATTERN = re.compile(r'&(\S+?);')

def strip_encoding_declarations(raw):
    limit = 50*1024
    for pat in ENCODING_PATS:
        prefix = raw[:limit]
        suffix = raw[limit:]
        prefix = pat.sub('', prefix)
        raw = prefix + suffix
    return raw

def substitute_entites(raw):
    from calibre import xml_entity_to_unicode
    return ENTITY_PATTERN.sub(xml_entity_to_unicode, raw)

_CHARSET_ALIASES = { "macintosh" : "mac-roman",
                        "x-sjis" : "shift-jis" }

def detect(*args, **kwargs):
    from chardet import detect
    return detect(*args, **kwargs)

def force_encoding(raw, verbose, assume_utf8=False):
    from calibre.constants import preferred_encoding

    try:
        chardet = detect(raw[:1024*50])
    except:
        chardet = {'encoding':preferred_encoding, 'confidence':0}
    encoding = chardet['encoding']
    if chardet['confidence'] < 1 and assume_utf8:
        encoding = 'utf-8'
    if chardet['confidence'] < 1 and verbose:
        print('WARNING: Encoding detection confidence %d%%'%(
            chardet['confidence']*100))
    if not encoding:
        encoding = preferred_encoding
    encoding = encoding.lower()
    if _CHARSET_ALIASES.has_key(encoding):
        encoding = _CHARSET_ALIASES[encoding]
    if encoding == 'ascii':
        encoding = 'utf-8'
    return encoding

def detect_xml_encoding(raw, verbose=False, assume_utf8=False):
    if not raw or isinstance(raw, unicode):
        return raw, None
    for x in ('utf8', 'utf-16-le', 'utf-16-be'):
        bom = getattr(codecs, 'BOM_'+x.upper().replace('-16', '16').replace(
            '-', '_'))
        if raw.startswith(bom):
            return raw[len(bom):], x
    encoding = None
    for pat in ENCODING_PATS:
        match = pat.search(raw)
        if match:
            encoding = match.group(1)
            break
    if encoding is None:
        encoding = force_encoding(raw, verbose, assume_utf8=assume_utf8)
    if encoding.lower().strip() == 'macintosh':
        encoding = 'mac-roman'
    if encoding.lower().replace('_', '-').strip() in (
            'gb2312', 'chinese', 'csiso58gb231280', 'euc-cn', 'euccn',
            'eucgb2312-cn', 'gb2312-1980', 'gb2312-80', 'iso-ir-58'):
        # Microsoft Word exports to HTML with encoding incorrectly set to
        # gb2312 instead of gbk. gbk is a superset of gb2312, anyway.
        encoding = 'gbk'
    try:
        codecs.lookup(encoding)
    except LookupError:
        encoding = 'utf-8'

    return raw, encoding

def xml_to_unicode(raw, verbose=False, strip_encoding_pats=False,
                   resolve_entities=False, assume_utf8=False):
    '''
    Force conversion of byte string to unicode. Tries to look for XML/HTML
    encoding declaration first, if not found uses the chardet library and
    prints a warning if detection confidence is < 100%
    @return: (unicode, encoding used)
    '''
    if not raw:
        return '', None
    raw, encoding = detect_xml_encoding(raw, verbose=verbose,
            assume_utf8=assume_utf8)
    if not isinstance(raw, unicode):
        raw = raw.decode(encoding, 'replace')

    if strip_encoding_pats:
        raw = strip_encoding_declarations(raw)
    if resolve_entities:
        raw = substitute_entites(raw)

    return raw, encoding
