#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING, cast

from kgcss import FontFaceRule, RuleType, StyleRule, iter_urls, parse_font, parse_font_family, serialize_font, serialize_font_family

from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.css import delete_rule

if TYPE_CHECKING:
    from kgcss import DeclarationBlock, Stylesheet
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container


def font_family_data_from_declaration(style: DeclarationBlock, families: dict[str, bool]) -> None:
    font_families: list[str] = []
    f = style.get_property('font')
    if f is not None:
        font_families = parse_font(f.value).get('font-family', [])
    f = style.get_property('font-family')
    if f is not None:
        font_families = parse_font_family(f.value)

    for f in font_families:
        families[f] = families.get(f, False)


def font_family_data_from_sheet(sheet: Stylesheet, families: dict[str, bool]) -> None:
    for rule in sheet.iter_rules(RuleType.STYLE, RuleType.FONT_FACE):
        if isinstance(rule, StyleRule):
            font_family_data_from_declaration(rule.style, families)
        elif isinstance(rule, FontFaceRule):
            ff = rule.style.get_property('font-family')
            if ff is not None:
                for f in parse_font_family(ff.value):
                    families[f] = True


def font_family_data(container: Container) -> dict[str, bool]:
    families: dict[str, bool] = {}
    for name, mt in container.mime_map.items():
        if mt in OEB_STYLES:
            font_family_data_from_sheet(container.parsed_stylesheet(name), families)
        elif mt in OEB_DOCS:
            root = cast('_Element', container.parsed(name))  # HTML files are parsed into lxml trees
            for style in root.xpath('//*[local-name() = "style"]'):
                if style.text and style.get('type', 'text/css').lower() == 'text/css':
                    font_family_data_from_sheet(container.parse_stylesheet(style.text), families)
            for style in root.xpath('//*/@style'):
                if style:
                    font_family_data_from_declaration(container.parse_style(style), families)
    return families


def change_font_in_declaration(style: DeclarationBlock, old_name: str, new_name: str | None = None) -> bool:
    changed = False
    ff = style.get_property('font-family')
    if ff is not None:
        fams = parse_font_family(ff.value)
        nfams = list(filter(None, [new_name if x == old_name else x for x in fams]))
        if fams != nfams:
            if nfams:
                ff.value = serialize_font_family(nfams)
            else:
                style.remove(ff.name)
            changed = True
    ff = style.get_property('font')
    if ff is not None:
        props = parse_font(ff.value)
        fams = props.get('font-family') or []
        nfams = list(filter(None, [new_name if x == old_name else x for x in fams]))
        if fams != nfams:
            props['font-family'] = nfams
            if nfams:
                ff.value = serialize_font(props)
            else:
                style.remove(ff.name)
            changed = True
    return changed


def remove_embedded_font(container: Container, rule: FontFaceRule, sheet_name: str) -> None:
    src = next(iter_urls(rule), None)
    delete_rule(rule)
    if src:
        name = container.href_to_name(src, sheet_name)
        if container.has_name(name):
            container.remove_item(name)


def change_font_in_sheet(container: Container, sheet: Stylesheet, old_name: str, new_name: str | None, sheet_name: str) -> bool:
    changed = False
    removals: list[FontFaceRule] = []
    for rule in sheet.iter_rules(RuleType.STYLE, RuleType.FONT_FACE):
        if isinstance(rule, StyleRule):
            changed |= change_font_in_declaration(rule.style, old_name, new_name)
        elif isinstance(rule, FontFaceRule):
            ff = rule.style.get_property('font-family')
            if ff is not None:
                families = set(parse_font_family(ff.value))
                if old_name in families:
                    changed = True
                    removals.append(rule)
    for rule in reversed(removals):
        remove_embedded_font(container, rule, sheet_name)
    return changed


def change_font(container: Container, old_name: str, new_name: str | None = None) -> bool:
    """
    Change a font family from old_name to new_name. Changes all occurrences of
    the font family in stylesheets, style tags and style attributes.
    If the old_name refers to an embedded font, it is removed. You can set
    new_name to None to remove the font family instead of changing it.
    """
    changed = False
    for name, mt in tuple(container.mime_map.items()):
        if mt in OEB_STYLES:
            sheet = container.parsed_stylesheet(name)
            if change_font_in_sheet(container, sheet, old_name, new_name, name):
                container.dirty(name)
                changed = True
        elif mt in OEB_DOCS:
            root = cast('_Element', container.parsed(name))  # HTML files are parsed into lxml trees
            for style in root.xpath('//*[local-name() = "style"]'):
                if style.text and style.get('type', 'text/css').lower() == 'text/css':
                    sheet = container.parse_stylesheet(style.text)
                    if change_font_in_sheet(container, sheet, old_name, new_name, name):
                        style.text = container.stylesheet_text(sheet)
                        container.dirty(name)
                        changed = True
            for elem in root.xpath('//*[@style]'):
                style = elem.get('style', '')
                if style:
                    block = container.parse_style(style)
                    if change_font_in_declaration(block, old_name, new_name):
                        if len(block):
                            elem.set('style', block.to_css(single_line=True))
                        else:
                            del elem.attrib['style']
                        container.dirty(name)
                        changed = True
    return changed
