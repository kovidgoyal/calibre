#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.docx.names import makeelement
from calibre.ebooks.docx.writer.utils import convert_color

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

    def __init__(self, row, html_tag, tag_style):
        self.row = row
        self.html_tag = html_tag
        self.items = []
        self.width = convert_width(tag_style)
        self.background_color = None if tag_style is None else convert_color(tag_style.backgroundColor)

    def add_block(self, block):
        self.items.append(block)

    def add_table(self, table):
        self.items.append(table)
        return table

    def serialize(self, parent):
        tc = makeelement(parent, 'w:tc')
        tcPr = makeelement(tc, 'w:tcPr')
        makeelement(tcPr, 'w:tcW', w_type=self.width[0], w_w=str(self.width[1]))
        # For some reason, Word 2007 refuses to honor <w:shd> at the table or row
        # level, despite what the specs say, so we inherit and apply at the
        # cell level
        bc = self.background_color or self.row.background_color or self.row.table.background_color
        if bc:
            makeelement(tcPr, 'w:shd', w_val="clear", w_color="auto", w_fill=bc)
        for item in self.items:
            item.serialize(tc)

class Row(object):

    def __init__(self, table, html_tag, tag_style=None):
        self.table = table
        self.html_tag = html_tag
        self.cells = []
        self.current_cell = None
        self.background_color = None if tag_style is None else convert_color(tag_style.backgroundColor)

    def start_new_cell(self, html_tag, tag_style):
        self.current_cell = Cell(self, html_tag, tag_style)

    def finish_tag(self, html_tag):
        if self.current_cell is not None:
            if html_tag is self.current_cell.html_tag:
                self.cells.append(self.current_cell)
                self.current_cell = None

    def add_block(self, block):
        self.current_cell.add_block(block)

    def add_table(self, table):
        return self.current_cell.add_table(table)

    def serialize(self, parent):
        tr = makeelement(parent, 'w:tr')
        tblPrEx = makeelement(tr, 'w:tblPrEx')
        if len(tblPrEx) == 0:
            tr.remove(tblPrEx)
        for cell in self.cells:
            cell.serialize(tr)

class Table(object):

    def __init__(self, html_tag, tag_style=None):
        self.html_tag = html_tag
        self.rows = []
        self.current_row = None
        self.width = convert_width(tag_style)
        self.background_color = None if tag_style is None else convert_color(tag_style.backgroundColor)
        self.jc = None
        if tag_style is not None:
            ml, mr = tag_style._get('margin-left'), tag_style.get('margin-right')
            if ml == 'auto':
                self.jc = 'center' if mr == 'auto' else 'right'

    def finish_tag(self, html_tag):
        if self.current_row is not None:
            self.current_row.finish_tag(html_tag)
            if self.current_row.html_tag is html_tag:
                self.rows.append(self.current_row)
                self.current_row = None
        table_ended = self.html_tag is html_tag
        return table_ended

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
        return self.current_row.add_table(table)

    def serialize(self, parent):
        rows = [r for r in self.rows if r.cells]
        if not rows:
            return
        tbl = makeelement(parent, 'w:tbl')
        tblPr = makeelement(tbl, 'w:tblPr')
        makeelement(tblPr, 'w:tblW', w_type=self.width[0], w_w=str(self.width[1]))
        if self.jc is not None:
            makeelement(tblPr, 'w:jc', w_val=self.jc)
        for row in rows:
            row.serialize(tbl)
