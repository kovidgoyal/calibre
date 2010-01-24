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

    def __init__(self):
        self.starts_block = None
        self.block_style = None

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

class Image(Element):

    def __init__(self, img, opts, log, idc):
        Element.__init__(self)
        self.opts, self.log = opts, log
        self.id = idc.next()
        self.top, self.left, self.width, self.height, self.iwidth, self.iheight = \
          map(float, map(img.get, ('top', 'left', 'rwidth', 'rheight', 'iwidth',
              'iheight')))
        self.src = img.get('src')


class Text(Element):

    def __init__(self, text, font_map, opts, log, idc):
        Element.__init__(self)
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

class Column(object):

    # A column contains an element is the element bulges out to
    # the left or the right by at most HFUZZ*col width.
    HFUZZ = 0.2


    def __init__(self):
        self.left = self.right = self.top = self.bottom = 0
        self.width = self.height = 0
        self.elements = []
        self.average_line_separation = 0

    def add(self, elem):
        if elem in self.elements: return
        self.elements.append(elem)
        self.elements.sort(cmp=lambda x,y:cmp(x.bottom,y.bottom))
        self.top = self.elements[0].top
        self.bottom = self.elements[-1].bottom
        self.left, self.right = sys.maxint, 0
        for x in self:
            self.left = min(self.left, x.left)
            self.right = max(self.right, x.right)
        self.width, self.height = self.right-self.left, self.bottom-self.top

    def __iter__(self):
        for x in self.elements:
            yield x

    def contains(self, elem):
        return elem.left > self.left - self.HFUZZ*self.width and \
               elem.right < self.right + self.HFUZZ*self.width

    def collect_stats(self):
        if len(self.elements) > 1:
            gaps = [self.elements[i+1].top - self.elements[i].bottom for i in
                    range(len(0, len(self.elements)-1))]
            self.average_line_separation = sum(gaps)/len(gaps)
        for i, elem in enumerate(self.elements):
            left_margin = elem.left - self.left
            elem.indent_fraction = left_margin/self.width
            elem.width_fraction = elem.width/self.width
            if i == 0:
                elem.top_gap = None
            else:
                elem.top_gap = self.elements[i-1].bottom - elem.top

    def previous_element(self, idx):
        if idx == 0:
            return None
        return self.elements[idx-1]




class Region(object):

    def __init__(self):
        self.columns = []
        self.top = self.bottom = self.left = self.right = self.width = self.height = 0

    def add(self, columns):
        if not self.columns:
            for x in sorted(columns, cmp=lambda x,y: cmp(x.left, y.left)):
                self.columns.append(x)
        else:
            for i in range(len(columns)):
                for elem in columns[i]:
                    self.columns[i].add(elem)

    def contains(self, columns):
        # TODO: handle unbalanced columns
        if not self.columns:
            return True
        if len(columns) != len(self.columns):
            return False
        for i in range(len(columns)):
            c1, c2 = self.columns[i], columns[i]
            x1 = Interval(c1.left, c1.right)
            x2 = Interval(c2.left, c2.right)
            intersection = x1.intersection(x2)
            base = min(x1.width, x2.width)
            if intersection.width/base < 0.6:
                return False
        return True

    @property
    def is_empty(self):
        return len(self.elements) == 0

    def collect_stats(self):
        for column in self.columns:
            column.collect_stats()
        self.average_line_separation = sum([x.average_line_separation for x in
            self.columns])/float(len(self.columns))

    def __iter__(self):
        for x in self.columns:
            yield x

    def linearize(self):
        self.elements = []
        for x in self.columns:
            self.elements.extend(x)


class Page(object):

    # Fraction of a character width that two strings have to be apart,
    # for them to be considered part of the same text fragment
    COALESCE_FACTOR = 0.5

    # Fraction of text height that two strings' bottoms can differ by
    # for them to be considered to be part of the same text fragment
    LINE_FACTOR = 0.4

    # Multiplies the average line height when determining row height
    # of a particular element to detect columns.
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
        'Sort page into regions and columns'
        self.regions = []
        if not self.elements:
            return
        for i, x in enumerate(self.elements):
            x.idx = i
        current_region = Region()
        processed = set([])
        for x in self.elements:
            if x in processed: continue
            elems = set(self.find_elements_in_row_of(x))
            columns = self.sort_into_columns(x, elems)
            processed.update(elems)
            if not current_region.contains(columns):
                self.regions.append(self.current_region)
                current_region = Region()
            current_region.add(columns)
        if not self.current_region.is_empty():
            self.regions.append(current_region)

    def sort_into_columns(self, elem, neighbors):
        columns = [Column()]
        columns[0].add(elem)
        for x in neighbors:
            added = False
            for c in columns:
                if c.contains(x):
                    c.add(x)
                    added = True
                    break
            if not added:
                columns.append(Column())
                columns[-1].add(x)
                columns.sort(cmp=lambda x,y:cmp(x.left, y.left))
        return columns

    def find_elements_in_row_of(self, x):
        interval = Interval(x.top,
                x.top + self.YFUZZ*(self.average_text_height))
        h_interval = Interval(x.left, x.right)
        for y in self.elements[x.idx:x.idx+15]:
            if y is not x:
                y_interval = Interval(y.top, y.bottom)
                x_interval = Interval(y.left, y.right)
                if interval.intersection(y_interval).width > \
                    0.5*self.average_text_height and \
                    x_interval.intersection(h_interval).width <= 0:
                    yield y

    def second_pass(self):
        'Locate paragraph boundaries in each column'
        for region in self.regions:
            region.collect_stats()
            region.linearize()


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
            page.second_pass()

    def collect_font_statistics(self):
        self.font_size_stats = {}
        for p in self.pages:
            for sz in p.font_size_stats:
                chars = p.font_size_stats[sz]
                if sz not in self.font_size_stats:
                    self.font_size_stats[sz] = 0
                self.font_size_stats[sz] += chars

        self.font_size_stats = FontSizeStats(self.font_size_stats)



