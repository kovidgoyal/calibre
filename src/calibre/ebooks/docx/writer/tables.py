#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.docx.names import makeelement

class Cell(object):

    def __init__(self, html_tag, tag_style):
        self.html_tag = html_tag
        self.items = []

    def add_block(self, block):
        self.items.append(block)

    def add_table(self, table):
        self.items.append(table)
        return table

    def serialize(self, parent):
        tc = makeelement(parent, 'w:tc')
        for item in self.items:
            item.serialize(tc)

class Row(object):

    def __init__(self, html_tag, tag_style=None):
        self.html_tag = html_tag
        self.cells = []
        self.current_cell = None

    def start_new_cell(self, html_tag, tag_style):
        self.current_cell = Cell(html_tag, tag_style)

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
        for cell in self.cells:
            cell.serialize(tr)

class Table(object):

    def __init__(self, html_tag, tag_style=None):
        self.html_tag = html_tag
        self.rows = []
        self.current_row = None

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
        self.current_row = Row(html_tag, html_style)

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
        tblPr
        for row in rows:
            row.serialize(tbl)
