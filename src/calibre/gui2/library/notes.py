#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
from functools import partial
from qt.core import (
    QCheckBox, QDialogButtonBox, QHBoxLayout, QIcon, QLabel, QMenu, QSize, Qt,
    QToolButton, QVBoxLayout, QWidget, pyqtSignal,
)

from calibre.db.cache import Cache
from calibre.gui2 import Application, gprefs
from calibre.gui2.viewer.widgets import SearchBox
from calibre.gui2.widgets2 import Dialog, FlowLayout


def current_db() -> Cache:
    from calibre.gui2.ui import get_gui
    return (getattr(current_db, 'ans', None) or get_gui().current_db).new_api


class RestrictFields(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = FlowLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.restrict_label = QLabel(_('Restrict to:'))
        self.restricted_fields = []
        self.add_button = b = QToolButton(self)
        b.setIcon(QIcon.ic('plus.png')), b.setText(_('Add')), b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.fields_menu = m = QMenu()
        b.setMenu(m)
        m.aboutToShow.connect(self.build_add_menu)
        self.remove_button = b = QToolButton(self)
        b.setIcon(QIcon.ic('minus.png')), b.setText(_('Remove')), b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.remove_fields_menu = m = QMenu()
        b.setMenu(m)
        m.aboutToShow.connect(self.build_remove_menu)

        db = current_db()
        fm = db.field_metadata
        def field_name(field):
            return fm[field].get('name') or field
        self.field_names = {f:field_name(f) for f in db.field_supports_notes()}
        self.field_labels = {f: QLabel(self.field_names[f], self) for f in sorted(self.field_names, key=self.field_names.get)}
        for l in self.field_labels.values():
            l.setVisible(False)

        self.relayout()

    def relayout(self):
        for i in range(self.l.count()):
            self.l.removeItem(self.l.itemAt(i))
        for l in self.field_labels.values():
            l.setVisible(False)
        self.l.addWidget(self.restrict_label)
        self.l.addWidget(self.add_button)
        for field in self.restricted_fields:
            w = self.field_labels[field]
            w.setVisible(True)
            self.l.addWidget(w)
        self.l.addWidget(self.remove_button)
        self.remove_button.setVisible(bool(self.restricted_fields))

    def build_add_menu(self):
        m = self.fields_menu
        m.clear()
        for field in self.field_labels:
            if field not in self.restricted_fields:
                m.addAction(self.field_names[field], partial(self.add_field, field))

    def build_remove_menu(self):
        m = self.remove_fields_menu
        m.clear()

        for field in self.restricted_fields:
            m.addAction(self.field_names[field], partial(self.remove_field, field))

    def add_field(self, field):
        self.restricted_fields.append(field)
        self.relayout()

    def remove_field(self, field):
        self.restricted_fields.remove(field)
        self.relayout()


class SearchInput(QWidget):

    cleared_signal = pyqtSignal()
    show_next_signal = pyqtSignal()
    show_previous_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        l.addLayout(h)
        self.search_box = sb = SearchBox(self)
        sb.initialize('library-notes-browser-search-box')
        sb.cleared.connect(self.cleared, type=Qt.ConnectionType.QueuedConnection)
        sb.lineEdit().returnPressed.connect(self.show_next)
        sb.lineEdit().setPlaceholderText(_('Enter words to search for'))
        h.addWidget(sb)

        self.next_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nb.setIcon(QIcon.ic('arrow-down.png'))
        nb.clicked.connect(self.show_next)
        nb.setToolTip(_('Find next match'))

        self.prev_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nb.setIcon(QIcon.ic('arrow-up.png'))
        nb.clicked.connect(self.show_previous)
        nb.setToolTip(_('Find previous match'))

        self.restrict = r = RestrictFields(self)
        l.addWidget(r)


    @property
    def current_query(self):
        return {
            'query': self.search_box.lineEdit().text().strip(),
            'restrict_to_fields': tuple(self.restrict.restricted_fields),
        }

    def cleared(self):
        raise NotImplementedError('TODO: Implement me')

    def show_next(self):
        raise NotImplementedError('TODO: Implement me')

    def show_previous(self):
        raise NotImplementedError('TODO: Implement me')


class NotesBrowser(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Browse notes'), 'browse-notes-dialog', default_buttons=QDialogButtonBox.StandardButton.Close)
        self.setWindowIcon(QIcon.ic('notes.png'))

    def sizeHint(self):
        return QSize(900, 600)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)

        self.search_input = si = SearchInput(self)
        l.addWidget(si)

        self.use_stemmer = us = QCheckBox(_('&Match on related words'))
        us.setChecked(gprefs['browse_notes_use_stemmer'])
        us.setToolTip('<p>' + _(
            'With this option searching for words will also match on any related words (supported in several languages). For'
            ' example, in the English language: <i>correction</i> matches <i>correcting</i> and <i>corrected</i> as well'))
        us.stateChanged.connect(lambda state: gprefs.set('browse_notes_use_stemmer', state != Qt.CheckState.Unchecked.value))

        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(us), h.addStretch(10), h.addWidget(self.bb)



if __name__ == '__main__':
    from calibre.library import db
    app = Application([])
    current_db.ans = db(os.path.expanduser('~/test library'))
    br = NotesBrowser()
    br.exec()
    del br
    del app
