#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, numbers
from itertools import count

from lxml import etree

from polyglot.builtins import range, map
from calibre.utils.xml_parse import safe_xml_fromstring


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
        self.id = next(idc)
        self.top, self.left, self.width, self.height, self.iwidth, self.iheight = \
          map(float, map(img.get, ('top', 'left', 'rwidth', 'rheight', 'iwidth',
              'iheight')))
        self.src = img.get('src')
        self.bottom = self.top + self.height
        self.right = self.left + self.width

    def to_html(self):
        return '<img src="%s" width="%dpx" height="%dpx"/>' % \
                (self.src, int(self.width), int(self.height))

    def dump(self, f):
        f.write(self.to_html())
        f.write('\n')


class Text(Element):

    def __init__(self, text, font_map, opts, log, idc):
        Element.__init__(self)
        self.id = next(idc)
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
                encoding='unicode')
        self.raw = text.text if text.text else u''
        for x in text.iterchildren():
            self.raw += etree.tostring(x, method='xml', encoding='unicode')
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

    def to_html(self):
        return self.raw

    def dump(self, f):
        f.write(self.to_html().encode('utf-8'))
        f.write('\n')


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

    def centered_in(self, parent):
        left = abs(self.left - parent.left)
        right = abs(self.right - parent.right)
        return abs(left-right) < 3

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
        if elem in self.elements:
            return
        self.elements.append(elem)
        self._post_add()

    def prepend(self, elem):
        if elem in self.elements:
            return
        self.elements.insert(0, elem)
        self._post_add()

    def _post_add(self):
        self.elements.sort(key=lambda x: x.bottom)
        self.top = self.elements[0].top
        self.bottom = self.elements[-1].bottom
        self.left, self.right = sys.maxsize, 0
        for x in self:
            self.left = min(self.left, x.left)
            self.right = max(self.right, x.right)
        self.width, self.height = self.right-self.left, self.bottom-self.top

    def __iter__(self):
        for x in self.elements:
            yield x

    def __len__(self):
        return len(self.elements)

    def contains(self, elem):
        return elem.left > self.left - self.HFUZZ*self.width and \
               elem.right < self.right + self.HFUZZ*self.width

    def collect_stats(self):
        if len(self.elements) > 1:
            gaps = [self.elements[i+1].top - self.elements[i].bottom for i in
                    range(0, len(self.elements)-1)]
            self.average_line_separation = sum(gaps)/len(gaps)
        for i, elem in enumerate(self.elements):
            left_margin = elem.left - self.left
            elem.indent_fraction = left_margin/self.width
            elem.width_fraction = elem.width/self.width
            if i == 0:
                elem.top_gap_ratio = None
            else:
                elem.top_gap_ratio = (self.elements[i-1].bottom -
                        elem.top)/self.average_line_separation

    def previous_element(self, idx):
        if idx == 0:
            return None
        return self.elements[idx-1]

    def dump(self, f, num):
        f.write('******** Column %d\n\n'%num)
        for elem in self.elements:
            elem.dump(f)


class Box(list):

    def __init__(self, type='p'):
        self.tag = type

    def to_html(self):
        ans = ['<%s>'%self.tag]
        for elem in self:
            if isinstance(elem, numbers.Integral):
                ans.append('<a name="page_%d"/>'%elem)
            else:
                ans.append(elem.to_html()+' ')
        ans.append('</%s>'%self.tag)
        return ans


class ImageBox(Box):

    def __init__(self, img):
        Box.__init__(self)
        self.img = img

    def to_html(self):
        ans = ['<div style="text-align:center">']
        ans.append(self.img.to_html())
        if len(self) > 0:
            ans.append('<br/>')
            for elem in self:
                if isinstance(elem, numbers.Integral):
                    ans.append('<a name="page_%d"/>'%elem)
                else:
                    ans.append(elem.to_html()+' ')
        ans.append('</div>')
        return ans


class Region(object):

    def __init__(self, opts, log):
        self.opts, self.log = opts, log
        self.columns = []
        self.top = self.bottom = self.left = self.right = self.width = self.height = 0

    def add(self, columns):
        if not self.columns:
            for x in sorted(columns, key=lambda x: x.left):
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
        return len(self.columns) == 0

    @property
    def line_count(self):
        max_lines = 0
        for c in self.columns:
            max_lines = max(max_lines, len(c))
        return max_lines

    @property
    def is_small(self):
        return self.line_count < 3

    def absorb(self, singleton):

        def most_suitable_column(elem):
            mc, mw = None, 0
            for c in self.columns:
                i = Interval(c.left, c.right)
                e = Interval(elem.left, elem.right)
                w = i.intersection(e).width
                if w > mw:
                    mc, mw = c, w
            if mc is None:
                self.log.warn('No suitable column for singleton',
                        elem.to_html())
                mc = self.columns[0]
            return mc

        for c in singleton.columns:
            for elem in c:
                col = most_suitable_column(elem)
                if self.opts.verbose > 3:
                    idx = self.columns.index(col)
                    self.log.debug(u'Absorbing singleton %s into column'%elem.to_html(),
                            idx)
                col.add(elem)

    def collect_stats(self):
        for column in self.columns:
            column.collect_stats()
        self.average_line_separation = sum([x.average_line_separation for x in
            self.columns])/float(len(self.columns))

    def __iter__(self):
        for x in self.columns:
            yield x

    def absorb_regions(self, regions, at):
        for region in regions:
            self.absorb_region(region, at)

    def absorb_region(self, region, at):
        if len(region.columns) <= len(self.columns):
            for i in range(len(region.columns)):
                src, dest = region.columns[i], self.columns[i]
                if at != 'bottom':
                    src = reversed(list(iter(src)))
                for elem in src:
                    func = dest.add if at == 'bottom' else dest.prepend
                    func(elem)

        else:
            col_map = {}
            for i, col in enumerate(region.columns):
                max_overlap, max_overlap_index = 0, 0
                for j, dcol in enumerate(self.columns):
                    sint = Interval(col.left, col.right)
                    dint = Interval(dcol.left, dcol.right)
                    width = sint.intersection(dint).width
                    if width > max_overlap:
                        max_overlap = width
                        max_overlap_index = j
                col_map[i] = max_overlap_index
            lines = max(map(len, region.columns))
            if at == 'bottom':
                lines = range(lines)
            else:
                lines = range(lines-1, -1, -1)
            for i in lines:
                for j, src in enumerate(region.columns):
                    dest = self.columns[col_map[j]]
                    if i < len(src):
                        func = dest.add if at == 'bottom' else dest.prepend
                        func(src.elements[i])

    def dump(self, f):
        f.write('############################################################\n')
        f.write('########## Region (%d columns) ###############\n'%len(self.columns))
        f.write('############################################################\n\n')
        for i, col in enumerate(self.columns):
            col.dump(f, i)

    def linearize(self):
        self.elements = []
        for x in self.columns:
            self.elements.extend(x)
        self.boxes = [Box()]
        for i, elem in enumerate(self.elements):
            if isinstance(elem, Image):
                self.boxes.append(ImageBox(elem))
                img = Interval(elem.left, elem.right)
                for j in range(i+1, len(self.elements)):
                    t = self.elements[j]
                    if not isinstance(t, Text):
                        break
                    ti = Interval(t.left, t.right)
                    if not ti.centered_in(img):
                        break
                    self.boxes[-1].append(t)
                self.boxes.append(Box())
            else:
                is_indented = False
                if i+1 < len(self.elements):
                    indent_diff = elem.indent_fraction - \
                        self.elements[i+1].indent_fraction
                    if indent_diff > 0.05:
                        is_indented = True
                if elem.top_gap_ratio > 1.2 or is_indented:
                    self.boxes.append(Box())
                self.boxes[-1].append(elem)


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
        if len(self.texts):
            self.average_text_height /= len(self.texts)

        self.font_size_stats = FontSizeStats(self.font_size_stats)

        self.coalesce_fragments()

        self.elements = list(self.texts)
        for img in page.xpath('descendant::img'):
            self.elements.append(Image(img, self.opts, self.log, idc))
        self.elements.sort(key=lambda x: x.top)

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
        current_region = Region(self.opts, self.log)
        processed = set()
        for x in self.elements:
            if x in processed:
                continue
            elems = set(self.find_elements_in_row_of(x))
            columns = self.sort_into_columns(x, elems)
            processed.update(elems)
            if not current_region.contains(columns):
                self.regions.append(current_region)
                current_region = Region(self.opts, self.log)
            current_region.add(columns)
        if not current_region.is_empty:
            self.regions.append(current_region)

        if self.opts.verbose > 2:
            self.debug_dir = 'page-%d'%self.number
            os.mkdir(self.debug_dir)
            self.dump_regions('pre-coalesce')

        self.coalesce_regions()
        self.dump_regions('post-coalesce')

    def dump_regions(self, fname):
        fname = 'regions-'+fname+'.txt'
        with open(os.path.join(self.debug_dir, fname), 'wb') as f:
            f.write('Page #%d\n\n'%self.number)
            for region in self.regions:
                region.dump(f)

    def coalesce_regions(self):
        # find contiguous sets of small regions
        # absorb into a neighboring region (prefer the one with number of cols
        # closer to the avg number of cols in the set, if equal use larger
        # region)
        found = True
        absorbed = set()
        processed = set()
        while found:
            found = False
            for i, region in enumerate(self.regions):
                if region in absorbed:
                    continue
                if region.is_small and region not in processed:
                    found = True
                    processed.add(region)
                    regions = [region]
                    end = i+1
                    for j in range(i+1, len(self.regions)):
                        end = j
                        if self.regions[j].is_small:
                            regions.append(self.regions[j])
                        else:
                            break
                    prev_region = None if i == 0 else i-1
                    next_region = end if end < len(self.regions) and self.regions[end] not in regions else None
                    absorb_at = 'bottom'
                    if prev_region is None and next_region is not None:
                        absorb_into = next_region
                        absorb_at = 'top'
                    elif next_region is None and prev_region is not None:
                        absorb_into = prev_region
                    elif prev_region is None and next_region is None:
                        if len(regions) > 1:
                            absorb_into = i
                            regions = regions[1:]
                        else:
                            absorb_into = None
                    else:
                        absorb_into = prev_region
                        if self.regions[next_region].line_count >= \
                                self.regions[prev_region].line_count:
                            avg_column_count = sum([len(r.columns) for r in
                                regions])/float(len(regions))
                            if self.regions[next_region].line_count > \
                                    self.regions[prev_region].line_count \
                               or abs(avg_column_count -
                                       len(self.regions[prev_region].columns)) \
                               > abs(avg_column_count -
                                       len(self.regions[next_region].columns)):
                                absorb_into = next_region
                                absorb_at = 'top'
                    if absorb_into is not None:
                        self.regions[absorb_into].absorb_regions(regions, absorb_at)
                        absorbed.update(regions)
        for region in absorbed:
            self.regions.remove(region)

    def sort_into_columns(self, elem, neighbors):
        neighbors.add(elem)
        neighbors = sorted(neighbors, key=lambda x: x.left)
        if self.opts.verbose > 3:
            self.log.debug('Neighbors:', [x.to_html() for x in neighbors])
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
                columns.sort(key=lambda x: x.left)
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
        self.root = safe_xml_fromstring(xml)
        idc = count()

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

        self.linearize()
        self.render()

    def collect_font_statistics(self):
        self.font_size_stats = {}
        for p in self.pages:
            for sz in p.font_size_stats:
                chars = p.font_size_stats[sz]
                if sz not in self.font_size_stats:
                    self.font_size_stats[sz] = 0
                self.font_size_stats[sz] += chars

        self.font_size_stats = FontSizeStats(self.font_size_stats)

    def linearize(self):
        self.elements = []
        last_region = last_block = None
        for page in self.pages:
            page_number_inserted = False
            for region in page.regions:
                merge_first_block = last_region is not None and \
                    len(last_region.columns) == len(region.columns) and \
                    not hasattr(last_block, 'img')
                for i, block in enumerate(region.boxes):
                    if merge_first_block:
                        merge_first_block = False
                        if not page_number_inserted:
                            last_block.append(page.number)
                            page_number_inserted = True
                        for elem in block:
                            last_block.append(elem)
                    else:
                        if not page_number_inserted:
                            block.insert(0, page.number)
                            page_number_inserted = True
                        self.elements.append(block)
                    last_block = block
                last_region = region

    def render(self):
        html = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<html xmlns="http://www.w3.org/1999/xhtml">', '<head>',
                '<title>PDF Reflow conversion</title>', '</head>', '<body>',
                '<div>']
        for elem in self.elements:
            html.extend(elem.to_html())
        html += ['</body>', '</html>']
        raw = (u'\n'.join(html)).replace('</strong><strong>', '')
        with open('index.html', 'wb') as f:
            f.write(raw.encode('utf-8'))
