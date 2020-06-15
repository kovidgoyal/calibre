#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from PyQt5.Qt import (
    QApplication, QCursor, QHBoxLayout, QIcon, QListWidget, QSize, QSplitter, Qt,
    QToolButton, QVBoxLayout, QWidget
)

from calibre.gui2 import Application
from calibre.gui2.viewer.search import SearchBox
from calibre.gui2.widgets2 import Dialog


def current_db():
    from calibre.gui2.ui import get_gui
    return (getattr(current_db, 'ans', None) or get_gui().current_db).new_api


class BusyCursor(object):

    def __enter__(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def __exit__(self, *args):
        QApplication.restoreOverrideCursor()


class ResultsList(QListWidget):

    def __init__(self, parent):
        QListWidget.__init__(self, parent)

    def set_results(self, results):
        self.clear()
        for result in results:
            print(result)


class BrowsePanel(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.current_query = None
        l = QVBoxLayout(self)

        h = QHBoxLayout()
        l.addLayout(h)
        self.search_box = sb = SearchBox(self)
        sb.initialize('library-annotations-browser-search-box')
        sb.cleared.connect(self.cleared)
        sb.lineEdit().returnPressed.connect(self.show_next)
        h.addWidget(sb)

        self.next_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.NoFocus)
        nb.setIcon(QIcon(I('arrow-down.png')))
        nb.clicked.connect(self.show_next)
        nb.setToolTip(_('Find next match'))

        self.prev_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.NoFocus)
        nb.setIcon(QIcon(I('arrow-up.png')))
        nb.clicked.connect(self.show_previous)
        nb.setToolTip(_('Find previous match'))

        self.results_list = rl = ResultsList(self)
        l.addWidget(rl)

    def sizeHint(self):
        return QSize(450, 600)

    @property
    def effective_query(self):
        text = self.search_box.lineEdit().text().strip()
        if not text:
            return None
        return {
            'fts_engine_query': text,
        }

    def cleared(self):
        self.current_query = None

    def do_find(self, backwards=False):
        q = self.effective_query
        if not q:
            return
        if q == self.current_query:
            self.results_list.show_next(backwards)
            return
        with BusyCursor():
            db = current_db()
            results = db.search_annotations(**q)
            self.results_list.set_results(results)

    def show_next(self):
        self.do_find()

    def show_previous(self):
        self.do_find(backwards=True)


class DetailsPanel(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)

    def sizeHint(self):
        return QSize(450, 600)


class AnnotationsBrowser(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Annotations browser'), 'library-annotations-browser-1', parent=parent)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

    def keyPressEvent(self, ev):
        if ev.key() not in (Qt.Key_Enter, Qt.Key_Return):
            return Dialog.keyPressEvent(self, ev)

    def setup_ui(self):
        l = QVBoxLayout(self)

        self.splitter = s = QSplitter(self)
        l.addWidget(s)
        s.setChildrenCollapsible(False)

        self.browse_panel = bp = BrowsePanel(self)
        s.addWidget(bp)

        self.details_panel = dp = DetailsPanel(self)
        s.addWidget(dp)

        self.bb.setStandardButtons(self.bb.Close)
        l.addWidget(self.bb)

    def show_dialog(self):
        self.browse_panel.search_box.setFocus(Qt.OtherFocusReason)
        if self.parent() is None:
            self.exec_()
        else:
            self.show()


if __name__ == '__main__':
    from calibre.library import db
    app = Application([])
    current_db.ans = db(os.path.expanduser('~/test library'))
    br = AnnotationsBrowser()
    br.show_dialog()
    del br
    del app
