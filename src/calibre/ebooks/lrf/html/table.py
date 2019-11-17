

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import math, sys, re, numbers

from calibre.ebooks.lrf.fonts import get_font
from calibre.ebooks.lrf.pylrs.pylrs import TextBlock, Text, CR, Span, \
                                             CharButton, Plot, Paragraph, \
                                             LrsTextTag
from polyglot.builtins import string_or_bytes, range, native_string_type


def ceil(num):
    return int(math.ceil(num))


def print_xml(elem):
    from calibre.ebooks.lrf.pylrs.pylrs import ElementWriter
    elem = elem.toElement(native_string_type('utf8'))
    ew = ElementWriter(elem, sourceEncoding=native_string_type('utf8'))
    ew.write(sys.stdout)
    print()


def cattrs(base, extra):
    new = base.copy()
    new.update(extra)
    return new


def tokens(tb):
    '''
    Return the next token. A token is :
    1. A string
    a block of text that has the same style
    '''
    def process_element(x, attrs):
        if isinstance(x, CR):
            yield 2, None
        elif isinstance(x, Text):
            yield x.text, cattrs(attrs, {})
        elif isinstance(x, string_or_bytes):
            yield x, cattrs(attrs, {})
        elif isinstance(x, (CharButton, LrsTextTag)):
            if x.contents:
                if hasattr(x.contents[0], 'text'):
                    yield x.contents[0].text, cattrs(attrs, {})
                elif hasattr(x.contents[0], 'attrs'):
                    for z in process_element(x.contents[0], x.contents[0].attrs):
                        yield z
        elif isinstance(x, Plot):
            yield x, None
        elif isinstance(x, Span):
            attrs = cattrs(attrs, x.attrs)
            for y in x.contents:
                for z in process_element(y, attrs):
                    yield z

    for i in tb.contents:
        if isinstance(i, CR):
            yield 1, None
        elif isinstance(i, Paragraph):
            for j in i.contents:
                attrs = {}
                if hasattr(j, 'attrs'):
                    attrs = j.attrs
                for k in process_element(j, attrs):
                    yield k


class Cell(object):

    def __init__(self, conv, tag, css):
        self.conv = conv
        self.tag = tag
        self.css  = css
        self.text_blocks = []
        self.pwidth = -1.
        if tag.has_attr('width') and '%' in tag['width']:
            try:
                self.pwidth = float(tag['width'].replace('%', ''))
            except ValueError:
                pass
        if 'width' in css and '%' in css['width']:
            try:
                self.pwidth = float(css['width'].replace('%', ''))
            except ValueError:
                pass
        if self.pwidth > 100:
            self.pwidth = -1
        self.rowspan = self.colspan = 1
        try:
            self.colspan = int(tag['colspan']) if tag.has_attr('colspan') else 1
            self.rowspan = int(tag['rowspan']) if tag.has_attr('rowspan') else 1
        except:
            pass

        pp = conv.current_page
        conv.book.allow_new_page = False
        conv.current_page = conv.book.create_page()
        conv.parse_tag(tag, css)
        conv.end_current_block()
        for item in conv.current_page.contents:
            if isinstance(item, TextBlock):
                self.text_blocks.append(item)
        conv.current_page = pp
        conv.book.allow_new_page = True
        if not self.text_blocks:
            tb = conv.book.create_text_block()
            tb.Paragraph(' ')
            self.text_blocks.append(tb)
        for tb in self.text_blocks:
            tb.parent = None
            tb.objId  = 0
            # Needed as we have to eventually change this BlockStyle's width and
            # height attributes. This blockstyle may be shared with other
            # elements, so doing that causes havoc.
            tb.blockStyle = conv.book.create_block_style()
            ts = conv.book.create_text_style(**tb.textStyle.attrs)
            ts.attrs['parindent'] = 0
            tb.textStyle = ts
            if ts.attrs['align'] == 'foot':
                if isinstance(tb.contents[-1], Paragraph):
                    tb.contents[-1].append(' ')

    def pts_to_pixels(self, pts):
        pts = int(pts)
        return ceil((float(self.conv.profile.dpi)/72)*(pts/10))

    def minimum_width(self):
        return max([self.minimum_tb_width(tb) for tb in self.text_blocks])

    def minimum_tb_width(self, tb):
        ts = tb.textStyle.attrs
        default_font = get_font(ts['fontfacename'], self.pts_to_pixels(ts['fontsize']))
        parindent = self.pts_to_pixels(ts['parindent'])
        mwidth = 0
        for token, attrs in tokens(tb):
            font = default_font
            if isinstance(token, numbers.Integral):  # Handle para and line breaks
                continue
            if isinstance(token, Plot):
                return self.pts_to_pixels(token.xsize)
            ff = attrs.get('fontfacename', ts['fontfacename'])
            fs = attrs.get('fontsize', ts['fontsize'])
            if (ff, fs) != (ts['fontfacename'], ts['fontsize']):
                font = get_font(ff, self.pts_to_pixels(fs))
            if not token.strip():
                continue
            word = token.split()
            word = word[0] if word else ""
            width = font.getsize(word)[0]
            if width > mwidth:
                mwidth = width
        return parindent + mwidth + 2

    def text_block_size(self, tb, maxwidth=sys.maxsize, debug=False):
        ts = tb.textStyle.attrs
        default_font = get_font(ts['fontfacename'], self.pts_to_pixels(ts['fontsize']))
        parindent = self.pts_to_pixels(ts['parindent'])
        top, bottom, left, right = 0, 0, parindent, parindent

        def add_word(width, height, left, right, top, bottom, ls, ws):
            if left + width > maxwidth:
                left = width + ws
                top += ls
                bottom = top+ls if top+ls > bottom else bottom
            else:
                left += (width + ws)
                right = left if left > right else right
                bottom = top+ls if top+ls > bottom else bottom
            return left, right, top, bottom

        for token, attrs in tokens(tb):
            if attrs is None:
                attrs = {}
            font = default_font
            ls = self.pts_to_pixels(attrs.get('baselineskip', ts['baselineskip']))+\
                 self.pts_to_pixels(attrs.get('linespace', ts['linespace']))
            ws = self.pts_to_pixels(attrs.get('wordspace', ts['wordspace']))
            if isinstance(token, numbers.Integral):  # Handle para and line breaks
                if top != bottom:  # Previous element not a line break
                    top = bottom
                else:
                    top += ls
                    bottom += ls
                left = parindent if int == 1 else 0
                continue
            if isinstance(token, Plot):
                width, height = self.pts_to_pixels(token.xsize), self.pts_to_pixels(token.ysize)
                left, right, top, bottom = add_word(width, height, left, right, top, bottom, height, ws)
                continue
            ff = attrs.get('fontfacename', ts['fontfacename'])
            fs = attrs.get('fontsize', ts['fontsize'])
            if (ff, fs) != (ts['fontfacename'], ts['fontsize']):
                font = get_font(ff, self.pts_to_pixels(fs))
            for word in token.split():
                width, height = font.getsize(word)
                left, right, top, bottom = add_word(width, height, left, right, top, bottom, ls, ws)
        return right+3+max(parindent, 10), bottom

    def text_block_preferred_width(self, tb, debug=False):
        return self.text_block_size(tb, sys.maxsize, debug=debug)[0]

    def preferred_width(self, debug=False):
        return ceil(max([self.text_block_preferred_width(i, debug=debug) for i in self.text_blocks]))

    def height(self, width):
        return sum([self.text_block_size(i, width)[1] for i in self.text_blocks])


class Row(object):

    def __init__(self, conv, row, css, colpad):
        self.cells = []
        self.colpad = colpad
        cells = row.findAll(re.compile('td|th', re.IGNORECASE))
        self.targets = []
        for cell in cells:
            ccss = conv.tag_css(cell, css)[0]
            self.cells.append(Cell(conv, cell, ccss))
        for a in row.findAll(id=True) + row.findAll(name=True):
            name = a['name'] if a.has_attr('name') else a['id'] if a.has_attr('id') else None
            if name is not None:
                self.targets.append(name.replace('#', ''))

    def number_of_cells(self):
        '''Number of cells in this row. Respects colspan'''
        ans = 0
        for cell in self.cells:
            ans += cell.colspan
        return ans

    def height(self, widths):
        i, heights = 0, []
        for cell in self.cells:
            width = sum(widths[i:i+cell.colspan])
            heights.append(cell.height(width))
            i += cell.colspan
        if not heights:
            return 0
        return max(heights)

    def cell_from_index(self, col):
        i = -1
        cell = None
        for cell in self.cells:
            for k in range(0, cell.colspan):
                if i == col:
                    break
                i += 1
            if i == col:
                break
        return cell

    def minimum_width(self, col):
        cell = self.cell_from_index(col)
        if not cell:
            return 0
        return cell.minimum_width()

    def preferred_width(self, col):
        cell = self.cell_from_index(col)
        if not cell:
            return 0
        return 0 if cell.colspan > 1 else cell.preferred_width()

    def width_percent(self, col):
        cell = self.cell_from_index(col)
        if not cell:
            return -1
        return -1 if cell.colspan > 1 else cell.pwidth

    def cell_iterator(self):
        for c in self.cells:
            yield c


class Table(object):

    def __init__(self, conv, table, css, rowpad=10, colpad=10):
        self.rows = []
        self.conv = conv
        self.rowpad = rowpad
        self.colpad = colpad
        rows = table.findAll('tr')
        conv.in_table = True
        for row in rows:
            rcss = conv.tag_css(row, css)[0]
            self.rows.append(Row(conv, row, rcss, colpad))
        conv.in_table = False

    def number_of_columns(self):
        max = 0
        for row in self.rows:
            max = row.number_of_cells() if row.number_of_cells() > max else max
        return max

    def number_or_rows(self):
        return len(self.rows)

    def height(self, maxwidth):
        ''' Return row heights + self.rowpad'''
        widths = self.get_widths(maxwidth)
        return sum([row.height(widths) + self.rowpad for row in self.rows]) - self.rowpad

    def minimum_width(self, col):
        return max([row.minimum_width(col) for row in self.rows])

    def width_percent(self, col):
        return max([row.width_percent(col) for row in self.rows])

    def get_widths(self, maxwidth):
        '''
        Return widths of columns + self.colpad
        '''
        rows, cols = self.number_or_rows(), self.number_of_columns()
        widths = list(range(cols))
        for c in range(cols):
            cellwidths = [0 for i in range(rows)]
            for r in range(rows):
                try:
                    cellwidths[r] = self.rows[r].preferred_width(c)
                except IndexError:
                    continue
            widths[c] = max(cellwidths)

        min_widths = [self.minimum_width(i)+10 for i in range(cols)]
        for i in range(len(widths)):
            wp = self.width_percent(i)
            if wp >= 0:
                widths[i] = max(min_widths[i], ceil((wp/100) * (maxwidth - (cols-1)*self.colpad)))

        itercount = 0

        while sum(widths) > maxwidth-((len(widths)-1)*self.colpad) and itercount < 100:
            for i in range(cols):
                widths[i] = ceil((95/100)*widths[i]) if \
                    ceil((95/100)*widths[i]) >= min_widths[i] else widths[i]
            itercount += 1

        return [i+self.colpad for i in widths]

    def blocks(self, maxwidth, maxheight):
        rows, cols = self.number_or_rows(), self.number_of_columns()
        cellmatrix = [[None for c in range(cols)] for r in range(rows)]
        rowpos = [0 for i in range(rows)]
        for r in range(rows):
            nc = self.rows[r].cell_iterator()
            try:
                while True:
                    cell = next(nc)
                    cellmatrix[r][rowpos[r]] = cell
                    rowpos[r] += cell.colspan
                    for k in range(1, cell.rowspan):
                        try:
                            rowpos[r+k] += 1
                        except IndexError:
                            break
            except StopIteration:  # No more cells in this row
                continue

        widths = self.get_widths(maxwidth)
        heights = [row.height(widths) for row in self.rows]

        xpos = [sum(widths[:i]) for i in range(cols)]
        delta = maxwidth - sum(widths)
        if delta < 0:
            delta = 0
        for r in range(len(cellmatrix)):
            yield None, 0, heights[r], 0, self.rows[r].targets
            for c in range(len(cellmatrix[r])):
                cell = cellmatrix[r][c]
                if not cell:
                    continue
                width = sum(widths[c:c+cell.colspan])-self.colpad*cell.colspan
                sypos = 0
                for tb in cell.text_blocks:
                    tb.blockStyle = self.conv.book.create_block_style(
                                    blockwidth=width,
                                    blockheight=cell.text_block_size(tb, width)[1],
                                    blockrule='horz-fixed')

                    yield tb, xpos[c], sypos, delta, None
                    sypos += tb.blockStyle.attrs['blockheight']
