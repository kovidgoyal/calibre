#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from calibre.ebooks.chardet import xml_to_unicode
from lxml import etree

PARSER = etree.XMLParser(recover=True, no_network=True)

def parse_opf(stream_or_path):
    stream = stream_or_path
    if not hasattr(stream, 'read'):
        stream = open(stream, 'rb')
    raw = stream.read()
    if not raw:
        raise ValueError('Empty file: '+getattr(stream, 'name', 'stream'))
    raw, encoding = xml_to_unicode(raw, strip_encoding_pats=True, resolve_entities=True, assume_utf8=True)
    raw = raw[raw.find('<'):]
    root = etree.fromstring(raw, PARSER)
    if root is None:
        raise ValueError('Not an OPF file')
    return root


