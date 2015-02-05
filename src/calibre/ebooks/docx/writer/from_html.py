#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml import etree

from calibre.ebooks.docx.writer.utils import convert_color, int_or_zero
from calibre.ebooks.oeb.stylizer import Stylizer as Sz, Style as St
from calibre.ebooks.oeb.base import XPath, barename

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

class TextStyle(object):

    ALL_PROPS = ('font_family', 'font_size', 'bold', 'italic', 'color',
                 'background_color', 'underline', 'strike', 'dstrike', 'caps',
                 'shadow', 'small_caps', 'spacing', 'vertical-align')

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

    def __hash__(self):
        return hash(tuple(
            getattr(self, x) for x in self.ALL_PROPS))

    def __eq__(self, other):
        for x in self.ALL_PROPS:
            if getattr(self, x) != getattr(other, x, None):
                return False
        return True

    def __ne__(self, other):
        return not self == other

class LineBreak(object):

    def __init__(self, clear='none'):
        self.clear = clear

class TextRun(object):

    def __init__(self, style):
        self.style = style
        self.texts = []

    def add_text(self, text, preserve_whitespace):
        self.texts.append((text, preserve_whitespace))

    def add_break(self, clear='none'):
        self.texts.append(LineBreak(clear=clear))

style_cache = {}

class Block(object):

    def __init__(self):
        self.runs = []

    def add_text(self, text, style):
        ts = TextStyle(style)
        ws = style['white-space']
        if self.runs and ts == self.runs[-1].style:
            run = self.runs[-1]
        else:
            run = TextRun(ts)
        if ws == 'pre-line':
            for text in text.splitlines():
                run.add_text(text, False)
                run.add_break()
        else:
            run.add_text(text, ws in {'pre', 'pre-wrap'})

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

    def process_item(self, item):
        stylizer = Stylizer(item.data, item.href, self.oeb, self.opts, self.opts.output_profile)

        for body in XPath('//h:body')(item.data):
            b = Block()
            self.blocks.append(b)
            self.process_block(body, b, stylizer, ignore_tail=True)

    def process_block(self, html_block, docx_block, stylizer, ignore_tail=False):
        if html_block.text:
            docx_block.add_text(html_block.text, stylizer.style(html_block))

        for child in html_block.iterchildren(etree.Element):
            tag = barename(child.tag)
            style = stylizer.style(child)
            display = style.get('display', 'inline')
            if tag == 'img':
                return  # TODO: Handle images
            if display == 'block':
                b = Block()
                self.blocks.append(b)
                self.process_block(child, b, stylizer)
            else:
                self.process_inline(child, self.blocks[-1], stylizer)

        if ignore_tail is False and html_block.tail:
            b = docx_block
            if b is not self.blocks[-1]:
                b = Block()
                self.blocks.append(b)
            b.add_text(html_block.tail, stylizer.style(html_block.getparent()))

    def process_inline(self, html_child, docx_block, stylizer):
        tag = barename(html_child.tag)
        if tag == 'img':
            return  # TODO: Handle images
        style = stylizer.style(html_child)
        if html_child.text:
            docx_block.add_text(html_child.text, style)
        for child in html_child.iterchildren(etree.Element):
            style = stylizer.style(child)
            display = style.get('display', 'inline')
            if display == 'block':
                b = Block()
                self.blocks.append(b)
                self.process_block(child, b, stylizer)
            else:
                self.process_inline(child, self.blocks[-1], stylizer)

        if html_child.tail:
            docx_block.add_text(html_child.tail, stylizer.style(html_child.getparent()))


