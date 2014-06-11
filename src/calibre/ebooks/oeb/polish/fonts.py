#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.oeb.polish.container import OEB_STYLES, OEB_DOCS
from calibre.ebooks.oeb.normalize_css import normalize_font

def unquote(x):
    if x and len(x) > 1 and x[0] == x[-1] and x[0] in ('"', "'"):
        x = x[1:-1]
    return x

def font_family_data_from_declaration(style, families):
    font_families = []
    f = style.getProperty('font')
    if f is not None:
        f = normalize_font(f.cssValue, font_family_as_list=True).get('font-family', None)
        if f is not None:
            font_families = f
    f = style.getProperty('font-family')
    if f is not None:
        font_families = [x.cssText for x in f.cssValue]

    for f in font_families:
        f = unquote(f)
        families[f] = families.get(f, False)

def font_family_data_from_sheet(sheet, families):
    for rule in sheet.cssRules:
        if rule.type == rule.STYLE_RULE:
            font_family_data_from_declaration(rule.style, families)
        elif rule.type == rule.FONT_FACE_RULE:
            ff = rule.style.getProperty('font-family')
            if ff is not None:
                for f in ff.cssValue:
                    families[unquote(f.cssText)] = True

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
