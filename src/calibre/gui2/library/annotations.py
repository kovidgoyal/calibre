#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from textwrap import fill

from PyQt5.Qt import (
    QApplication, QCheckBox, QComboBox, QCursor, QFont, QHBoxLayout, QIcon, QLabel,
    QSize, QSplitter, Qt, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget, pyqtSignal
)

from calibre.gui2 import Application, gprefs
from calibre.gui2.viewer.search import ResultsDelegate, SearchBox
from calibre.gui2.widgets2 import Dialog


def current_db():
    from calibre.gui2.ui import get_gui
    return (getattr(current_db, 'ans', None) or get_gui().current_db).new_api


class BusyCursor(object):

    def __enter__(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def __exit__(self, *args):
        QApplication.restoreOverrideCursor()


class AnnotsResultsDelegate(ResultsDelegate):

    add_ellipsis = False

    def result_data(self, result):
        if not isinstance(result, dict):
            return None, None, None, None
        full_text = result['text'].replace('0x1f', ' ')
        parts = full_text.split('\x1d')
        before = after = ''
        if len(parts) > 2:
            before, text = parts[:2]
            after = ' '.join(parts[2:]).replace('\x1d', '')
        elif len(parts) == 2:
            before, text = parts
        else:
            text = parts[0]
        return False, before, text, after


class ResultsList(QTreeWidget):

    def __init__(self, parent):
        QTreeWidget.__init__(self, parent)
        self.setHeaderHidden(True)
        self.delegate = AnnotsResultsDelegate(self)
        self.setItemDelegate(self.delegate)
        self.section_font = QFont(self.font())
        self.section_font.setItalic(True)

    def set_results(self, results):
        self.clear()
        book_id_map = {}
        db = current_db()
        for result in results:
            book_id = result['book_id']
            if book_id not in book_id_map:
                book_id_map[book_id] = {'title': db.field_for('title', book_id), 'matches': []}
            book_id_map[book_id]['matches'].append(result)
        for book_id, entry in book_id_map.items():
            section = QTreeWidgetItem([entry['title']], 1)
            section.setFlags(Qt.ItemIsEnabled)
            section.setFont(0, self.section_font)
            self.addTopLevelItem(section)
            section.setExpanded(True)
            for result in entry['matches']:
                item = QTreeWidgetItem(section, [' '], 2)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)
                item.setData(0, Qt.UserRole, result)


class Restrictions(QWidget):

    restrictions_changed = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QLabel(_('Restrict to') + ': '))
        la = QLabel(_('Types:'))
        h.addWidget(la)
        self.types_box = tb = QComboBox(self)
        tb.la = la
        tb.currentIndexChanged.connect(self.restrictions_changed)
        connect_lambda(tb.currentIndexChanged, tb, lambda tb: gprefs.set('browse_annots_restrict_to_type', tb.currentData()))
        la.setBuddy(tb)
        tb.setToolTip(_('Show only annotations of the specified type'))
        h.addWidget(tb)
        la = QLabel(_('User:'))
        h.addWidget(la)
        self.user_box = ub = QComboBox(self)
        ub.la = la
        ub.currentIndexChanged.connect(self.restrictions_changed)
        connect_lambda(ub.currentIndexChanged, ub, lambda ub: gprefs.set('browse_annots_restrict_to_user', ub.currentData()))
        la.setBuddy(ub)
        ub.setToolTip(_('Show only annotations created by the specified user'))
        h.addWidget(ub)
        h.addStretch(10)

    def re_initialize(self, db):
        tb = self.types_box
        before = tb.currentData()
        if not before:
            before = gprefs['browse_annots_restrict_to_type']
        tb.blockSignals(True)
        tb.clear()
        tb.addItem(' ', ' ')
        for atype in db.all_annotation_types():
            name = {'bookmark': _('Bookmarks'), 'highlight': _('Highlights')}.get(atype, atype)
            tb.addItem(name, atype)
        if before:
            row = tb.findData(before)
            if row > -1:
                tb.setCurrentIndex(row)
        tb.blockSignals(False)
        tb_is_visible = tb.count() > 2
        tb.setVisible(tb_is_visible), tb.la.setVisible(tb_is_visible)
        tb = self.user_box
        before = tb.currentData()
        if not before:
            before = gprefs['browse_annots_restrict_to_user']
        tb.blockSignals(True)
        tb.clear()
        tb.addItem(' ', ' ')
        for user_type, user in db.all_annotation_users():
            q = '{}: {}'.format(user_type, user)
            tb.addItem(q, '{}:{}'.format(user_type, user))
        if before:
            row = tb.findData(before)
            if row > -1:
                tb.setCurrentIndex(row)
        tb.blockSignals(False)
        ub_is_visible = tb.count() > 2
        tb.setVisible(ub_is_visible), tb.la.setVisible(ub_is_visible)
        self.setVisible(tb_is_visible or ub_is_visible)


class BrowsePanel(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.use_stemmer = parent.use_stemmer
        self.current_query = None
        l = QVBoxLayout(self)

        h = QHBoxLayout()
        l.addLayout(h)
        self.search_box = sb = SearchBox(self)
        sb.initialize('library-annotations-browser-search-box')
        sb.cleared.connect(self.cleared)
        sb.lineEdit().returnPressed.connect(self.show_next)
        sb.lineEdit().setPlaceholderText(_('Enter words to search for'))
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

        self.restrictions = rs = Restrictions(self)
        rs.restrictions_changed.connect(self.effective_query_changed)
        self.use_stemmer.stateChanged.connect(self.effective_query_changed)
        l.addWidget(rs)

        self.results_list = rl = ResultsList(self)
        l.addWidget(rl)

    def re_initialize(self):
        db = current_db()
        self.search_box.setFocus(Qt.OtherFocusReason)
        self.restrictions.re_initialize(db)

    def sizeHint(self):
        return QSize(450, 600)

    @property
    def effective_query(self):
        text = self.search_box.lineEdit().text().strip()
        if not text:
            return None
        atype = self.restrictions.types_box.currentData()
        if not atype or not atype.strip():
            atype = None
        user = self.restrictions.user_box.currentData()
        restrict_to_user = None
        if user and ':' in user:
            restrict_to_user = user.split(':', 1)
        return {
            'fts_engine_query': text,
            'annotation_type': atype,
            'restrict_to_user': restrict_to_user,
            'use_stemming': bool(self.use_stemmer.isChecked()),
        }

    def cleared(self):
        self.current_query = None
        self.results_list.clear()

    def do_find(self, backwards=False):
        q = self.effective_query
        if not q:
            return
        if q == self.current_query:
            self.results_list.show_next(backwards)
            return
        with BusyCursor():
            db = current_db()
            results = db.search_annotations(highlight_start='\x1d', highlight_end='\x1d', snippet_size=64, **q)
            self.results_list.set_results(results)
            self.current_query = q

    def effective_query_changed(self):
        self.do_find()

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
        self.use_stemmer = us = QCheckBox(_('Match on related English words'))
        us.setChecked(gprefs['browse_annots_use_stemmer'])
        us.setToolTip(fill(_(
            'With this option searching for words will also match on any related English words. For'
            ' example: correction matches correcting and corrected as well')))
        us.stateChanged.connect(lambda state: gprefs.set('browse_annots_use_stemmer', state != Qt.Unchecked))

        l = QVBoxLayout(self)

        self.splitter = s = QSplitter(self)
        l.addWidget(s)
        s.setChildrenCollapsible(False)

        self.browse_panel = bp = BrowsePanel(self)
        s.addWidget(bp)

        self.details_panel = dp = DetailsPanel(self)
        s.addWidget(dp)

        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(us), h.addStretch(10), h.addWidget(self.bb)

    def show_dialog(self):
        self.browse_panel.re_initialize()
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
