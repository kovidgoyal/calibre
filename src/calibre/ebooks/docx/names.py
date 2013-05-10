#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml.etree import XPath as X

DOCUMENT  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument'
DOCPROPS  = 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties'
APPPROPS  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties'
STYLES    = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles'
NUMBERING = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering'

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

def XPath(expr):
    return X(expr, namespaces=namespaces)

def is_tag(x, q):
    tag = getattr(x, 'tag', x)
    ns, name = q.partition(':')[0::2]
    return '{%s}%s' % (namespaces.get(ns, None), name) == tag

def barename(x):
    return x.rpartition('}')[-1]

def XML(x):
    return '{%s}%s' % (namespaces['xml'], x)

def get(x, attr, default=None):
    ns, name = attr.partition(':')[0::2]
    return x.attrib.get('{%s}%s' % (namespaces[ns], name), default)

