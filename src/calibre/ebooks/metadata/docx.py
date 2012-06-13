#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from lxml import etree

from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.zipfile import ZipFile
from calibre.utils.magick.draw import identify_data
from calibre.ebooks.oeb.base import DC11_NS
from calibre.ebooks.oeb.parse_utils import RECOVER_PARSER

NSMAP = {'dc':DC11_NS,
'cp':'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'}

def XPath(expr):
    return etree.XPath(expr, namespaces=NSMAP)

def _read_doc_props(raw, mi):
    from calibre.ebooks.metadata import string_to_authors
    root = etree.fromstring(raw, parser=RECOVER_PARSER)
    titles = XPath('//dc:title')(root)
    if titles:
        title = titles[0].text
        if title and title.strip():
            mi.title = title.strip()
    tags = []
    for subject in XPath('//dc:subject')(root):
        if subject.text and subject.text.strip():
            tags.append(subject.text.strip().replace(',', '_'))
    for keywords in XPath('//cp:keywords')(root):
        if keywords.text and keywords.text.strip():
            for x in keywords.text.split():
                tags.extend(y.strip() for y in x.split(','))
    if tags:
        mi.tags = tags
    authors = XPath('//dc:creator')(root)
    aut = []
    for author in authors:
        if author.text and author.text.strip():
            aut.extend(string_to_authors(author.text))
    if aut:
        mi.authors = aut

    desc = XPath('//dc:description')(root)
    if desc:
        raw = etree.tostring(desc[0], method='text', encoding=unicode)
        mi.comments = raw

def _read_app_props(raw, mi):
    root = etree.fromstring(raw, parser=RECOVER_PARSER)
    company = root.xpath('//*[local-name()="Company"]')
    if company and company[0].text and company[0].text.strip():
        mi.publisher = company[0].text.strip()

def get_metadata(stream):
    with ZipFile(stream, 'r') as zf:

        mi = Metadata(_('Unknown'))
        cdata = None

        for zi in zf.infolist():
            ext = zi.filename.rpartition('.')[-1].lower()
            if zi.filename.lower() == 'docprops/core.xml':
                _read_doc_props(zf.read(zi), mi)
            elif zi.filename.lower() == 'docprops/app.xml':
                _read_app_props(zf.read(zi), mi)
            elif cdata is None and ext in {'jpeg', 'jpg', 'png', 'gif'}:
                raw = zf.read(zi)
                try:
                    width, height, fmt = identify_data(raw)
                except:
                    continue
                if 0.8 <= height/width <= 1.8 and height*width >= 12000:
                    cdata = (fmt, raw)
        if cdata is not None:
            mi.cover_data = cdata

    return mi

if __name__ == '__main__':
    import sys
    with open(sys.argv[-1], 'rb') as stream:
        print (get_metadata(stream))
