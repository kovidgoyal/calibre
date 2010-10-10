# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into SNB format
'''

import os
import re

from lxml import etree

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer

def ProcessFileName(fileName):
    # Flat the path 
    fileName = fileName.replace("/", "_").replace(os.sep, "_")
    # Handle bookmark for HTML file
    fileName = fileName.replace("#", "_")
    # Make it lower case
    fileName = fileName.lower()
    # Change extension from jpeg to jpg
    root, ext = os.path.splitext(fileName) 
    if ext in [ '.jpeg', '.jpg', '.gif', '.svg' ]:
        fileName = root + '.png'
    return fileName
    

BLOCK_TAGS = [
    'div',
    'p',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'li',
    'tr',
]

BLOCK_STYLES = [
    'block',
]

SPACE_TAGS = [
    'td',
]

CLIABRE_SNB_IMG_TAG = "<calibre_snb_temp_img>"

class SNBMLizer(object):
    
    curSubItem = ""
    curText = [ ]

    def __init__(self, log):
        self.log = log

    def extract_content(self, oeb_book, item, subitems, opts):
        self.log.info('Converting XHTML to SNBC...')
        self.oeb_book = oeb_book
        self.opts = opts
        self.item = item
        self.subitems = subitems
        return self.mlize();


    def mlize(self):
        stylizer = Stylizer(self.item.data, self.item.href, self.oeb_book, self.opts, self.opts.output_profile)
        content = unicode(etree.tostring(self.item.data.find(XHTML('body')), encoding=unicode))
        content = self.remove_newlines(content)
        trees = { }
        for subitem, subtitle in self.subitems:
            snbcTree = etree.Element("snbc")
            etree.SubElement(etree.SubElement(snbcTree, "head"), "title").text = subtitle
            etree.SubElement(snbcTree, "body")
            trees[subitem] = snbcTree

        self.dump_text(trees, self.subitems, etree.fromstring(content), stylizer)
        self.Output(trees)
        return trees

    def remove_newlines(self, text):
        self.log.debug('\tRemove newlines for processing...')
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')

        return text

    def dump_text(self, trees, subitems, elem, stylizer, end=''):
        '''
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        @end: The last two characters of the text from the previous element.
              This is used to determine if a blank line is needed when starting
              a new block element.
        '''
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return ['']

        if elem.attrib.get('id') != None and elem.attrib['id'] in [ href for href, title in subitems ]:
            if self.curSubItem != None and self.curSubItem != elem.attrib['id']:
                self.Output(trees)
                self.curSubItem = elem.attrib['id']
                self.curText = [ ]

        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return ['']

        tag = barename(elem.tag)
        in_block = False

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            in_block = True
            if not end.endswith(u'\n\n') and hasattr(elem, 'text') and elem.text:
                self.curText.append(u'\n\n')

        if tag in SPACE_TAGS:
            if not end.endswith('u ') and hasattr(elem, 'text') and elem.text:
                self.curText.append(u' ')

        if tag == 'img':
            self.curText.append(u'%s%s' % (CLIABRE_SNB_IMG_TAG, ProcessFileName(elem.attrib['src'])))

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            self.curText.append(elem.text)

        for item in elem:
            en = u''
            if len(self.curText) >= 2:
                en = self.curText[-1][-2:]
            self.dump_text(trees, subitems, item, stylizer, en)

        if in_block:
            self.curText.append(u'\n\n')

        if hasattr(elem, 'tail') and elem.tail:
            self.curText.append(elem.tail)

    def Output(self, trees):
        if self.curSubItem == None or not self.curSubItem in trees:
            return
        for t in self.curText:
            if len(t.strip(' \t\n\r')) != 0:
                if t.find(CLIABRE_SNB_IMG_TAG) == 0:
                    etree.SubElement(trees[self.curSubItem], "img").text = t[len(CLIABRE_SNB_IMG_TAG):]
                else:
                    etree.SubElement(trees[self.curSubItem], "text").text = etree.CDATA(unicode(u'\u3000\u3000' + t))
