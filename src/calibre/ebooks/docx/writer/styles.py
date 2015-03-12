#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import Counter, defaultdict
from operator import attrgetter

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

def w(x):
    return '{%s}%s' % (namespaces['w'], x)

def makeelement(parent, name, **attrs):
    return parent.makeelement(w(name), **{w(k):v for k, v in attrs.iteritems()})

def bmap(x):
    return 'on' if x else 'off'

class DOCXStyle(object):

    ALL_PROPS = ()
    TYPE = 'paragraph'

    def __init__(self):
        self._hash = hash(tuple(
            getattr(self, x) for x in self.ALL_PROPS))
        self.id = self.name = None
        self.next_style = None

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

    def serialize_borders(self, bdr, normal_style):
        for edge in border_edges:
            e = bdr.makeelement(w(edge))
            padding = getattr(self, 'padding_' + edge)
            if (self is normal_style and padding > 0) or (padding != getattr(normal_style, 'padding_' + edge)):
                e.set(w('space'), str(padding))
            width = getattr(self, 'border_%s_width' % edge)
            bstyle = getattr(self, 'border_%s_style' % edge)
            if (self is normal_style and width > 0 and bstyle != 'none'
                    ) or width != getattr(normal_style, 'border_%s_width' % edge
                    ) or bstyle != getattr(normal_style, 'border_%s_style' % edge):
                e.set(w('val'), bstyle)
                e.set(w('sz'), str(width))
                e.set(w('color'), getattr(self, 'border_%s_color' % edge))
            if e.attrib:
                bdr.append(e)
        return bdr

    def serialize(self, styles, normal_style):
        style = makeelement(styles, 'style', styleId=self.id, type=self.TYPE)
        style.append(makeelement(style, 'name', val=self.name))
        if self is normal_style:
            style.set(w('default'), '1')
            style.append(makeelement(style, 'qFormat'))
        else:
            style.append(makeelement(style, 'basedOn', val=normal_style.id))
        styles.append(style)
        return style

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

class TextStyle(DOCXStyle):

    ALL_PROPS = ('font_family', 'font_size', 'bold', 'italic', 'color',
                 'background_color', 'underline', 'strike', 'dstrike', 'caps',
                 'shadow', 'small_caps', 'spacing', 'vertical_align') + tuple(
        x%edge for edge in border_edges for x in border_props)
    TYPE = 'character'

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
            setattr(self, 'border_%s_style' % edge, LINE_STYLES.get(css['border-%s-style' % edge].lower(), 'none'))

        DOCXStyle.__init__(self)

    def serialize(self, styles, normal_style):
        style = DOCXStyle.serialize(self, styles, normal_style)

        if self is normal_style or self.font_family != normal_style.font_family:
            style.append(makeelement(
                style, 'rFonts', **{k:self.font_family for k in 'ascii cs eastAsia hAnsi'.split()}))

        for name, attr, vmap in (('sz', 'font_size', str), ('b', 'bold', bmap), ('i', 'italic', bmap)):
            val = getattr(self, attr)
            if self is normal_style or getattr(normal_style, attr) != val:
                for suffix in ('', 'Cs'):
                    style.append(makeelement(style, 'sz' + suffix, val=vmap(val)))

        def check_attr(attr):
            val = getattr(self, attr)
            return (self is normal_style and val is not False and val is not None) or (val != getattr(normal_style, attr))

        if check_attr('color'):
            style.append(makeelement(style, 'color', val=self.color or 'auto'))
        if check_attr('background_color'):
            style.append(makeelement(style, 'shd', fill=self.background_color or 'auto'))
        if check_attr('underline'):
            style.append(makeelement(style, 'u', val='single' if self.underline else 'none'))
        if check_attr('dstrike'):
            style.append(makeelement(style, 'dstrike', val=bmap(self.dstrike)))
        if check_attr('strike'):
            style.append(makeelement(style, 'strike', val=bmap(self.strike)))
        if check_attr('caps'):
            style.append(makeelement(style, 'caps', val=bmap(self.caps)))
        if check_attr('small_caps'):
            style.append(makeelement(style, 'smallCaps', val=bmap(self.small_caps)))
        if check_attr('shadow'):
            style.append(makeelement(style, 'shadow', val=bmap(self.shadow)))
        if check_attr('spacing'):
            style.append(makeelement(style, 'spacing', val=str(self.spacing or 0)))
        if isinstance(self.vertical_align, (int, float)):
            val = int(self.vertical_align * 2)
            style.append(makeelement(style, 'position', val=str(val)))
        elif isinstance(self.vertical_align, basestring):
            val = {'top':'superscript', 'text-top':'superscript', 'sup':'superscript', 'bottom':'subscript', 'text-bottom':'subscript', 'sub':'subscript'}.get(
                self.vertical_align.lower())
            if val:
                style.append(makeelement(style, 'vertAlign', val=val))

        bdr = self.serialize_borders(makeelement(style, 'bdr', normal_style))
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

    def serialize(self, styles, normal_style):
        style = DOCXStyle.serialize(self, styles, normal_style)

        spacing = makeelement(style, 'spacing')
        for edge, attr in {'top':'before', 'bottom':'after'}.iteritems():
            getter = attrgetter('css_margin_' + edge)
            css_val, css_unit = parse_css_length(getter(self))
            if css_unit in ('em', 'ex'):
                lines = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
                if (self is normal_style and lines > 0) or getter(self) != getter(normal_style):
                    spacing.set(w(attr + 'Lines'), str(lines))
            else:
                getter = attrgetter('margin_' + edge)
                val = getter(self)
                if (self is normal_style and val > 0) or val != getter(normal_style):
                    spacing.set(w(attr), str(val))

        if (self is normal_style and self.css_line_height != 'normal') or self.css_line_height != normal_style.css_line_height:
            try:
                css_val, css_unit = float(self.css_line_height), 'ratio'
            except Exception:
                css_val, css_unit = parse_css_length(self.css_line_height)
            if css_unit in {'em', 'ex', '%', 'ratio'}:
                mult = {'ex':0.5, '%':0.01}.get(css_unit, 1)
                val = int(css_val * 240 * mult)
                spacing.set(w('line'), str(val))
            else:
                spacing.set(w('line'), (0 if self.css_line_height == 'normal' else str(self.line_height)))
                spacing.set(w('lineRule', 'exactly'))

        if spacing.attrib:
            style.append(spacing)

        ind = makeelement(style, 'ind')
        for edge in ('left', 'right'):
            getter = attrgetter('css_margin_' + edge)
            css_val, css_unit = parse_css_length(getter(self))
            if css_unit in ('em', 'ex'):
                chars = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
                if (self is normal_style and chars > 0) or getter(self) != getter(normal_style):
                    ind.set(w(edge + 'Chars'), str(chars))
            else:
                getter = attrgetter('margin_' + edge)
                val = getter(self)
                if (self is normal_style and val > 0) or val != getter(normal_style):
                    ind.set(w(edge), str(val))
        css_val, css_unit = parse_css_length(self.css_text_indent)
        if css_unit in ('em', 'ex'):
            chars = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
            if (self is normal_style and chars > 0) or self.css_text_indent != normal_style.css_text_indent:
                ind.set('firstLineChars', str(chars))
        else:
            val = self.text_indent
            if (self is normal_style and val > 0) or self.text_indent != normal_style.text_indent:
                ind.set('firstLine', str(val))
        if ind.attrib:
            style.append(ind)

        if (self is normal_style and self.background_color) or self.background_color != normal_style.background_color:
            makeelement(style, 'shd', val='clear', color='auto', fill=self.background_color or 'auto')

        pbdr = self.serialize_borders(style.makeelement(w('pBdr')), normal_style)
        if len(pbdr):
            style.append(pbdr)

        if self is normal_style or self.text_align != normal_style.text_align:
            style.append(makeelement(style, 'jc', val=self.text_align))

        if (self is normal_style and self.page_break_before) or self.page_break_before != normal_style.page_break_before:
            style.append(makeelement(style, 'pageBreakBefore', bmap(self.page_break_before)))
        if (self is normal_style and self.keep_lines) or self.keep_lines != normal_style.keep_lines:
            style.append(makeelement(style, 'keepLines', bmap(self.keep_lines)))

        if self is not normal_style and self.next_style is not None:
            style.append(style.makeelement(w('next'), **{w('val'):self.next_style}))
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

    def finalize(self, blocks):
        block_counts, run_counts = Counter(), Counter()
        block_rmap, run_rmap = defaultdict(list), defaultdict(list)
        for block in blocks:
            block_counts[block.style] += 1
            block_rmap[block.style].append(block)
            for run in block.runs:
                run_counts[run.style] += 1
                run_rmap[run.style].append(run)
        for i, (block_style, count) in enumerate(block_counts.most_common()):
            if i == 0:
                normal_block_style = block_style
                normal_block_style.id = 'BlockNormal'
                normal_block_style.name = 'Normal'
            else:
                block_style.id = 'Block%d' % i
                block_style.name = 'Paragraph %d' % i
        for i, (text_style, count) in enumerate(run_counts.most_common()):
            if i == 0:
                normal_text_style = text_style
                normal_text_style.id = 'TextNormal'
                normal_text_style.name = 'Normal'
            else:
                block_style.id = 'Text%d' % i
                block_style.name = 'Text %d' % i
