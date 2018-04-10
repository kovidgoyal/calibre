#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from lxml import etree

from calibre.ebooks.metadata.opf3 import (
    OPF, XPath, read_prefixes, read_refines, refdef, remove_element, set_refines
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


def upgrade_metadata(root):
    data = Data()
    data.prefixes = read_prefixes(root)
    data.refines = read_refines(root)

    upgrade_identifiers(root, data)
    upgrade_title(root, data)
    pretty_print_opf(root)


if __name__ == '__main__':
    import sys
    root = parse_opf(open(sys.argv[-1], 'rb'))
    upgrade_metadata(root)
    print(etree.tostring(root))
