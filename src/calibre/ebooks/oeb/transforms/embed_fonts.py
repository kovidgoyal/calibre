#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, cast

import css_parser
from css_parser.css import CSSStyleSheet
from lxml import etree

from calibre import guess_type
from calibre.ebooks.oeb.base import CSS_MIME, XHTML, XPath
from calibre.ebooks.oeb.polish.embed import font_key
from calibre.ebooks.oeb.transforms.subset import elem_style, find_font_face_rules, get_font_properties
from calibre.utils.filenames import ascii_filename
from calibre.utils.fonts.scanner import NoFonts, font_scanner

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.ebooks.oeb.transforms.subset import FontFaceInfo, FontStyle
    from calibre.utils.fonts.metadata import FontFace
    from calibre.utils.logging import Log

    type StyleKey = tuple[str | None, ...]


def font_families_from_style(style: FontStyle) -> list[str]:
    return [str(f) for f in style.get('font-family', []) if str(f).lower() not in {'serif', 'sansserif', 'sans-serif', 'fantasy', 'cursive', 'monospace'}]


def style_key(style: FontStyle) -> StyleKey:
    style = style.copy()
    style['font-family'] = font_families_from_style(style)[0]  # ty: ignore[invalid-assignment] font_key() wants a single family name
    return font_key(style)  # ty: ignore[invalid-argument-type] font_key() only reads the family, weight, style and stretch keys


def font_already_embedded(style: FontStyle, newly_embedded_fonts: set[StyleKey]) -> bool:
    return style_key(style) in newly_embedded_fonts


def used_font(style: FontStyle, embedded_fonts: list[FontFaceInfo]) -> tuple[bool, FontFaceInfo | None]:
    ff = font_families_from_style(style)
    if not ff:
        return False, None
    lnames = {str(x).lower() for x in ff}

    matching_set: list[FontFaceInfo] = []

    # Filter on font-family
    for ef in embedded_fonts:
        flnames = {x.lower() for x in ef.get('font-family', [])}
        if not lnames.intersection(flnames):
            continue
        matching_set.append(ef)
    if not matching_set:
        return True, None

    # Filter on font-stretch
    widths = {
        x: i
        for i, x in enumerate((
            'ultra-condensed',
            'extra-condensed',
            'condensed',
            'semi-condensed',
            'normal',
            'semi-expanded',
            'expanded',
            'extra-expanded',
            'ultra-expanded',
        ))
    }

    width = widths[style.get('font-stretch', 'normal')]
    for f in matching_set:
        f['width'] = widths[style.get('font-stretch', 'normal')]

    min_dist = min(abs(width - f['width']) for f in matching_set)
    if min_dist > 0:
        return True, None
    nearest = [f for f in matching_set if abs(width - f['width']) == min_dist]
    if width <= 4:
        lmatches = [f for f in nearest if f['width'] <= width]
    else:
        lmatches = [f for f in nearest if f['width'] >= width]
    matching_set = lmatches or nearest

    # Filter on font-style
    fs = style.get('font-style', 'normal')
    matching_set = [f for f in matching_set if f.get('font-style', 'normal') == fs]

    # Filter on font weight
    fw = int(style.get('font-weight', '400'))
    matching_set = [f for f in matching_set if f.get('weight', 400) == fw]

    if not matching_set:
        return True, None
    return True, matching_set[0]


class EmbedFonts:
    """
    Embed all referenced fonts, if found on system. Must be called after CSS flattening.
    """

    def __call__(self, oeb: OEBBook, log: Log, opts: Values | OptionValues) -> None:
        self.oeb, self.log, self.opts = oeb, log, opts
        self.sheet_cache: dict[str, object] = {}
        self.find_style_rules()
        self.find_embedded_fonts()
        self.parser = css_parser.CSSParser(loglevel=logging.CRITICAL, log=logging.getLogger('calibre.css'))
        self.warned: set[str] = set()
        self.warned2: set[str] = set()
        self.newly_embedded_fonts: set[StyleKey] = set()

        for item in oeb.spine:
            root = item.data
            if not isinstance(root, etree._Element):
                continue
            sheets: list[Manifest.Item] = []
            for href in XPath('//h:link[@href and @type="text/css"]/@href')(root):
                sheet = self.oeb.manifest.hrefs.get(item.abshref(href), None)
                if sheet is not None:
                    sheets.append(sheet)
            if sheets:
                self.process_item(item, sheets)

    def find_embedded_fonts(self) -> None:
        """
        Find all @font-face rules and extract the relevant info from them.
        """
        self.embedded_fonts: list[FontFaceInfo] = []
        for item in self.oeb.manifest:
            if not isinstance(item.data, CSSStyleSheet):
                continue
            self.embedded_fonts.extend(find_font_face_rules(item, self.oeb))

    def find_style_rules(self) -> None:
        """
        Extract all font related style information from all stylesheets into a
        dict mapping classes to font properties specified by that class. All
        the heavy lifting has already been done by the CSS flattening code.
        """
        rules: defaultdict[str, FontStyle] = defaultdict(dict)  # ty: ignore[no-matching-overload] FontStyle is total=False so {} is valid
        for item in self.oeb.manifest:
            data = item.data
            if not isinstance(data, CSSStyleSheet):
                continue
            for i, rule in enumerate(data.cssRules):
                if rule.type != rule.STYLE_RULE:
                    continue
                props = cast('FontStyle', {k: v for k, v in get_font_properties(rule).items() if v})  # None values removed
                if not props:
                    continue
                for sel in rule.selectorList:
                    sel = sel.selectorText
                    if sel and sel.startswith('.'):
                        # We don't care about pseudo-selectors as the worst that
                        # can happen is some extra characters will remain in
                        # the font
                        sel = sel.partition(':')[0]
                        rules[sel[1:]].update(props)

        self.style_rules = dict(rules)

    def get_page_sheet(self) -> Manifest.Item:
        if self.page_sheet is None:
            manifest = self.oeb.manifest
            id_, href = manifest.generate('page_css', 'page_styles.css')
            self.page_sheet = manifest.add(id_, href, CSS_MIME, data=self.parser.parseString('', validate=False))
            root = self.current_item.data
            assert isinstance(root, etree._Element)  # process_item() is only called for spine items with parsed HTML
            head = root.xpath('//*[local-name()="head"][1]')
            if head:
                href = self.current_item.relhref(href)
                l = etree.SubElement(head[0], XHTML('link'), rel='stylesheet', type=CSS_MIME, href=href)
                l.tail = '\n'
            else:
                self.log.warn('No <head> cannot embed font rules')
        return self.page_sheet

    def process_item(self, item: Manifest.Item, sheets: list[Manifest.Item]) -> None:
        ff_rules: list[FontFaceInfo] = []
        self.current_item = item
        self.page_sheet: Manifest.Item | None = None
        for sheet in sheets:
            if 'page_css' in sheet.id:
                ff_rules.extend(find_font_face_rules(sheet, self.oeb))
                self.page_sheet = sheet

        base: FontStyle = {'font-family': ['serif'], 'font-weight': '400', 'font-style': 'normal', 'font-stretch': 'normal'}

        root = item.data
        assert isinstance(root, etree._Element)  # only called for spine items with parsed HTML
        for body in root.xpath('//*[local-name()="body"]'):
            self.find_usage_in(body, base, ff_rules)

    def find_usage_in(self, elem: etree._Element, inherited_style: FontStyle, ff_rules: list[FontFaceInfo]) -> None:
        style = elem_style(self.style_rules, elem.get('class', '') or '', inherited_style)
        for child in elem:
            self.find_usage_in(child, style, ff_rules)
        has_font, existing = used_font(style, ff_rules)
        if not has_font or font_already_embedded(style, self.newly_embedded_fonts):
            return
        if existing is None:
            in_book = used_font(style, self.embedded_fonts)[1]
            if in_book is None:
                # Try to find the font in the system
                added = self.embed_font(style)
                if added is not None:
                    self.newly_embedded_fonts.add(style_key(style))
                    ff_rules.append(added)
                    self.embedded_fonts.append(added)
            else:
                # TODO: Create a page rule from the book rule (cannot use it
                # directly as paths might be different)
                item = in_book['item']
                sheet = self.parser.parseString(in_book['rule'].cssText, validate=False)
                rule = sheet.cssRules[0]
                page_sheet = self.get_page_sheet()
                href = page_sheet.abshref(item.href)
                rule.style.setProperty('src', f'url({href})')
                ff_rules.append(find_font_face_rules(sheet, self.oeb)[0])
                page_css = page_sheet.data
                assert isinstance(page_css, CSSStyleSheet)  # page_css items are always stylesheets
                page_css.insertRule(rule, len(page_css.cssRules))

    def embed_font(self, style: FontStyle) -> FontFaceInfo | None:
        from calibre.ebooks.oeb.polish.embed import find_matching_font, weight_as_number

        ff = font_families_from_style(style)
        if not ff:
            return
        ff = ff[0]
        if ff in self.warned or ff == 'inherit':
            return
        try:
            fonts = font_scanner.fonts_for_family(ff)
        except NoFonts:
            self.log.warn('Failed to find fonts for family:', ff, 'not embedding')
            self.warned.add(ff)
            return
        weight = weight_as_number(style.get('font-weight', '400'))

        def do_embed(f: FontFace) -> FontFaceInfo:
            data = font_scanner.get_font_data(f)
            name = f['full_name'] or f['family_name'] or 'font'
            ext = 'otf' if f['is_otf'] else 'ttf'
            name = ascii_filename(name).replace(' ', '-').replace('(', '').replace(')', '')
            fid, href = self.oeb.manifest.generate(id='font', href=f'fonts/{name}.{ext}')
            item = self.oeb.manifest.add(fid, href, cast('str', guess_type('dummy.' + ext)[0]), data=data)
            item.unload_data_from_memory()
            page_sheet = self.get_page_sheet()
            href = page_sheet.relhref(item.href)
            css = '''@font-face {{ font-family: "{}"; font-weight: {}; font-style: {}; font-stretch: {}; src: url({}) }}'''.format(
                f['font-family'], f['font-weight'], f['font-style'], f['font-stretch'], href
            )
            sheet = self.parser.parseString(css, validate=False)
            page_css = page_sheet.data
            assert isinstance(page_css, CSSStyleSheet)  # page_css items are always stylesheets
            page_css.insertRule(sheet.cssRules[0], len(page_css.cssRules))
            return find_font_face_rules(sheet, self.oeb)[0]

        for f in fonts:
            if f['weight'] == weight and f['font-style'] == style.get('font-style', 'normal') and f['font-stretch'] == style.get('font-stretch', 'normal'):
                self.log('Embedding font {} from {}'.format(f['full_name'], f['path']))
                return do_embed(f)
        try:
            f = find_matching_font(
                fonts,
                style.get('font-weight', 'normal'),
                style.get('font-style', 'normal'),
                style.get('font-stretch', 'normal'),
            )
        except Exception:
            if ff not in self.warned2:
                self.log.exception('Failed to find a matching font for family', ff, 'not embedding')
                self.warned2.add(ff)
                return
        self.log('Embedding font {} from {}'.format(f['full_name'], f['path']))
        return do_embed(f)
