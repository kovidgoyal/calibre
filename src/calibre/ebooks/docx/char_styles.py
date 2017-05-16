#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict
from calibre.ebooks.docx.block_styles import (  # noqa
    inherit, simple_color, LINE_STYLES, simple_float, binary_property, read_shd)

# Read from XML {{{


def read_text_border(parent, dest, XPath, get):
    border_color = border_style = border_width = padding = inherit
    elems = XPath('./w:bdr')(parent)
    if elems and elems[0].attrib:
        border_color = simple_color('auto')
        border_style = 'none'
        border_width = 1
    for elem in elems:
        color = get(elem, 'w:color')
        if color is not None:
            border_color = simple_color(color)
        style = get(elem, 'w:val')
        if style is not None:
            border_style = LINE_STYLES.get(style, 'solid')
        space = get(elem, 'w:space')
        if space is not None:
            try:
                padding = float(space)
            except (ValueError, TypeError):
                pass
        sz = get(elem, 'w:sz')
        if sz is not None:
            # we dont care about art borders (they are only used for page borders)
            try:
                # A border of less than 1pt is not rendered by WebKit
                border_width = min(96, max(8, float(sz))) / 8
            except (ValueError, TypeError):
                pass

    setattr(dest, 'border_color', border_color)
    setattr(dest, 'border_style', border_style)
    setattr(dest, 'border_width', border_width)
    setattr(dest, 'padding', padding)


def read_color(parent, dest, XPath, get):
    ans = inherit
    for col in XPath('./w:color[@w:val]')(parent):
        val = get(col, 'w:val')
        if not val:
            continue
        ans = simple_color(val)
    setattr(dest, 'color', ans)


def convert_highlight_color(val):
    return {
        'darkBlue': '#000080', 'darkCyan': '#008080', 'darkGray': '#808080',
        'darkGreen': '#008000', 'darkMagenta': '#800080', 'darkRed': '#800000', 'darkYellow': '#808000',
        'lightGray': '#c0c0c0'}.get(val, val)


def read_highlight(parent, dest, XPath, get):
    ans = inherit
    for col in XPath('./w:highlight[@w:val]')(parent):
        val = get(col, 'w:val')
        if not val:
            continue
        if not val or val == 'none':
            val = 'transparent'
        else:
            val = convert_highlight_color(val)
        ans = val
    setattr(dest, 'highlight', ans)


def read_lang(parent, dest, XPath, get):
    ans = inherit
    for col in XPath('./w:lang[@w:val]')(parent):
        val = get(col, 'w:val')
        if not val:
            continue
        try:
            code = int(val, 16)
        except (ValueError, TypeError):
            ans = val
        else:
            from calibre.ebooks.docx.lcid import lcid
            val = lcid.get(code, None)
            if val:
                ans = val
    setattr(dest, 'lang', ans)


def read_letter_spacing(parent, dest, XPath, get):
    ans = inherit
    for col in XPath('./w:spacing[@w:val]')(parent):
        val = simple_float(get(col, 'w:val'), 0.05)
        if val is not None:
            ans = val
    setattr(dest, 'letter_spacing', ans)


def read_underline(parent, dest, XPath, get):
    ans = inherit
    for col in XPath('./w:u[@w:val]')(parent):
        val = get(col, 'w:val')
        if val:
            ans = val if val == 'none' else 'underline'
    setattr(dest, 'text_decoration', ans)


def read_vert_align(parent, dest, XPath, get):
    ans = inherit
    for col in XPath('./w:vertAlign[@w:val]')(parent):
        val = get(col, 'w:val')
        if val and val in {'baseline', 'subscript', 'superscript'}:
            ans = val
    setattr(dest, 'vert_align', ans)


def read_position(parent, dest, XPath, get):
    ans = inherit
    for col in XPath('./w:position[@w:val]')(parent):
        val = get(col, 'w:val')
        try:
            ans = float(val)/2.0
        except Exception:
            pass
    setattr(dest, 'position', ans)


def read_font(parent, dest, XPath, get):
    ff = inherit
    used_cs = False
    for col in XPath('./w:rFonts')(parent):
        val = get(col, 'w:asciiTheme')
        if val:
            val = '|%s|' % val
        else:
            val = get(col, 'w:ascii')
        if not val:
            val = get(col, 'w:cs')
            used_cs = bool(val)
        if val:
            ff = val
    setattr(dest, 'font_family', ff)
    sizes = ('szCs', 'sz') if used_cs else ('sz', 'szCs')
    for q in sizes:
        for col in XPath('./w:%s[@w:val]' % q)(parent):
            val = simple_float(get(col, 'w:val'), 0.5)
            if val is not None:
                setattr(dest, 'font_size', val)
                return
    setattr(dest, 'font_size', inherit)

# }}}


class RunStyle(object):

    all_properties = {
        'b', 'bCs', 'caps', 'cs', 'dstrike', 'emboss', 'i', 'iCs', 'imprint',
        'rtl', 'shadow', 'smallCaps', 'strike', 'vanish', 'webHidden',

        'border_color', 'border_style', 'border_width', 'padding', 'color', 'highlight', 'background_color',
        'letter_spacing', 'font_size', 'text_decoration', 'vert_align', 'lang', 'font_family', 'position',
    }

    toggle_properties = {
        'b', 'bCs', 'caps', 'emboss', 'i', 'iCs', 'imprint', 'shadow', 'smallCaps', 'strike', 'vanish',
    }

    def __init__(self, namespace, rPr=None):
        self.namespace = namespace
        self.linked_style = None
        if rPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for p in (
                'b', 'bCs', 'caps', 'cs', 'dstrike', 'emboss', 'i', 'iCs', 'imprint', 'rtl', 'shadow',
                'smallCaps', 'strike', 'vanish', 'webHidden',
            ):
                setattr(self, p, binary_property(rPr, p, namespace.XPath, namespace.get))

            read_font(rPr, self, namespace.XPath, namespace.get)
            for x in ('text_border', 'color', 'highlight', 'shd', 'letter_spacing', 'underline', 'vert_align', 'position', 'lang'):
                f = globals()['read_%s' % x]
                f(rPr, self, namespace.XPath, namespace.get)

            for s in namespace.XPath('./w:rStyle[@w:val]')(rPr):
                self.linked_style = namespace.get(s, 'w:val')

        self._css = None

    def update(self, other):
        for prop in self.all_properties:
            nval = getattr(other, prop)
            if nval is not inherit:
                setattr(self, prop, nval)
        if other.linked_style is not None:
            self.linked_style = other.linked_style

    def resolve_based_on(self, parent):
        for p in self.all_properties:
            val = getattr(self, p)
            if val is inherit:
                setattr(self, p, getattr(parent, p))

    def get_border_css(self, ans):
        for x in ('color', 'style', 'width'):
            val = getattr(self, 'border_'+x)
            if x == 'width' and val is not inherit:
                val = '%.3gpt' % val
            if val is not inherit:
                ans['border-%s' % x] = val

    def clear_border_css(self):
        for x in ('color', 'style', 'width'):
            setattr(self, 'border_'+x, inherit)

    @property
    def css(self):
        if self._css is None:
            c = self._css = OrderedDict()
            td = set()
            if self.text_decoration is not inherit:
                td.add(self.text_decoration)
            if self.strike and self.strike is not inherit:
                td.add('line-through')
            if self.dstrike and self.dstrike is not inherit:
                td.add('line-through')
            if td:
                c['text-decoration'] = ' '.join(td)
            if self.caps is True:
                c['text-transform'] = 'uppercase'
            if self.i is True:
                c['font-style'] = 'italic'
            if self.shadow and self.shadow is not inherit:
                c['text-shadow'] = '2px 2px'
            if self.smallCaps is True:
                c['font-variant'] = 'small-caps'
            if self.vanish is True or self.webHidden is True:
                c['display'] = 'none'

            self.get_border_css(c)
            if self.padding is not inherit:
                c['padding'] = '%.3gpt' % self.padding

            for x in ('color', 'background_color'):
                val = getattr(self, x)
                if val is not inherit:
                    c[x.replace('_', '-')] = val

            for x in ('letter_spacing', 'font_size'):
                val = getattr(self, x)
                if val is not inherit:
                    c[x.replace('_', '-')] = '%.3gpt' % val

            if self.position is not inherit:
                c['vertical-align'] = '%.3gpt' % self.position

            if self.highlight is not inherit and self.highlight != 'transparent':
                c['background-color'] = self.highlight

            if self.b:
                c['font-weight'] = 'bold'

            if self.font_family is not inherit:
                c['font-family'] = self.font_family

        return self._css

    def same_border(self, other):
        return self.get_border_css({}) == other.get_border_css({})
