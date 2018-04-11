#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from lxml import etree

from calibre.ebooks.metadata.opf3 import (
    DC, OPF, XPath, create_timestamp, ensure_id, parse_date, read_prefixes,
    read_refines, refdef, remove_element, set_refines
)
from calibre.ebooks.metadata.utils import parse_opf, pretty_print_opf


class Data(object):
    pass


def upgrade_identifiers(root, data):
    for ident in XPath('./opf:metadata/dc:identifier')(root):
        val = (ident.text or '').strip()
        lval = val.lower()
        scheme = ident.attrib.pop(OPF('scheme'), None)
        if lval.startswith('urn:'):
            prefix, rest = val[4:].partition(':')[::2]
            if prefix and rest:
                scheme, val = prefix, rest
        if scheme and val:
            ident.text = '{}:{}'.format(scheme, val)
        for attr in tuple(ident.attrib):
            if attr != 'id':
                del ident.attrib[attr]


def upgrade_title(root, data):
    first_title = None
    for title in XPath('./opf:metadata/dc:title')(root):
        if not title.text or not title.text.strip():
            remove_element(title, data.refines)
            continue
        if first_title is None:
            first_title = title

    title_sort = None
    for m in XPath('./opf:metadata/opf:meta[@name="calibre:title_sort"]')(root):
        ans = m.get('content')
        if ans:
            title_sort = ans
        remove_element(m, data.refines)

    if first_title is not None:
        ts = [refdef('file-as', title_sort)] if title_sort else ()
        set_refines(first_title, data.refines, refdef('title-type', 'main'), *ts)


def upgrade_languages(root, data):
    langs = XPath('./opf:metadata/dc:language')(root)
    if langs:
        for lang in langs:
            lang.attrib.clear()
    else:
        # EPUB spec says dc:language is required
        metadata = XPath('./opf:metadata')(root)[0]
        l = metadata.makeelement(DC('language'))
        l.text = 'und'
        metadata.append(l)


def upgrade_authors(root, data):
    for which in 'creator', 'contributor':
        for elem in XPath('./opf:metadata/dc:' + which)(root):
            role = elem.attrib.pop(OPF('role'), None)
            sort = elem.attrib.pop(OPF('file-as'), None)
            if role or sort:
                aid = ensure_id(elem)
                metadata = elem.getparent()
                if role:
                    m = metadata.makeelement(OPF('meta'), attrib={'refines':'#'+aid, 'property':'role', 'scheme':'marc:relators'})
                    m.text = role
                    metadata.append(m)
                if sort:
                    m = metadata.makeelement(OPF('meta'), attrib={'refines':'#'+aid, 'property':'file-as'})
                    m.text = sort
                    metadata.append(m)


def upgrade_timestamp(root, data):
    for meta in XPath('./opf:metadata/opf:meta[@name="calibre:timestamp"]')(root):
        m = meta.getparent()
        remove_element(meta, data.refines)
        val = meta.get('content')
        if val:
            try:
                val = parse_date(val, is_w3cdtf=True)
            except Exception:
                pass
            else:
                create_timestamp(m, val)


def upgrade_date(root, data):
    found = False
    for date in XPath('./opf:metadata/dc:date')(root):
        val = date.text
        if val:
            found = True
            continue
        if not val or found:  # only one dc:date allowed
            remove_element(date, data.refines)


def upgrade_metadata(root):
    data = Data()
    data.prefixes = read_prefixes(root)
    data.refines = read_refines(root)

    upgrade_identifiers(root, data)
    upgrade_title(root, data)
    upgrade_languages(root, data)
    upgrade_authors(root, data)
    upgrade_timestamp(root, data)
    upgrade_date(root, data)

    pretty_print_opf(root)


if __name__ == '__main__':
    import sys
    root = parse_opf(open(sys.argv[-1], 'rb'))
    upgrade_metadata(root)
    print(etree.tostring(root))
