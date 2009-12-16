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

class Text(object):

    def __init__(self, text, font_map, opts, log):
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

        self.text_as_string = etree.tostring(text, method='text',
                encoding=unicode)

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


class HorizontalBox(object):

    def __init__(self, base_text):
        self.texts = [base_text]
        self.bottom = base_text.bottom
        self.number_of_columns = None
        self.column_map = {}

    def append(self, t):
        self.texts.append(t)

    def sort(self, left_margin, right_margin):
        self.texts.sort(cmp=lambda x,y: cmp(x.left, y.left))
        self.top, self.bottom = sys.maxint, 0
        for t in self.texts:
            self.top = min(self.top, t.top)
            self.bottom = max(self.bottom, t.bottom)
        self.left = self.texts[0].left
        self.right = self.texts[-1].right
        self.gaps = []
        for i, t in enumerate(self.texts[1:]):
            gap = Interval(self.texts[i].right, t.left)
            if gap.width > 3:
                self.gaps.append(gap)
        left = Interval(left_margin, self.texts[0].left)
        if left.width > 3:
            self.gaps.insert(0, left)
        right = Interval(self.texts[-1].right, right_margin)
        if right.width > 3:
            self.gaps.append(right)

    def has_intersection_with(self, gap):
        for g in self.gaps:
            if g.intersection(gap):
                return True
        return False

    def identify_columns(self, column_gaps):
        self.number_of_columns = len(column_gaps) + 1


class Page(object):

    def __init__(self, page, font_map, opts, log):
        self.opts, self.log = opts, log
        self.font_map = font_map
        self.number = int(page.get('number'))
        self.width, self.height = map(float, map(page.get,
            ('width', 'height')))
        self.id = 'page%d'%self.number

        self.texts = []
        self.left_margin, self.right_margin = self.width, 0

        for text in page.xpath('descendant::text'):
            self.texts.append(Text(text, self.font_map, self.opts, self.log))
            self.left_margin = min(text.left, self.left_margin)
            self.right_margin = max(text.right, self.right_margin)

        self.textwidth = self.right_margin - self.left_margin

        self.font_size_stats = {}
        for t in self.texts:
            if t.font_size not in self.font_size_stats:
                self.font_size_stats[t.font_size] = 0
            self.font_size_stats[t.font_size] += len(t.text_as_string)

        self.font_size_stats = FontSizeStats(self.font_size_stats)

        self.identify_columns()

    def sort_into_horizontal_boxes(self, document_font_size_stats):
        self.horizontal_boxes = []

        def find_closest_match(text):
            'Return horizontal box whose bottom is closest to text or None'
            min, ans = 3.1, None
            for hb in self.horizontal_boxes:
                diff = abs(text.bottom - hb.bottom)
                if diff < min:
                    diff, ans = min, hb
            return ans

        for t in self.texts:
            hb = find_closest_match(t)
            if hb is None:
                self.horizontal_boxes.append(HorizontalBox(t))
            else:
                hb.append(t)


        for hb in self.horizontal_boxes:
            hb.sort(self.left_margin, self.right_margin)

        self.horizontal_boxes.sort(cmp=lambda x,y: cmp(x.bottom, y.bottom))

    def identify_columns(self):

        def neighborhood(i):
            if i == len(self.horizontal_boxes)-1:
                return self.horizontal_boxes[i-2:i]
            if i == len(self.horizontal_boxes)-2:
                return (self.horizontal_boxes[i-1], self.horizontal_boxes[i+1])
            return self.horizontal_boxes[i+1], self.horizontal_boxes[i+2]

        for i, hbox in enumerate(self.horizontal_boxes):
            n1, n2 = neighborhood(i)
            for gap in hbox.gaps:
                gap.is_column_gap =  n1.has_intersection_with(gap) and \
                    n2.has_intersection_with(gap)



class PDFDocument(object):

    def __init__(self, xml, opts, log):
        self.opts, self.log = opts, log
        parser = etree.XMLParser(recover=True)
        self.root = etree.fromstring(xml, parser=parser)

        self.fonts = []
        self.font_map = {}

        for spec in self.root.xpath('//fonts'):
            self.fonts.append(Font(spec))
            self.font_map[self.fonts[-1].id] = self.fonts[-1]

        self.pages = []
        self.page_map = {}

        for page in self.root.xpath('//page'):
            page = Page(page, self.font_map, opts, log)
            self.page_map[page.id] = page
            self.pages.append(page)

        self.collect_font_statistics()

        for page in self.pages:
            page.sort_into_horizontal_boxes(self.font_size_stats)

    def collect_font_statistics(self):
        self.font_size_stats = {}
        for p in self.pages:
            for sz, chars in p.font_size_stats:
                if sz not in self.font_size_stats:
                    self.font_size_stats[sz] = 0
                self.font_size_stats[sz] += chars

        self.font_size_stats = FontSizeStats(self.font_size_stats)



