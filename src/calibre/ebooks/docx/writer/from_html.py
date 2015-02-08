#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml import etree
from lxml.builder import ElementMaker

from calibre.ebooks.docx.names import namespaces
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

    ws_pat = None

    def __init__(self, style):
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

style_cache = {}

class Block(object):

    def __init__(self):
        self.runs = []

    def add_text(self, text, style, ignore_leading_whitespace=False):
        ts = TextStyle(style)
        ws = style['white-space']
        if self.runs and ts == self.runs[-1].style:
            run = self.runs[-1]
        else:
            run = TextRun(ts)
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

        for body in XPath('//h:body')(item.data):
            b = Block()
            self.blocks.append(b)
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
                b = Block()
                self.blocks.append(b)
                self.process_block(child, b, stylizer)
            else:
                self.process_inline(child, self.blocks[-1], stylizer)

        if ignore_tail is False and html_block.tail and html_block.tail.strip():
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
                        E.rFonts(),
                    )
                ),
                E.pPrDefault(
                    E.pPr(
                    )
                )
            )
        )
