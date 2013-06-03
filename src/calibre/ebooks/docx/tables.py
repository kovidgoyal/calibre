#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml.html.builder import TABLE, TR, TD

from calibre.ebooks.docx.block_styles import inherit, read_shd as rs, read_border, binary_property, border_props, ParagraphStyle
from calibre.ebooks.docx.char_styles import RunStyle
from calibre.ebooks.docx.names import XPath, get, is_tag

# Read from XML {{{
read_shd = rs
edges = ('left', 'top', 'right', 'bottom')

def _read_width(elem):
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

def read_width(parent, dest):
    ans = inherit
    for tblW in XPath('./w:tblW')(parent):
        ans = _read_width(tblW)
    setattr(dest, 'width', ans)

def read_cell_width(parent, dest):
    ans = inherit
    for tblW in XPath('./w:tcW')(parent):
        ans = _read_width(tblW)
    setattr(dest, 'width', ans)

def read_padding(parent, dest):
    name = 'tblCellMar' if parent.tag.endswith('}tblPr') else 'tcMar'
    ans = {x:inherit for x in edges}
    for mar in XPath('./w:%s' % name)(parent):
        for x in edges:
            for edge in XPath('./w:%s' % x)(mar):
                ans[x] = _read_width(edge)
    for x in edges:
        setattr(dest, 'cell_padding_%s' % x, ans[x])

def read_justification(parent, dest):
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

def read_spacing(parent, dest):
    ans = inherit
    for cs in XPath('./w:tblCellSpacing')(parent):
        ans = _read_width(cs)
    setattr(dest, 'spacing', ans)

def read_float(parent, dest):
    ans = inherit
    for x in XPath('./w:tblpPr')(parent):
        ans = x.attrib
    setattr(dest, 'float', ans)

def read_indent(parent, dest):
    ans = inherit
    for cs in XPath('./w:tblInd')(parent):
        ans = _read_width(cs)
    setattr(dest, 'indent', ans)

border_edges = ('left', 'top', 'right', 'bottom', 'insideH', 'insideV')

def read_borders(parent, dest):
    name = 'tblBorders' if parent.tag.endswith('}tblPr') else 'tcBorders'
    read_border(parent, dest, border_edges, name)

def read_height(parent, dest):
    ans = inherit
    for rh in XPath('./w:trHeight')(parent):
        rule = get(rh, 'w:hRule', 'auto')
        if rule in {'auto', 'atLeast', 'exact'}:
            val = get(rh, 'w:val')
            ans = (rule, val)
    setattr(dest, 'height', ans)

def read_vertical_align(parent, dest):
    ans = inherit
    for va in XPath('./w:vAlign')(parent):
        val = get(va, 'w:val')
        ans = {'center': 'middle', 'top': 'top', 'bottom': 'bottom'}.get(val, 'middle')
    setattr(dest, 'vertical_align', ans)

def read_col_span(parent, dest):
    ans = inherit
    for gs in XPath('./w:gridSpan')(parent):
        try:
            ans = int(get(gs, 'w:val'))
        except (TypeError, ValueError):
            continue
    setattr(dest, 'col_span', ans)

def read_merge(parent, dest):
    for x in ('hMerge', 'vMerge'):
        ans = inherit
        for m in XPath('./w:%s' % x)(parent):
            ans = get(m, 'w:val', 'continue')
        setattr(dest, x, ans)

def read_band_size(parent, dest):
    for x in ('Col', 'Row'):
        ans = 1
        for y in XPath('./w:tblStyle%sBandSize' % x)(parent):
            try:
                ans = int(get(y, 'w:val'))
            except (TypeError, ValueError):
                continue
        setattr(dest, '%s_band_size' % x.lower(), ans)

def read_look(parent, dest):
    ans = 0
    for x in XPath('./w:tblLook')(parent):
        try:
            ans = int(get(x, 'w:val'), 16)
        except (ValueError, TypeError):
            continue
    setattr(dest, 'look', ans)

# }}}

def clone(style):
    try:
        ans = type(style)()
    except TypeError:
        return None
    ans.update(style)
    return ans

class Style(object):

    def update(self, other):
        for prop in self.all_properties:
            nval = getattr(other, prop)
            if nval is not inherit:
                setattr(self, prop, nval)

    def convert_spacing(self):
        ans = {}
        if self.spacing is not inherit:
            if self.spacing in {'auto', '0'}:
                ans['border-collapse'] = 'collapse'
            else:
                ans['border-collapse'] = 'separate'
                ans['border-spacing'] = self.spacing
        return ans

class RowStyle(Style):

    all_properties = ('height', 'cantSplit', 'hidden', 'spacing',)

    def __init__(self, trPr=None):
        if trPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for p in ('hidden', 'cantSplit'):
                setattr(self, p, binary_property(trPr, p))
            for p in ('spacing', 'height'):
                f = globals()['read_%s' % p]
                f(trPr, self)
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
        'cell_padding_bottom', 'width', 'vertical_align', 'col_span', 'vMerge', 'hMerge',
    ) + tuple(k % edge for edge in border_edges for k in border_props)

    def __init__(self, tcPr=None):
        if tcPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for x in ('borders', 'shd', 'padding', 'cell_width', 'vertical_align', 'col_span', 'merge'):
                f = globals()['read_%s' % x]
                f(tcPr, self)
        self._css = None

    @property
    def css(self):
        if self._css is None:
            self._css = c = {}
            if self.background_color is not inherit:
                c['background-color'] = self.background_color
            if self.width not in (inherit, 'auto'):
                c['width'] = self.width
            if self.vertical_align is not inherit:
                c['vertical-align'] = self.vertical_align
            for x in edges:
                val = getattr(self, 'cell_padding_%s' % x)
                if val not in (inherit, 'auto'):
                    c['padding-%s' % x] =  val
                elif val is inherit and x in {'left', 'right'}:
                    c['padding-%s' % x] = '%.3gpt' % (115/20)

        return self._css

class TableStyle(Style):

    all_properties = (
        'width', 'float', 'cell_padding_left', 'cell_padding_right', 'cell_padding_top',
        'cell_padding_bottom', 'margin_left', 'margin_right', 'background_color',
        'spacing', 'indent', 'overrides', 'col_band_size', 'row_band_size', 'look',
    ) + tuple(k % edge for edge in border_edges for k in border_props)

    def __init__(self, tblPr=None):
        if tblPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            self.overrides = inherit
            for x in ('width', 'float', 'padding', 'shd', 'justification', 'spacing', 'indent', 'borders', 'band_size', 'look'):
                f = globals()['read_%s' % x]
                f(tblPr, self)
            parent = tblPr.getparent()
            if is_tag(parent, 'w:style'):
                self.overrides = {}
                for tblStylePr in XPath('./w:tblStylePr[@w:type]')(parent):
                    otype = get(tblStylePr, 'w:type')
                    orides = self.overrides[otype] = {}
                    for tblPr in XPath('./w:tblPr')(tblStylePr):
                        orides['table'] = TableStyle(tblPr)
                    for trPr in XPath('./w:trPr')(tblStylePr):
                        orides['row'] = RowStyle(trPr)
                    for tcPr in XPath('./w:tcPr')(tblStylePr):
                        orides['cell'] = CellStyle(tcPr)
                    for pPr in XPath('./w:pPr')(tblStylePr):
                        orides['para'] = ParagraphStyle(pPr)
                    for rPr in XPath('./w:rPr')(tblStylePr):
                        orides['run'] = RunStyle(rPr)
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
        return self._css


class Table(object):

    def __init__(self, tbl, styles, para_map):
        self.tbl = tbl
        self.styles = styles

        # Read Table Style
        style = {'table':TableStyle()}
        for tblPr in XPath('./w:tblPr')(tbl):
            for ts in XPath('./w:tblStyle[@w:val]')(tblPr):
                style_id = get(ts, 'w:val')
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
            style['table'].update(TableStyle(tblPr))
        self.table_style, self.paragraph_style = style['table'], style.get('paragraph', None)
        self.run_style = style.get('run', None)
        self.overrides = self.table_style.overrides
        if 'wholeTable' in self.overrides and 'table' in self.overrides['wholeTable']:
            self.table_style.update(self.overrides['wholeTable']['table'])

        self.style_map = {}
        self.paragraphs = []

        rows = XPath('./w:tr')(tbl)
        for r, tr in enumerate(rows):
            overrides = self.get_overrides(r, None, len(rows), None)
            self.resolve_row_style(tr, overrides)
            cells = XPath('./w:tc')(tr)
            for c, tc in enumerate(cells):
                overrides = self.get_overrides(r, c, len(rows), len(cells))
                self.resolve_cell_style(tc, overrides)
                for p in XPath('./w:p')(tc):
                    para_map[p] = self
                    self.paragraphs.append(p)
                    self.resolve_para_style(p, overrides)

        self.sub_tables = {x:Table(x, styles, para_map) for x in XPath('./w:tr/w:tc/w:tbl')(tbl)}

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
        if r == 0:
            overrides.append('firstRow')
        if r >= num_of_rows - 1:
            overrides.append('lastRow')
        if c is not None:
            if c == 0:
                overrides.append('firstCol')
            if c >= num_of_cols_in_row - 1:
                overrides.append('lastCol')
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
        rs = RowStyle()
        for o in overrides:
            if o in self.overrides:
                ovr = self.overrides[o]
                ors = ovr.get('row', None)
                if ors is not None:
                    rs.update(ors)

        for trPr in XPath('./w:trPr')(tr):
            rs.update(RowStyle(trPr))
        self.style_map[tr] = rs

    def resolve_cell_style(self, tc, overrides):
        cs = CellStyle()
        for o in overrides:
            if o in self.overrides:
                ovr = self.overrides[o]
                ors = ovr.get('cell', None)
                if ors is not None:
                    cs.update(ors)

        for tcPr in XPath('./w:tcPr')(tc):
            cs.update(CellStyle(tcPr))

        for x in ('left', 'top', 'right', 'bottom'):
            p = 'cell_padding_%s' % x
            val = getattr(cs, p)
            if val is inherit:
                setattr(cs, p, getattr(self.table_style, p))
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

    def __iter__(self):
        for p in self.paragraphs:
            yield p
        for t in self.sub_tables.itervalues():
            for p in t:
                yield p

    def apply_markup(self, rmap, page, parent=None):
        table = TABLE('\n\t\t')
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
        for row in XPath('./w:tr')(self.tbl):
            tr = TR('\n\t\t\t')
            style_map[tr] = self.style_map[row]
            tr.tail = '\n\t\t'
            table.append(tr)
            for tc in XPath('./w:tc')(row):
                td = TD()
                style_map[td] = s = self.style_map[tc]
                if s.col_span is not inherit:
                    td.set('colspan', type('')(s.col_span))
                td.tail = '\n\t\t\t'
                tr.append(td)
                for x in XPath('./w:p|./w:tbl')(tc):
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
        for elem, style in style_map.iteritems():
            css = style.css
            if css:
                elem.set('class', self.styles.register(css, elem.tag))

class Tables(object):

    def __init__(self):
        self.tables = []
        self.para_map = {}
        self.sub_tables = set()

    def register(self, tbl, styles):
        if tbl in self.sub_tables:
            return
        self.tables.append(Table(tbl, styles, self.para_map))
        self.sub_tables |= set(self.tables[-1].sub_tables)

    def apply_markup(self, object_map, page_map):
        rmap = {v:k for k, v in object_map.iteritems()}
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

