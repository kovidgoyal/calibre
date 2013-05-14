#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict
from calibre.ebooks.docx.block_styles import (  # noqa
    inherit, simple_color, LINE_STYLES, simple_float, binary_property, read_shd)
from calibre.ebooks.docx.names import XPath, get

# Read from XML {{{
def read_text_border(parent, dest):
    border_color = border_style = border_width = padding = inherit
    elems = XPath('./w:bdr')(parent)
    if elems:
        border_color = simple_color('auto')
        border_style = 'solid'
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
                border_width = min(96, max(2, float(sz))) / 8
            except (ValueError, TypeError):
                pass

    setattr(dest, 'border_color', border_color)
    setattr(dest, 'border_style', border_style)
    setattr(dest, 'border_width', border_width)
    setattr(dest, 'padding', padding)

def read_color(parent, dest):
    ans = inherit
    for col in XPath('./w:color[@w:val]')(parent):
        val = get(col, 'w:val')
        if not val:
            continue
        ans = simple_color(val)
    setattr(dest, 'color', ans)

def read_highlight(parent, dest):
    ans = inherit
    for col in XPath('./w:highlight[@w:val]')(parent):
        val = get(col, 'w:val')
        if not val:
            continue
        if not val or val == 'none':
            val = 'transparent'
        ans = val
    setattr(dest, 'highlight', ans)

def read_lang(parent, dest):
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

def read_letter_spacing(parent, dest):
    ans = inherit
    for col in XPath('./w:spacing[@w:val]')(parent):
        val = simple_float(get(col, 'w:val'), 0.05)
        if val is not None:
            ans = val
    setattr(dest, 'letter_spacing', ans)

def read_sz(parent, dest):
    ans = inherit
    for col in XPath('./w:sz[@w:val]')(parent):
        val = simple_float(get(col, 'w:val'), 0.5)
        if val is not None:
            ans = val
    setattr(dest, 'font_size', ans)

def read_underline(parent, dest):
    ans = inherit
    for col in XPath('./w:u[@w:val]')(parent):
        val = get(col, 'w:val')
        if val:
            ans = 'underline'
    setattr(dest, 'text_decoration', ans)

def read_vert_align(parent, dest):
    ans = inherit
    for col in XPath('./w:vertAlign[@w:val]')(parent):
        val = get(col, 'w:val')
        if val and val in {'baseline', 'subscript', 'superscript'}:
            ans = val
    setattr(dest, 'vert_align', ans)

def read_font_family(parent, dest):
    ans = inherit
    for col in XPath('./w:rFonts[@w:ascii]')(parent):
        val = get(col, 'w:ascii')
        if val:
            ans = val
    setattr(dest, 'font_family', ans)
# }}}

class RunStyle(object):

    all_properties = {
        'b', 'bCs', 'caps', 'cs', 'dstrike', 'emboss', 'i', 'iCs', 'imprint',
        'rtl', 'shadow', 'smallCaps', 'strike', 'vanish',

        'border_color', 'border_style', 'border_width', 'padding', 'color', 'highlight', 'background_color',
        'letter_spacing', 'font_size', 'text_decoration', 'vert_align', 'lang', 'font_family'
    }

    toggle_properties = {
        'b', 'bCs', 'caps', 'emboss', 'i', 'iCs', 'imprint', 'shadow', 'smallCaps', 'strike', 'dstrike', 'vanish',
    }

    def __init__(self, rPr=None):
        self.linked_style = None
        if rPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for p in (
                'b', 'bCs', 'caps', 'cs', 'dstrike', 'emboss', 'i', 'iCs', 'imprint', 'rtl', 'shadow',
                'smallCaps', 'strike', 'vanish',
            ):
                setattr(self, p, binary_property(rPr, p))

            for x in ('text_border', 'color', 'highlight', 'shd', 'letter_spacing', 'sz', 'underline', 'vert_align', 'lang', 'font_family'):
                f = globals()['read_%s' % x]
                f(rPr, self)

            for s in XPath('./w:rStyle[@w:val]')(rPr):
                self.linked_style = get(s, 'w:val')

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

    @property
    def css(self):
        if self._css is None:
            c = self._css = OrderedDict()
            td = set()
            if self.text_decoration is not inherit:
                td.add(self.text_decoration)
            if self.strike:
                td.add('line-through')
            if self.dstrike:
                td.add('line-through')
            if td:
                c['text-decoration'] = ' '.join(td)
            if self.caps is True:
                c['text-transform'] = 'uppercase'
            if self.i is True:
                c['font-style'] = 'italic'
            if self.shadow:
                c['text-shadow'] = '2px 2px'
            if self.smallCaps is True:
                c['font-variant'] = 'small-caps'
            if self.vanish is True:
                c['display'] = 'none'

            for x in ('color', 'style', 'width'):
                val = getattr(self, 'border_'+x)
                if x == 'width' and val is not inherit:
                    val = '%.3gpt' % val
                if val is not inherit:
                    c['border-%s' % x] = val
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

            if self.highlight is not inherit and self.highlight != 'transparent':
                c['background-color'] = self.highlight

            if self.b:
                c['font-weight'] = 'bold'

            if self.font_family is not inherit:
                c['font-family'] = self.font_family
        return self._css

    def same_border(self, other):
        for x in (self, other):
            has_border = False
            for y in ('color', 'style', 'width'):
                if ('border-%s' % y) in x.css:
                    has_border = True
                    break
            if not has_border:
                return False

        s = tuple(self.css.get('border-%s' % y, None) for y in ('color', 'style', 'width'))
        o = tuple(other.css.get('border-%s' % y, None) for y in ('color', 'style', 'width'))
        return s == o

