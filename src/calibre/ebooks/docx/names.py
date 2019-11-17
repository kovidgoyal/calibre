#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml.etree import XPath as X

from calibre.utils.filenames import ascii_text
from polyglot.builtins import iteritems

# Names {{{
TRANSITIONAL_NAMES = {
    'DOCUMENT'  : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
    'DOCPROPS'  : 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties',
    'APPPROPS'  : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties',
    'STYLES'    : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles',
    'NUMBERING' : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering',
    'FONTS'     : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable',
    'EMBEDDED_FONT' : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/font',
    'IMAGES'    : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
    'LINKS'     : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
    'FOOTNOTES' : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes',
    'ENDNOTES'  : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes',
    'THEMES'    : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme',
    'SETTINGS'  : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings',
    'WEB_SETTINGS' : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/webSettings',
}

STRICT_NAMES = {
    k:v.replace('http://schemas.openxmlformats.org/officeDocument/2006',  'http://purl.oclc.org/ooxml/officeDocument')
    for k, v in iteritems(TRANSITIONAL_NAMES)
}

TRANSITIONAL_NAMESPACES = {
    'mo': 'http://schemas.microsoft.com/office/mac/office/2008/main',
    'o': 'urn:schemas-microsoft-com:office:office',
    've': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
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

STRICT_NAMESPACES = {
    k:v.replace(
        'http://schemas.openxmlformats.org/officeDocument/2006', 'http://purl.oclc.org/ooxml/officeDocument').replace(
        'http://schemas.openxmlformats.org/wordprocessingml/2006', 'http://purl.oclc.org/ooxml/wordprocessingml').replace(
        'http://schemas.openxmlformats.org/drawingml/2006', 'http://purl.oclc.org/ooxml/drawingml')
    for k, v in iteritems(TRANSITIONAL_NAMESPACES)
}
# }}}


def barename(x):
    return x.rpartition('}')[-1]


def XML(x):
    return '{%s}%s' % (TRANSITIONAL_NAMESPACES['xml'], x)


def generate_anchor(name, existing):
    x = y = 'id_' + re.sub(r'[^0-9a-zA-Z_]', '', ascii_text(name)).lstrip('_')
    c = 1
    while y in existing:
        y = '%s_%d' % (x, c)
        c += 1
    return y


class DOCXNamespace(object):

    def __init__(self, transitional=True):
        self.xpath_cache = {}
        if transitional:
            self.namespaces = TRANSITIONAL_NAMESPACES.copy()
            self.names = TRANSITIONAL_NAMES.copy()
        else:
            self.namespaces = STRICT_NAMESPACES.copy()
            self.names = STRICT_NAMES.copy()

    def XPath(self, expr):
        ans = self.xpath_cache.get(expr, None)
        if ans is None:
            self.xpath_cache[expr] = ans = X(expr, namespaces=self.namespaces)
        return ans

    def is_tag(self, x, q):
        tag = getattr(x, 'tag', x)
        ns, name = q.partition(':')[0::2]
        return '{%s}%s' % (self.namespaces.get(ns, None), name) == tag

    def expand(self, name, sep=':'):
        ns, tag = name.partition(sep)[::2]
        if ns and tag:
            tag = '{%s}%s' % (self.namespaces[ns], tag)
        return tag or ns

    def get(self, x, attr, default=None):
        return x.attrib.get(self.expand(attr), default)

    def ancestor(self, elem, name):
        try:
            return self.XPath('ancestor::%s[1]' % name)(elem)[0]
        except IndexError:
            return None

    def children(self, elem, *args):
        return self.XPath('|'.join('child::%s' % a for a in args))(elem)

    def descendants(self, elem, *args):
        return self.XPath('|'.join('descendant::%s' % a for a in args))(elem)

    def makeelement(self, root, tag, append=True, **attrs):
        ans = root.makeelement(self.expand(tag), **{self.expand(k, sep='_'):v for k, v in iteritems(attrs)})
        if append:
            root.append(ans)
        return ans
