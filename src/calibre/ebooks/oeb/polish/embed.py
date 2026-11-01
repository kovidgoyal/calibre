#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from typing import TYPE_CHECKING, cast

from lxml import etree

from calibre import prints
from calibre.ebooks.oeb.base import XHTML
from calibre.utils.filenames import ascii_filename
from calibre.utils.icu import lower as icu_lower
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.ebooks.oeb.polish.stats import FontFaceRule, StatsCollector, UsedFont
    from calibre.utils.fonts.metadata import FontFace

    # An @font-face rule for a font embedded by this module
    type EmbeddedFontRule = dict[str, str | None]
    type Report = Callable[[str], object]

props: dict[str, str | None] = {'font-family': None, 'font-weight': 'normal', 'font-style': 'normal', 'font-stretch': 'normal'}


def matching_rule(font: UsedFont, rules: Iterable[FontFaceRule]) -> FontFaceRule | None:
    ff = font['font-family']
    if not isinstance(ff, (str, bytes)):
        ff = tuple(ff)[0]
    family = icu_lower(ff)
    wt = font['font-weight']
    style = font['font-style']
    stretch = font['font-stretch']

    for rule in rules:
        if rule['font-style'] == style and rule['font-stretch'] == stretch and rule['font-weight'] == wt:
            ff = rule['font-family']
            if not isinstance(ff, (str, bytes)):
                ff = tuple(ff)[0]
            if icu_lower(ff) == family:
                return rule


def format_fallback_match_report(matched_font: FontFace, font_family: str, css_font: UsedFont, report: Report) -> None:
    msg = (
        _('Could not find a font in the "%s" family exactly matching the CSS font specification, will embed a fallback font instead. CSS font specification:')
        % font_family
    )
    msg += '\n\n* font-weight: {}'.format(css_font.get('font-weight', 'normal'))
    msg += '\n* font-style: {}'.format(css_font.get('font-style', 'normal'))
    msg += '\n* font-stretch: {}'.format(css_font.get('font-stretch', 'normal'))
    msg += '\n\n' + _('Matched font specification:')
    msg += '\n' + matched_font['path']
    msg += '\n\n* font-weight: {}'.format(matched_font.get('font-weight', 'normal').strip())
    msg += '\n* font-style: {}'.format(matched_font.get('font-style', 'normal').strip())
    msg += '\n* font-stretch: {}'.format(matched_font.get('font-stretch', 'normal').strip())
    report(msg)
    report('')


def stretch_as_number(val: str) -> int:
    try:
        return int(val)
    except Exception:
        pass
    try:
        return (
            'ultra-condensed',
            'extra-condensed',
            'condensed',
            'semi-condensed',
            'normal',
            'semi-expanded',
            'expanded',
            'extra-expanded',
            'ultra-expanded',
        ).index(val)
    except Exception:
        return 4  # normal


def filter_by_stretch(fonts: Sequence[FontFace], val: str) -> list[FontFace]:
    nval = stretch_as_number(val)
    stretch_map = [stretch_as_number(f['font-stretch']) for f in fonts]
    equal = [f for i, f in enumerate(fonts) if stretch_map[i] == nval]
    if equal:
        return equal
    condensed = [i for i in range(len(fonts)) if stretch_map[i] <= 4]
    expanded = [i for i in range(len(fonts)) if stretch_map[i] > 4]
    if nval <= 4:
        candidates = condensed or expanded
    else:
        candidates = expanded or condensed
    distance_map = {i: abs(stretch_map[i] - nval) for i in candidates}
    min_dist = min(distance_map.values())
    return [fonts[i] for i in candidates if distance_map[i] == min_dist]


def filter_by_style(fonts: Sequence[FontFace], val: str) -> list[FontFace]:
    order = {
        'normal': ('normal', 'oblique', 'italic'),
        'italic': ('italic', 'oblique', 'normal'),
        'oblique': ('oblique', 'italic', 'normal'),
    }
    if val not in order:
        val = 'normal'
    for q in order[val]:
        ans = [f for f in fonts if f['font-style'] == q]
        if ans:
            return ans
    return list(fonts)


def weight_as_number(wt: str) -> int:
    try:
        return int(wt)
    except Exception:
        return {'normal': 400, 'bold': 700}.get(wt, 400)


def filter_by_weight(fonts: Sequence[FontFace], val: str) -> list[FontFace]:
    nval = weight_as_number(val)
    weight_map = [weight_as_number(f['font-weight']) for f in fonts]
    equal = [f for i, f in enumerate(fonts) if weight_map[i] == nval]
    if equal:
        return equal
    rmap = {w: i for i, w in enumerate(weight_map)}
    below = [i for i in range(len(fonts)) if weight_map[i] < nval]
    above = [i for i in range(len(fonts)) if weight_map[i] > nval]
    if nval < 400:
        candidates = below or above
    elif nval > 500:
        candidates = above or below
    elif nval == 400:
        if 500 in rmap:
            return [fonts[rmap[500]]]
        candidates = below or above
    else:
        if 400 in rmap:
            return [fonts[rmap[400]]]
        candidates = below or above
    distance_map = {i: abs(weight_map[i] - nval) for i in candidates}
    min_dist = min(distance_map.values())
    return [fonts[i] for i in candidates if distance_map[i] == min_dist]


def find_matching_font(fonts: Sequence[FontFace], weight: str = 'normal', style: str = 'normal', stretch: str = 'normal') -> FontFace:
    # See https://www.w3.org/TR/css-fonts-3/#font-style-matching
    # We don't implement the unicode character range testing
    # We also don't implement bolder, lighter
    for f, q in ((filter_by_stretch, stretch), (filter_by_style, style), (filter_by_weight, weight)):
        fonts = f(fonts, q)
        if len(fonts) == 1:
            return fonts[0]
    return fonts[0]


def do_embed(container: Container, font: FontFace, report: Report) -> EmbeddedFontRule:
    from calibre.utils.fonts.scanner import font_scanner

    report('Embedding font {} from {}'.format(font['full_name'], font['path']))
    data = font_scanner.get_font_data(font)
    fname = font['full_name'] or font['family_name'] or 'font'
    ext = 'otf' if font['is_otf'] else 'ttf'
    fname = ascii_filename(fname).replace(' ', '-').replace('(', '').replace(')', '')
    item = container.generate_item(f'fonts/{fname}.{ext}', id_prefix='font')
    name = cast('str', container.href_to_name(item.get('href'), container.opf_name))  # generated items always have a href
    with container.open(name, 'wb') as out:
        out.write(data)
    href = container.name_to_href(name)
    rule = {k: font.get(k, v) for k, v in props.items()}
    rule['src'] = f'url({href})'
    rule['name'] = name
    return rule


def embed_font(
    container: Container, font: UsedFont, all_font_rules: Iterable[FontFaceRule], report: Report, warned: set[str | tuple[str | int | None, ...]]
) -> EmbeddedFontRule | None:
    rule = matching_rule(font, all_font_rules)
    ff = font['font-family']
    if not isinstance(ff, (str, bytes)):
        ff = ff[0]
    if rule is None:
        from calibre.utils.fonts.scanner import NoFonts, font_scanner

        if ff in warned:
            return
        try:
            fonts = font_scanner.fonts_for_family(ff)
        except NoFonts:
            report(_('Failed to find fonts for family: %s, not embedding') % ff)
            warned.add(ff)
            return
        wt = weight_as_number(font.get('font-weight'))
        for f in fonts:
            if f['weight'] == wt and f['font-style'] == font.get('font-style', 'normal') and f['font-stretch'] == font.get('font-stretch', 'normal'):
                return do_embed(container, f, report)
        f = find_matching_font(fonts, font.get('font-weight', '400'), font.get('font-style', 'normal'), font.get('font-stretch', 'normal'))
        wkey = ('fallback-font', ff, wt, font.get('font-style'), font.get('font-stretch'))
        if wkey not in warned:
            warned.add(wkey)
            format_fallback_match_report(f, ff, font, report)
        return do_embed(container, f, report)
    else:
        name = rule['src']
        href = container.name_to_href(name)
        rule = {k: ff if k == 'font-family' else rule.get(k, v) for k, v in props.items()}
        rule['src'] = f'url({href})'
        rule['name'] = name
        return rule


def font_key(font: UsedFont) -> tuple[str | None, ...]:
    return tuple(map(font.get, 'font-family font-weight font-style font-stretch'.split()))


def embed_all_fonts(container: Container, stats: StatsCollector, report: Report) -> bool:
    all_font_rules = tuple(stats.all_font_rules.values())
    warned: set[str | tuple[str | int | None, ...]] = set()
    rules: list[EmbeddedFontRule] = []
    nrules: dict[tuple[str | None, ...], EmbeddedFontRule] = {}
    modified: set[str] = set()

    for path in container.spine_items:
        name = container.abspath_to_name(path)
        fu = stats.font_usage_map.get(name, None)
        fs = stats.font_spec_map.get(name, None)
        fr = stats.font_rule_map.get(name, None)
        if fs is None or fu is None or fr is None:
            continue
        fs = {icu_lower(x) for x in fs}
        for font in fu.values():
            if icu_lower(font['font-family']) not in fs:
                continue
            rule = matching_rule(font, fr)
            if rule is None:
                # This font was not already embedded in this HTML file, before
                # processing started
                key = font_key(font)
                rule = nrules.get(key)
                if rule is None:
                    rule = embed_font(container, font, all_font_rules, report, warned)
                    if rule is not None:
                        rules.append(rule)
                        nrules[key] = rule
                        modified.add(name)
                        stats.font_stats[rule['name']] = font['text']
                else:
                    # This font was previously embedded by this code, update its stats
                    stats.font_stats[rule['name']] |= font['text']
                    modified.add(name)

    if not rules:
        report(_('No embeddable fonts found'))
        return False

    # Write out CSS
    rule_texts = [
        ';\n\t'.join(
            '{}: {}'.format(k, f'"{v}"' if k == 'font-family' else v) for k, v in rulel.items() if (k in props and props[k] != v and v != '400') or k == 'src'
        )
        for rulel in rules
    ]
    css = '\n\n'.join([f'@font-face {{\n\t{r}\n}}' for r in rule_texts])
    item = container.generate_item('fonts.css', id_prefix='font_embed')
    name = cast('str', container.href_to_name(item.get('href'), container.opf_name))  # generated items always have a href
    with container.open(name, 'wb') as out:
        out.write(css.encode('utf-8'))

    # Add link to CSS in all files that need it
    for spine_name in modified:
        root = cast('_Element', container.parsed(spine_name))  # spine items are HTML, parsed into lxml trees
        try:
            head = root.xpath('//*[local-name()="head"][1]')[0]
        except IndexError:
            head = root.makeelement(XHTML('head'))
            root.insert(0, head)
            head.tail = '\n'
            head.text = '\n  '
        href = container.name_to_href(name, spine_name)
        etree.SubElement(head, XHTML('link'), rel='stylesheet', type='text/css', href=href).tail = '\n'
        container.dirty(spine_name)
    return True


if __name__ == '__main__':
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.ebooks.oeb.polish.stats import StatsCollector
    from calibre.utils.logging import default_log

    default_log.filter_level = default_log.DEBUG
    inbook = sys.argv[-1]
    ebook = get_container(inbook, default_log)
    report: list[str] = []
    stats = StatsCollector(ebook, do_embed=True)
    embed_all_fonts(ebook, stats, report.append)
    outbook, ext = inbook.rpartition('.')[0::2]
    outbook += '_subset.' + ext
    ebook.commit(outbook)
    prints('\nReport:')
    for msg in report:
        prints(msg)
    print()
    prints('Output written to:', outbook)
