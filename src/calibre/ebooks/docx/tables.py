#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict

from lxml.html.builder import TABLE, TR, TD

from calibre.ebooks.docx.block_styles import inherit, read_shd, read_border ,border_props  # noqa
from calibre.ebooks.docx.names import XPath, get

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

def read_padding(parent, dest):
    name = 'tblCellMar' if parent.tag.endswith('}tblPr') else 'tcMar'
    left = top = bottom = right = inherit
    for mar in XPath('./w:%s' % name)(parent):
        for x in ('left', 'top', 'right', 'bottom'):
            for edge in XPath('./w:%s' % x)(mar):
                locals()[x] = _read_width(edge)
    for x in ('left', 'top', 'right', 'bottom'):
        setattr(dest, 'cell_padding_%s' % x, locals()[x])

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

def read_indent(parent, dest):
    ans = inherit
    for cs in XPath('./w:tblInd')(parent):
        ans = _read_width(cs)
    setattr(dest, 'indent', ans)

border_edges = ('left', 'top', 'right', 'bottom', 'insideH', 'insideV')

def read_borders(parent, dest):
    name = 'tblBorders' if parent.tag.endswith('}tblPr') else 'tcBorders'
    read_border(parent, dest, border_edges, name)

class TableStyle(object):

    all_properties = (
        'width', 'cell_padding_left', 'cell_padding_right', 'cell_padding_top',
        'cell_padding_bottom', 'margin_left', 'margin_right', 'background_color',
        'spacing', 'indent',
    ) + tuple(k % edge for edge in border_edges for k in border_props)

    def __init__(self, tblPr=None):
        if tblPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for x in ('width', 'padding', 'shd', 'justification', 'spacing', 'indent', 'borders'):
                f = globals()['read_%s' % x]
                f(tblPr, self)

        self._css = None

    def update(self, other):
        for prop in self.all_properties:
            nval = getattr(other, prop)
            if nval is not inherit:
                setattr(self, prop, nval)

    def resolve_based_on(self, parent):
        for p in self.all_properties:
            val = getattr(self, p)
            if val is inherit:
                setattr(self, p, getattr(parent, p))

    @property
    def css(self):
        return self._css

class Tables(object):

    def __init__(self):
        self.tables = OrderedDict()

    def register(self, tbl):
        self.tables[tbl] = self.current_table = []

    def add(self, p):
        self.current_table.append(p)

    def apply_markup(self, object_map):
        rmap = {v:k for k, v in object_map.iteritems()}
        for tbl, blocks in self.tables.iteritems():
            if not blocks:
                continue
            parent = rmap[blocks[0]].getparent()
            table = TABLE('\n\t\t')
            idx = parent.index(rmap[blocks[0]])
            parent.insert(idx, table)
            for row in XPath('./w:tr')(tbl):
                tr = TR('\n\t\t\t')
                tr.tail = '\n\t\t'
                table.append(tr)
                for tc in XPath('./w:tc')(row):
                    td = TD()
                    td.tail = '\n\t\t\t'
                    tr.append(td)
                    for p in XPath('./w:p')(tc):
                        block = rmap[p]
                        td.append(block)
                if len(tr):
                    tr[-1].tail = '\n\t\t'
            if len(table):
                table[-1].tail = '\n\t'

