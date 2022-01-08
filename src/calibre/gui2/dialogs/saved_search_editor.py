#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import (
    QFormLayout, QIcon, QLabel, QLineEdit, QListWidget, Qt, QVBoxLayout, QDialog,
    QDialogButtonBox, QPlainTextEdit
)

from calibre import prepare_string_for_xml
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import sort_key


def commit_searches(searches):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db
    db.saved_search_set_all(searches)


class AddSavedSearch(Dialog):

    def __init__(self, parent=None, search=None, commit_changes=True, label=None, validate=None):
        self.initial_search = search
        self.validate = validate
        self.label = label
        self.commit_changes = commit_changes
        Dialog.__init__(
            self, _('Add a new Saved search'), 'add-saved-search', parent)
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        self.searches = {}
        for name in db.saved_search_names():
            self.searches[name] = db.saved_search_lookup(name)
        self.search_names = {icu_lower(n):n for n in db.saved_search_names()}

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.la = la = QLabel(self.label or _(
            'You can create a <i>Saved search</i>, for frequently used searches here.'
            ' The search will be visible under <i>Saved searches</i> in the Tag browser,'
            ' using the name that you specify here.'))
        la.setWordWrap(True)
        l.addRow(la)

        self.sname = n = QLineEdit(self)
        l.addRow(_('&Name:'), n)
        n.setPlaceholderText(_('The Saved search name'))

        self.search = s = QPlainTextEdit(self)
        s.setMinimumWidth(400)
        l.addRow(_('&Search:'), s)
        s.setPlaceholderText(_('The search expression'))
        if self.initial_search:
            s.setPlainText(self.initial_search)
        n.setFocus(Qt.FocusReason.OtherFocusReason)
        l.addRow(self.bb)

    def accept(self):
        name = self.sname.text().strip()
        if not name:
            return error_dialog(
                self,
                _('No search name'),
                _('You must specify a name for the Saved search'),
                show=True)
        expression = self.search.toPlainText().strip()
        if not expression:
            return error_dialog(
                self,
                _('No search expression'),
                _('You must specify a search expression for the Saved search'),
                show=True)
        self.accepted_data = name, expression
        if self.validate is not None:
            err = self.validate(name, expression)
            if err:
                return error_dialog(self, _('Invalid saved search'), err, show=True)
        Dialog.accept(self)
        if self.commit_changes:
            if icu_lower(name) in self.search_names:
                self.searches.pop(self.search_names[icu_lower(name)], None)
            self.searches[name] = expression
            commit_searches(self.searches)


class SavedSearchEditor(Dialog):

    def __init__(self, parent, initial_search=None):
        self.initial_search = initial_search
        Dialog.__init__(
            self, _('Manage Saved searches'), 'manage-saved-searches', parent)

    def setup_ui(self):
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        self.l = l = QVBoxLayout(self)
        b = self.bb.addButton(_('&Add search'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('plus.png'))
        b.clicked.connect(self.add_search)

        b = self.bb.addButton(_('&Remove search'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('minus.png'))
        b.clicked.connect(self.del_search)

        b = self.bb.addButton(_('&Edit search'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('modified.png'))
        b.clicked.connect(self.edit_search)

        self.slist = QListWidget(self)
        self.slist.setStyleSheet('QListView::item { padding: 3px }')
        self.slist.activated.connect(self.edit_search)
        self.slist.setAlternatingRowColors(True)
        self.searches = {name: db.saved_search_lookup(name) for name in db.saved_search_names()}
        self.populate_search_list()
        if self.initial_search is not None and self.initial_search in self.searches:
            self.select_search(self.initial_search)
        elif self.searches:
            self.slist.setCurrentRow(0)
        self.slist.currentItemChanged.connect(self.current_index_changed)
        l.addWidget(self.slist)

        self.desc = la = QLabel('\xa0')
        la.setWordWrap(True)
        l.addWidget(la)

        l.addWidget(self.bb)
        self.current_index_changed(self.slist.currentItem())
        self.setMinimumHeight(500)
        self.setMinimumWidth(600)

    @property
    def current_search_name(self):
        i = self.slist.currentItem()
        if i is not None:
            ans = i.text()
            if ans in self.searches:
                return ans

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Delete:
            self.del_search()
            return
        return Dialog.keyPressEvent(self, ev)

    def populate_search_list(self):
        self.slist.clear()
        for name in sorted(self.searches.keys(), key=sort_key):
            self.slist.addItem(name)

    def add_search(self):
        d = AddSavedSearch(parent=self, commit_changes=False, validate=self.validate_add)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        name, expression = d.accepted_data
        self.searches[name] = expression
        self.populate_search_list()
        self.select_search(name)

    def del_search(self):
        n = self.current_search_name
        if n is not None:
            if not confirm(
                '<p>' + _(
                    'The current saved search will be '
                    '<b>permanently deleted</b>. Are you sure?') + '</p>',
                'saved_search_editor_delete', self):
                return
            self.slist.takeItem(self.slist.currentRow())
            del self.searches[n]

    def edit_search(self):
        n = self.current_search_name
        if not n:
            return
        d = AddSavedSearch(parent=self, commit_changes=False,
                           label=_('Edit the name and/or expression below.'),
                           validate=self.validate_edit)
        d.setWindowTitle(_('Edit saved search'))
        d.sname.setText(n)
        d.search.setPlainText(self.searches[n])
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        name, expression = d.accepted_data
        self.slist.currentItem().setText(name)
        del self.searches[n]
        self.searches[name] = expression
        self.current_index_changed(self.slist.currentItem())

    def duplicate_msg(self, name):
        return _('A saved search with the name {} already exists. Choose another name').format(name)

    def validate_edit(self, name, expression):
        q = self.current_search_name
        if icu_lower(name) in {icu_lower(n) for n in self.searches if n != q}:
            return self.duplicate_msg(name)

    def validate_add(self, name, expression):
        if icu_lower(name) in {icu_lower(n) for n in self.searches}:
            return self.duplicate_msg(name)

    def select_search(self, name):
        items = self.slist.findItems(name, Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive)
        if items:
            self.slist.setCurrentItem(items[0])

    def current_index_changed(self, item):
        n = self.current_search_name
        if n:
            t = self.searches[n]
        else:
            t = ''
        self.desc.setText('<p><b>{}</b>: '.format(_('Search expression')) + prepare_string_for_xml(t))

    def accept(self):
        commit_searches(self.searches)
        Dialog.accept(self)
