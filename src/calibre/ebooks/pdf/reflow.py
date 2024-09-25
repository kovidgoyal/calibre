#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import re
import sys
from operator import attrgetter

from lxml import etree

# Global constants affecting formatting decisions

#### Pages/lines

# How many pages/lines to scan when finding header/footer automatically
PAGE_SCAN_COUNT = 20		# Arbitrary
LINE_SCAN_COUNT = 2		# Arbitrary

# Fraction of a character width that two strings have to be apart,
# for them to be considered part of the same text fragment
# The problem is justified text where fragments can be widely spaced
# Was 0.5 but this forces just about anything to coalesce.
# It also means no columns will be found
COALESCE_FACTOR = 20.0

# Allow some dither of bottom of characters when checking if same line.
# The bottom of 1 line can overlap the top of the next by this amount
# and they are considered different lines.
# Pixels from the PDF file
BOTTOM_FACTOR = 2.0

# Fraction of text height that two strings' bottoms can differ by
# for them to be considered to be part of the same text fragment
LINE_FACTOR = 0.2

# Long words can force a new line (at a new page)
# although the end of the previous is < this percent.
# Needs to find whether 1st word of 2nd page would fit on
# the last line of previous rather than the length of the last line.
LAST_LINE_PERCENT = 60.0

# Pages can split early to avoid orphans.
# Allow a margin when deciding whether a page finishes early,
# and a page break should be put in the HTML.
ORPHAN_LINES = 5

# Fraction of the gap between lines to determine if setting the paragraph break
# is likely to be valid.  Somewhere between 1 and 2, probably nearer 2
PARA_FACTOR = 1.8

# Multiplies the gap between paragraphs to determine if this is a section break
# not a paragraph break
SECTION_FACTOR = 1.3

# Multiplies the average line height when determining row height
# of a particular element to detect columns.
YFUZZ = 1.5

# Left (and other) margins can waver.
# Plus or minus this
LEFT_WAVER = 2.0

# Amount left margin must be greater than right for text
# to be considered right aligned. 1.8 = 180%
RIGHT_FACTOR = 1.8

# Percentage amount left and right margins can differ
# and still be considered centered. 0.15 = 15%
CENTER_FACTOR = 0.15

#### Indents and line spacing
# How near must pixel values be to appear the same
SAME_SPACE = 3.0
SAME_INDENT = 2.0


class Font:

    def __init__(self, spec):
        self.id = spec.get('id')
        self.size = float(spec.get('size'))
        self.size_em = 0.0
        self.color = spec.get('color')
        self.family = spec.get('family')

class Element:

    def __init__(self):
        self.starts_block = None
        self.block_style = None

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

class DocStats:

    def __init__(self):
        self.top = self.bottom = self.left_odd = self.left_even = self.right \
          = self.line_space = self.para_space = self.indent_odd = self.indent_even = 0
        self.font_size = 0

class Image(Element):

    def __init__(self, img, opts, log, idc):
        Element.__init__(self)
        self.opts, self.log = opts, log
        self.id = next(idc)
        self.top, self.left, self.width, self.height = \
          map(float, map(img.get, ('top', 'left', 'width', 'height')))
        self.src = img.get('src')
        self.bottom = self.top + self.height
        self.right = self.left + self.width
        # Check for alignment done later
        self.align = 'L'

    def to_html(self):
        return '<img src="%s" alt="" width="%dpx" height="%dpx"/>' % \
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
        self.top, self.left, self.width, self.height = map(round, map(float, map(text.get,
            ('top', 'left', 'width', 'height'))))
        # This does nothing, as expected,
        # but somewhere left (at least) is changed sometimes to not .0
        if self.left != round(self.left) :
            self.left = round(self.left)
        self.bottom  = self.top + self.height
        self.right = self.left + self.width
        self.tag = 'p'    # Normal paragraph <p...>
        self.indented = 0
        self.margin_left = 0    # Normal margins
        self.margin_right = 0   # Normal margins
        # When joining lines for a paragraph, remember position of last line joined
        self.last_left = self.left
        # Remember the length of this line if it is merged into a paragraph
        self.final_width = self.width
        # Align = Left, Right, Center, Justified.  Default L
        self.align = 'L'
        # Should there be extra space before/after paragraph?
        self.blank_line_before = 0
        self.blank_line_after = 0

        if self.font_map:
            self.font = self.font_map[text.get('font')]
            self.font_size = self.font.size
            self.font_size_em = self.font.size_em
            self.color = self.font.color
            self.font_family = self.font.family
        else:
            self.font = {}
            self.font_size = 0.0
            self.font_size_em = 0.0
        #    self.color = 0

        text.tail = ''
        self.text_as_string = etree.tostring(text, method='text', encoding='unicode')
        self.raw = text.text if text.text else ''
        for x in text.iterchildren():
            self.raw += etree.tostring(x, method='xml', encoding='unicode')
        self.average_character_width = self.width/len(self.text_as_string)

    def coalesce(self, other, page_number, left_margin):
        if self.opts.verbose > 2:
            self.log.debug('Coalescing %r with %r on page %d'%(self.text_as_string,
                other.text_as_string, page_number))
        # Need to work out how to decide this
        # For elements of the same line, is there a space between?
        # Spaces are narrow, so a_c_w/3
        if (self.top <= other.top and self.bottom >= other.bottom) \
          and abs(other.left - self.right) < self.average_character_width / 3.0:
            has_gap = 0
        else:	# Insert n spaces to fill gap.  Use TAB?  Columns?
            if other.left < self.right:
                has_gap = 1  # Coalescing different lines. 1 space
            else:    # Multiple texts on same line
                has_gap = round(abs(other.left - self.right) / self.average_character_width)

        # Allow for super or subscript.  These probably have lower heights
        # In this case, don't use their top/bottom
        if other.left >= self.right:
            # Same line
            if self.top > other.top:
                pass
            elif self.bottom < other.bottom:
                pass
            if self.height >= other.height:
                self.top = min(self.top, other.top)
                self.bottom = max(self.bottom, other.bottom)
            else:
                self.top = other.top
                self.bottom = other.bottom
        else:
            self.top = min(self.top, other.top)
            self.bottom = max(self.bottom, other.bottom)

        self.left = min(self.left, other.left)
        self.right = max(self.right, other.right)
        self.width +=  other.width
        self.final_width +=  other.final_width
        self.height = self.bottom - self.top
        # Need to check for </span> <span... as well
        # This test does not work in its present form
        # The matches can lose data, so force test to fail
        if self.font_size_em == other.font_size_em \
          and False \
          and self.font.id == other.font.id \
          and re.match('<span style="font-size:', self.raw) is not None \
          and re.match('<span style="font-size:', other.raw) is not None :
            # We have the same class, so merge
            m_self = re.match('^(.+)</span>$', self.raw)
            m_other = re.match('^<span style="font-size:.+em">(.+</span>)$', other.raw)
            if m_self and m_other:
                self.raw = m_self.group(1)
                other.raw = m_other.group(1)
        elif self.font_size_em != other.font_size_em \
          and self.font_size_em != 1.00 :
            if re.match('<span', self.raw) is None :
                self.raw = '<span style="font-size:%sem">%s</span>'%(str(self.font_size_em),self.raw)
            # Try to allow for a very large initial character
            elif len(self.text_as_string) <= 2 \
              and self.font_size_em >= other.font_size_em * 2.0 :
                # Insert 'float: left' etc. into current font info
                # Unfortunately, processing to generate the .epub file changes things.
                # The line height gets set to the same as other parts of the file
                # and the font size is reduced.
                # These need to be fixed manually.
                m_self = re.match('^(.+em">)(.+)$', self.raw)
                self.raw = m_self.group(1) \
                  + '<span style="float:left"><span style="line-height:0.5">' \
                  + m_self.group(2) + '</span></span>'

        self.font_size = max(self.font_size, other.font_size)
        self.font_size_em = max(self.font_size_em, other.font_size_em)
        self.font = other.font if self.font_size == other.font_size else other.font
        if has_gap > 0:
            if has_gap < 3:	# Small number of spaces = 1 space
                if not (self.text_as_string.endswith(' ') \
                     or self.text_as_string.endswith('-') \
                     or other.text_as_string.startswith(' ') \
                     or other.text_as_string.startswith('-') ):
                    has_gap = 1
                else:
                    has_gap = 0
            # Insert multiple spaces
            while has_gap > 0:
                self.text_as_string += ' '
                self.raw += ' '
                self.width += self.average_character_width
                #self.final_width += self.average_character_width
                has_gap -= 1

        self.text_as_string += other.text_as_string
        #self.width += other.width

        # Try to merge href where there are 2 for the same place
        # Beware multiple hrefs on the same line, but for different places
        # e.g.
        # self.raw = '<a href="index.html#2">T</a>'
        # other.raw = '<span style="font-size:0.7em"><a href="index.html#2">ITLE</a></span>'
        # becomes '<a href="index.html#2">T<span style="font-size:0.7em">ITLE</span></a>'
        # Are there problems if self.raw does not end </a>?
        # Note that the 2 parts could have different font sizes
        matchObj = re.match(r'^([^<]*)(<span[^>]*>)*(<a href[^>]+>)(.*)</a>(</span>)*(\s*)$', self.raw)
        if matchObj is not None :
            otherObj = re.match('^([^<]*)(<span[^>]*>)*(<a href[^>]+>)(.*)(</a>)(</span>)*(.*)$', other.raw)
            # There is another href, but is it for the same place?
            if otherObj is not None  and  matchObj.group(3) == otherObj.group(3) :
                m2 = matchObj.group(2)
                if m2 is None:
                    m2 = ''
                m5 = matchObj.group(5)
                if m5 is None:
                    m5 = ''
                o2 = otherObj.group(2)
                if o2 is None:
                    o2 = ''
                o6 = otherObj.group(6)
                if o6 is None:
                    o6 = ''
                # Remove the other <a...> stuff and put the </a> last
                other.raw = otherObj.group(1)+o2+otherObj.group(4)+o6+otherObj.group(5)+otherObj.group(7)
                # Move the <span... after the <a... and remove the </a>
                self.raw = matchObj.group(1)+matchObj.group(3)+m2+matchObj.group(4)+m5+matchObj.group(6)
        # This needs more work
        #if sub_super < 0:
        #    other.raw = '<sup>' + other.raw + '</sup>'
        #elif sub_super > 0:
        #    other.raw = '<sub>' + other.raw + '</sub>'

        self.raw += other.raw
        self.average_character_width = self.width/len(self.text_as_string)
        #self.last_left = other.left

    def to_html(self):
        return self.raw

    def dump(self, f):
        f.write('T top={}, left={}, width={}, height={}: '.format(self.top, self.left, self.width, self.height))
        f.write(self.to_html().encode('utf-8'))
        f.write('\n')

class Paragraph(Text):

    def __init__(self, text, font_map, opts, log, idc):
        Text.__init__(self)
        self.id = next(idc)
        self.opts, self.log = opts, log
        self.font_map = font_map
        self.top, self.left, self.width, self.height = map(float, map(text.get,
            ('top', 'left', 'width', 'height')))
        self.bottom  = self.top + self.height
        self.right = self.left + self.width
        if self.font_map:
            self.font = self.font_map[text.get('font')]
            self.font_size = self.font.size
            self.color = self.font.color
            self.font_family = self.font.family
        else:
            self.font = {}
            self.font_size = 0
        #    self.color = 0

        text.tail = ''
        self.text_as_string = etree.tostring(text, method='text',
                encoding='unicode')
        self.raw = text.text if text.text else ''
        for x in text.iterchildren():
            self.raw += etree.tostring(x, method='xml', encoding='unicode')
        self.average_character_width = self.width/len(self.text_as_string)

    def to_html(self):
        return self.raw

    def dump(self, f):
        f.write('P top={}, left={}, width={}, height={}: '.format(self.top, self.left, self.width, self.height))
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

class Interval:

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

class Column:

    # A column contains an element if the element bulges out to
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
        self.elements.sort(key=attrgetter('bottom'))
        self.top = self.elements[0].top
        self.bottom = self.elements[-1].bottom
        self.left, self.right = sys.maxint, 0
        for x in self:
            self.left = min(self.left, x.left)
            self.right = max(self.right, x.right)
        self.width, self.height = self.right-self.left, self.bottom-self.top

    def __iter__(self):
        yield from self.elements

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
            if i == 0  or  self.average_line_separation == 0:
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
            if isinstance(elem, int):
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
                if isinstance(elem, int):
                    ans.append('<a name="page_%d"/>'%elem)
                else:
                    ans.append(elem.to_html()+' ')
        ans.append('</div>')
        return ans


class Region:

    def __init__(self, opts, log):
        self.opts, self.log = opts, log
        self.columns = []
        self.top = self.bottom = self.left = self.right = self.width = self.height = 0

    def add(self, columns):
        if not self.columns:
            for x in sorted(columns, key=attrgetter('left')):
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
                    self.log.debug('Absorbing singleton %s into column'%elem.to_html(),
                            idx)
                col.add(elem)


    def collect_stats(self):
        for column in self.columns:
            column.collect_stats()
        self.average_line_separation = sum([x.average_line_separation for x in
            self.columns])/float(len(self.columns))

    def __iter__(self):
        yield from self.columns

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



class Page:

    def __init__(self, page, font_map, opts, log, idc):
        def text_cmp(frst, secnd):
            # Compare 2 text objects.
            # Order by line (top/bottom) then left
            if (frst.top <= secnd.top and frst.bottom >= secnd.bottom-BOTTOM_FACTOR) \
              or (secnd.top <= frst.top and secnd.bottom >= frst.bottom-BOTTOM_FACTOR) :
                # Overlap = same line
                if frst.left < secnd.left :
                    return -1
                elif frst.left == secnd.left :
                    return 0
                return 1
            # Different line so sort into line number
            if frst.bottom < secnd.bottom :
                return -1
            elif frst.bottom == secnd.bottom :
                return 0
            return 1

        # The sort comparison caller
        from functools import cmp_to_key

        self.opts, self.log = opts, log
        self.font_map = font_map
        self.number = int(page.get('number'))
        self.odd_even = self.number % 2    # Odd = 1
        self.top, self.left, self.width, self.height = map(float, map(page.get, ('top', 'left', 'width', 'height')))
        self.id = 'page%d'%self.number
        self.page_break_after = False

        self.texts = []
        self.imgs = []
        # Set margins to values that will get adjusted
        self.left_margin = self.width
        self.right_margin = 0
        # For whether page number has been put in <a>
        self.id_used = 0

        for text in page.xpath('descendant::text'):
            self.texts.append(Text(text, self.font_map, self.opts, self.log, idc))
            text = self.texts[-1]
            # Allow for '  <i|b|etc>  ...'
            # In fact, these get split by xpath, so the '<' will be at the start of a fragment
            matchObj = re.match(r'^(\s*)(<[^>]+>)?(\s*)(.*)$', text.raw)
            s1 = matchObj.group(1)
            s2 = matchObj.group(3)
            t1 = matchObj.group(2)
            t2 = matchObj.group(4)
            if t1 is None:
                t1 = ''
            if t2 is None:
                t2 = ''
            tx = t1 + t2
            # Check within page boundaries.
            # Remove lines of only spaces.  Could be <i> </i> etc., but process later
            # Need to keep any href= (and others?)
            if len(tx) == 0 \
              or text.top < self.top \
              or text.top > self.height \
              or text.left > self.left+self.width \
              or text.left < self.left:
              #and re.match(r'href=', text.raw) is None:
                self.texts.remove(text)
            elif  (self.opts.pdf_header_skip <= 0 or text.top >= self.opts.pdf_header_skip) \
              and (self.opts.pdf_footer_skip <= 0 or text.top <= self.opts.pdf_footer_skip):
                # Remove leading spaces and make into indent
                # Assume 1 space = 1 av_char_width?
                s = len(s1) + len(s2)
                if s > 2:	# Allow two leading spaces
                    # Assume this is a standard indent
                    # Normally text.indented gets set later
                    text.indented = 1
                    w = round(s * text.average_character_width/2.0)	# Spaces < avg width
                    text.raw = tx
                    text.text_as_string = text.text_as_string[s:]
                    text.left += w	# Add indent
                    text.last_left += w
                    text.width -= w	# Reduce width
                    text.final_width -= w
                self.left_margin = min(text.left, self.left_margin)
                self.right_margin = max(text.right, self.right_margin)
                # Change #nnn to page_nnn in hrefs
                matchObj = re.match(r'^(.*)(<a href)(.+)("index.html#)(\d+)(".+)$', text.raw)
                if matchObj is not None:
                    text.raw = matchObj.group(1)+matchObj.group(2)+matchObj.group(3)+matchObj.group(4) \
                        +'page_'+matchObj.group(5)+matchObj.group(6)

            else:
                # Not within text boundaries
                self.texts.remove(text)

        # Find any image occurances if requested
        # These can be interspersed with text
        if not self.opts.no_images:
            for img in page.xpath('descendant::image'):
                self.imgs.append(Image(img, self.opts, self.log, idc))

        self.textwidth = self.right_margin - self.left_margin

        # Sort into page order.  bottom then left
        # NB. This is only approximate as different sized characters
        #     can mean sections of a line vary in top or bottom.
        #     bottom is less varied than top, but is not guaranteed.
        # Multi-line characters make things even more interesting.
        self.texts.sort(key=cmp_to_key(text_cmp))

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

    def find_match(self, frag):
        for t in self.texts:
            #  and abs(t.bottom - frag.bottom) <= BOTTOM_FACTOR :
            if t is not frag :
                # Do the parts of a line overlap?
                # Some files can have separate lines overlapping slightly
                # BOTTOM_FACTOR allows for this
                if (frag.top == t.top or frag.bottom == t.bottom) \
                  or (frag.top < t.top and frag.bottom > t.top+BOTTOM_FACTOR) \
                  or (frag.top < t.top and frag.bottom+BOTTOM_FACTOR > t.bottom) \
                  or (t.top < frag.top and t.bottom > frag.top+BOTTOM_FACTOR) \
                  or (t.top < frag.top and t.bottom+BOTTOM_FACTOR > frag.bottom):
                    #return t	# Force match if same line
                    # Sorting can put parts of a line in the wrong order if there are small chars
                    if t.left < frag.left:
                        hdelta = frag.left - t.right
                    else:
                        hdelta = t.left - frag.right
                    hoverlap = COALESCE_FACTOR * frag.average_character_width
                    if hdelta > -hoverlap and hdelta < hoverlap:
                        return t
        return None

    def join_fragments(self, opts):
        # Join fragments on a line
        # Do some basic checks on structure

        match_found = True
        tind = 0
        while match_found:
            match_found, match = False, None
            while tind < len(self.texts):
                frag = self.texts[tind]
                match = self.find_match(frag)
                if match is not None:
                    match_found = True
                    # Because texts are sorted top, left we can get small chars on the same line
                    # appearing after larger ones, even though they are further left
                    if frag.left > match.left:
                        x = frag
                        frag = match
                        match = x
                    frag.coalesce(match, self.number, self.left_margin)
                    break    # Leave tind
                tind += 1
            if match is not None:
                self.texts.remove(match)

    def check_centered(self, stats):
        # Check for centered text
        # Also check for right aligned, and basic chapter structure

        # If there are different left/indents, need to adjust for this page

        # The centering check would fail where all lines on a page are centered
        # so use stats_left, stats_right, and stats_indent
        first = True
        # Assume not Contents
        self.contents = False
        # Even or odd page?
        if self.odd_even:
            left = self.stats_left_odd
            indent = self.stats_indent_odd
            indent1 = self.stats_indent_odd1
        else:
            left = self.stats_left_even
            indent = self.stats_indent_even
            indent1 = self.stats_indent_even1

        m = len(self.texts)
        for i in range(m):
            t = self.texts[i]
            lmargin = t.left
            rmargin = self.width - t.right
            # Do we have a sequence of indented lines?
            xmargin = ymargin = -1
            if i > 0:
                xmargin = self.texts[i-1].left
            if i < m-1:
                ymargin = self.texts[i+1].left

            # Don't want to set headings on a Contents page
            # NB Doesn't work where Contents goes to another page
            if re.match(r'(?i)^\s*(table of )?contents\s*$', t.text_as_string) is not None:
                self.contents = True
                t.tag = 'h2'	# It won't get set later
            # Centered if left and right margins are within FACTOR%
            # Because indents can waver a bit, use between indent and indent1 as == indent
            if (lmargin < indent or lmargin > indent1) \
              and lmargin > left \
              and lmargin != xmargin \
              and lmargin != ymargin \
              and lmargin >= rmargin - rmargin*CENTER_FACTOR \
              and lmargin <= rmargin + rmargin*CENTER_FACTOR:
               #and t.left + t.width + t.left >= self.width + l_offset - t.average_character_width \
               #and t.left + t.width + t.left <= self.width + l_offset + t.average_character_width:
                t.align = 'C'
            # Right aligned if left > FACTOR% of right
            elif lmargin > indent \
              and lmargin > rmargin*RIGHT_FACTOR:
              #and t.right >= self.width - t.average_character_width:
                # What about right-aligned but indented on right?
                # What about indented rather than right-aligned?
                t.align = 'R'
            if not self.contents:
              # We can get <a href=...Chapter...  Should this check be done?
              #if 'href=' not in t.raw:
                # Check for Roman numerals as the only thing on a line
                if re.match(r'^\s*[iIxXvV]+\s*$', t.text_as_string) is not None:
                    t.tag = 'h3'
                # Check for centered digits only
                elif first and t.align == 'C' and re.match(r'^\s*\d+\s*$', t.text_as_string) is not None:
                    t.tag = 'h2'
                elif re.match(r'(?i)^\s*part\s[A-Za-z0-9]+$', t.text_as_string) is not None:
                    t.tag = 'h1'
                # Check for 'Chapter' or a centered word at the top of the page
                # Some PDFs have chapter starts within the page so this check often fails
                elif re.match(r'(?i)^\s*chapter\s', t.text_as_string) is not None \
                  or re.match(r'(?i)^\s*prologue|epilogue\s*$', t.text_as_string) is not None \
                  or (first and t.align == 'C' and re.match(r'(?i)^\s*[a-z -]+\s*$', t.text_as_string) is not None) \
                  or (first and re.match(r'^\s*[A-Z -]+\s*$', t.text_as_string) is not None):
                    t.tag = 'h2'
            first = False

        # Now check image alignment
        for i in self.imgs:
            lmargin = i.left
            rmargin = self.width - i.right
            if lmargin > left \
              and lmargin != indent \
              and lmargin >= rmargin - rmargin*CENTER_FACTOR \
              and lmargin <= rmargin + rmargin*CENTER_FACTOR:
                i.align = 'C'

    def coalesce_paras(self, stats):
        # Join lines into paragraphs
        # Even or odd page?
        if self.odd_even:
            left = self.stats_left_odd
            indent = self.stats_indent_odd
            indent1 = self.stats_indent_odd1
        else:
            left = self.stats_left_even
            indent = self.stats_indent_even
            indent1 = self.stats_indent_even1


        def can_merge(self, first_text, second_text, stats):
            # Can two lines be merged into one paragraph?
            # Some PDFs have a wandering left margin which is consistent on a page
            # but not within the whole document.  Hence use self.stats_left
            # Try to avoid close double quote at end of one and open double quote at start of next
            #
            # "float:left" occurs where there is a multi-line character, so indentation is messed up
            if ((second_text.left < left + second_text.average_character_width \
                and (second_text.left == first_text.last_left \
                 or (second_text.left < first_text.last_left \
                  and (first_text.indented > 0 or '"float:left"' in first_text.raw)))) \
               or (second_text.left == first_text.last_left \
                and first_text.indented == 0 \
                and second_text.left >= indent) \
               or (second_text.left == first_text.last_left \
                and first_text.indented == second_text.indented \
                and second_text.indented > 1) \
               or (second_text.left >= first_text.last_left \
                and second_text.bottom <= first_text.bottom)) \
              and 'href=' not in second_text.raw \
              and first_text.bottom + stats.line_space + (stats.line_space*LINE_FACTOR) \
                    >= second_text.bottom \
              and first_text.final_width > self.width*self.opts.unwrap_factor \
              and not (re.match('.*[.!?].$', first_text.text_as_string) is not None \
                   and ((first_text.text_as_string[-1] == '\u0022' and second_text.text_as_string[0] == '\u0022') \
                     or (first_text.text_as_string[-1] == '\u2019' and second_text.text_as_string[0] == '\u2018') \
                     or (first_text.text_as_string[-1] == '\u201d' and second_text.text_as_string[0] == '\u201c'))):
                # This has checked for single quotes (9...6), double quotes (99...66), and "..."
                # at end of 1 line then start of next as a check for Don't merge
                return True
            return False

        # Loop through texts elements and coalesce if same lmargin
        # and no large gap between lines
        # Have to restart loop if an entry is removed
        # Doesn't work well with things like Contents list, hence check href
        match_found = True
        last_frag = None
        tind = 0
        while match_found:
            match_found, match = False, None
            # Same left margin probably means coalesce
            while tind < len(self.texts):
                frag = self.texts[tind]
                # Remove lines of only spaces
                if re.match(r'^\s+$', frag.raw) is not None:
                    match = frag
                    break    # Leave tind

                if last_frag is not None \
                  and frag != last_frag \
                  and can_merge(self, last_frag, frag, stats):
                    last_frag.coalesce(frag, self.number, self.left_margin)
                    last_frag.last_left = frag.left
                    last_frag.final_width = frag.final_width
                    match = frag
                    break    # Leave tind
                else:
                    # Check for start of a paragraph being indented
                    # Ought to have some way of setting a standard indent
                    if frag.tag == 'p':
                        if frag.indented == 0 \
                          and frag.align != 'C' \
                          and frag.left > left + frag.average_character_width:
                            #frag.indented = int((frag.left - self.stats_left) / frag.average_character_width)
                            # Is it approx self.stats_indent?
                            if frag.left >= indent and frag.left <= indent1:
                                frag.indented = 1  # 1em
                            else:  # Assume left margin of approx = number of chars
                                # Should check for values approx the same, as with indents
                                frag.margin_left = int(round((frag.left - left) / frag.average_character_width)+0.5)
                        if last_frag is not None \
                          and frag.bottom - last_frag.bottom \
                              > stats.para_space*SECTION_FACTOR:
                          #and frag.top - last_frag.bottom > frag.height + stats.line_space + (stats.line_space*LINE_FACTOR):
                            frag.blank_line_before = 1
                last_frag = frag
                tind += 1
            if match is not None:
                match_found = True
                self.texts.remove(match)    # Leave tind

    def remove_head_foot_regex(self, opts):

        # Remove headers or footers from a page
        # if there is a regex supplied
        if len(opts.pdf_header_regex) > 0 \
          and len(self.texts) > 0:
            # Remove lines if they match
            for i in range(LINE_SCAN_COUNT):
                if len(self.texts) < 1:
                    break
                if re.match(opts.pdf_header_regex, self.texts[0].text_as_string) is not None :
                    # There could be fragments which are spread out, so join_fragments has not coalesced them
                    # Not sure that this would work as it relies on the first fragment matching regex
                    t = self.texts[0]
                    #match = self.find_match(t)
                    #while match is not None:
                    #    self.texts.remove(match)
                    #    match = self.find_match(t)
                    self.texts.remove(t)

        if len(opts.pdf_footer_regex) > 0 \
          and len(self.texts) > 0:
            # Remove the last lines if they match
            for i in range(LINE_SCAN_COUNT):
                if len(self.texts) < 1:
                    break
                if re.match(opts.pdf_footer_regex, self.texts[-1].text_as_string) is not None :
                    # There could be fragments which are spread out, so join_fragments has not coalesced them
                    t = self.texts[-1]
                    #match = self.find_match(t)
                    #while match is not None:
                    #    self.texts.remove(match)
                    #    match = self.find_match(t)
                    self.texts.remove(t)

    def create_page_format(self, stats, opts):
        # Join fragments into lines
        # then remove any headers/footers/unwanted areas

        self.update_font_sizes(stats)

        # Join fragments on a line
        self.join_fragments(opts)

        # This processes user-supplied regex for header/footer
        # Do this before automatic actions
        self.remove_head_foot_regex(opts)

    def find_margins(self, tops, indents_odd, indents_even, line_spaces, bottoms, rights):

        #from collections import Counter

        # Should check for left margin and indent for this page
        # Find the most used top, left margins, and gaps between lines
        # The most used font will be treated as size 1em
        max_bot = 0
        max_right = 0
        last_top = 0
        #last_bottom = 0
        first = True
        for text in self.texts:
            top = text.top
            left = text.left
            if round(left) != left :
                text.left = left = round(left)
            right = text.right
            if round(right) != right :
                text.right = right = round(right)
            if first:
                tops[top] = tops.get(top, 0) + 1
                first = False
            else:
                # Space from 1 line to the next
                space = abs(top - last_top)
                # Beware of multiple text on same line. These look like small spacing
                if text.height <= space:
                    line_spaces[space] = line_spaces.get(space, 0) + 1

            last_top = top
            max_bot = max(max_bot, text.bottom)

            max_right = max(max_right, text.right)

            if self.odd_even:
                indents_odd[left] = indents_odd.get(left, 0) + 1
            else:
                indents_even[left] = indents_even.get(left, 0) + 1

        if max_bot > 0:
            bottoms[max_bot] = bottoms.get(max_bot, 0) + 1
        if max_right > 0:
            rights[max_right] = rights.get(max_right, 0) + 1

        return
        #########################
        #### NOT IMPLEMENTED ####
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
        if self.opts.verbose > 2:
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
        neighbors = sorted(neighbors, key=attrgetter('left'))
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
                columns.sort(key=attrgetter('left'))
        return columns

    def find_elements_in_row_of(self, x):
        interval = Interval(x.top,
                x.top + YFUZZ*(self.average_text_height))
        h_interval = Interval(x.left, x.right)
        for y in self.elements[x.idx:x.idx+15]:
            if y is not x:
                y_interval = Interval(y.top, y.bottom)
                x_interval = Interval(y.left, y.right)
                if interval.intersection(y_interval).width > \
                    0.5*self.average_text_height and \
                    x_interval.intersection(h_interval).width <= 0:
                    yield y

    def update_font_sizes(self, stats):
        # Font sizes start as pixels/points, but em is more useful
        for text in self.texts:
            text.font_size_em = self.font_map[text.font.id].size_em
            if text.font_size_em != 0.00 and text.font_size_em != 1.00:
                text.raw = '<span style="font-size:%sem">%s</span>'%(str(text.font_size_em),text.raw)

    def second_pass(self, stats, opts):

        # If there are alternating pages, pick the left and indent for this one
        self.stats_left_odd = stats.left_odd
        self.stats_indent_odd = stats.indent_odd
        self.stats_indent_odd1 = stats.indent_odd1
        self.stats_left_even = stats.left_even
        self.stats_indent_even = stats.indent_even
        self.stats_indent_even1 = stats.indent_even1
        self.stats_right = stats.right

        # Join lines to form paragraphs
        self.coalesce_paras(stats)

        self.check_centered(stats)

        #self.elements = list(self.texts)
        #for img in page.xpath('descendant::img'):
        #    self.elements.append(Image(img, self.opts, self.log, idc))
        #self.elements.sort(cmp=lambda x,y:cmp(x.top, y.top))

        return
        # NOT IMPLEMENTED
        'Locate paragraph boundaries in each column'
        for region in self.regions:
            region.collect_stats()
            region.linearize()


    def to_html(self):
        # If ans.append is used, newlines are inserted between each element
        ans = []
        iind = 0
        itop = 0
        ilen = len(self.imgs)
        for text in self.texts:
            if iind < ilen:
                itop = self.imgs[iind].top
            else:
                itop = 999999
            if itop <= text.top:
                ans.append('<p')
                if self.imgs[iind].align == 'C':
                    ans[-1] += ' style="text-align:center"'
                if self.id_used == 0:
                    self.id_used = 1
                    ans[-1] += ' id="page_%d"'%self.number
                ans[-1] += '>'
                ans[-1] += self.imgs[iind].to_html()
                ans[-1] += '</p>'
                iind += 1
            if text.blank_line_before > 0:
                ans.append('<p style="text-align:center">&#160;</p>')
            ans.append('<%s'%text.tag)
            # Should be only for Headings, but there is no guarantee that the heading will be recognised
            # So put in an ID once per page in case the Contents references it
            #   and  text.tag[0] == 'h'
            if self.id_used == 0:
                self.id_used = 1
                ans[-1] += ' id="page_%d"'%self.number
            if text.align == 'C':
                ans[-1] += ' style="text-align:center"'
            elif text.align == 'R':
                ans[-1] += ' style="text-align:right"'
            elif text.indented > 0:
                ans[-1] += ' style="text-indent:'
                ans[-1] += str(text.indented)
                #ans[-1] += '1'
                ans[-1] += 'em"'
            # The margins need more work.  e.g. can have indented + left + right
            elif text.margin_left > 0:
                ans[-1] += ' style="margin-left:'
                ans[-1] += str(text.margin_left)
                ans[-1] += 'em"'
            elif text.margin_right > 0:
                ans[-1] += ' style="margin-right:'
                ans[-1] += str(text.margin_right)
                ans[-1] += 'em"'
            ans[-1] += '>'
            ans[-1] += text.to_html()
            ans[-1] += '</%s>'%text.tag  # Closing tag
            if text.blank_line_after > 0:
                ans.append('<p style="text-align:center">&#160;</p>')

        # Any remaining images
        while iind < ilen:
            ans.append('<p')
            if self.imgs[iind].align == 'C':
                ans[-1] += ' style="text-align:center"'
            if self.id_used == 0:
                self.id_used = 1
                ans[-1] += ' id="page_%d"'%self.number
            ans[-1] += '>'
            ans[-1] += self.imgs[iind].to_html()
            ans[-1] += '</p>'
            iind += 1

        return ans

class PDFDocument:

    def __init__(self, xml, opts, log):
        #from calibre.rpdb import set_trace;  set_trace()

        self.opts, self.log = opts, log

        # Check for a testable value
        if self.opts.pdf_header_regex is None:
            self.opts.pdf_header_regex = ''	# Do nothing
        if self.opts.pdf_footer_regex is None:
            self.opts.pdf_footer_regex = ''	# Do nothing

        parser = etree.XMLParser(recover=True)
        self.root = etree.fromstring(xml, parser=parser)
        idc = iter(range(sys.maxsize))
        self.stats = DocStats()

        self.fonts = []

        self.font_map = {}

        for spec in self.root.xpath('//fontspec'):
            self.fonts.append(Font(spec))
            self.font_map[self.fonts[-1].id] = self.fonts[-1]

        self.pages = []
        #self.page_map = {}

        for page in self.root.xpath('//page'):
            page = Page(page, self.font_map, opts, log, idc)
            #self.page_map[page.id] = page
            self.pages.append(page)

        self.tops = {}
        self.indents_odd = {}
        self.indents_even = {}
        self.line_spaces = {}
        self.bottoms = {}
        self.rights = {}
        self.font_sizes = {}

        self.collect_font_statistics()

        # Create lines for pages and remove headers/footers etc.
        for page in self.pages:
            page.document_font_stats = self.font_size_stats
            # This processes user-supplied regex for header/footer
            page.create_page_format(self.stats, self.opts)

        # Need to work out the header/footer automatically if opt < 0
        if self.opts.pdf_header_skip < 0 or self.opts.pdf_footer_skip < 0:
            self.find_header_footer()

        # Remove any header/footer
        if self.opts.pdf_header_skip > 0 or self.opts.pdf_footer_skip > 0:
            self.remove_header_footer()

        # Work out document dimensions from page format
        for page in self.pages:
            page.find_margins(self.tops, self.indents_odd, self.indents_even, \
                             self.line_spaces, self.bottoms, self.rights)

        self.setup_stats()

        # Joins lines etc. into paragraphs
        for page in self.pages:
            page.second_pass(self.stats, self.opts)

        # Join paragraphs across page boundaries
        self.merge_pages(idc)

        #self.linearize()
        self.render()

    def collect_font_statistics(self):
        self.font_size_stats = {}
        for p in self.pages:
            for sz in p.font_size_stats:
                chars = p.font_size_stats[sz]
                if sz not in self.font_size_stats:
                    self.font_size_stats[sz] = 0
                self.font_size_stats[sz] += chars

            for text in p.texts:
                font = int(text.font.id)
                self.font_sizes[font] = self.font_sizes.get(font, 0) + 1

        self.font_size_stats = FontSizeStats(self.font_size_stats)

        # Find most popular font so that will be treated as 1em
        fcount = f_ind = 0
        for f in self.font_sizes:
            if fcount < self.font_sizes[f]:
                fcount = self.font_sizes[f]
                f_ind = f

        if len(self.fonts) > 0:
            self.stats.font_size = self.fonts[f_ind].size
        else:
            self.stats.font_size = 12.0

        for f in self.fonts:
            f.size_em = round(f.size / self.stats.font_size, 2)

    def setup_stats(self):
        # This probably needs more work on line spacing/para spacing
        # Maybe sort the line_spaces array.
        # It is possible to have more than 1 line space value, e.g. 8.0, 9.0, 10.0
        # then more than 1 para space, e.g. 24.0, 25.0, 26.0
        # Thus the count of a para space could be > the most popular line space.
        # So, probably need to find the max line space and max para space
        # rather than simply the most popular.
        # At the moment it only does this when spaces are close in popularity.

        # Find (next) most popular gap between lines
        def find_line_space(skip):
            scount, soffset = 0, 0
            for s in self.line_spaces:
                if scount <= self.line_spaces[s] \
                and (skip <= 0 or self.line_spaces[s] < skip):
                    scount = self.line_spaces[s]
                    soffset = s
            return scount, soffset

        # Find (next) most popular indent
        def find_indent(indents, skip):
            icount, ioffset = 0, 0
            for i in indents:
                if icount <= indents[i] \
                and (skip <= 0 or indents[i] < skip):
                    icount = indents[i]
                    ioffset = i
            return icount, ioffset

        def set_indents(indents, odd_even):
            # Find most popular left so that will be treated as left of page
            indent_c = 0
            indent_k = indent_k1 = 0
            count = len(indents)
            while count > 0:
                c, k = find_indent(indents, indent_c)
                if indent_c <= 0:
                    indent_c = c
                if indent_k <= 0:
                    indent_k = k
                elif abs(indent_k - k) <= SAME_INDENT:
                    indent_k = min(indent_k, k)
                    indent_k1 = max(indent_k1, k)
                    indent_c = min(indent_c, c)
                else:
                    break
                count -= 1

            save_left = indent_k
            if odd_even:
                self.stats.left_odd = indent_k    # Min left value
                # Max left value
                if indent_k1:
                    self.stats.left_odd1 = indent_k1
                else:
                    self.stats.left_odd1 = indent_k
            else:
                self.stats.left_even = indent_k    # Min left value
                # Max left value
                if indent_k1:
                    self.stats.left_even1 = indent_k1
                else:
                    self.stats.left_even1 = indent_k

            # Find second most popular left so that will be treated as indent
            indent_c -= 1
            total_c = 0
            indent_k = indent_k1 = 0
            count = len(indents)
            while count > 0:
                c, k = find_indent(indents, indent_c)
                if indent_c <= 0:
                    indent_c = c
                if indent_k <= 0:
                    indent_k = k
                elif abs(indent_k - k) <= SAME_INDENT:
                    indent_k = min(indent_k, k)
                    indent_k1 = max(indent_k1, k)
                    indent_c = min(indent_c, c)
                else:
                    break
                total_c += c
                count -= 1

            # Find third most popular left as that might actually be the indent
            # if between left and current and occurs a reasonable number of times.
            save_k = indent_k
            save_k1 = indent_k1
            save_count = total_c
            indent_c -= 1
            total_c = 0
            indent_k = indent_k1 = 0
            count = len(indents)
            while count > 0:
                c, k = find_indent(indents, indent_c)
                if indent_c <= 0:
                    indent_c = c
                if indent_k <= 0:
                    indent_k = k
                elif abs(indent_k - k) <= SAME_INDENT:
                    indent_k = min(indent_k, k)
                    indent_k1 = max(indent_k1, k)
                    indent_c = min(indent_c, c)
                else:
                    break
                total_c += c
                count -= 1
            # Is this to be used?
            if (save_k < indent_k \
               and save_k > save_left) \
              or total_c < save_count / 2:
                # The usual case. The first ones found are to be used
                indent_k = save_k
                indent_k1 = save_k1

            if odd_even:
                self.stats.indent_odd = indent_k    # Min indent value
                # Max indent value
                if indent_k1:
                    self.stats.indent_odd1 = indent_k1
                else:
                    self.stats.indent_odd1 = indent_k
            else:
                self.stats.indent_even = indent_k    # Min indent value
                # Max indent value
                if indent_k1:
                    self.stats.indent_even1 = indent_k1
                else:
                    self.stats.indent_even1 = indent_k

            # For safety, check left and indent are in the right order
            if odd_even:
                if self.stats.indent_odd != 0 \
                  and self.stats.left_odd > self.stats.indent_odd:
                    l = self.stats.left_odd
                    l1 = self.stats.left_odd1
                    self.stats.left_odd = self.stats.indent_odd
                    self.stats.left_odd1 = self.stats.indent_odd1
                    self.stats.indent_odd = l
                    self.stats.indent_odd1 = l1
            else:
                if self.stats.indent_even != 0 \
                  and self.stats.left_even > self.stats.indent_even:
                    l = self.stats.left_even
                    l1 = self.stats.left_even1
                    self.stats.left_even = self.stats.indent_even
                    self.stats.left_even1 = self.stats.indent_even1
                    self.stats.indent_even = l
                    self.stats.indent_even1 = l1

        # Find most popular top so that will be treated as top of page
        tcount = 0
        for t in self.tops:
            if tcount < self.tops[t]:
                tcount = self.tops[t]
                self.stats.top = t

        # Some PDFs have alternating pages with different lefts/indents.
        # Always separate odd and even, though they are usually the same.
        # Find most left/indent for odd pages
        set_indents(self.indents_odd, 1)
        # Find most left/indent for even pages
        set_indents(self.indents_even, 0)

        # Find farthest right so that will be treated as page right
        ## SHOULD DO RIGHT2 as well
        rcount = 0
        for r in self.rights:
            if rcount < r:
                rcount = r
                self.stats.right = r

        # Do something about left and right margin values
        # They need the same sort of treatment as indents
        # self.stats.margin_left = 0
        # self.stats.margin_right = 0

        # Some PDFs have no indentation of paragraphs.
        # In this case, any value for indent is random.
        # Assume that at least 20% of lines would be indented
        # or that indent offset will be < 10% of line width
        if self.stats.indent_odd - self.stats.left_odd > (self.stats.right - self.stats.left_odd) * 0.10:    # 10%
            self.stats.indent_odd = self.stats.indent_odd1 = self.stats.left_odd
            # Assume for both if self.stats.indent_even - self.stats.left_even > (self.stats.right - self.stats.left_even) * 0.10:    # 10%
            self.stats.indent_even = self.stats.indent_even1 = self.stats.left_even

        # Sort spaces into ascending order then loop through.
        # Lowest value(s) are line spacing, next are para
        # Spaces not yet set up
        self.stats.line_space = self.stats.para_space = -1.0
        # Find spacing values
        # Find most popular space so that will be treated as line space
        line_k = 0
        line_c = 0
        count = len(self.line_spaces)
        while count > 0:
            c, k = find_line_space(line_c)
            if line_c <= 0:
                line_c = c
            if line_k <= 0:
                line_k = k
            elif abs(line_k - k) <= SAME_SPACE:
                line_k = max(line_k, k)
                line_c = min(line_c, c)
            else:
                break
            count -= 1

        # Get the next most popular gap
        para_c = line_c-1
        para_k = 0
        count = len(self.line_spaces)
        while count > 0:
            c, k = find_line_space(para_c)
            if para_k <= 0:
                para_k = k
            if abs(para_k - k) <= SAME_SPACE:
                para_k = max(para_k, k)
                para_c = min(para_c, c)
            else:
                break
            count -= 1

        # For safety, check in the right order
        if line_k > para_k:
            x = para_k
            para_k = line_k
            line_k = x

        self.stats.line_space = line_k
        # Some docs have no great distinction for paragraphs
        # Limit the size of the gap, or section breaks not found
        if para_k > line_k * PARA_FACTOR:
            self.stats.para_space = round(line_k * PARA_FACTOR)
        else:
            self.stats.para_space = para_k

        # Find the max bottom so that will be treated as bottom of page
        # Or most popular bottom?  Or the max used value within 10% of max value?
        bcount = 0
        for b in self.bottoms:
            if bcount < self.bottoms[b]:
              #and b > self.stats.bottom*0.9:
                bcount = self.bottoms[b]
            if b > self.stats.bottom:
                self.stats.bottom = b

    def find_header_footer(self):
        # If requested, scan first few pages for possible headers/footers

        if (self.opts.pdf_header_skip >= 0 \
            and self.opts.pdf_footer_skip >= 0) \
          or len(self.pages) < 2:
            # If doc is empty or 1 page, can't decide on any skips
            return

        scan_count = PAGE_SCAN_COUNT
        head_text = [''] * LINE_SCAN_COUNT
        head_match = [0] * LINE_SCAN_COUNT
        head_match1 = [0] * LINE_SCAN_COUNT
        #head_text = ''
        #head_match = 0
        #head_match1 = 0
        head_page = 0
        head_skip = 0
        foot_text = [''] * LINE_SCAN_COUNT
        foot_match = [0] * LINE_SCAN_COUNT
        foot_match1 = [0] * LINE_SCAN_COUNT
        #foot_text = ''
        #foot_match = 0
        #foot_match1 = 0
        foot_page = 0
        foot_skip = 0
        pagenum_text = r'(.*\d+\s+\w+\s+\d+.*)|(\s*\d+\s+.*)|(^\s*[ivxlcIVXLC]+\s*$)'

        pages_to_scan = scan_count
        # Note the a line may be in more than 1 part
        # e.g. Page 1 of 6 ... DocName.pdf
        # so should merge first 2 lines if same top
        # Ditto last 2 lines
        # Maybe should do more than 2 parts
        for page in self.pages:
            if self.opts.pdf_header_skip < 0 \
              and len(page.texts) > 0:
                # There is something at the top of the page
                for head_ind in range(LINE_SCAN_COUNT):
                    if len(page.texts) < head_ind+1 \
                      or page.texts[head_ind].top > page.height/2:
                        break  # Short page
                    t = page.texts[head_ind].text_as_string
                    #if len(page.texts) > 1 and page.texts[0].top == page.texts[1].top:
                    #    t += ' ' + page.texts[1].text_as_string
                    if len(head_text[head_ind]) == 0:
                        head_text[head_ind] = t
                    else:
                        if head_text[head_ind] == t:
                            head_match[head_ind] += 1
                            if head_page == 0:
                                head_page = page.number
                        else:	# Look for page count of format 'n xxx n'
                            if re.match(pagenum_text, t) is not None:
                                head_match1[head_ind] += 1
                                if head_page == 0:
                                    head_page = page.number

            if self.opts.pdf_footer_skip < 0 \
              and len(page.texts) > 0:
                # There is something at the bottom of the page
                for foot_ind in range(LINE_SCAN_COUNT):
                    if len(page.texts) < foot_ind+1 \
                      or page.texts[-foot_ind-1].top < page.height/2:
                        break  # Short page
                    t = page.texts[-foot_ind-1].text_as_string
                    #if len(page.texts) > 1 and page.texts[-1].top == page.texts[-2].top:
                    #    t += ' ' + page.texts[-2].text_as_string
                    if len(foot_text[foot_ind]) == 0:
                        foot_text[foot_ind] = t
                    else:
                        if foot_text[foot_ind] == t:
                            foot_match[foot_ind] += 1
                            if foot_page == 0:
                                foot_page = page.number
                        else:	# Look for page count of format 'n xxx n'
                            if re.match(pagenum_text, t) is not None:
                                foot_match1[foot_ind] += 1
                                if foot_page == 0:
                                    foot_page = page.number

            pages_to_scan -= 1
            if pages_to_scan < 1:
                break

        if pages_to_scan > 0:
            # Doc is shorter than scan_count
            pages_to_scan = scan_count - pages_to_scan	# Number scanned
        else:
            # All required pages scanned
            pages_to_scan = scan_count
        pages_to_scan /= 2	# Are at least half matching?

        head_ind = 0
        for i in range(LINE_SCAN_COUNT):
            if head_match[i] > pages_to_scan or head_match1[i] > pages_to_scan:
                head_ind = i  # Remember the last matching line
        if head_match[head_ind] > pages_to_scan or head_match1[head_ind] > pages_to_scan:
            t = self.pages[head_page].texts[head_ind]
            head_skip = t.top + t.height + 1

        foot_ind = 0
        for i in range(LINE_SCAN_COUNT):
            if foot_match[i] > pages_to_scan or foot_match1[i] > pages_to_scan:
                foot_ind = i  # Remember the last matching line
        if foot_match[foot_ind] > pages_to_scan or foot_match1[foot_ind] > pages_to_scan:
            t = self.pages[foot_page].texts[-foot_ind-1]
            foot_skip = t.top - 1

        if head_skip > 0:
            self.opts.pdf_header_skip = head_skip
        if foot_skip > 0:
            self.opts.pdf_footer_skip = foot_skip

    def remove_header_footer(self):
        # Remove any header/footer lines from all pages
        for page in self.pages:
            # If a text is removed, we need to restart the loop or what was the next will be skipped
            removed = True
            while removed:
                removed = False
                for t in page.texts:
                    if (self.opts.pdf_header_skip > 0 and t.top < self.opts.pdf_header_skip) \
                    or (self.opts.pdf_footer_skip > 0 and t.top > self.opts.pdf_footer_skip):
                        page.texts.remove(t)
                        removed = True
                        break    # Restart loop

    def merge_pages(self, idc):
        # Check for pages that can be merged

        # When merging pages, assume short last lines mean no merge
        # BUT unfortunately there is no way to tell the difference
        # between a continuation of a paragraph and a 'section break'
        # if the previous page ends a sentence.
        # First, find the minimum text top and the maximum text bottom
        min_top = self.stats.top
        max_bottom = self.stats.bottom
        # The space at the end of a page that indicates there is no merge
        orphan_space = max_bottom - ORPHAN_LINES*self.stats.line_space
        # Keep a note of the position of the final line on the merged page
        save_bottom = 0
        # After merge, skip to this page
        pind = 0

        # Now merge where bottom of one is within ORPHAN_LINES lines of max_bottom
        # and top of next is within a line of min_top
        # and margins correspond, and it's a normal paragraph
        merge_done = True
        while merge_done:
            merge_done = False  # A merge was done
            merged_page = None  # Page merged into previous
            candidate = None    # Lines close enough to the bottom that it might merge
            while pind < len(self.pages):
                page = self.pages[pind]
                if page.odd_even:
                    stats_left = page.stats_left_odd
                else:
                    stats_left = page.stats_left_even
                # Do not merge if the next paragraph is indented
                if page.texts:
                    if candidate \
                      and page.texts[0].indented == 0:
                        last_line = candidate.texts[-1]
                        merged_text = page.texts[0]
                        top = merged_text.top
                        # How much space in pixels was at the end of the last line?
                        # If the book is justified text, any space could mean end-of-para
                        # So, how to check for a justified book/page?
                        last_spare = candidate.right_margin - last_line.final_width    # Pixels
                        # How big is the first word on the next line?
                        merged_first = re.match(r'^([^ ]+)\s', merged_text.text_as_string)
                        if merged_first is not None:
                            # First word number of chars as pixels
                            merged_len = len(merged_first.group(1)) * merged_text.average_character_width
                        else:
                            merged_len = merged_text.right
                        # Allow where the last line ends with or next line starts with lower case.
                        if re.match('.*[a-z, -]$', last_line.text_as_string) is not None \
                          or re.match('^[a-z, -]', merged_text.text_as_string) is not None :
                            merged_len = merged_text.right

                        # To use merged_len etc.
                        # Should not merge if speech where last ends 99 or 9 and next starts 66 or 6
                        if top <= min_top + page.average_text_height \
                          and merged_text.tag == 'p' \
                          and 'href=' not in merged_text.raw \
                          and merged_text.left < stats_left + merged_text.average_character_width \
                          and not last_spare > merged_len \
                          and not (re.match('.*[.!?](\u201d|”)$', last_line.text_as_string) is not None
                               and re.match('^(\u201c|“).*', merged_text.text_as_string) is not None):
                            merge_done = True
                            # We don't want to merge partial pages
                            # i.e. if this is the last line, preserve its top/bottom till after merge
                            if len(page.texts) == 1 :
                                save_bottom = merged_text.bottom
                            else:
                                save_bottom = 0.0
                            # Update this page final top/bottom
                            merged_text.top = candidate.texts[-1].top + page.average_text_height
                            merged_text.bottom = merged_text.top + merged_text.height
                            merged_page = page
                            break
                        # If the next page starts below the top, add a blank line before the first line
                        # This must not be done after a merge as the top has moved
                        if page.texts[0].top > self.stats.top + self.stats.line_space:
                            page.texts[0].blank_line_after = 1
                        candidate = None
                    last_line = page.texts[-1]
                    bottom = last_line.bottom
                    # Decide on whether merging is a good idea
                    # Non-indented paragraphs are a problem
                    # Do we have a short page?
                    if bottom < orphan_space \
                      and (len(page.imgs) == 0 or page.imgs[-1].bottom < orphan_space):
                        # Force a new page.
                        # Avoid this if the next page starts with an image that wouldn't fit
                        if pind < len(self.pages)-1:  # There is another page
                            if len(self.pages[pind+1].imgs) == 0 \
                              or (self.pages[pind+1].imgs[0].height < orphan_space \
                                and (len(self.pages[pind+1].texts) == 0 \
                                 or self.pages[pind+1].texts[0].top > self.pages[pind+1].imgs[0].top)):
                                page.page_break_after = True
                    elif (re.match('.*[a-z, ]$', last_line.text_as_string) is not None \
                      or  last_line.final_width > page.width*self.opts.unwrap_factor):
                    #  or (last_line.right * 100.0 / page.right_margin) > LAST_LINE_PERCENT):
                        candidate = page
                else:
                    candidate = None
                pind += 1

            if merge_done:
                # We now need to skip to the next page number
                # The text has been appended to this page, so coalesce the paragraph
                if merged_page.odd_even:
                    left_margin = merged_page.stats_left_odd
                else:
                    left_margin = merged_page.stats_left_even
                candidate.texts[-1].coalesce(merged_text, candidate.number, left_margin)
                merged_page.texts.remove(merged_text)
                # Put back top/bottom after coalesce if final line
                if save_bottom != 0.0 :
                    # Ignore top as that can confuse things where the 1st para of a page
                    # was merged with a previous.  Keep the original top
                    candidate.texts[-1].bottom = save_bottom
                #candidate.coalesce_paras()
                # Have we removed everything from this page (well, all texts and images)
                if len(merged_page.texts) == 0 \
                  and len(merged_page.imgs) == 0:
                    candidate.texts[-1].blank_line_before = 1
                    self.pages.remove(merged_page)

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
        #### Where does the title come from if not run from command line?
        title = 'Converted Ebook'
        if len(sys.argv) > 1:
            title = sys.argv[1]
        # Need to insert font info and styles
        html = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<html xmlns="http://www.w3.org/1999/xhtml">', '<head>',
                '<title>'+title+'</title>',
                '<meta content="PDF Reflow conversion" name="generator"/>',
                '</head>', '<body>']
        for page in self.pages:
            html.extend(page.to_html())
            if page.page_break_after:
                html+= ['<div style="page-break-after:always"></div>']
        html += ['</body>', '</html>']
        raw = ('\n'.join(html)).replace('</strong><strong>', '')
        raw = raw.replace('</i><i>', '')
        raw = raw.replace('</em><em>', '')
        raw = raw.replace('</b><b>', '')
        raw = raw.replace('</strong> <strong>', ' ')
        raw = raw.replace('</i> <i>', ' ')
        raw = raw.replace('</em> <em>', ' ')
        raw = raw.replace('</b> <b>', ' ')
        with open('index.html', 'wb') as f:
            f.write(raw.encode('utf-8'))
