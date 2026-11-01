#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

import os
from collections import defaultdict
from io import BytesIO
from typing import TYPE_CHECKING, cast

from css_parser.css import CSSStyleSheet
from lxml import etree
from tinycss.fonts3 import parse_font_family

from calibre.ebooks.oeb.base import css_text, urlnormalize
from calibre.utils.fonts.subset import subset

if TYPE_CHECKING:
    from optparse import Values
    from typing import TypedDict

    from css_parser.css import CSSFontFaceRule, CSSStyleRule
    from lxml.etree import _Element

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.utils.logging import Log

    # The result of get_font_properties(), values are None when not specified/invalid
    FontProps = TypedDict(
        'FontProps',
        {
            'font-family': list[str] | None,
            'src': str | None,
            'font-weight': str | None,
            'font-stretch': str | None,
            'font-style': str | None,
            'text-transform': str | None,
        },
        total=False,
    )
    # The (inherited) font properties of an element, built from FontProps with the None values removed
    FontStyle = TypedDict(
        'FontStyle',
        {'font-family': list[str], 'src': str, 'font-weight': str, 'font-stretch': str, 'font-style': str, 'text-transform': str},
        total=False,
    )
    # An @font-face rule, see find_font_face_rules()
    FontFaceInfo = TypedDict(
        'FontFaceInfo',
        {
            'font-family': list[str],
            'src': str,
            'font-weight': str,
            'font-stretch': str,
            'font-style': str,
            'text-transform': str,
            'item': Manifest.Item,
            'weight': int,
            'width': int,
            'rule': CSSFontFaceRule,
            'chars': set[str],
        },
        total=False,
    )

font_properties = ('font-family', 'src', 'font-weight', 'font-stretch', 'font-style', 'text-transform')


def get_font_properties(rule: CSSStyleRule | CSSFontFaceRule, default: str | None = None) -> FontProps:
    """
    Given a CSS rule, extract normalized font properties from
    it. Note that shorthand font property should already have been expanded
    by the CSS flattening code.
    """
    props: FontProps = {}
    s = rule.style
    for q in font_properties:
        g = 'uri' if q == 'src' else 'value'
        try:
            val = s.getProperty(q).propertyValue[0]
            val = getattr(val, g)
            if q == 'font-family':
                val = parse_font_family(css_text(s.getProperty(q).propertyValue))
                if val and val[0] == 'inherit':
                    val = None
        except IndexError, KeyError, AttributeError, TypeError, ValueError:
            val = None if q in {'src', 'font-family'} else default
        if q in {'font-weight', 'font-stretch', 'font-style'}:
            val = str(val).lower() if (val or val == 0) else val
            if val == 'inherit':
                val = default
        if q == 'font-weight':
            val = {'normal': '400', 'bold': '700'}.get(val, val)
            if val not in {'100', '200', '300', '400', '500', '600', '700', '800', '900', 'bolder', 'lighter'}:
                val = default
            if val == 'normal':
                val = '400'
        elif q == 'font-style':
            if val not in {'normal', 'italic', 'oblique'}:
                val = default
        elif q == 'font-stretch':
            if val not in {
                'normal',
                'ultra-condensed',
                'extra-condensed',
                'condensed',
                'semi-condensed',
                'semi-expanded',
                'expanded',
                'extra-expanded',
                'ultra-expanded',
            }:
                val = default
        props[q] = val  # ty: ignore[invalid-assignment] font-family is a list, other values are str
    return props


def find_font_face_rules(sheet: Manifest.Item | CSSStyleSheet, oeb: OEBBook) -> list[FontFaceInfo]:
    """
    Find all @font-face rules in the given sheet and extract the relevant info from them.
    sheet can be either a ManifestItem or a CSSStyleSheet.
    """
    ans: list[FontFaceInfo] = []
    if isinstance(sheet, CSSStyleSheet):
        rules = sheet.cssRules
    else:
        data = sheet.data
        assert isinstance(data, CSSStyleSheet)  # only called for stylesheet items
        rules = data.cssRules

    for i, rule in enumerate(rules):
        if rule.type != rule.FONT_FACE_RULE:
            continue
        # with default='normal' the weight, style and stretch are never None
        props = cast('FontFaceInfo', get_font_properties(rule, default='normal'))
        if not props['font-family'] or not props['src']:
            continue

        try:
            path = sheet.abshref(props['src'])
        except AttributeError:
            path = props['src']
        ff = oeb.manifest.hrefs.get(urlnormalize(path), None)
        if not ff:
            continue
        props['item'] = ff
        if props['font-weight'] in {'bolder', 'lighter'}:
            props['font-weight'] = '400'
        props['weight'] = int(props['font-weight'])
        props['rule'] = rule
        props['chars'] = set()
        ans.append(props)

    return ans


def elem_style(style_rules: dict[str, FontStyle], cls: str, inherited_style: FontStyle) -> FontStyle:
    """
    Find the effective style for the given element.
    """
    classes = cls.split()
    style = inherited_style.copy()
    for cls in classes:
        style.update(style_rules.get(cls, {}))
    wt = style.get('font-weight', None)
    pwt = inherited_style.get('font-weight', '400')
    if wt == 'bolder':
        style['font-weight'] = {
            '100': '400',
            '200': '400',
            '300': '400',
            '400': '700',
            '500': '700',
        }.get(pwt, '900')
    elif wt == 'lighter':
        style['font-weight'] = {'600': '400', '700': '400', '800': '700', '900': '700'}.get(pwt, '100')

    return style


class SubsetFonts:
    """
    Subset all embedded fonts. Must be run after CSS flattening, as it requires
    CSS normalization and flattening to work.
    """

    def __call__(self, oeb: OEBBook, log: Log, opts: Values | OptionValues) -> None:
        self.oeb, self.log, self.opts = oeb, log, opts

        self.find_embedded_fonts()
        if not self.embedded_fonts:
            self.log.debug('No embedded fonts found')
            return
        self.find_style_rules()
        self.find_font_usage()

        totals = [0, 0]

        def remove(font: FontFaceInfo) -> None:
            data = font['item'].data
            # font files are bytes, or an element for SVG fonts, len() raised TypeError otherwise
            assert isinstance(data, (etree._Element, str, bytes))
            totals[1] += len(data)
            self.oeb.manifest.remove(font['item'])
            font['rule'].parentStyleSheet.deleteRule(font['rule'])

        fonts: dict[str, FontFaceInfo] = {}
        for font in self.embedded_fonts:
            item, chars = font['item'], font['chars']
            if item.href in fonts:
                fonts[item.href]['chars'] |= chars
            else:
                fonts[item.href] = font

        for font in fonts.values():
            if not font['chars']:
                self.log('The font {} is unused. Removing it.'.format(font['src']))
                remove(font)
                continue
            old_raw = font['item'].data
            output = BytesIO()
            font_type = os.path.splitext(font['item'].href)[1][1:].lower()
            try:
                assert isinstance(old_raw, bytes)  # BytesIO() raised TypeError for anything else
                subset(BytesIO(old_raw), output, font_type, font['chars'])
            except Exception as e:
                self.log.warn('The font {} is unsupported for subsetting. {}'.format(font['src'], e))
                data = font['item'].data
                # font files are bytes, or an element for SVG fonts, len() raised TypeError otherwise
                assert isinstance(data, (etree._Element, str, bytes))
                sz = len(data)
                totals[0] += sz
                totals[1] += sz
            else:
                new_raw = output.getvalue()
                font['item'].data = new_raw
                nlen = len(new_raw)
                olen = len(old_raw)
                self.log('Decreased the font {} to {:.1f}% of its original size'.format(font['src'], nlen / olen * 100))
                totals[0] += nlen
                totals[1] += olen

            font['item'].unload_data_from_memory()

        if totals[0]:
            self.log(f'Reduced total font size to {totals[0] / totals[1] * 100:.1f}% of original')

    def find_embedded_fonts(self) -> None:
        """
        Find all @font-face rules and extract the relevant info from them.
        """
        self.embedded_fonts: list[FontFaceInfo] = []
        for item in self.oeb.manifest:
            try:
                if not hasattr(item.data, 'cssRules'):
                    continue
            except FileNotFoundError:
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

    def find_font_usage(self) -> None:
        for item in self.oeb.manifest:
            root = item.data
            if not isinstance(root, etree._Element):
                continue
            for body in root.xpath('//*[local-name()="body"]'):
                base: FontStyle = {
                    'font-family': ['serif'],
                    'font-weight': '400',
                    'font-style': 'normal',
                    'font-stretch': 'normal',
                }
                self.find_usage_in(body, base)

    def used_font(self, style: FontStyle) -> FontFaceInfo | None:
        """
        Given a style find the embedded font that matches it. Returns None if
        no match is found (can happen if no family matches).
        """
        ff = style.get('font-family', [])
        lnames = {str(x).lower() for x in ff}
        matching_set: list[FontFaceInfo] = []

        # Filter on font-family
        for ef in self.embedded_fonts:
            flnames = {x.lower() for x in ef.get('font-family', [])}
            if not lnames.intersection(flnames):
                continue
            matching_set.append(ef)
        if not matching_set:
            return None

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
        nearest = [f for f in matching_set if abs(width - f['width']) == min_dist]
        if width <= 4:
            lmatches = [f for f in nearest if f['width'] <= width]
        else:
            lmatches = [f for f in nearest if f['width'] >= width]
        matching_set = lmatches or nearest

        # Filter on font-style
        fs = style.get('font-style', 'normal')
        order = {'oblique': ['oblique', 'italic', 'normal'], 'normal': ['normal', 'oblique', 'italic']}.get(fs, ['italic', 'oblique', 'normal'])
        for q in order:
            matches = [f for f in matching_set if f.get('font-style', 'normal') == q]
            if matches:
                matching_set = matches
                break

        # Filter on font weight
        fw = int(style.get('font-weight', '400'))
        if fw == 400:
            q = [400, 500, 300, 200, 100, 600, 700, 800, 900]
        elif fw == 500:
            q = [500, 400, 300, 200, 100, 600, 700, 800, 900]
        elif fw < 400:
            q = [fw] + list(range(fw - 100, -100, -100)) + list(range(fw + 100, 100, 1000))
        else:
            q = [fw] + list(range(fw + 100, 100, 1000)) + list(range(fw - 100, -100, -100))
        for wt in q:
            matches = [f for f in matching_set if f['weight'] == wt]
            if matches:
                return matches[0]

    def find_chars(self, elem: _Element, style: FontStyle) -> set[str]:
        ans: set[str] = set()
        transform = lambda x: x  # ruff: ignore[lambda-assignment]
        tt = style.get('text-transform')
        if tt:
            if tt in ('uppercase', 'capitalize'):
                transform = str.upper
            elif tt == 'lowercase':
                transform = str.lower
        if elem.text:
            ans |= set(transform(elem.text))
        for child in elem:
            if child.tail:
                ans |= set(transform(child.tail))
        return ans

    def find_usage_in(self, elem: _Element, inherited_style: FontStyle) -> None:
        style = elem_style(self.style_rules, elem.get('class', '') or '', inherited_style)
        for child in elem:
            self.find_usage_in(child, style)
        font = self.used_font(style)
        if font:
            chars = self.find_chars(elem, style)
            if chars:
                font['chars'] |= chars
