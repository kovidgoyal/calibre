#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
import sys

from lxml import etree

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'


def clone_node(node: etree.Element, parent: etree.Element) -> etree.Element:
    ans = parent.makeelement(node.tag)
    for k in node.keys():
        ans.set(k, node.get(k))  # ty: ignore[invalid-argument-type]
    ans.text, ans.tail = node.text, node.tail
    for child in node.iterchildren('*'):
        clone_node(child, ans)
    parent.append(ans)
    return ans


def merge() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    ans = etree.fromstring(f'<svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}"/>', parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
    for f in sorted(os.listdir(base)):
        if not f.endswith('.svg'):
            continue
        with open(os.path.join(base, f), 'rb') as ff:
            raw = ff.read()
        svg = etree.fromstring(raw, parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
        symbol = ans.makeelement('{%s}symbol' % SVG_NS)  # ruff: ignore[printf-string-formatting]
        symbol.set('viewBox', svg.get('viewBox') or '')
        symbol.set('id', 'icon-' + f.rpartition('.')[0])
        for child in svg.iterchildren('*'):
            clone_node(child, symbol)
        ans.append(symbol)
    ans = etree.tostring(ans, encoding='unicode', pretty_print=True, with_tail=False)
    ans = re.sub(r'<svg[^>]+>', '<svg style="display:none">', ans, count=1)
    return ans


if __name__ == '__main__':
    sys.stdout.write(merge())
