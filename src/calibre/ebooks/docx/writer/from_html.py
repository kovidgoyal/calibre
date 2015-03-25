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
from calibre.ebooks.docx.writer.styles import w, StylesManager
from calibre.ebooks.docx.writer.images import ImagesManager
from calibre.ebooks.oeb.stylizer import Stylizer as Sz, Style as St
from calibre.ebooks.oeb.base import XPath, barename
from calibre.ebooks.pdf.render.common import PAPER_SIZES

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
        self.texts.append((None, clear))

    def add_image(self, drawing):
        self.texts.append((drawing, None))

    def serialize(self, p):
        r = p.makeelement(w('r'))
        p.append(r)
        rpr = r.makeelement(w('rPr'))
        rpr.append(rpr.makeelement(w('rStyle'), **{w('val'):self.style.id}))
        r.append(rpr)
        for text, preserve_whitespace in self.texts:
            if text is None:
                r.append(r.makeelement(w('br'), **{w('clear'):preserve_whitespace}))
            elif hasattr(text, 'xpath'):
                r.append(text)
            else:
                t = r.makeelement(w('t'))
                r.append(t)
                t.text = text or ''
                if preserve_whitespace:
                    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

    def is_empty(self):
        if not self.texts:
            return True
        if len(self.texts) == 1 and self.texts[0] == ('', False):
            return True
        return False

class Block(object):

    def __init__(self, styles_manager, html_block, style, is_first_block=False):
        self.html_block = html_block
        self.html_style = style
        self.style = styles_manager.create_block_style(style, html_block, is_first_block=is_first_block)
        self.styles_manager = styles_manager
        self.keep_next = False
        self.runs = []

    def add_text(self, text, style, ignore_leading_whitespace=False, html_parent=None, is_parent_style=False):
        ts = self.styles_manager.create_text_style(style, is_parent_style=is_parent_style)
        ws = style['white-space']
        if self.runs and ts == self.runs[-1].style:
            run = self.runs[-1]
        else:
            run = TextRun(ts, self.html_block if html_parent is None else html_parent)
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

    def add_break(self, clear='none'):
        if self.runs:
            run = self.runs[-1]
        else:
            run = TextRun(self.styles_manager.create_text_style(self.html_style), self.html_block)
            self.runs.append(run)
        run.add_break(clear=clear)

    def add_image(self, drawing):
        if self.runs:
            run = self.runs[-1]
        else:
            run = TextRun(self.styles_manager.create_text_style(self.html_style), self.html_block)
            self.runs.append(run)
        run.add_image(drawing)

    def serialize(self, body):
        p = body.makeelement(w('p'))
        body.append(p)
        ppr = p.makeelement(w('pPr'))
        p.append(ppr)
        if self.keep_next:
            ppr.append(ppr.makeelement(w('keepNext')))
        ppr.append(ppr.makeelement(w('pStyle'), **{w('val'):self.style.id}))
        for run in self.runs:
            run.serialize(p)

    def is_empty(self):
        for run in self.runs:
            if not run.is_empty():
                return False
        return True

class Convert(object):

    def __init__(self, oeb, docx):
        self.oeb, self.docx = oeb, docx
        self.log, self.opts = docx.log, docx.opts

        self.blocks = []

    def __call__(self):
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
        self.svg_rasterizer = SVGRasterizer()
        self.svg_rasterizer(self.oeb, self.opts)

        self.styles_manager = StylesManager()
        self.images_manager = ImagesManager(self.oeb, self.docx.document_relationships)

        try:
            for item in self.oeb.spine:
                self.process_item(item)

            self.styles_manager.finalize(self.blocks)
            self.write()
        finally:
            self.images_manager.cleanup()

    def process_item(self, item):
        stylizer = self.svg_rasterizer.stylizer_cache.get(item)
        if stylizer is None:
            stylizer = Stylizer(item.data, item.href, self.oeb, self.opts, self.opts.output_profile)
        self.abshref = self.images_manager.abshref = item.abshref

        is_first_block = True
        for body in XPath('//h:body')(item.data):
            b = Block(self.styles_manager, body, stylizer.style(body), is_first_block=is_first_block)
            self.blocks.append(b)
            is_first_block = False
            self.process_block(body, b, stylizer, ignore_tail=True)
        if self.blocks and self.blocks[0].is_empty():
            del self.blocks[0]

    def process_block(self, html_block, docx_block, stylizer, ignore_tail=False):
        block_style = stylizer.style(html_block)
        if block_style.is_hidden:
            return
        if html_block.tag.endswith('}img'):
            b = Block(self.styles_manager, html_block, stylizer.style(html_block))
            self.blocks.append(b)
            self.images_manager.add_image(html_block, b, stylizer)
        else:
            if html_block.text:
                docx_block.add_text(html_block.text, block_style, ignore_leading_whitespace=True, is_parent_style=True)

            for child in html_block.iterchildren(etree.Element):
                tag = barename(child.tag)
                style = stylizer.style(child)
                display = style._get('display')
                if display == 'block' and tag != 'br':
                    b = Block(self.styles_manager, child, style)
                    self.blocks.append(b)
                    self.process_block(child, b, stylizer)
                else:
                    self.process_inline(child, self.blocks[-1], stylizer)

        if ignore_tail is False and html_block.tail and html_block.tail.strip():
            b = docx_block
            if b is not self.blocks[-1]:
                b = Block(self.styles_manager, html_block, block_style)
                self.blocks.append(b)
            b.add_text(html_block.tail, stylizer.style(html_block.getparent()), is_parent_style=True)
        if block_style['page-break-after'] == 'avoid':
            self.blocks[-1].keep_next = True

    def process_inline(self, html_child, docx_block, stylizer):
        tag = barename(html_child.tag)
        style = stylizer.style(html_child)
        if style.is_hidden:
            return
        if tag == 'br':
            if html_child.tail or html_child is not html_child.getparent()[-1]:
                docx_block.add_break(clear={'both':'all', 'left':'left', 'right':'right'}.get(style['clear'], 'none'))
        elif tag == 'img':
            self.images_manager.add_image(html_child, docx_block, stylizer)
        else:
            if html_child.text:
                docx_block.add_text(html_child.text, style, html_parent=html_child)
            for child in html_child.iterchildren(etree.Element):
                style = stylizer.style(child)
                display = style.get('display', 'inline')
                if display == 'block':
                    b = Block(self.styles_manager, child, style)
                    self.blocks.append(b)
                    self.process_block(child, b, stylizer)
                else:
                    self.process_inline(child, self.blocks[-1], stylizer)

        if html_child.tail:
            self.blocks[-1].add_text(html_child.tail, stylizer.style(html_child.getparent()), html_parent=html_child.getparent(), is_parent_style=True)

    def write(self):
        dn = {k:v for k, v in namespaces.iteritems() if k in {'w', 'r', 'm', 've', 'o', 'wp', 'w10', 'wne', 'a', 'pic'}}
        E = ElementMaker(namespace=dn['w'], nsmap=dn)
        self.docx.document = doc = E.document()
        body = E.body()
        doc.append(body)
        for block in self.blocks:
            block.serialize(body)
        width, height = PAPER_SIZES[self.opts.docx_page_size]
        if self.opts.docx_custom_page_size is not None:
            width, height = map(float, self.opts.docx_custom_page_size.partition('x')[0::2])
        width, height = int(20 * width), int(20 * height)
        def margin(which):
            return w(which), str(int(getattr(self.opts, 'margin_'+which) * 20))
        body.append(E.sectPr(
            E.pgSz(**{w('w'):str(width), w('h'):str(height)}),
            E.pgMar(**dict(map(margin, 'left top right bottom'.split()))),
            E.cols(**{w('space'):'720'}),
            E.docGrid(**{w('linePitch'):"360"}),
        ))

        dn = {k:v for k, v in namespaces.iteritems() if k in tuple('wra') + ('wp',)}
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
        self.docx.images = {}
        self.styles_manager.serialize(self.docx.styles)
        self.images_manager.serialize(self.docx.images)
