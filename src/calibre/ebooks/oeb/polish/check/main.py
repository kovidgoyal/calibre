#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import TYPE_CHECKING, cast

from lxml import etree

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.check.accessibility import check_accessibility
from calibre.ebooks.oeb.polish.check.base import WARN, BaseError, run_checkers
from calibre.ebooks.oeb.polish.check.fonts import check_fonts
from calibre.ebooks.oeb.polish.check.images import check_raster_images
from calibre.ebooks.oeb.polish.check.links import CaseMismatch, check_link_destinations, check_links, check_mimetypes
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

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from calibre.ebooks.oeb.polish.check.css import Job
    from calibre.ebooks.oeb.polish.container import Container

XML_TYPES = frozenset(map(guess_type, ('a.xml', 'a.svg', 'a.opf', 'a.ncx'))) | {'application/oebps-page-map+xml'}


class CSSChecker:
    def __init__(self, skipped_rules: frozenset[str] = frozenset()) -> None:
        self.jobs: list[Job] = []
        self.skipped_rules = skipped_rules

    def create_job(self, name: str, raw: str | bytes, line_offset: int = 0) -> None:
        from calibre.ebooks.oeb.polish.check.css import Job

        self.jobs.append(Job(name, as_unicode(raw), line_offset))

    def __call__(self) -> Sequence[BaseError]:
        from calibre.ebooks.oeb.polish.check.css import check_css

        return check_css(self.jobs, self.skipped_rules)


def remove_skipped(errors: Iterable[BaseError], skipped_rules: frozenset[str]) -> list[BaseError]:
    return [e for e in errors if not e.can_be_skipped or e.rule_id not in skipped_rules]


def run_checks(container: Container, skipped_rules: frozenset[str] = frozenset(), accessibility: bool = False) -> list[BaseError]:

    errors: list[BaseError] = []

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
        assert isinstance(root, etree._Element)
        for style in root.xpath('//*[local-name()="style"]'):
            if style.get('type', 'text/css') == 'text/css' and style.text:
                css_checker.create_job(name, style.text, line_offset=style.sourceline - 1)
        for elem in root.xpath('//*[@style]'):
            raw = elem.get('style')
            if raw:
                css_checker.create_job(name, raw, line_offset=elem.sourceline - 1)

    errors.extend(css_checker())
    errors += check_mimetypes(container)
    errors += check_links(container) + check_link_destinations(container)
    errors += check_fonts(container)
    errors += check_ids(container)
    errors += check_filenames(container)
    errors += check_markup(container)
    errors += check_opf(container)
    if accessibility:
        errors += check_accessibility(container)

    return remove_skipped(errors, skipped_rules)


def fix_css(container: Container, skipped_rules: frozenset[str] = frozenset()) -> bool:
    from calibre.ebooks.oeb.polish.check.css import fix_css_text

    changed = False
    for name, mt in container.mime_map.items():
        if mt in OEB_STYLES:
            css = cast('str', container.raw_data(name, decode=True))  # CSS files are decoded to str
            if (fixed := fix_css_text(css, skipped_rules)) is not None:
                with container.open(name, 'wb') as f:
                    f.write(fixed.encode('utf-8'))
                changed = True
        elif mt in OEB_DOCS:
            root = container.parsed(name)
            assert isinstance(root, etree._Element)
            dirtied = False
            for style in root.xpath('//*[local-name()="style"]'):
                if style.get('type', 'text/css') == 'text/css' and style.text:
                    if (fixed := fix_css_text(style.text, skipped_rules)) is not None:
                        style.text = fixed
                        dirtied = True
            for elem in root.xpath('//*[@style]'):
                raw = elem.get('style')
                if raw and (fixed := fix_css_text(raw, skipped_rules)) is not None:
                    elem.set('style', fixed)
                    dirtied = True
            if dirtied:
                container.dirty(name)
                changed = True
    return changed


def fix_errors(container: Container, errors: Sequence[BaseError], skipped_rules: frozenset[str] = frozenset()) -> bool:
    # Fix parsing
    changed = False
    for name in {e.name for e in errors if getattr(e, 'is_parsing_error', False)}:
        try:
            root = container.parsed(name)
        except TypeError:
            continue
        container.dirty(name)
        if container.mime_map[name] in OEB_DOCS:
            assert isinstance(root, etree._Element)
            for style in root.xpath('//*[local-name()="style"]'):
                if style.get('type', 'text/css') == 'text/css' and style.text and style.text.strip():
                    fix_style_tag(container, style)

        changed = True

    has_fixable_css_errors = False
    fixable: list[BaseError] = []
    # Errors whose types support it are fixed in batches, as fixing them one
    # by one would mean processing the whole book once per error. All errors of
    # a type are fixed together at the position of the first error of that type.
    batches: dict[type[BaseError], list[BaseError]] = {}
    for err in errors:
        if getattr(err, 'FIXABLE_CSS_ERROR', False):
            has_fixable_css_errors = True
        if err.INDIVIDUAL_FIX:
            if type(err).has_batch_fix:
                batches.setdefault(type(err), []).append(err)
            fixable.append(err)
    # Fixes that rename files run last, as other errors refer to files by
    # their current names. The sort is stable, preserving the order otherwise.
    fixable.sort(key=lambda e: type(e).renames_file)
    # Correcting the case of links first ensures that subsequent fixes, such as
    # renaming ids or files, update those links as well. It cannot harm any
    # other fix as it only changes links that do not point to any file.
    case_mismatches = [e for e in batches.pop(CaseMismatch, ()) if isinstance(e, CaseMismatch)]
    if case_mismatches and CaseMismatch.fix_batch(container, case_mismatches):
        changed = True
    existing_names = set(container.name_path_map)
    for err in fixable:
        if err.name in existing_names and not container.has_name(err.name):
            continue  # the file was removed or renamed by a previous fix
        if (batch := batches.pop(type(err), None)) is not None:
            if type(err).fix_batch(container, batch):
                changed = True
        elif type(err).has_batch_fix:
            continue  # already fixed in a batch
        elif err(container) is not False:
            # Assume changed unless fixer explicitly says no change (this
            # is because sometimes I forget to return True, and it is
            # better to have a false positive than a false negative)
            changed = True
    if has_fixable_css_errors:
        if fix_css(container, skipped_rules):
            changed = True
    return changed
