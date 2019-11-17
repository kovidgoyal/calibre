#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from css_parser.css import CSSRule

from calibre import force_unicode
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN
from calibre.ebooks.oeb.polish.container import OEB_FONTS
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style
from calibre.ebooks.oeb.polish.fonts import change_font_in_declaration
from calibre.utils.fonts.utils import get_all_font_names, is_font_embeddable, UnsupportedFont
from tinycss.fonts3 import parse_font_family
from polyglot.builtins import iteritems


class InvalidFont(BaseError):

    HELP = _('This font could not be processed. It most likely will'
             ' not work in an e-book reader, either')


def fix_sheet(sheet, css_name, font_name):
    changed = False
    for rule in sheet.cssRules:
        if rule.type in (CSSRule.FONT_FACE_RULE, CSSRule.STYLE_RULE):
            changed = change_font_in_declaration(rule.style, css_name, font_name) or changed
    return changed


class NotEmbeddable(BaseError):

    level = WARN

    def __init__(self, name, fs_type):
        BaseError.__init__(self, _('The font {} is not allowed to be embedded').format(name), name)
        self.HELP = _('The font has a flag in its metadata ({:09b}) set indicating that it is'
                      ' not licensed for embedding. You can ignore this warning, if you are'
                      ' sure you have permission to embed this font.').format(fs_type)


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
        for name, mt in iteritems(container.mime_map):
            if mt in OEB_STYLES:
                sheet = container.parsed(name)
                if fix_sheet(sheet, self.css_name, self.font_name):
                    container.dirty(name)
                    changed = True
            elif mt in OEB_DOCS:
                for style in container.parsed(name).xpath('//*[local-name()="style"]'):
                    if style.get('type', 'text/css') == 'text/css' and style.text:
                        sheet = container.parse_css(style.text)
                        if fix_sheet(sheet, self.css_name, self.font_name):
                            style.text = force_unicode(sheet.cssText, 'utf-8')
                            pretty_script_or_style(container, style)
                            container.dirty(name)
                            changed = True
                for elem in container.parsed(name).xpath('//*[@style and contains(@style, "font-family")]'):
                    style = container.parse_css(elem.get('style'), is_declaration=True)
                    if change_font_in_declaration(style, self.css_name, self.font_name):
                        elem.set('style', force_unicode(style.cssText, 'utf-8').replace('\n', ' '))
                        container.dirty(name)
                        changed = True
        return changed


def check_fonts(container):
    font_map = {}
    errors = []
    for name, mt in iteritems(container.mime_map):
        if mt in OEB_FONTS:
            raw = container.raw_data(name)
            try:
                name_map = get_all_font_names(raw)
            except Exception as e:
                errors.append(InvalidFont(_('Not a valid font: %s') % e, name))
                continue
            font_map[name] = name_map.get('family_name', None) or name_map.get('preferred_family_name', None) or name_map.get('wws_family_name', None)
            try:
                embeddable, fs_type = is_font_embeddable(raw)
            except UnsupportedFont:
                embeddable = True
            if not embeddable:
                errors.append(NotEmbeddable(name, fs_type))

    sheets = []
    for name, mt in iteritems(container.mime_map):
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
                    families = parse_font_family(rule.style.getPropertyValue('font-family'))
                    if families:
                        if families[0] != font_name:
                            errors.append(FontAliasing(font_name, families[0], name, line_offset))

    return errors
