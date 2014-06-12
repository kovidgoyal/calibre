#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from cssutils.css import CSSRule

from calibre import force_unicode
from calibre.constants import plugins
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN
from calibre.ebooks.oeb.polish.container import OEB_FONTS
from calibre.ebooks.oeb.polish.fonts import change_font_family_value
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style
from calibre.utils.fonts.utils import get_all_font_names

woff = plugins['woff'][0]

class InvalidFont(BaseError):

    HELP = _('This font could not be processed. It most likely will'
             ' not work in an ebook reader, either')

def fix_property(prop, css_name, font_name):
    changed = False
    ff = prop.propertyValue
    for i in xrange(ff.length):
        val = ff.item(i)
        if hasattr(val.value, 'lower') and val.value.lower() == css_name.lower():
            change_font_family_value(val, font_name)
            changed = True
    return changed

def fix_declaration(style, css_name, font_name):
    changed = False
    for x in ('font-family', 'font'):
        prop = style.getProperty(x)
        if prop is not None:
            changed |= fix_property(prop, css_name, font_name)
    return changed

def fix_sheet(sheet, css_name, font_name):
    changed = False
    for rule in sheet.cssRules:
        if rule.type in (CSSRule.FONT_FACE_RULE, CSSRule.STYLE_RULE):
            if fix_declaration(rule.style, css_name, font_name):
                changed = True
    return changed

class FontAliasing(BaseError):

    level = WARN

    def __init__(self, font_name, css_name, name, line):
        BaseError.__init__(self, _('The CSS font-family name {0} does not match the actual font name {1}').format(css_name, font_name), name, line)
        self.HELP = _('The font family name specified in the CSS @font-face rule: "{0}" does'
                      ' not match the font name inside the actual font file: "{1}". This can'
                      ' cause problems in some viewers. You should change the CSS font name'
                      ' to match the actual font name.').format(css_name, font_name)
        self.INDIVIDUAL_FIX = _('Change the font name {0} to {1} everywhere').format(css_name, font_name)
        self.font_name, self.css_name = font_name, css_name

    def __call__(self, container):
        changed = False
        for name, mt in container.mime_map.iteritems():
            if mt in OEB_STYLES:
                sheet = container.parsed(name)
                if fix_sheet(sheet, self.css_name, self.font_name):
                    container.dirty(name)
                    changed = True
            elif mt in OEB_DOCS:
                for style in container.parsed(name).xpath('//*[local-name()="style"]'):
                    if style.get('type', 'text/css') == 'text/css':
                        sheet = container.parse_css(style.text)
                        if fix_sheet(sheet, self.css_name, self.font_name):
                            style.text = force_unicode(sheet.cssText, 'utf-8')
                            pretty_script_or_style(container, style)
                            container.dirty(name)
                            changed = True
                for elem in container.parsed(name).xpath('//*[@style and contains(@style, "font-family")]'):
                    style = container.parse_css(elem.get('style'), is_declaration=True)
                    if fix_declaration(style, self.css_name, self.font_name):
                        elem.set('style', force_unicode(style.cssText, 'utf-8').replace('\n', ' '))
                        container.dirty(name)
                        changed = True
        return changed

def check_fonts(container):
    font_map = {}
    errors = []
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_FONTS:
            raw = container.raw_data(name)
            if mt == guess_type('a.woff'):
                try:
                    raw = woff.from_woff(raw)
                except Exception as e:
                    errors.append(InvalidFont(_('Not a valid WOFF font: %s') % e, name))
                    continue
            try:
                name_map = get_all_font_names(raw)
            except Exception as e:
                errors.append(InvalidFont(_('Not a valid font: %s') % e, name))
                continue
            font_map[name] = name_map.get('family_name', None) or name_map.get('preferred_family_name', None) or name_map.get('wws_family_name', None)

    sheets = []
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_STYLES:
            try:
                sheets.append((name, container.parsed(name), None))
            except Exception:
                pass  # Could not parse, ignore
        elif mt in OEB_DOCS:
            for style in container.parsed(name).xpath('//*[local-name()="style"]'):
                if style.get('type', 'text/css') == 'text/css' and style.text:
                    sheets.append((name, container.parse_css(style.text), style.sourceline))

    for name, sheet, line_offset in sheets:
        for rule in sheet.cssRules.rulesOfType(CSSRule.FONT_FACE_RULE):
            src = rule.style.getPropertyCSSValue('src')
            if src is not None and src.length > 0:
                href = getattr(src.item(0), 'uri', None)
                if href is not None:
                    fname = container.href_to_name(href, name)
                    font_name = font_map.get(fname, None)
                    if font_name is None:
                        continue
                    ff = rule.style.getPropertyCSSValue('font-family')
                    if ff is not None and ff.length > 0:
                        ff = getattr(ff.item(0), 'value', None)
                        if ff is not None and ff != font_name:
                            errors.append(FontAliasing(font_name, ff, name, line_offset))

    return errors
