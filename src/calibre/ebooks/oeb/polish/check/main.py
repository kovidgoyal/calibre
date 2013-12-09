#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from future_builtins import map

from calibre.ebooks.oeb.base import OEB_DOCS
from calibre.ebooks.oeb.polish.container import guess_type
from calibre.ebooks.oeb.polish.check.base import run_checkers
from calibre.ebooks.oeb.polish.check.parsing import check_xml_parsing

def run_checks(container):

    errors = []

    # Check parsing
    XML_TYPES = frozenset(map(guess_type, ('a.xml', 'a.svg', 'a.opf', 'a.ncx')))
    xml_items, html_items = [], []
    for name, mt in container.mime_map.iteritems():
        items = None
        if mt in XML_TYPES:
            items = xml_items
        elif mt in OEB_DOCS:
            items = html_items
        if items is not None:
            items.append((name, mt, container.open(name, 'rb').read()))
    errors.extend(run_checkers(check_xml_parsing, xml_items))
    errors.extend(run_checkers(check_xml_parsing, html_items))

    return errors

