#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from lxml import etree
from urlparse import urlparse

from calibre.ebooks.oeb.base import XPNSMAP, TOC, XHTML, xml2text
from calibre.ebooks import ConversionError

def XPath(x):
    try:
        return etree.XPath(x, namespaces=XPNSMAP)
    except etree.XPathSyntaxError:
        raise ConversionError(
        'The syntax of the XPath expression %s is invalid.' % repr(x))

class DetectStructure(object):

    def __call__(self, oeb, opts):
        self.log = oeb.log
        self.oeb = oeb
        self.opts = opts
        self.log('Detecting structure...')

        self.detect_chapters()
        if self.oeb.auto_generated_toc or opts.use_auto_toc:
            orig_toc = self.oeb.toc
            self.oeb.toc = TOC()
            self.create_level_based_toc()
            if self.oeb.toc.count() < 1:
                if not opts.no_chapters_in_toc and self.detected_chapters:
                    self.create_toc_from_chapters()
                if self.oeb.toc.count() < opts.toc_threshold:
                    self.create_toc_from_links()
            if self.oeb.toc.count() < 2 and orig_toc.count() > 2:
                self.oeb.toc = orig_toc
            else:
                self.oeb.auto_generated_toc = True
                self.log('Auto generated TOC with %d entries.' %
                        self.oeb.toc.count())

        if opts.toc_filter is not None:
            regexp = re.compile(opts.toc_filter)
            for node in list(self.oeb.toc.iter()):
                if not node.title or regexp.search(node.title) is not None:
                    self.log('Filtering', node.title if node.title else\
                            'empty node', 'from TOC')
                    self.oeb.toc.remove(node)

        if opts.page_breaks_before is not None:
            pb_xpath = XPath(opts.page_breaks_before)
            for item in oeb.spine:
                for elem in pb_xpath(item.data):
                    style = elem.get('style', '')
                    if style:
                        style += '; '
                    elem.set('style', style+'page-break-before:always')

        for node in self.oeb.toc.iter():
            if not node.title or not node.title.strip():
                node.title = _('Unnamed')

    def detect_chapters(self):
        self.detected_chapters = []
        if self.opts.chapter:
            chapter_xpath = XPath(self.opts.chapter)
            for item in self.oeb.spine:
                for x in chapter_xpath(item.data):
                    self.detected_chapters.append((item, x))

            chapter_mark = self.opts.chapter_mark
            page_break_before = 'display: block; page-break-before: always'
            page_break_after = 'display: block; page-break-after: always'
            for item, elem in self.detected_chapters:
                text = xml2text(elem).strip()
                self.log('\tDetected chapter:', text[:50])
                if chapter_mark == 'none':
                    continue
                elif chapter_mark == 'rule':
                    mark = etree.Element(XHTML('hr'))
                elif chapter_mark == 'pagebreak':
                    mark = etree.Element(XHTML('div'), style=page_break_after)
                else: # chapter_mark == 'both':
                    mark = etree.Element(XHTML('hr'), style=page_break_before)
                try:
                    elem.addprevious(mark)
                except TypeError:
                    self.log.exception('Failed to mark chapter')

    def create_level_based_toc(self):
        if self.opts.level1_toc is None:
            return
        for item in self.oeb.spine:
            self.add_leveled_toc_items(item)

    def create_toc_from_chapters(self):
        counter = self.oeb.toc.next_play_order()
        for item, elem in self.detected_chapters:
            text, href = self.elem_to_link(item, elem, counter)
            self.oeb.toc.add(text, href, play_order=counter)
            counter += 1

    def create_toc_from_links(self):
        num = 0
        for item in self.oeb.spine:
            for a in XPath('//h:a[@href]')(item.data):
                href = a.get('href')
                purl = urlparse(href)
                if not purl[0] or purl[0] == 'file':
                    href, frag = purl.path, purl.fragment
                    href = item.abshref(href)
                    if frag:
                        href = '#'.join((href, frag))
                    if not self.oeb.toc.has_href(href):
                        text = xml2text(a)
                        text = text[:100].strip()
                        if not self.oeb.toc.has_text(text):
                            num += 1
                            self.oeb.toc.add(text, href,
                                play_order=self.oeb.toc.next_play_order())
                            if self.opts.max_toc_links > 0 and \
                                    num >= self.opts.max_toc_links:
                                self.log('Maximum TOC links reached, stopping.')
                                return



    def elem_to_link(self, item, elem, counter):
        text = xml2text(elem).strip()
        if not text:
            text = elem.get('title', '')
        if not text:
            text = elem.get('alt', '')
        text = text[:100].strip()
        id = elem.get('id', 'calibre_toc_%d'%counter)
        elem.set('id', id)
        href = '#'.join((item.href, id))
        return text, href


    def add_leveled_toc_items(self, item):
        level1 = XPath(self.opts.level1_toc)(item.data)
        level1_order = []
        document = item

        counter = 1
        if level1:
            added = {}
            for elem in level1:
                text, _href = self.elem_to_link(document, elem, counter)
                counter += 1
                if text:
                    node = self.oeb.toc.add(text, _href,
                            play_order=self.oeb.toc.next_play_order())
                    level1_order.append(node)
                    added[elem] = node
                    #node.add(_('Top'), _href)
            if self.opts.level2_toc is not None:
                added2 = {}
                level2 = list(XPath(self.opts.level2_toc)(document.data))
                for elem in level2:
                    level1 = None
                    for item in document.data.iterdescendants():
                        if item in added.keys():
                            level1 = added[item]
                        elif item == elem and level1 is not None:
                            text, _href = self.elem_to_link(document, elem, counter)
                            counter += 1
                            if text:
                                added2[elem] = level1.add(text, _href,
                                    play_order=self.oeb.toc.next_play_order())
                if self.opts.level3_toc is not None:
                    level3 = list(XPath(self.opts.level3_toc)(document.data))
                    for elem in level3:
                        level2 = None
                        for item in document.data.iterdescendants():
                            if item in added2.keys():
                                level2 = added2[item]
                            elif item == elem and level2 is not None:
                                text, _href = \
                                        self.elem_to_link(document, elem, counter)
                                counter += 1
                                if text:
                                    level2.add(text, _href,
                                    play_order=self.oeb.toc.next_play_order())

