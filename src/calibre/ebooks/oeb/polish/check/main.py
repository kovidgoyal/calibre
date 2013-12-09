#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from future_builtins import map

from calibre.ebooks.oeb.base import OEB_DOCS
from calibre.ebooks.oeb.polish.container import guess_type
from calibre.ebooks.oeb.polish.cover import is_raster_image
from calibre.ebooks.oeb.polish.check.base import run_checkers
from calibre.ebooks.oeb.polish.check.parsing import check_xml_parsing
from calibre.ebooks.oeb.polish.check.images import check_raster_images
from calibre.ebooks.oeb.polish.check.links import check_links

XML_TYPES = frozenset(map(guess_type, ('a.xml', 'a.svg', 'a.opf', 'a.ncx')))

def run_checks(container):

    errors = []

    # Check parsing
    xml_items, html_items, raster_images = [], [], []
    for name, mt in container.mime_map.iteritems():
        items = None
        if mt in XML_TYPES:
            items = xml_items
        elif mt in OEB_DOCS:
            items = html_items
        elif is_raster_image(mt):
            items = raster_images
        if items is not None:
            items.append((name, mt, container.open(name, 'rb').read()))
    errors.extend(run_checkers(check_xml_parsing, xml_items))
    errors.extend(run_checkers(check_xml_parsing, html_items))
    errors.extend(run_checkers(check_raster_images, raster_images))

    errors += check_links(container)

    return errors

def fix_errors(container, errors):
    # Fix parsing
    changed = False
    for name in {e.name for e in errors if getattr(e, 'is_parsing_error', False)}:
        container.parsed(name)
        container.dirty(name)
        changed = True

    for err in errors:
        if err.INDIVIDUAL_FIX:
            if err(container):
                changed = True
    return changed

