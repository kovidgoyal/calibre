#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml.html.builder import TABLE, TR, TD

from calibre.ebooks.docx.block_styles import inherit, read_shd as rs, read_border, binary_property, border_props, ParagraphStyle, border_to_css
from calibre.ebooks.docx.char_styles import RunStyle
from polyglot.builtins import filter, iteritems, itervalues, range, unicode_type

# Read from XML {{{
read_shd = rs
edges = ('left', 'top', 'right', 'bottom')


def _read_width(elem, get):
    ans = inherit
    try:
        w = int(get(elem, 'w:w'))
    except (TypeError, ValueError):
        w = 0
    typ = get(elem, 'w:type', 'auto')
    if typ == 'nil':
        ans = '0'
    elif typ == 'auto':
        ans = 'auto'
    elif typ == 'dxa':
        ans = '%.3gpt' % (w/20)
    elif typ == 'pct':
        ans = '%.3g%%' % (w/50)
    return ans


def read_width(parent, dest, XPath, get):
    ans = inherit
    for tblW in XPath('./w:tblW')(parent):
        ans = _read_width(tblW, get)
    setattr(dest, 'width', ans)


def read_cell_width(parent, dest, XPath, get):
    ans = inherit
    for tblW in XPath('./w:tcW')(parent):
        ans = _read_width(tblW, get)
    setattr(dest, 'width', ans)


def read_padding(parent, dest, XPath, get):
    name = 'tblCellMar' if parent.tag.endswith('}tblPr') else 'tcMar'
    ans = {x:inherit for x in edges}
    for mar in XPath('./w:%s' % name)(parent):
        for x in edges:
            for edge in XPath('./w:%s' % x)(mar):
                ans[x] = _read_width(edge, get)
    for x in edges:
        setattr(dest, 'cell_padding_%s' % x, ans[x])


def read_justification(parent, dest, XPath, get):
    left = right = inherit
    for jc in XPath('./w:jc[@w:val]')(parent):
        val = get(jc, 'w:val')
        if not val:
            continue
        if val == 'left':
            right = 'auto'
        elif val == 'right':
            left = 'auto'
        elif val == 'center':
            left = right = 'auto'
    setattr(dest, 'margin_left', left)
    setattr(dest, 'margin_right', right)


def read_spacing(parent, dest, XPath, get):
    ans = inherit
    for cs in XPath('./w:tblCellSpacing')(parent):
        ans = _read_width(cs, get)
    setattr(dest, 'spacing', ans)


def read_float(parent, dest, XPath, get):
    ans = inherit
    for x in XPath('./w:tblpPr')(parent):
        ans = {k.rpartition('}')[-1]: v for k, v in iteritems(x.attrib)}
    setattr(dest, 'float', ans)


def read_indent(parent, dest, XPath, get):
    ans = inherit
    for cs in XPath('./w:tblInd')(parent):
        ans = _read_width(cs, get)
    setattr(dest, 'indent', ans)


border_edges = ('left', 'top', 'right', 'bottom', 'insideH', 'insideV')


def read_borders(parent, dest, XPath, get):
    name = 'tblBorders' if parent.tag.endswith('}tblPr') else 'tcBorders'
    read_border(parent, dest, XPath, get, border_edges, name)


def read_height(parent, dest, XPath, get):
    ans = inherit
    for rh in XPath('./w:trHeight')(parent):
        rule = get(rh, 'w:hRule', 'auto')
        if rule in {'auto', 'atLeast', 'exact'}:
            val = get(rh, 'w:val')
            ans = (rule, val)
    setattr(dest, 'height', ans)


def read_vertical_align(parent, dest, XPath, get):
    ans = inherit
    for va in XPath('./w:vAlign')(parent):
        val = get(va, 'w:val')
        ans = {'center': 'middle', 'top': 'top', 'bottom': 'bottom'}.get(val, 'middle')
    setattr(dest, 'vertical_align', ans)


def read_col_span(parent, dest, XPath, get):
    ans = inherit
    for gs in XPath('./w:gridSpan')(parent):
        try:
            ans = int(get(gs, 'w:val'))
        except (TypeError, ValueError):
            continue
    setattr(dest, 'col_span', ans)


def read_merge(parent, dest, XPath, get):
    for x in ('hMerge', 'vMerge'):
        ans = inherit
        for m in XPath('./w:%s' % x)(parent):
            ans = get(m, 'w:val', 'continue')
        setattr(dest, x, ans)


def read_band_size(parent, dest, XPath, get):
    for x in ('Col', 'Row'):
        ans = 1
        for y in XPath('./w:tblStyle%sBandSize' % x)(parent):
            try:
                ans = int(get(y, 'w:val'))
            except (TypeError, ValueError):
                continue
        setattr(dest, '%s_band_size' % x.lower(), ans)


def read_look(parent, dest, XPath, get):
    ans = 0
    for x in XPath('./w:tblLook')(parent):
        try:
            ans = int(get(x, 'w:val'), 16)
        except (ValueError, TypeError):
            continue
    setattr(dest, 'look', ans)

# }}}


def clone(style):
    if style is None:
        return None
    try:
        ans = type(style)(style.namespace)
    except TypeError:
        return None
    ans.update(style)
    return ans


class Style(object):

    is_bidi = False

    def update(self, other):
        for prop in self.all_properties:
            nval = getattr(other, prop)
            if nval is not inherit:
                setattr(self, prop, nval)

    def apply_bidi(self):
        self.is_bidi = True

    def convert_spacing(self):
        ans = {}
        if self.spacing is not inherit:
            if self.spacing in {'auto', '0'}:
                ans['border-collapse'] = 'collapse'
            else:
                ans['border-collapse'] = 'separate'
                ans['border-spacing'] = self.spacing
        return ans

    def convert_border(self):
        c = {}
        for x in edges:
            border_to_css(x, self, c)
            val = getattr(self, 'padding_%s' % x)
            if val is not inherit:
                c['padding-%s' % x] = '%.3gpt' % val
        if self.is_bidi:
            for a in ('padding-%s', 'border-%s-style', 'border-%s-color', 'border-%s-width'):
                l, r = c.get(a % 'left'), c.get(a % 'right')
                if l is not None:
                    c[a % 'right'] = l
                if r is not None:
                    c[a % 'left'] = r
        return c


class RowStyle(Style):

    all_properties = ('height', 'cantSplit', 'hidden', 'spacing',)

    def __init__(self, namespace, trPr=None):
        self.namespace = namespace
        if trPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for p in ('hidden', 'cantSplit'):
                setattr(self, p, binary_property(trPr, p, namespace.XPath, namespace.get))
            for p in ('spacing', 'height'):
                f = globals()['read_%s' % p]
                f(trPr, self, namespace.XPath, namespace.get)
        self._css = None

    @property
    def css(self):
        if self._css is None:
            c = self._css = {}
            if self.hidden is True:
                c['display'] = 'none'
            if self.cantSplit is True:
                c['page-break-inside'] = 'avoid'
            if self.height is not inherit:
                rule, val = self.height
                if rule != 'auto':
                    try:
                        c['min-height' if rule == 'atLeast' else 'height'] = '%.3gpt' % (int(val)/20)
                    except (ValueError, TypeError):
                        pass
            c.update(self.convert_spacing())
        return self._css


class CellStyle(Style):

    all_properties = ('background_color', 'cell_padding_left', 'cell_padding_right', 'cell_padding_top',
        'cell_padding_bottom', 'width', 'vertical_align', 'col_span', 'vMerge', 'hMerge', 'row_span',
    ) + tuple(k % edge for edge in border_edges for k in border_props)

    def __init__(self, namespace, tcPr=None):
        self.namespace = namespace
        if tcPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for x in ('borders', 'shd', 'padding', 'cell_width', 'vertical_align', 'col_span', 'merge'):
                f = globals()['read_%s' % x]
                f(tcPr, self, namespace.XPath, namespace.get)
            self.row_span = inherit
        self._css = None

    @property
    def css(self):
        if self._css is None:
            self._css = c = {}
            if self.background_color is not inherit:
                c['background-color'] = self.background_color
            if self.width not in (inherit, 'auto'):
                c['width'] = self.width
            c['vertical-align'] = 'top' if self.vertical_align is inherit else self.vertical_align
            for x in edges:
                val = getattr(self, 'cell_padding_%s' % x)
                if val not in (inherit, 'auto'):
                    c['padding-%s' % x] =  val
                elif val is inherit and x in {'left', 'right'}:
                    c['padding-%s' % x] = '%.3gpt' % (115/20)
            # In Word, tables are apparently rendered with some default top and
            # bottom padding irrespective of the cellMargin values. Simulate
            # that here.
            for x in ('top', 'bottom'):
                if c.get('padding-%s' % x, '0pt') == '0pt':
                    c['padding-%s' % x] = '0.5ex'
            c.update(self.convert_border())

        return self._css


class TableStyle(Style):

    all_properties = (
        'width', 'float', 'cell_padding_left', 'cell_padding_right', 'cell_padding_top',
        'cell_padding_bottom', 'margin_left', 'margin_right', 'background_color',
        'spacing', 'indent', 'overrides', 'col_band_size', 'row_band_size', 'look', 'bidi',
    ) + tuple(k % edge for edge in border_edges for k in border_props)

    def __init__(self, namespace, tblPr=None):
        self.namespace = namespace
        if tblPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            self.overrides = inherit
            self.bidi = binary_property(tblPr, 'bidiVisual', namespace.XPath, namespace.get)
            for x in ('width', 'float', 'padding', 'shd', 'justification', 'spacing', 'indent', 'borders', 'band_size', 'look'):
                f = globals()['read_%s' % x]
                f(tblPr, self, self.namespace.XPath, self.namespace.get)
            parent = tblPr.getparent()
            if self.namespace.is_tag(parent, 'w:style'):
                self.overrides = {}
                for tblStylePr in self.namespace.XPath('./w:tblStylePr[@w:type]')(parent):
                    otype = self.namespace.get(tblStylePr, 'w:type')
                    orides = self.overrides[otype] = {}
                    for tblPr in self.namespace.XPath('./w:tblPr')(tblStylePr):
                        orides['table'] = TableStyle(self.namespace, tblPr)
                    for trPr in self.namespace.XPath('./w:trPr')(tblStylePr):
                        orides['row'] = RowStyle(self.namespace, trPr)
                    for tcPr in self.namespace.XPath('./w:tcPr')(tblStylePr):
                        orides['cell'] = CellStyle(self.namespace, tcPr)
                    for pPr in self.namespace.XPath('./w:pPr')(tblStylePr):
                        orides['para'] = ParagraphStyle(self.namespace, pPr)
                    for rPr in self.namespace.XPath('./w:rPr')(tblStylePr):
                        orides['run'] = RunStyle(self.namespace, rPr)
        self._css = None

    def resolve_based_on(self, parent):
        for p in self.all_properties:
            val = getattr(self, p)
            if val is inherit:
                setattr(self, p, getattr(parent, p))

    @property
    def css(self):
        if self._css is None:
            c = self._css = {}
            if self.width not in (inherit, 'auto'):
                c['width'] = self.width
            for x in ('background_color', 'margin_left', 'margin_right'):
                val = getattr(self, x)
                if val is not inherit:
                    c[x.replace('_', '-')] = val
            if self.indent not in (inherit, 'auto') and self.margin_left != 'auto':
                c['margin-left'] = self.indent
            if self.float is not inherit:
                for x in ('left', 'top', 'right', 'bottom'):
                    val = self.float.get('%sFromText' % x, 0)
                    try:
                        val = '%.3gpt' % (int(val) / 20)
                    except (ValueError, TypeError):
                        val = '0'
                    c['margin-%s' % x] = val
                if 'tblpXSpec' in self.float:
                    c['float'] = 'right' if self.float['tblpXSpec'] in {'right', 'outside'} else 'left'
                else:
                    page = self.page
                    page_width = page.width - page.margin_left - page.margin_right
                    try:
                        x = int(self.float['tblpX']) / 20
                    except (KeyError, ValueError, TypeError):
                        x = 0
                    c['float'] = 'left' if (x/page_width) < 0.65 else 'right'
            c.update(self.convert_spacing())
            if 'border-collapse' not in c:
                c['border-collapse'] = 'collapse'
            c.update(self.convert_border())

        return self._css


class Table(object):

    def __init__(self, namespace, tbl, styles, para_map, is_sub_table=False):
        self.namespace = namespace
        self.tbl = tbl
        self.styles = styles
        self.is_sub_table = is_sub_table

        # Read Table Style
        style = {'table':TableStyle(self.namespace)}
        for tblPr in self.namespace.XPath('./w:tblPr')(tbl):
            for ts in self.namespace.XPath('./w:tblStyle[@w:val]')(tblPr):
                style_id = self.namespace.get(ts, 'w:val')
                s = styles.get(style_id)
                if s is not None:
                    if s.table_style is not None:
                        style['table'].update(s.table_style)
                    if s.paragraph_style is not None:
                        if 'paragraph' in style:
                            style['paragraph'].update(s.paragraph_style)
                        else:
                            style['paragraph'] = s.paragraph_style
                    if s.character_style is not None:
                        if 'run' in style:
                            style['run'].update(s.character_style)
                        else:
                            style['run'] = s.character_style
            style['table'].update(TableStyle(self.namespace, tblPr))
        self.table_style, self.paragraph_style = style['table'], style.get('paragraph', None)
        self.run_style = style.get('run', None)
        self.overrides = self.table_style.overrides
        if self.overrides is inherit:
            self.overrides = {}
        if 'wholeTable' in self.overrides and 'table' in self.overrides['wholeTable']:
            self.table_style.update(self.overrides['wholeTable']['table'])

        self.style_map = {}
        self.paragraphs = []
        self.cell_map = []

        rows = self.namespace.XPath('./w:tr')(tbl)
        for r, tr in enumerate(rows):
            overrides = self.get_overrides(r, None, len(rows), None)
            self.resolve_row_style(tr, overrides)
            cells = self.namespace.XPath('./w:tc')(tr)
            self.cell_map.append([])
            for c, tc in enumerate(cells):
                overrides = self.get_overrides(r, c, len(rows), len(cells))
                self.resolve_cell_style(tc, overrides, r, c, len(rows), len(cells))
                self.cell_map[-1].append(tc)
                for p in self.namespace.XPath('./w:p')(tc):
                    para_map[p] = self
                    self.paragraphs.append(p)
                    self.resolve_para_style(p, overrides)

        self.handle_merged_cells()
        self.sub_tables = {x:Table(namespace, x, styles, para_map, is_sub_table=True) for x in self.namespace.XPath('./w:tr/w:tc/w:tbl')(tbl)}

    @property
    def bidi(self):
        return self.table_style.bidi is True

    def override_allowed(self, name):
        'Check if the named override is allowed by the tblLook element'
        if name.endswith('Cell') or name == 'wholeTable':
            return True
        look = self.table_style.look
        if (look & 0x0020 and name == 'firstRow') or (look & 0x0040 and name == 'lastRow') or \
           (look & 0x0080 and name == 'firstCol') or (look & 0x0100 and name == 'lastCol'):
            return True
        if name.startswith('band'):
            if name.endswith('Horz'):
                return not bool(look & 0x0200)
            if name.endswith('Vert'):
                return not bool(look & 0x0400)
        return False

    def get_overrides(self, r, c, num_of_rows, num_of_cols_in_row):
        'List of possible overrides for the given para'
        overrides = ['wholeTable']

        def divisor(m, n):
            return (m - (m % n)) // n
        if c is not None:
            odd_column_band = (divisor(c, self.table_style.col_band_size) % 2) == 1
            overrides.append('band%dVert' % (1 if odd_column_band else 2))
        odd_row_band = (divisor(r, self.table_style.row_band_size) % 2) == 1
        overrides.append('band%dHorz' % (1 if odd_row_band else 2))

        # According to the OOXML spec columns should have higher override
        # priority than rows, but Word seems to do it the other way around.
        if c is not None:
            if c == 0:
                overrides.append('firstCol')
            if c >= num_of_cols_in_row - 1:
                overrides.append('lastCol')
        if r == 0:
            overrides.append('firstRow')
        if r >= num_of_rows - 1:
            overrides.append('lastRow')
        if c is not None:
            if r == 0:
                if c == 0:
                    overrides.append('nwCell')
                if c == num_of_cols_in_row - 1:
                    overrides.append('neCell')
            if r == num_of_rows - 1:
                if c == 0:
                    overrides.append('swCell')
                if c == num_of_cols_in_row - 1:
                    overrides.append('seCell')
        return tuple(filter(self.override_allowed, overrides))

    def resolve_row_style(self, tr, overrides):
        rs = RowStyle(self.namespace)
        for o in overrides:
            if o in self.overrides:
                ovr = self.overrides[o]
                ors = ovr.get('row', None)
                if ors is not None:
                    rs.update(ors)

        for trPr in self.namespace.XPath('./w:trPr')(tr):
            rs.update(RowStyle(self.namespace, trPr))
        if self.bidi:
            rs.apply_bidi()
        self.style_map[tr] = rs

    def resolve_cell_style(self, tc, overrides, row, col, rows, cols_in_row):
        cs = CellStyle(self.namespace)
        for o in overrides:
            if o in self.overrides:
                ovr = self.overrides[o]
                ors = ovr.get('cell', None)
                if ors is not None:
                    cs.update(ors)

        for tcPr in self.namespace.XPath('./w:tcPr')(tc):
            cs.update(CellStyle(self.namespace, tcPr))

        for x in edges:
            p = 'cell_padding_%s' % x
            val = getattr(cs, p)
            if val is inherit:
                setattr(cs, p, getattr(self.table_style, p))

            is_inside_edge = (
                (x == 'left' and col > 0) or
                (x == 'top' and row > 0) or
                (x == 'right' and col < cols_in_row - 1) or
                (x == 'bottom' and row < rows -1)
            )
            inside_edge = ('insideH' if x in {'top', 'bottom'} else 'insideV') if is_inside_edge else None
            for prop in border_props:
                if not prop.startswith('border'):
                    continue
                eprop = prop % x
                iprop = (prop % inside_edge) if inside_edge else None
                val = getattr(cs, eprop)
                if val is inherit and iprop is not None:
                    # Use the insideX borders if the main cell borders are not
                    # specified
                    val = getattr(cs, iprop)
                    if val is inherit:
                        val = getattr(self.table_style, iprop)
                if not is_inside_edge and val == 'none':
                    # Cell borders must override table borders even when the
                    # table border is not null and the cell border is null.
                    val = 'hidden'
                setattr(cs, eprop, val)

        if self.bidi:
            cs.apply_bidi()
        self.style_map[tc] = cs

    def resolve_para_style(self, p, overrides):
        text_styles = [clone(self.paragraph_style), clone(self.run_style)]

        for o in overrides:
            if o in self.overrides:
                ovr = self.overrides[o]
                for i, name in enumerate(('para', 'run')):
                    ops = ovr.get(name, None)
                    if ops is not None:
                        if text_styles[i] is None:
                            text_styles[i] = ops
                        else:
                            text_styles[i].update(ops)
        self.style_map[p] = text_styles

    def handle_merged_cells(self):
        if not self.cell_map:
            return
        # Handle vMerge
        max_col_num = max(len(r) for r in self.cell_map)
        for c in range(max_col_num):
            cells = [row[c] if c < len(row) else None for row in self.cell_map]
            runs = [[]]
            for cell in cells:
                try:
                    s = self.style_map[cell]
                except KeyError:  # cell is None
                    s = CellStyle(self.namespace)
                if s.vMerge == 'restart':
                    runs.append([cell])
                elif s.vMerge == 'continue':
                    runs[-1].append(cell)
                else:
                    runs.append([])
            for run in runs:
                if len(run) > 1:
                    self.style_map[run[0]].row_span = len(run)
                    for tc in run[1:]:
                        tc.getparent().remove(tc)

        # Handle hMerge
        for cells in self.cell_map:
            runs = [[]]
            for cell in cells:
                try:
                    s = self.style_map[cell]
                except KeyError:  # cell is None
                    s = CellStyle(self.namespace)
                if s.col_span is not inherit:
                    runs.append([])
                    continue
                if s.hMerge == 'restart':
                    runs.append([cell])
                elif s.hMerge == 'continue':
                    runs[-1].append(cell)
                else:
                    runs.append([])

            for run in runs:
                if len(run) > 1:
                    self.style_map[run[0]].col_span = len(run)
                    for tc in run[1:]:
                        tc.getparent().remove(tc)

    def __iter__(self):
        for p in self.paragraphs:
            yield p
        for t in itervalues(self.sub_tables):
            for p in t:
                yield p

    def apply_markup(self, rmap, page, parent=None):
        table = TABLE('\n\t\t')
        if self.bidi:
            table.set('dir', 'rtl')
        self.table_style.page = page
        style_map = {}
        if parent is None:
            try:
                first_para = rmap[next(iter(self))]
            except StopIteration:
                return
            parent = first_para.getparent()
            idx = parent.index(first_para)
            parent.insert(idx, table)
        else:
            parent.append(table)
        for row in self.namespace.XPath('./w:tr')(self.tbl):
            tr = TR('\n\t\t\t')
            style_map[tr] = self.style_map[row]
            tr.tail = '\n\t\t'
            table.append(tr)
            for tc in self.namespace.XPath('./w:tc')(row):
                td = TD()
                style_map[td] = s = self.style_map[tc]
                if s.col_span is not inherit:
                    td.set('colspan', unicode_type(s.col_span))
                if s.row_span is not inherit:
                    td.set('rowspan', unicode_type(s.row_span))
                td.tail = '\n\t\t\t'
                tr.append(td)
                for x in self.namespace.XPath('./w:p|./w:tbl')(tc):
                    if x.tag.endswith('}p'):
                        td.append(rmap[x])
                    else:
                        self.sub_tables[x].apply_markup(rmap, page, parent=td)
            if len(tr):
                tr[-1].tail = '\n\t\t'
        if len(table):
            table[-1].tail = '\n\t'

        table_style = self.table_style.css
        if table_style:
            table.set('class', self.styles.register(table_style, 'table'))
        for elem, style in iteritems(style_map):
            css = style.css
            if css:
                elem.set('class', self.styles.register(css, elem.tag))


class Tables(object):

    def __init__(self, namespace):
        self.tables = []
        self.para_map = {}
        self.sub_tables = set()
        self.namespace = namespace

    def register(self, tbl, styles):
        if tbl in self.sub_tables:
            return
        self.tables.append(Table(self.namespace, tbl, styles, self.para_map))
        self.sub_tables |= set(self.tables[-1].sub_tables)

    def apply_markup(self, object_map, page_map):
        rmap = {v:k for k, v in iteritems(object_map)}
        for table in self.tables:
            table.apply_markup(rmap, page_map[table.tbl])

    def para_style(self, p):
        table = self.para_map.get(p, None)
        if table is not None:
            return table.style_map.get(p, (None, None))[0]

    def run_style(self, p):
        table = self.para_map.get(p, None)
        if table is not None:
            return table.style_map.get(p, (None, None))[1]
