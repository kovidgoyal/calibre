#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import textwrap
from collections import namedtuple

from PyQt5.Qt import (
    QCheckBox, QComboBox, QHBoxLayout, QIcon, Qt, QToolButton, QVBoxLayout, QWidget,
    pyqtSignal
)

from calibre.gui2.viewer.web_view import vprefs
from calibre.gui2.widgets2 import HistoryComboBox

Search = namedtuple('Search', 'text mode case_sensitive backwards')


class SearchInput(QWidget):

    do_search = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)

        self.search_box = sb = HistoryComboBox(self)
        sb.lineEdit().setPlaceholderText(_('Search'))
        sb.lineEdit().setClearButtonEnabled(True)
        sb.lineEdit().returnPressed.connect(self.find_next)
        sb.initialize('viewer-search-box-history')
        h.addWidget(sb)

        self.next_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.NoFocus)
        nb.setIcon(QIcon(I('arrow-down.png')))
        nb.clicked.connect(self.find_next)
        nb.setToolTip(_('Find next match'))

        self.prev_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.NoFocus)
        nb.setIcon(QIcon(I('arrow-up.png')))
        nb.clicked.connect(self.find_previous)
        nb.setToolTip(_('Find previous match'))

        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        self.query_type = qt = QComboBox(self)
        qt.setFocusPolicy(Qt.NoFocus)
        qt.addItem(_('Normal'), 'normal')
        qt.addItem(_('Regex'), 'regex')
        qt.setToolTip(textwrap.fill(_('Choose the type of search: Normal will search'
            ' for the entered text, Regex will interpret the text as a'
            ' regular expression')))
        qt.setCurrentIndex(qt.findData(vprefs.get('viewer-search-mode', 'normal') or 'normal'))
        h.addWidget(qt)

        self.case_sensitive = cs = QCheckBox(_('Case sensitive'), self)
        cs.setFocusPolicy(Qt.NoFocus)
        cs.setChecked(bool(vprefs.get('viewer-search-case-sensitive', False)))
        h.addWidget(cs)

    def search_query(self, backwards=False):
        text = self.search_box.currentText().strip()
        if text:
            return Search(text, self.query_type.currentData() or 'normal', self.case_sensitive.isChecked(), backwards)

    def emit_search(self, backwards=False):
        vprefs['viewer-search-case-sensitive'] = self.case_sensitive.isChecked()
        vprefs['viewer-search-mode'] = self.query_type.currentData()
        sq = self.search_query(backwards)
        if sq is not None:
            self.do_search.emit(sq)

    def find_next(self):
        self.emit_search()

    def find_previous(self):
        self.emit_search(backwards=True)

    def focus_input(self):
        self.search_box.setFocus(Qt.OtherFocusReason)
        le = self.search_box.lineEdit()
        le.end(False)
        le.selectAll()


class SearchPanel(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.search_input = si = SearchInput(self)
        l.addWidget(si)
        l.addStretch(10)

    def focus_input(self):
        self.search_input.focus_input()
