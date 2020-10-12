#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple

from calibre.ebooks.docx.writer.utils import convert_color
from calibre.ebooks.docx.writer.styles import read_css_block_borders as rcbb, border_edges
from polyglot.builtins import iteritems, range, unicode_type


class Dummy(object):
    pass


Border = namedtuple('Border', 'css_style style width color level')
border_style_weight = {
    x:100-i for i, x in enumerate(('double', 'solid', 'dashed', 'dotted', 'ridge', 'outset', 'groove', 'inset'))}


class SpannedCell(object):

    def __init__(self, spanning_cell, horizontal=True):
        self.spanning_cell = spanning_cell
        self.horizontal = horizontal
        self.row_span = self.col_span = 1

    def resolve_borders(self):
        pass

    def serialize(self, tr, makeelement):
        tc = makeelement(tr, 'w:tc')
        tcPr = makeelement(tc, 'w:tcPr')
        makeelement(tcPr, 'w:%sMerge' % ('h' if self.horizontal else 'v'), w_val='continue')
        makeelement(tc, 'w:p')

    def applicable_borders(self, edge):
        return self.spanning_cell.applicable_borders(edge)


def read_css_block_borders(self, css):
    obj = Dummy()
    rcbb(obj, css, store_css_style=True)
    for edge in border_edges:
        setattr(self, 'border_' + edge, Border(
            getattr(obj, 'border_%s_css_style' % edge),
            getattr(obj, 'border_%s_style' % edge),
            getattr(obj, 'border_%s_width' % edge),
            getattr(obj, 'border_%s_color' % edge),
            self.BLEVEL
        ))
        setattr(self, 'padding_' + edge, getattr(obj, 'padding_' + edge))


def as_percent(x):
    if x and x.endswith('%'):
        try:
            return float(x.rstrip('%'))
        except Exception:
            pass


def convert_width(tag_style):
    if tag_style is not None:
        w = tag_style._get('width')
        wp = as_percent(w)
        if w == 'auto':
            return ('auto', 0)
        elif wp is not None:
            return ('pct', int(wp * 50))
        else:
            try:
                return ('dxa', int(float(tag_style['width']) * 20))
            except Exception:
                pass
    return ('auto', 0)


class Cell(object):

    BLEVEL = 2

    def __init__(self, row, html_tag, tag_style=None):
        self.row = row
        self.table = self.row.table
        self.html_tag = html_tag
        try:
            self.row_span = max(0, int(html_tag.get('rowspan', 1)))
        except Exception:
            self.row_span = 1
        try:
            self.col_span = max(0, int(html_tag.get('colspan', 1)))
        except Exception:
            self.col_span = 1
        if tag_style is None:
            self.valign = 'center'
        else:
            self.valign = {'top':'top', 'bottom':'bottom', 'middle':'center'}.get(tag_style._get('vertical-align'))
        self.items = []
        self.width = convert_width(tag_style)
        self.background_color = None if tag_style is None else convert_color(tag_style.backgroundColor)
        read_css_block_borders(self, tag_style)

    def add_block(self, block):
        self.items.append(block)
        block.parent_items = self.items

    def add_table(self, table):
        self.items.append(table)
        return table

    def serialize(self, parent, makeelement):
        tc = makeelement(parent, 'w:tc')
        tcPr = makeelement(tc, 'w:tcPr')
        makeelement(tcPr, 'w:tcW', w_type=self.width[0], w_w=unicode_type(self.width[1]))
        # For some reason, Word 2007 refuses to honor <w:shd> at the table or row
        # level, despite what the specs say, so we inherit and apply at the
        # cell level
        bc = self.background_color or self.row.background_color or self.row.table.background_color
        if bc:
            makeelement(tcPr, 'w:shd', w_val="clear", w_color="auto", w_fill=bc)

        b = makeelement(tcPr, 'w:tcBorders', append=False)
        for edge, border in iteritems(self.borders):
            if border is not None and border.width > 0 and border.style != 'none':
                makeelement(b, 'w:' + edge, w_val=border.style, w_sz=unicode_type(border.width), w_color=border.color)
        if len(b) > 0:
            tcPr.append(b)

        m = makeelement(tcPr, 'w:tcMar', append=False)
        for edge in border_edges:
            padding = getattr(self, 'padding_' + edge)
            if edge in {'top', 'bottom'} or (edge == 'left' and self is self.row.first_cell) or (edge == 'right' and self is self.row.last_cell):
                padding += getattr(self.row, 'padding_' + edge)
            if padding > 0:
                makeelement(m, 'w:' + edge, w_type='dxa', w_w=unicode_type(int(padding * 20)))
        if len(m) > 0:
            tcPr.append(m)

        if self.valign is not None:
            makeelement(tcPr, 'w:vAlign', w_val=self.valign)

        if self.row_span > 1:
            makeelement(tcPr, 'w:vMerge', w_val='restart')
        if self.col_span > 1:
            makeelement(tcPr, 'w:hMerge', w_val='restart')

        item = None
        for item in self.items:
            item.serialize(tc)
        if item is None or isinstance(item, Table):
            # Word 2007 requires the last element in a table cell to be a paragraph
            makeelement(tc, 'w:p')

    def applicable_borders(self, edge):
        if edge == 'left':
            items = {self.table, self.row, self} if self.row.first_cell is self else {self}
        elif edge == 'top':
            items = ({self.table} if self.table.first_row is self.row else set()) | {self, self.row}
        elif edge == 'right':
            items = {self.table, self, self.row} if self.row.last_cell is self else {self}
        elif edge == 'bottom':
            items = ({self.table} if self.table.last_row is self.row else set()) | {self, self.row}
        return {getattr(x, 'border_' + edge) for x in items}

    def resolve_border(self, edge):
        # In Word cell borders override table borders, and Word ignores row
        # borders, so we consolidate all borders as cell borders
        # In HTML the priority is as described here:
        # http://www.w3.org/TR/CSS21/tables.html#border-conflict-resolution
        neighbor = self.neighbor(edge)
        borders = self.applicable_borders(edge)
        if neighbor is not None:
            nedge = {'left':'right', 'top':'bottom', 'right':'left', 'bottom':'top'}[edge]
            borders |= neighbor.applicable_borders(nedge)

        for b in borders:
            if b.css_style == 'hidden':
                return None

        def weight(border):
            return (
                0 if border.css_style == 'none' else 1,
                border.width,
                border_style_weight.get(border.css_style, 0),
                border.level)
        border = sorted(borders, key=weight)[-1]
        return border

    def resolve_borders(self):
        self.borders = {edge:self.resolve_border(edge) for edge in border_edges}

    def neighbor(self, edge):
        idx = self.row.cells.index(self)
        ans = None
        if edge == 'left':
            ans = self.row.cells[idx-1] if idx > 0 else None
        elif edge == 'right':
            ans = self.row.cells[idx+1] if (idx + 1) < len(self.row.cells) else None
        elif edge == 'top':
            ridx = self.table.rows.index(self.row)
            if ridx > 0 and idx < len(self.table.rows[ridx-1].cells):
                ans = self.table.rows[ridx-1].cells[idx]
        elif edge == 'bottom':
            ridx = self.table.rows.index(self.row)
            if ridx + 1 < len(self.table.rows) and idx < len(self.table.rows[ridx+1].cells):
                ans = self.table.rows[ridx+1].cells[idx]
        return getattr(ans, 'spanning_cell', ans)


class Row(object):

    BLEVEL = 1

    def __init__(self, table, html_tag, tag_style=None):
        self.table = table
        self.html_tag = html_tag
        self.orig_tag_style = tag_style
        self.cells = []
        self.current_cell = None
        self.background_color = None if tag_style is None else convert_color(tag_style.backgroundColor)
        read_css_block_borders(self, tag_style)

    @property
    def first_cell(self):
        return self.cells[0] if self.cells else None

    @property
    def last_cell(self):
        return self.cells[-1] if self.cells else None

    def start_new_cell(self, html_tag, tag_style):
        self.current_cell = Cell(self, html_tag, tag_style)

    def finish_tag(self, html_tag):
        if self.current_cell is not None:
            if html_tag is self.current_cell.html_tag:
                self.cells.append(self.current_cell)
                self.current_cell = None

    def add_block(self, block):
        if self.current_cell is None:
            self.start_new_cell(self.html_tag, self.orig_tag_style)
        self.current_cell.add_block(block)

    def add_table(self, table):
        if self.current_cell is None:
            self.current_cell = Cell(self, self.html_tag, self.orig_tag_style)
        return self.current_cell.add_table(table)

    def serialize(self, parent, makeelement):
        tr = makeelement(parent, 'w:tr')
        for cell in self.cells:
            cell.serialize(tr, makeelement)


class Table(object):

    BLEVEL = 0

    def __init__(self, namespace, html_tag, tag_style=None):
        self.namespace = namespace
        self.html_tag = html_tag
        self.orig_tag_style = tag_style
        self.rows = []
        self.current_row = None
        self.width = convert_width(tag_style)
        self.background_color = None if tag_style is None else convert_color(tag_style.backgroundColor)
        self.jc = None
        self.float = None
        self.margin_left = self.margin_right = self.margin_top = self.margin_bottom = None
        if tag_style is not None:
            ml, mr = tag_style._get('margin-left'), tag_style.get('margin-right')
            if ml == 'auto':
                self.jc = 'center' if mr == 'auto' else 'right'
            self.float = tag_style['float']
            for edge in border_edges:
                setattr(self, 'margin_' + edge, tag_style['margin-' + edge])
        read_css_block_borders(self, tag_style)

    @property
    def first_row(self):
        return self.rows[0] if self.rows else None

    @property
    def last_row(self):
        return self.rows[-1] if self.rows else None

    def finish_tag(self, html_tag):
        if self.current_row is not None:
            self.current_row.finish_tag(html_tag)
            if self.current_row.html_tag is html_tag:
                self.rows.append(self.current_row)
                self.current_row = None
        table_ended = self.html_tag is html_tag
        if table_ended:
            self.expand_spanned_cells()
            for row in self.rows:
                for cell in row.cells:
                    cell.resolve_borders()
        return table_ended

    def expand_spanned_cells(self):
        # Expand horizontally
        for row in self.rows:
            for cell in tuple(row.cells):
                idx = row.cells.index(cell)
                if cell.col_span > 1 and (cell is row.cells[-1] or not isinstance(row.cells[idx+1], SpannedCell)):
                    row.cells[idx:idx+1] = [cell] + [SpannedCell(cell, horizontal=True) for i in range(1, cell.col_span)]

        # Expand vertically
        for r, row in enumerate(self.rows):
            for idx, cell in enumerate(row.cells):
                if cell.row_span > 1:
                    for nrow in self.rows[r+1:]:
                        sc = SpannedCell(cell, horizontal=False)
                        try:
                            tcell = nrow.cells[idx]
                        except Exception:
                            tcell = None
                        if tcell is None:
                            nrow.cells.extend([SpannedCell(nrow.cells[-1], horizontal=True) for i in range(idx - len(nrow.cells))])
                            nrow.cells.append(sc)
                        else:
                            if isinstance(tcell, SpannedCell):
                                # Conflict between rowspan and colspan
                                break
                            else:
                                nrow.cells.insert(idx, sc)

    def start_new_row(self, html_tag, html_style):
        if self.current_row is not None:
            self.rows.append(self.current_row)
        self.current_row = Row(self, html_tag, html_style)

    def start_new_cell(self, html_tag, html_style):
        if self.current_row is None:
            self.start_new_row(html_tag, None)
        self.current_row.start_new_cell(html_tag, html_style)

    def add_block(self, block):
        self.current_row.add_block(block)

    def add_table(self, table):
        if self.current_row is None:
            self.current_row = Row(self, self.html_tag, self.orig_tag_style)
        return self.current_row.add_table(table)

    def serialize(self, parent):
        makeelement = self.namespace.makeelement
        rows = [r for r in self.rows if r.cells]
        if not rows:
            return
        tbl = makeelement(parent, 'w:tbl')
        tblPr = makeelement(tbl, 'w:tblPr')
        makeelement(tblPr, 'w:tblW', w_type=self.width[0], w_w=unicode_type(self.width[1]))
        if self.float in {'left', 'right'}:
            kw = {'w_vertAnchor':'text', 'w_horzAnchor':'text', 'w_tblpXSpec':self.float}
            for edge in border_edges:
                val = getattr(self, 'margin_' + edge) or 0
                if {self.float, edge} == {'left', 'right'}:
                    val = max(val, 2)
                kw['w_' + edge + 'FromText'] = unicode_type(max(0, int(val *20)))
            makeelement(tblPr, 'w:tblpPr', **kw)
        if self.jc is not None:
            makeelement(tblPr, 'w:jc', w_val=self.jc)
        for row in rows:
            row.serialize(tbl, makeelement)
