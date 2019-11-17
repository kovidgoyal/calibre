#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from polyglot.builtins import iteritems, map

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.oeb.polish.cover import is_raster_image
from calibre.ebooks.oeb.polish.check.base import run_checkers, WARN
from calibre.ebooks.oeb.polish.check.parsing import (
    check_filenames, check_xml_parsing, fix_style_tag,
    check_html_size, check_ids, check_markup, EmptyFile, check_encoding_declarations)
from calibre.ebooks.oeb.polish.check.images import check_raster_images
from calibre.ebooks.oeb.polish.check.links import check_links, check_mimetypes, check_link_destinations
from calibre.ebooks.oeb.polish.check.fonts import check_fonts
from calibre.ebooks.oeb.polish.check.opf import check_opf
from polyglot.builtins import as_unicode


XML_TYPES = frozenset(map(guess_type, ('a.xml', 'a.svg', 'a.opf', 'a.ncx'))) | {'application/oebps-page-map+xml'}


class CSSChecker(object):

    def __init__(self):
        self.jobs = []

    def create_job(self, name, raw, line_offset=0, is_declaration=False):
        from calibre.ebooks.oeb.polish.check.css import create_job
        self.jobs.append(create_job(name, as_unicode(raw), line_offset, is_declaration))

    def __call__(self):
        from calibre.ebooks.oeb.polish.check.css import check_css
        if not self.jobs:
            return ()
        return check_css(self.jobs)


def run_checks(container):

    errors = []

    # Check parsing
    xml_items, html_items, raster_images, stylesheets = [], [], [], []
    for name, mt in iteritems(container.mime_map):
        items = None
        decode = False
        if mt in XML_TYPES:
            items = xml_items
        elif mt in OEB_DOCS:
            items = html_items
        elif mt in OEB_STYLES:
            decode = True
            items = stylesheets
        elif is_raster_image(mt):
            items = raster_images
        if items is not None:
            items.append((name, mt, container.raw_data(name, decode=decode)))
    errors.extend(run_checkers(check_html_size, html_items))
    errors.extend(run_checkers(check_xml_parsing, xml_items))
    errors.extend(run_checkers(check_xml_parsing, html_items))
    errors.extend(run_checkers(check_raster_images, raster_images))

    for err in errors:
        if err.level > WARN:
            return errors

    # css uses its own worker pool
    css_checker = CSSChecker()
    for name, mt, raw in stylesheets:
        if not raw:
            errors.append(EmptyFile(name))
            continue
        css_checker.create_job(name, raw)
    errors.extend(css_checker())

    for name, mt, raw in html_items + xml_items:
        errors.extend(check_encoding_declarations(name, container))

    css_checker = CSSChecker()
    for name, mt, raw in html_items:
        if not raw:
            continue
        root = container.parsed(name)
        for style in root.xpath('//*[local-name()="style"]'):
            if style.get('type', 'text/css') == 'text/css' and style.text:
                css_checker.create_job(name, style.text, line_offset=style.sourceline - 1)
        for elem in root.xpath('//*[@style]'):
            raw = elem.get('style')
            if raw:
                css_checker.create_job(name, raw, line_offset=elem.sourceline - 1, is_declaration=True)

    errors.extend(css_checker())
    errors += check_mimetypes(container)
    errors += check_links(container) + check_link_destinations(container)
    errors += check_fonts(container)
    errors += check_ids(container)
    errors += check_filenames(container)
    errors += check_markup(container)
    errors += check_opf(container)

    return errors


def fix_errors(container, errors):
    # Fix parsing
    changed = False
    for name in {e.name for e in errors if getattr(e, 'is_parsing_error', False)}:
        try:
            root = container.parsed(name)
        except TypeError:
            continue
        container.dirty(name)
        if container.mime_map[name] in OEB_DOCS:
            for style in root.xpath('//*[local-name()="style"]'):
                if style.get('type', 'text/css') == 'text/css' and style.text and style.text.strip():
                    fix_style_tag(container, style)

        changed = True

    for err in errors:
        if err.INDIVIDUAL_FIX:
            if err(container) is not False:
                # Assume changed unless fixer explicitly says no change (this
                # is because sometimes I forget to return True, and it is
                # better to have a false positive than a false negative)
                changed = True
    return changed
