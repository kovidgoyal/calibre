#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml import etree
from lxml.builder import ElementMaker

from calibre.ebooks import parse_css_length
from calibre.ebooks.docx.names import namespaces
from calibre.ebooks.docx.writer.utils import convert_color, int_or_zero
from calibre.ebooks.oeb.stylizer import Stylizer as Sz, Style as St
from calibre.ebooks.oeb.base import XPath, barename
from tinycss.color3 import parse_color_string

class Style(St):

    def __init__(self, *args, **kwargs):
        St.__init__(self, *args, **kwargs)
        self._letterSpacing = None

    @property
    def letterSpacing(self):
        if self._letterSpacing is not None:
            val = self._get('letter-spacing')
            if val == 'normal':
                self._letterSpacing = val
            else:
                self._letterSpacing = self._unit_convert(val)
        return self._letterSpacing

class Stylizer(Sz):

    def style(self, element):
        try:
            return self._styles[element]
        except KeyError:
            return Style(element, self)

border_edges = ('left', 'top', 'right', 'bottom')
border_props = ('padding_%s', 'border_%s_width', 'border_%s_style', 'border_%s_color')

def css_color_to_rgb(value):
    if not value:
        return
    if value.lower() == 'currentcolor':
        return 'auto'
    val = parse_color_string(value)
    if val is None:
        return
    if val.alpha < 0.01:
        return
    return '%02X%02X%02X' % (int(val.red * 255), int(val.green * 255), int(val.blue * 255))

class DOCXStyle(object):

    ALL_PROPS = ()

    def __init__(self):
        self.update_hash()

    def __hash__(self):
        return self._hash

    def update_hash(self):
        self._hash = hash(tuple(
            getattr(self, x) for x in self.ALL_PROPS))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return etree.tostring(self.serialize(etree.Element(w('style'), nsmap={'w':namespaces['w']})), pretty_print=True)
    __str__ = __repr__

LINE_STYLES = {
    'none': 'none',
    'hidden': 'none',
    'dotted': 'dotted',
    'dashed': 'dashed',
    'solid': 'single',
    'double': 'double',
    'groove': 'threeDEngrave',
    'ridge': 'threeDEmboss',
    'inset': 'inset',
    'outset': 'outset',
}

def w(x):
    return '{%s}%s' % (namespaces['w'], x)

class TextStyle(DOCXStyle):

    ALL_PROPS = ('font_family', 'font_size', 'bold', 'italic', 'color',
                 'background_color', 'underline', 'strike', 'dstrike', 'caps',
                 'shadow', 'small_caps', 'spacing', 'vertical_align')

    def __init__(self, css):
        self.font_family = css['font-family']  # TODO: Resolve multiple font families and generic font family names
        try:
            self.font_size = int(float(css['font-size']) * 2)  # stylizer normalizes all font sizes into pts
        except (ValueError, TypeError, AttributeError):
            self.font_size = None

        fw = self.font_weight = css['font-weight']
        self.bold = fw in {'bold', 'bolder'} or int_or_zero(fw) >= 700
        self.font_style = css['font-style']
        self.italic = self.font_style in {'italic', 'oblique'}
        self.color = convert_color(css['color'])
        self.background_color = convert_color(css.backgroundColor)
        td = set((css.effective_text_decoration or '').split())
        self.underline = 'underline' in td
        self.dstrike = 'line-through' in td and 'overline' in td
        self.strike = not self.dstrike and 'line-through' in td
        self.text_transform = css['text-transform']  # TODO: If lowercase or capitalize, transform the actual text
        self.caps = self.text_transform == 'uppercase'
        self.shadow = css['text-shadow'] not in {'none', None}
        self.small_caps = css['font-variant'] in {'small-caps', 'smallcaps'}
        try:
            self.spacing = int(float(css['letter-spacing']) * 20)
        except (ValueError, TypeError, AttributeError):
            self.spacing = None
        self.vertical_align = {'sub':'subscript', 'super':'superscript'}.get((css['vertical-align'] or '').lower(), 'baseline')
        # TODO: Borders and padding

        DOCXStyle.__init__(self)

class BlockStyle(DOCXStyle):

    ALL_PROPS = tuple(
        'text_align page_break_before keep_lines keep_next css_text_indent text_indent line_height css_line_height background_color'.split()
        + ['margin_' + edge for edge in border_edges]
        + ['css_margin_' + edge for edge in border_edges]
        + [x%edge for edge in border_edges for x in border_props]
    )

    def __init__(self, css, html_block, is_first_block=False):
        self.page_break_before = html_block.tag.endswith('}body') or (not is_first_block and css['page-break-before'] == 'always')
        self.keep_lines = css['page-break-inside'] == 'avoid'
        # TODO: Ensure that only the last docx block for this html block has the correct value for keep next
        self.keep_next = css['page-break-after'] == 'avoid'
        for edge in border_edges:
            # In DOCX padding can only be a positive integer
            setattr(self, 'padding_' + edge, max(0, int(css['padding-' + edge])))
            # In DOCX margin must be a positive integer in twips (twentieth of a point)
            setattr(self, 'margin_' + edge, max(0, int(css['margin-' + edge] * 20)))
            setattr(self, 'css_margin_' + edge, css._style.get('margin-' + edge, ''))
            val = min(96, max(2, int({'thin':0.2, 'medium':1, 'thick':2}.get(css['border-%s-width' % edge], 0) * 8)))
            setattr(self, 'border_%s_width' % edge, val)
            setattr(self, 'border_%s_color' % edge, css_color_to_rgb(css['border-%s-color' % edge]))
            setattr(self, 'border_%s_style' %  edge, LINE_STYLES.get(css['border-%s-style' % edge].lower(), 'none'))
        self.text_indent = max(0, int(css['text-indent'] * 20))
        self.css_text_indent = css._get('text-indent')
        self.line_height = max(0, int(css['line-height'] * 20))
        self.css_line_height = css._get('line-height')
        self.background_color = css_color_to_rgb(css['background-color'])
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

        pbdr = style.makeelement(w('pBdr'))
        for edge in border_edges:
            e = pbdr.makeelement(w(edge))
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
                pbdr.append(e)
        if len(pbdr):
            style.append(pbdr)
        jc = style.makeelement(w('jc'))
        jc.set(w('val'), self.text_align)
        style.append(jc)
        if self.page_break_before:
            style.append(style.makeelement(w('pageBreakBefore'), **{w('val'):'on'}))
        if self.keep_lines:
            style.append(style.makeelement(w('keepLines'), **{w('val'):'on'}))
        if self.keep_next:
            style.append(style.makeelement(w('keepNext'), **{w('val'):'on'}))
        return style


class LineBreak(object):

    def __init__(self, clear='none'):
        self.clear = clear

class TextRun(object):

    ws_pat = None

    def __init__(self, style, first_html_parent):
        self.first_html_parent = first_html_parent
        if self.ws_pat is None:
            TextRun.ws_pat = self.ws_pat = re.compile(r'\s+')
        self.style = style
        self.texts = []

    def add_text(self, text, preserve_whitespace):
        if not preserve_whitespace:
            text = self.ws_pat.sub(' ', text)
            if text.strip() != text:
                # If preserve_whitespace is False, Word ignores leading and
                # trailing whitespace
                preserve_whitespace = True
        self.texts.append((text, preserve_whitespace))

    def add_break(self, clear='none'):
        self.texts.append(LineBreak(clear=clear))

    def serialize(self, p):
        r = p.makeelement('{%s}r' % namespaces['w'])
        p.append(r)
        for text, preserve_whitespace in self.texts:
            t = r.makeelement('{%s}t' % namespaces['w'])
            r.append(t)
            t.text = text or ''
            if preserve_whitespace:
                t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

class Block(object):

    def __init__(self, html_block, style, is_first_block=False):
        self.html_block = html_block
        self.style = BlockStyle(style, html_block, is_first_block=is_first_block)
        self.runs = []

    def add_text(self, text, style, ignore_leading_whitespace=False, html_parent=None):
        ts = TextStyle(style)
        ws = style['white-space']
        if self.runs and ts == self.runs[-1].style:
            run = self.runs[-1]
        else:
            run = TextRun(ts, html_parent or self.html_block)
            self.runs.append(run)
        preserve_whitespace = ws in {'pre', 'pre-wrap'}
        if ignore_leading_whitespace and not preserve_whitespace:
            text = text.lstrip()
        if ws == 'pre-line':
            for text in text.splitlines():
                run.add_text(text, False)
                run.add_break()
        else:
            run.add_text(text, preserve_whitespace)

    def serialize(self, body):
        p = body.makeelement('{%s}p' % namespaces['w'])
        body.append(p)
        for run in self.runs:
            run.serialize(p)

class Convert(object):

    def __init__(self, oeb, docx):
        self.oeb, self.docx = oeb, docx
        self.log, self.opts = docx.log, docx.opts

        self.blocks = []

    def __call__(self):
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
        SVGRasterizer()(self.oeb, self.opts)

        for item in self.oeb.spine:
            self.process_item(item)

        self.write()

    def process_item(self, item):
        stylizer = Stylizer(item.data, item.href, self.oeb, self.opts, self.opts.output_profile)

        is_first_block = True
        for body in XPath('//h:body')(item.data):
            b = Block(body, stylizer.style(body), is_first_block=is_first_block)
            self.blocks.append(b)
            is_first_block = False
            self.process_block(body, b, stylizer, ignore_tail=True)

    def process_block(self, html_block, docx_block, stylizer, ignore_tail=False):
        if html_block.text:
            docx_block.add_text(html_block.text, stylizer.style(html_block), ignore_leading_whitespace=True)

        for child in html_block.iterchildren(etree.Element):
            tag = barename(child.tag)
            style = stylizer.style(child)
            display = style.get('display', 'inline')
            if tag == 'img':
                return  # TODO: Handle images
            if display == 'block':
                b = Block(child, style)
                self.blocks.append(b)
                self.process_block(child, b, stylizer)
            else:
                self.process_inline(child, self.blocks[-1], stylizer)

        if ignore_tail is False and html_block.tail and html_block.tail.strip():
            b = docx_block
            if b is not self.blocks[-1]:
                b = Block(html_block, stylizer.style(html_block))
                self.blocks.append(b)
            b.add_text(html_block.tail, stylizer.style(html_block.getparent()))

    def process_inline(self, html_child, docx_block, stylizer):
        tag = barename(html_child.tag)
        if tag == 'img':
            return  # TODO: Handle images
        style = stylizer.style(html_child)
        if html_child.text:
            docx_block.add_text(html_child.text, style, html_parent=html_child)
        for child in html_child.iterchildren(etree.Element):
            style = stylizer.style(child)
            display = style.get('display', 'inline')
            if display == 'block':
                b = Block(child, style)
                self.blocks.append(b)
                self.process_block(child, b, stylizer)
            else:
                self.process_inline(child, self.blocks[-1], stylizer)

        if html_child.tail:
            self.blocks[-1].add_text(html_child.tail, stylizer.style(html_child.getparent()), html_parent=html_child.getparent())

    def write(self):
        dn = {k:v for k, v in namespaces.iteritems() if k in {'w', 'r', 'm', 've', 'o', 'wp', 'w10', 'wne'}}
        E = ElementMaker(namespace=dn['w'], nsmap=dn)
        self.docx.document = doc = E.document()
        body = E.body()
        doc.append(body)
        for block in self.blocks:
            block.serialize(body)

        dn = {k:v for k, v in namespaces.iteritems() if k in 'wr'}
        E = ElementMaker(namespace=dn['w'], nsmap=dn)
        self.docx.styles = E.styles(
            E.docDefaults(
                E.rPrDefault(
                    E.rPr(
                        E.rFonts(**{w('asciiTheme'):"minorHAnsi", w('eastAsiaTheme'):"minorEastAsia", w('hAnsiTheme'):"minorHAnsi", w('cstheme'):"minorBidi"}),
                        E.sz(**{w('val'):'22'}),
                        E.szCs(**{w('val'):'22'}),
                        E.lang(**{w('val'):'en-US', w('eastAsia'):"en-US", w('bidi'):"ar-SA"})
                    )
                ),
                E.pPrDefault(
                    E.pPr(
                        E.spacing(**{w('after'):"0", w('line'):"276", w('lineRule'):"auto"})
                    )
                )
            )
        )
