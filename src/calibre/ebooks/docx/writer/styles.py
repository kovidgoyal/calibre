#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml import etree

from calibre.ebooks import parse_css_length
from calibre.ebooks.docx.names import namespaces
from calibre.ebooks.docx.writer.utils import convert_color, int_or_zero
from tinycss.css21 import CSS21Parser

css_parser = CSS21Parser()

border_edges = ('left', 'top', 'right', 'bottom')
border_props = ('padding_%s', 'border_%s_width', 'border_%s_style', 'border_%s_color')

def parse_css_font_family(raw):
    decl, errs = css_parser.parse_style_attr('font-family:' + raw)
    if decl:
        for token in decl[0].value:
            if token.type in 'STRING IDENT':
                val = token.value
                if val == 'inherit':
                    break
                yield val

def css_font_family_to_docx(raw):
    generic = {'serif':'Cambria', 'sansserif':'Candara', 'sans-serif':'Candara', 'fantasy':'Comic Sans', 'cursive':'Segoe Script'}
    for ff in parse_css_font_family(raw):
        return generic.get(ff.lower(), ff)

class DOCXStyle(object):

    ALL_PROPS = ()

    def __init__(self):
        self._hash = hash(tuple(
            getattr(self, x) for x in self.ALL_PROPS))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        for x in self.ALL_PROPS:
            if getattr(self, x) != getattr(other, x, None):
                return False
        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return etree.tostring(self.serialize(etree.Element(self.__class__.__name__, nsmap={'w':namespaces['w']})), pretty_print=True)
    __str__ = __repr__

    def serialize_borders(self, bdr):
        for edge in border_edges:
            e = bdr.makeelement(w(edge))
            padding = getattr(self, 'padding_' + edge)
            if padding > 0:
                e.set(w('space'), str(padding))
            width = getattr(self, 'border_%s_width' % edge)
            bstyle = getattr(self, 'border_%s_style' % edge)
            if width > 0 and bstyle != 'none':
                e.set(w('val'), bstyle)
                e.set(w('sz'), str(width))
                e.set(w('color'), getattr(self, 'border_%s_color' % edge))
            if e.attrib:
                bdr.append(e)
        return bdr

LINE_STYLES = {
    'none'  : 'none',
    'hidden': 'none',
    'dotted': 'dotted',
    'dashed': 'dashed',
    'solid' : 'single',
    'double': 'double',
    'groove': 'threeDEngrave',
    'ridge' : 'threeDEmboss',
    'inset' : 'inset',
    'outset': 'outset',
}

def w(x):
    return '{%s}%s' % (namespaces['w'], x)

class TextStyle(DOCXStyle):

    ALL_PROPS = ('font_family', 'font_size', 'bold', 'italic', 'color',
                 'background_color', 'underline', 'strike', 'dstrike', 'caps',
                 'shadow', 'small_caps', 'spacing', 'vertical_align') + tuple(
        x%edge for edge in border_edges for x in border_props)

    def __init__(self, css):
        self.font_family = css_font_family_to_docx(css['font-family'])
        try:
            self.font_size = max(0, int(float(css['font-size']) * 2))  # stylizer normalizes all font sizes into pts
        except (ValueError, TypeError, AttributeError):
            self.font_size = None

        fw = css['font-weight']
        self.bold = fw.lower() in {'bold', 'bolder'} or int_or_zero(fw) >= 700
        self.italic = css['font-style'].lower() in {'italic', 'oblique'}
        self.color = convert_color(css['color'])
        self.background_color = convert_color(css.backgroundColor)
        td = set((css.effective_text_decoration or '').split())
        self.underline = 'underline' in td
        self.dstrike = 'line-through' in td and 'overline' in td
        self.strike = not self.dstrike and 'line-through' in td
        self.text_transform = css['text-transform']  # TODO: If lowercase or capitalize, transform the actual text
        self.caps = self.text_transform == 'uppercase'
        self.small_caps = css['font-variant'].lower() in {'small-caps', 'smallcaps'}
        self.shadow = css['text-shadow'] not in {'none', None}
        try:
            self.spacing = int(float(css['letter-spacing']) * 20)
        except (ValueError, TypeError, AttributeError):
            self.spacing = None
        self.vertical_align = css['vertical-align']
        for edge in border_edges:
            # In DOCX padding can only be a positive integer
            setattr(self, 'padding_' + edge, max(0, int(css['padding-' + edge])))
            val = min(96, max(2, int({'thin':0.2, 'medium':1, 'thick':2}.get(css['border-%s-width' % edge], 0) * 8)))
            setattr(self, 'border_%s_width' % edge, val)
            setattr(self, 'border_%s_color' % edge, convert_color(css['border-%s-color' % edge]))
            setattr(self, 'border_%s_style' %  edge, LINE_STYLES.get(css['border-%s-style' % edge].lower(), 'none'))

        DOCXStyle.__init__(self)

    def serialize(self, style):
        style.append(style.makeelement(w('rFonts'), **{
            w(k):self.font_family for k in 'ascii cs eastAsia hAnsi'.split()}))
        for suffix in ('', 'Cs'):
            style.append(style.makeelement(w('sz' + suffix), **{w('val'):str(self.font_size)}))
            style.append(style.makeelement(w('b' + suffix), **{w('val'):('on' if self.bold else 'off')}))
            style.append(style.makeelement(w('i' + suffix), **{w('val'):('on' if self.italic else 'off')}))
        if self.color:
            style.append(style.makeelement(w('color'), **{w('val'):str(self.color)}))
        if self.background_color:
            style.append(style.makeelement(w('shd'), **{w('val'):str(self.background_color)}))
        if self.underline:
            style.append(style.makeelement(w('u'), **{w('val'):'single'}))
        if self.dstrike:
            style.append(style.makeelement(w('dstrike'), **{w('val'):'on'}))
        elif self.strike:
            style.append(style.makeelement(w('strike'), **{w('val'):'on'}))
        if self.caps:
            style.append(style.makeelement(w('caps'), **{w('val'):'on'}))
        if self.small_caps:
            style.append(style.makeelement(w('smallCaps'), **{w('val'):'on'}))
        if self.shadow:
            style.append(style.makeelement(w('shadow'), **{w('val'):'on'}))
        if self.spacing is not None:
            style.append(style.makeelement(w('spacing'), **{w('val'):str(self.spacing)}))
        if isinstance(self.vertical_align, (int, float)):
            val = int(self.vertical_align * 2)
            style.append(style.makeelement(w('position'), **{w('val'):str(val)}))
        elif isinstance(self.vertical_align, basestring):
            val = {'top':'superscript', 'text-top':'superscript', 'sup':'superscript', 'bottom':'subscript', 'text-bottom':'subscript', 'sub':'subscript'}.get(
                self.vertical_align.lower())
            if val:
                style.append(style.makeelement(w('vertAlign'), **{w('val'):val}))

        bdr = self.serialize_borders(style.makeelement(w('bdr')))
        if len(bdr):
            style.append(bdr)

        return style


class BlockStyle(DOCXStyle):

    ALL_PROPS = tuple(
        'text_align page_break_before keep_lines css_text_indent text_indent line_height css_line_height background_color'.split() +
        ['margin_' + edge for edge in border_edges] +
        ['css_margin_' + edge for edge in border_edges] +
        [x%edge for edge in border_edges for x in border_props]
    )

    def __init__(self, css, html_block, is_first_block=False):
        self.page_break_before = html_block.tag.endswith('}body') or (not is_first_block and css['page-break-before'] == 'always')
        self.keep_lines = css['page-break-inside'] == 'avoid'
        for edge in border_edges:
            # In DOCX padding can only be a positive integer
            setattr(self, 'padding_' + edge, max(0, int(css['padding-' + edge])))
            # In DOCX margin must be a positive integer in twips (twentieth of a point)
            setattr(self, 'margin_' + edge, max(0, int(css['margin-' + edge] * 20)))
            setattr(self, 'css_margin_' + edge, css._style.get('margin-' + edge, ''))
            val = min(96, max(2, int({'thin':0.2, 'medium':1, 'thick':2}.get(css['border-%s-width' % edge], 0) * 8)))
            setattr(self, 'border_%s_width' % edge, val)
            setattr(self, 'border_%s_color' % edge, convert_color(css['border-%s-color' % edge]))
            setattr(self, 'border_%s_style' %  edge, LINE_STYLES.get(css['border-%s-style' % edge].lower(), 'none'))
        self.text_indent = max(0, int(css['text-indent'] * 20))
        self.css_text_indent = css._get('text-indent')
        self.line_height = max(0, int(css['line-height'] * 20))
        self.css_line_height = css._get('line-height')
        self.background_color = convert_color(css['background-color'])
        self.text_align = {'start':'left', 'left':'left', 'end':'right', 'right':'right', 'center':'center', 'justify':'both', 'centre':'center'}.get(
            css['text-align'].lower(), 'left')

        DOCXStyle.__init__(self)

    def serialize(self, style):
        spacing = style.makeelement(w('spacing'))
        for edge, attr in {'top':'before', 'bottom':'after'}.iteritems():
            css_val, css_unit = parse_css_length(getattr(self, 'css_margin_' + edge))
            if css_unit in ('em', 'ex'):
                lines = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
                if lines > 0:
                    spacing.set(w(attr + 'Lines'), str(lines))
            else:
                val = getattr(self, 'margin_' + edge)
                if val > 0:
                    spacing.set(w(attr), str(val))
        if self.css_line_height != 'normal':
            try:
                css_val, css_unit = float(self.css_line_height), 'ratio'
            except Exception:
                css_val, css_unit = parse_css_length(self.css_line_height)
            if css_unit in {'em', 'ex', '%', 'ratio'}:
                mult = {'ex':0.5, '%':0.01}.get(css_unit, 1)
                val = int(css_val * 240 * mult)
                spacing.set(w('line'), str(val))
            else:
                spacing.set(w('line'), str(self.line_height))
                spacing.set(w('lineRule', 'exactly'))

        if spacing.attrib:
            style.append(spacing)

        ind = style.makeelement(w('ind'))
        for edge in ('left', 'right'):
            css_val, css_unit = parse_css_length(getattr(self, 'css_margin_' + edge))
            if css_unit in ('em', 'ex'):
                chars = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
                if chars > 0:
                    ind.set(w(edge + 'Chars'), str(chars))
            else:
                val = getattr(self, 'margin_' + edge)
                if val > 0:
                    ind.set(w(attr), str(val))
        css_val, css_unit = parse_css_length(self.css_text_indent)
        if css_unit in ('em', 'ex'):
            chars = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
            if chars > 0:
                ind.set('firstLineChars', str(chars))
        else:
            val = self.text_indent
            if val > 0:
                ind.set('firstLine', str(val))
        if ind.attrib:
            style.append(ind)

        if self.background_color:
            shd = style.makeelement(w('shd'))
            style.append(shd)
            shd.set(w('val'), 'clear'), shd.set(w('fill'), self.background_color), shd.set(w('color'), 'auto')

        pbdr = self.serialize_borders(style.makeelement(w('pBdr')))
        if len(pbdr):
            style.append(pbdr)
        jc = style.makeelement(w('jc'))
        jc.set(w('val'), self.text_align)
        style.append(jc)
        if self.page_break_before:
            style.append(style.makeelement(w('pageBreakBefore'), **{w('val'):'on'}))
        if self.keep_lines:
            style.append(style.makeelement(w('keepLines'), **{w('val'):'on'}))
        return style


class StylesManager(object):

    def __init__(self):
        self.block_styles, self.text_styles = {}, {}

    def create_text_style(self, css_style):
        ans = TextStyle(css_style)
        existing = self.text_styles.get(ans, None)
        if existing is None:
            self.text_styles[ans] = ans
        else:
            ans = existing
        return ans

    def create_block_style(self, css_style, html_block, is_first_block=False):
        ans = BlockStyle(css_style, html_block, is_first_block=is_first_block)
        existing = self.block_styles.get(ans, None)
        if existing is None:
            self.block_styles[ans] = ans
        else:
            ans = existing
        return ans
