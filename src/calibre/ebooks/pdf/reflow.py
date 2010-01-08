#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from lxml import etree

class Font(object):

    def __init__(self, spec):
        self.id = spec.get('id')
        self.size = float(spec.get('size'))
        self.color = spec.get('color')
        self.family = spec.get('family')

class Element(object):

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

class Image(Element):

    def __init__(self, img, opts, log, idc):
        self.opts, self.log = opts, log
        self.id = idc.next()
        self.top, self.left, self.width, self.height, self.iwidth, self.iheight = \
          map(float, map(img.get, ('top', 'left', 'rwidth', 'rheight', 'iwidth',
              'iheight')))
        self.src = img.get('src')



class Text(Element):

    def __init__(self, text, font_map, opts, log, idc):
        self.id = idc.next()
        self.opts, self.log = opts, log
        self.font_map = font_map
        self.top, self.left, self.width, self.height = map(float, map(text.get,
            ('top', 'left', 'width', 'height')))
        self.bottom  = self.top + self.height
        self.right = self.left + self.width
        self.font = self.font_map[text.get('font')]
        self.font_size = self.font.size
        self.color = self.font.color
        self.font_family = self.font.family

        text.tail = ''
        self.text_as_string = etree.tostring(text, method='text',
                encoding=unicode)
        self.raw = text.text if text.text else u''
        for x in text.iterchildren():
            self.raw += etree.tostring(x, method='xml', encoding=unicode)
            if x.tail:
                self.raw += x.tail
        self.average_character_width = self.width/len(self.text_as_string)

    def coalesce(self, other, page_number):
        if self.opts.verbose > 2:
            self.log.debug('Coalescing %r with %r on page %d'%(self.text_as_string,
                other.text_as_string, page_number))
        self.top = min(self.top, other.top)
        self.right = other.right
        self.width = self.right - self.left
        self.bottom = max(self.bottom, other.bottom)
        self.height = self.bottom - self.top
        self.font_size = max(self.font_size, other.font_size)
        self.font = other.font if self.font_size == other.font_size else other.font
        self.text_as_string += other.text_as_string
        self.raw += other.raw
        self.average_character_width = (self.average_character_width +
                other.average_character_width)/2.0

class FontSizeStats(dict):

    def __init__(self, stats):
        total = float(sum(stats.values()))
        self.most_common_size, self.chars_at_most_common_size = -1, 0

        for sz, chars in stats.items():
            if chars >= self.chars_at_most_common_size:
                self.most_common_size, self.chars_at_most_common_size = sz, chars
            self[sz] = chars/total

class Interval(object):

    def __init__(self, left, right):
        self.left, self.right = left, right
        self.width = right - left

    def intersection(self, other):
        left = max(self.left, other.left)
        right = min(self.right, other.right)
        return Interval(left, right)

    def __nonzero__(self):
        return self.width > 0

    def __eq__(self, other):
        return self.left == other.left and self.right == other.right

    def __hash__(self):
        return hash('(%f,%f)'%self.left, self.right)


class Page(object):

    # Fraction of a character width that two strings have to be apart,
    # for them to be considered part of the same text fragment
    COALESCE_FACTOR = 0.5

    # Fraction of text height that two strings' bottoms can differ by
    # for them to be considered to be part of the same text fragment
    LINE_FACTOR = 0.4

    YFUZZ = 1.5


    def __init__(self, page, font_map, opts, log, idc):
        self.opts, self.log = opts, log
        self.font_map = font_map
        self.number = int(page.get('number'))
        self.width, self.height = map(float, map(page.get,
            ('width', 'height')))
        self.id = 'page%d'%self.number

        self.texts = []
        self.left_margin, self.right_margin = self.width, 0

        for text in page.xpath('descendant::text'):
            self.texts.append(Text(text, self.font_map, self.opts, self.log, idc))
            text = self.texts[-1]
            self.left_margin = min(text.left, self.left_margin)
            self.right_margin = max(text.right, self.right_margin)

        self.textwidth = self.right_margin - self.left_margin

        self.font_size_stats = {}
        self.average_text_height = 0
        for t in self.texts:
            if t.font_size not in self.font_size_stats:
                self.font_size_stats[t.font_size] = 0
            self.font_size_stats[t.font_size] += len(t.text_as_string)
            self.average_text_height += t.height
        self.average_text_height /= len(self.texts)

        self.font_size_stats = FontSizeStats(self.font_size_stats)

        self.coalesce_fragments()

        self.elements = list(self.texts)
        for img in page.xpath('descendant::img'):
            self.elements.append(Image(img, self.opts, self.log, idc))
        self.elements.sort(cmp=lambda x,y:cmp(x.top, y.top))

    def coalesce_fragments(self):

        def find_match(frag):
            for t in self.texts:
                hdelta = t.left - frag.right
                hoverlap = self.COALESCE_FACTOR * frag.average_character_width
                if t is not frag and hdelta > -hoverlap and \
                    hdelta < hoverlap and \
                    abs(t.bottom - frag.bottom) < self.LINE_FACTOR*frag.height:
                        return t

        match_found = True
        while match_found:
            match_found, match = False, None
            for frag in self.texts:
                match = find_match(frag)
                if match is not None:
                    match_found = True
                    frag.coalesce(match, self.number)
                    break
            if match is not None:
                self.texts.remove(match)

    def first_pass(self):
        self.regions = []
        if not self.elements:
            return
        for i, x in enumerate(self.elements):
            x.idx = i
        self.current_region = None
        for x in self.elements:
            self.find_elements_in_row_of(x)

    def find_elements_in_row_of(self, x):
        interval = Interval(x.top - self.YFUZZ * self.average_text_height,
                x.top + self.YFUZZ*(1+self.average_text_height))
        m = max(0, x.idx-15)
        for y in self.elements[m:x.idx+15]:
            y_interval = Interval(y.top, y.bottom)
            if interval.intersection(y_interval).width > \
                0.5*self.average_text_height:
                yield y


class PDFDocument(object):

    def __init__(self, xml, opts, log):
        self.opts, self.log = opts, log
        parser = etree.XMLParser(recover=True)
        self.root = etree.fromstring(xml, parser=parser)
        idc = iter(xrange(sys.maxint))

        self.fonts = []
        self.font_map = {}

        for spec in self.root.xpath('//font'):
            self.fonts.append(Font(spec))
            self.font_map[self.fonts[-1].id] = self.fonts[-1]

        self.pages = []
        self.page_map = {}

        for page in self.root.xpath('//page'):
            page = Page(page, self.font_map, opts, log, idc)
            self.page_map[page.id] = page
            self.pages.append(page)

        self.collect_font_statistics()

        for page in self.pages:
            page.document_font_stats = self.font_size_stats
            page.first_pass()

    def collect_font_statistics(self):
        self.font_size_stats = {}
        for p in self.pages:
            for sz in p.font_size_stats:
                chars = p.font_size_stats[sz]
                if sz not in self.font_size_stats:
                    self.font_size_stats[sz] = 0
                self.font_size_stats[sz] += chars

        self.font_size_stats = FontSizeStats(self.font_size_stats)



