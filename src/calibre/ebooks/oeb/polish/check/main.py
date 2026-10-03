#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from collections import namedtuple
from collections.abc import Iterable
from functools import partial

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.check.base import WARN, BaseError, run_checkers
from calibre.ebooks.oeb.polish.check.fonts import check_fonts
from calibre.ebooks.oeb.polish.check.images import check_raster_images
from calibre.ebooks.oeb.polish.check.links import check_link_destinations, check_links, check_mimetypes
from calibre.ebooks.oeb.polish.check.opf import check_opf
from calibre.ebooks.oeb.polish.check.parsing import (
    EmptyFile,
    check_encoding_declarations,
    check_filenames,
    check_html_size,
    check_ids,
    check_markup,
    check_xml_parsing,
    fix_style_tag,
)
from calibre.ebooks.oeb.polish.cover import is_raster_image
from calibre.ebooks.oeb.polish.utils import guess_type
from polyglot.builtins import as_unicode

XML_TYPES = frozenset(map(guess_type, ('a.xml', 'a.svg', 'a.opf', 'a.ncx'))) | {'application/oebps-page-map+xml'}


class CSSChecker:
    def __init__(self, skipped_rules: frozenset[str] = frozenset()):
        self.jobs = []
        self.skipped_rules = skipped_rules

    def create_job(self, name, raw, line_offset=0, is_declaration=False):
        from calibre.ebooks.oeb.polish.check.css import create_job

        self.jobs.append(create_job(name, as_unicode(raw), line_offset, is_declaration))

    def __call__(self):
        from calibre.ebooks.oeb.polish.check.css import check_css

        if not self.jobs:
            return ()
        return check_css(self.jobs, self.skipped_rules)


def remove_skipped(errors: Iterable[BaseError], skipped_rules: frozenset[str]) -> list[BaseError]:
    return [e for e in errors if not e.can_be_skipped or e.rule_id not in skipped_rules]


def run_checks(container, skipped_rules: frozenset[str] = frozenset()):

    errors = []

    # Check parsing
    xml_items, html_items, raster_images, stylesheets = [], [], [], []
    for name, mt in container.mime_map.items():
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
    if container.MAX_HTML_FILE_SIZE:
        errors.extend(run_checkers(partial(check_html_size, max_size=container.MAX_HTML_FILE_SIZE), html_items))
    errors.extend(run_checkers(check_xml_parsing, xml_items))
    errors.extend(run_checkers(check_xml_parsing, html_items))
    errors.extend(run_checkers(check_raster_images, raster_images))
    errors = remove_skipped(errors, skipped_rules)

    for err in errors:
        if err.level > WARN:
            return errors

    # css uses its own worker pool
    css_checker = CSSChecker(skipped_rules)
    for name, mt, raw in stylesheets:
        if not raw:
            errors.append(EmptyFile(name))
            continue
        css_checker.create_job(name, raw)
    errors.extend(css_checker())

    for name, mt, raw in html_items + xml_items:
        errors.extend(check_encoding_declarations(name, container))

    css_checker = CSSChecker(skipped_rules)
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

    return remove_skipped(errors, skipped_rules)


CSSFix = namedtuple('CSSFix', 'original_css elem attribute')


def fix_css(container, skipped_rules: frozenset[str] = frozenset()):
    from calibre.ebooks.oeb.polish.check.css import create_job, pool, stylelint_rules_from_skipped_rules

    jobs = []

    for name, mt in container.mime_map.items():
        if mt in OEB_STYLES:
            css = container.raw_data(name, decode=True)
            jobs.append(create_job(name, css, fix_data=CSSFix(css, None, '')))
        elif mt in OEB_DOCS:
            root = container.parsed(name)
            for style in root.xpath('//*[local-name()="style"]'):
                if style.get('type', 'text/css') == 'text/css' and style.text:
                    jobs.append(create_job(name, style.text, fix_data=CSSFix(style.text, style, '')))
            for elem in root.xpath('//*[@style]'):
                raw = elem.get('style')
                if raw:
                    jobs.append(create_job(name, raw, is_declaration=True, fix_data=CSSFix(raw, elem, 'style')))
    results = pool.check_css([j.css for j in jobs], fix=True, disabled_rules=stylelint_rules_from_skipped_rules(skipped_rules))
    changed = False
    for job, result in zip(jobs, results):
        if result['type'] == 'error':
            continue
        fx = job.fix_data
        fixed_css = result['results']['output']
        if fixed_css == fx.original_css:
            continue
        changed = True
        if fx.elem is None:
            with container.open(job.name, 'wb') as f:
                f.write(fixed_css.encode('utf-8'))
        else:
            if fx.attribute:
                fx.elem.set(fx.attribute, ' '.join(fixed_css.splitlines()[1:-1]))
            else:
                fx.elem.text = fixed_css
            container.dirty(job.name)
    return changed


def fix_errors(container, errors, skipped_rules: frozenset[str] = frozenset()):
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

    has_fixable_css_errors = False
    for err in errors:
        if getattr(err, 'FIXABLE_CSS_ERROR', False):
            has_fixable_css_errors = True
        if err.INDIVIDUAL_FIX:
            if err(container) is not False:
                # Assume changed unless fixer explicitly says no change (this
                # is because sometimes I forget to return True, and it is
                # better to have a false positive than a false negative)
                changed = True
    if has_fixable_css_errors:
        if fix_css(container, skipped_rules):
            changed = True
    return changed
