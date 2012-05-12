#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from PyQt4.Qt import QStandardItem, QStandardItemModel, Qt

from calibre.ebooks.metadata.toc import TOC as MTOC

class TOCItem(QStandardItem):

    def __init__(self, toc):
        text = toc.text
        if text:
            text = re.sub(r'\s', ' ', text)
        QStandardItem.__init__(self, text if text else '')
        self.abspath = toc.abspath
        self.fragment = toc.fragment
        for t in toc:
            self.appendRow(TOCItem(t))
        self.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)

    @classmethod
    def type(cls):
        return QStandardItem.UserType+10

class TOC(QStandardItemModel):

    def __init__(self, spine, toc=None):
        QStandardItemModel.__init__(self)
        if toc is None:
            toc = MTOC()
        for t in toc:
            self.appendRow(TOCItem(t))
        self.setHorizontalHeaderItem(0, QStandardItem(_('Table of Contents')))


