#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os
from copy import deepcopy

from lxml import etree

class Font(object):

    def __init__(self, spec):
        self.id = spec.get('id')
        self.size = float(spec.get('size'))
        self.color = spec.get('color')
        self.family = spec.get('family')

class Text(object):

    A = etree.XPath('descendant::a[@href]')

    def __init__(self, text, font_map, classes, opts, log):
        self.opts, self.log = opts, log
        self.font_map = font_map
        self.top, self.left, self.width, self.height = map(float, map(text.get,
            ('top', 'left', 'width', 'height')))
        self.font = self.font_map[text.get('font')]
        self.font_size = self.font.size
        self.color = self.font.color
        self.font_family = self.font.family

        for a in self.A(text):
            href = a.get('href')
            if href.startswith('index.'):
                href = href.split('#')[-1]
                a.set('href', '#page'+href)

        self.text = etree.Element('span')
        css = {'font_size':'%.1fpt'%self.font_size, 'color': self.color}
        if css not in classes:
            classes.append(css)
        idx = classes.index(css)
        self.text.set('class', 't%d'%idx)
        if text.text:
            self.text.text = text.text
        for x in text:
            self.text.append(deepcopy(x))
        #print etree.tostring(self.text, encoding='utf-8', with_tail=False)

class Page(object):

    def __init__(self, page, font_map, classes, opts, log):
        self.opts, self.log = opts, log
        self.font_map = font_map
        self.number = int(page.get('number'))
        self.top, self.left, self.width, self.height = map(float, map(page.get,
            ('top', 'left', 'width', 'height')))
        self.id = 'page%d'%self.number

        self.texts = []

        for text in page.xpath('descendant::text'):
            self.texts.append(Text(text, self.font_map, classes, self.opts, self.log))


class PDFDocument(object):

    def __init__(self, xml, opts, log):
        self.opts, self.log = opts, log
        parser = etree.XMLParser(recover=True)
        self.root = etree.fromstring(xml, parser=parser)

        self.fonts = []
        self.font_map = {}

        for spec in self.root.xpath('//fontspec'):
            self.fonts.append(Font(spec))
            self.font_map[self.fonts[-1].id] = self.fonts[-1]

        self.pages = []
        self.page_map = {}

        self.classes = []

        for page in self.root.xpath('//page'):
            page = Page(page, self.font_map, self.classes, opts, log)
            self.page_map[page.id] = page
            self.pages.append(page)




def run(opts, pathtopdf, log):
    from calibre.constants import plugins
    pdfreflow, err = plugins['pdfreflow']
    if pdfreflow is None:
        raise RuntimeError('Failed to load PDF Reflow plugin: '+err)
    data = open(pathtopdf, 'rb').read()
    pdfreflow.reflow(data)
    index = os.path.join(os.getcwdu(), 'index.xml')
    xml = open(index, 'rb').read()
    #pdfdoc = PDFDocument(xml, opts, log)

def option_parser():
    from optparse import OptionParser
    p = OptionParser()
    p.add_option('-v', '--verbose', action='count', default=0)
    return p

def main(args=sys.argv):
    p = option_parser()
    opts, args = p.parse_args(args)
    from calibre.utils.logging import default_log

    if len(args) < 2:
        p.print_help()
        default_log('No input PDF file specified', file=sys.stderr)
        return 1


    run(opts, args[1], default_log)

    return 0
