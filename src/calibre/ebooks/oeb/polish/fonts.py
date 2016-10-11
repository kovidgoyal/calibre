#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.oeb.polish.container import OEB_STYLES, OEB_DOCS
from calibre.ebooks.oeb.normalize_css import normalize_font
from tinycss.fonts3 import parse_font_family, parse_font, serialize_font_family, serialize_font


def unquote(x):
    if x and len(x) > 1 and x[0] == x[-1] and x[0] in ('"', "'"):
        x = x[1:-1]
    return x


def font_family_data_from_declaration(style, families):
    font_families = []
    f = style.getProperty('font')
    if f is not None:
        f = normalize_font(f.propertyValue, font_family_as_list=True).get('font-family', None)
        if f is not None:
            font_families = [unquote(x) for x in f]
    f = style.getProperty('font-family')
    if f is not None:
        font_families = parse_font_family(f.propertyValue.cssText)

    for f in font_families:
        families[f] = families.get(f, False)


def font_family_data_from_sheet(sheet, families):
    for rule in sheet.cssRules:
        if rule.type == rule.STYLE_RULE:
            font_family_data_from_declaration(rule.style, families)
        elif rule.type == rule.FONT_FACE_RULE:
            ff = rule.style.getProperty('font-family')
            if ff is not None:
                for f in parse_font_family(ff.propertyValue.cssText):
                    families[f] = True


def font_family_data(container):
    families = {}
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_STYLES:
            sheet = container.parsed(name)
            font_family_data_from_sheet(sheet, families)
        elif mt in OEB_DOCS:
            root = container.parsed(name)
            for style in root.xpath('//*[local-name() = "style"]'):
                if style.text and style.get('type', 'text/css').lower() == 'text/css':
                    sheet = container.parse_css(style.text)
                    font_family_data_from_sheet(sheet, families)
            for style in root.xpath('//*/@style'):
                if style:
                    style = container.parse_css(style, is_declaration=True)
                    font_family_data_from_declaration(style, families)
    return families


def change_font_in_declaration(style, old_name, new_name=None):
    changed = False
    ff = style.getProperty('font-family')
    if ff is not None:
        fams = parse_font_family(ff.propertyValue.cssText)
        nfams = filter(None, [new_name if x == old_name else x for x in fams])
        if fams != nfams:
            if nfams:
                ff.propertyValue.cssText = serialize_font_family(nfams)
            else:
                style.removeProperty(ff.name)
            changed = True
    ff = style.getProperty('font')
    if ff is not None:
        props = parse_font(ff.propertyValue.cssText)
        fams = props.get('font-family') or []
        nfams = filter(None, [new_name if x == old_name else x for x in fams])
        if fams != nfams:
            props['font-family'] = nfams
            if nfams:
                ff.propertyValue.cssText = serialize_font(props)
            else:
                style.removeProperty(ff.name)
            changed = True
    return changed


def remove_embedded_font(container, sheet, rule, sheet_name):
    src = getattr(rule.style.getProperty('src'), 'value')
    if src is not None:
        if src.startswith('url('):
            src = src[4:-1]
    sheet.cssRules.remove(rule)
    if src:
        src = unquote(src)
        name = container.href_to_name(src, sheet_name)
        if container.has_name(name):
            container.remove_item(name)


def change_font_in_sheet(container, sheet, old_name, new_name, sheet_name):
    changed = False
    removals = []
    for rule in sheet.cssRules:
        if rule.type == rule.STYLE_RULE:
            changed |= change_font_in_declaration(rule.style, old_name, new_name)
        elif rule.type == rule.FONT_FACE_RULE:
            ff = rule.style.getProperty('font-family')
            if ff is not None:
                families = {x for x in parse_font_family(ff.propertyValue.cssText)}
                if old_name in families:
                    changed = True
                    removals.append(rule)
    for rule in reversed(removals):
        remove_embedded_font(container, sheet, rule, sheet_name)
    return changed


def change_font(container, old_name, new_name=None):
    '''
    Change a font family from old_name to new_name. Changes all occurrences of
    the font family in stylesheets, style tags and style attributes.
    If the old_name refers to an embedded font, it is removed. You can set
    new_name to None to remove the font family instead of changing it.
    '''
    changed = False
    for name, mt in tuple(container.mime_map.iteritems()):
        if mt in OEB_STYLES:
            sheet = container.parsed(name)
            if change_font_in_sheet(container, sheet, old_name, new_name, name):
                container.dirty(name)
                changed = True
        elif mt in OEB_DOCS:
            root = container.parsed(name)
            for style in root.xpath('//*[local-name() = "style"]'):
                if style.text and style.get('type', 'text/css').lower() == 'text/css':
                    sheet = container.parse_css(style.text)
                    if change_font_in_sheet(container, sheet, old_name, new_name, name):
                        container.dirty(name)
                        changed = True
            for elem in root.xpath('//*[@style]'):
                style = elem.get('style', '')
                if style:
                    style = container.parse_css(style, is_declaration=True)
                    if change_font_in_declaration(style, old_name, new_name):
                        style = style.cssText.strip().rstrip(';').strip()
                        if style:
                            elem.set('style', style)
                        else:
                            del elem.attrib['style']
                        container.dirty(name)
                        changed = True
    return changed
