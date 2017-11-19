#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import (
    QFormLayout, QIcon, QInputDialog, QLabel, QLineEdit, QListWidget, Qt,
    QVBoxLayout
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

    def __init__(self, parent=None, search=None, commit_changes=True):
        self.initial_search = search
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
        l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)

        self.la = la = QLabel(_(
            'You can create a <i>Saved search</i>, for frequently used searches here.'
            ' The search will be visible under <i>Searches</i> in the Tag browser,'
            ' using the name that you specify here.'))
        la.setWordWrap(True)
        l.addRow(la)

        self.sname = n = QLineEdit(self)
        l.addRow(_('&Name:'), n)
        n.setPlaceholderText(_('The Saved search name'))

        self.search = s = QLineEdit(self)
        s.setMinimumWidth(400)
        l.addRow(_('&Search:'), s)
        s.setPlaceholderText(_('The search expression'))
        if self.initial_search:
            s.setText(self.initial_search)
        n.setFocus(Qt.OtherFocusReason)
        l.addRow(self.bb)

    def accept(self):
        Dialog.accept(self)
        name = self.sname.text().strip()
        if not name:
            return error_dialog(
                self,
                _('No search name'),
                _('You must specify a name for the Saved search'),
                show=True)
        expression = self.search.text().strip()
        if not expression:
            return error_dialog(
                self,
                _('No search expression'),
                _('You must specify a search expression for the Saved search'),
                show=True)
        self.accepted_data = name, expression
        if self.commit_changes:
            if icu_lower(name) in self.search_names:
                self.searches.pop(self.search_names[icu_lower(name)], None)
            self.searches[name] = expression
            commit_searches(self.searches)


class SavedSearchEditor(Dialog):

    def __init__(self, parent, initial_search=None):
        self.initial_search = initial_search
        Dialog.__init__(
            self, _('Manage saved searches'), 'manage-saved-searches', parent)

    def setup_ui(self):
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        self.l = l = QVBoxLayout(self)
        b = self.bb.addButton(_('&Add search'), self.bb.ActionRole)
        b.setIcon(QIcon(I('plus.png')))
        b.clicked.connect(self.add_search)

        b = self.bb.addButton(_('&Remove search'), self.bb.ActionRole)
        b.setIcon(QIcon(I('minus.png')))
        b.clicked.connect(self.del_search)

        b = self.bb.addButton(_('Re&name search'), self.bb.ActionRole)
        b.setIcon(QIcon(I('modified.png')))
        b.clicked.connect(self.rename_search)

        self.slist = QListWidget(self)
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

    def populate_search_list(self):
        self.slist.clear()
        for name in sorted(self.searches.keys(), key=sort_key):
            self.slist.addItem(name)

    def add_search(self):
        d = AddSavedSearch(parent=self, commit_changes=False)
        if d.exec_() != d.Accepted:
            return
        name, expression = d.accepted_data
        nmap = {icu_lower(n):n for n in self.searches}
        if icu_lower(name) in nmap:
            q = nmap[icu_lower(name)]
            del self.searches[q]
            self.select_search(q)
            self.slist.takeItem(self.slist.currentRow())
        self.searches[name] = expression
        self.slist.insertItem(0, name)
        self.slist.setCurrentRow(0)
        self.current_index_changed(self.slist.currentItem())

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

    def rename_search(self):
        n = self.current_search_name
        if n:
            text, ok = QInputDialog.getText(self, _('Rename saved search'), _('&New name:'))
            if ok and text:
                self.slist.currentItem().setText(text)
                self.searches[text] = self.searches.pop(n)

    def select_search(self, name):
        items = self.slist.findItems(name, Qt.MatchFixedString | Qt.MatchCaseSensitive)
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
