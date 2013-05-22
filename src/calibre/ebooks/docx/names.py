#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml.etree import XPath as X

from calibre.utils.filenames import ascii_text

DOCUMENT  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument'
DOCPROPS  = 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties'
APPPROPS  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties'
STYLES    = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles'
NUMBERING = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering'
FONTS     = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable'
IMAGES    = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'

namespaces = {
    'mo': 'http://schemas.microsoft.com/office/mac/office/2008/main',
    'o': 'urn:schemas-microsoft-com:office:office',
    've': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    # Text Content
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w10': 'urn:schemas-microsoft-com:office:word',
    'wne': 'http://schemas.microsoft.com/office/word/2006/wordml',
    'xml': 'http://www.w3.org/XML/1998/namespace',
    # Drawing
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'mv': 'urn:schemas-microsoft-com:mac:vml',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'v': 'urn:schemas-microsoft-com:vml',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    # Properties (core and extended)
    'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'ep': 'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    # Content Types
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
    # Package Relationships
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'pr': 'http://schemas.openxmlformats.org/package/2006/relationships',
    # Dublin Core document properties
    'dcmitype': 'http://purl.org/dc/dcmitype/',
    'dcterms': 'http://purl.org/dc/terms/'
}

xpath_cache = {}

def XPath(expr):
    ans = xpath_cache.get(expr, None)
    if ans is None:
        xpath_cache[expr] = ans = X(expr, namespaces=namespaces)
    return ans

def is_tag(x, q):
    tag = getattr(x, 'tag', x)
    ns, name = q.partition(':')[0::2]
    return '{%s}%s' % (namespaces.get(ns, None), name) == tag

def barename(x):
    return x.rpartition('}')[-1]

def XML(x):
    return '{%s}%s' % (namespaces['xml'], x)

def expand(name):
    ns, tag = name.partition(':')[0::2]
    if ns:
        tag = '{%s}%s' % (namespaces[ns], tag)
    return tag

def get(x, attr, default=None):
    return x.attrib.get(expand(attr), default)

def ancestor(elem, name):
    tag = expand(name)
    while elem is not None:
        elem = elem.getparent()
        if getattr(elem, 'tag', None) == tag:
            return elem

def generate_anchor(name, existing):
    x = y = 'id_' + re.sub(r'[^0-9a-zA-Z_]', '', ascii_text(name)).lstrip('_')
    c = 1
    while y in existing:
        y = '%s_%d' % (x, c)
        c += 1
    return y

