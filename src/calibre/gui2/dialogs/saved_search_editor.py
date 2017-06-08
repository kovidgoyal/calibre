__license__ = 'GPL v3'

__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import QDialog, QFormLayout, Qt, QLineEdit, QLabel

from calibre.gui2.dialogs.saved_search_editor_ui import Ui_SavedSearchEditor
from calibre.utils.icu import sort_key
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.widgets2 import Dialog


def commit_searches(searches):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db
    db.saved_search_set_all(searches)


class AddSavedSearch(Dialog):

    def __init__(self, parent=None, search=None):
        self.initial_search = search
        Dialog.__init__(
            self, _('Add a new Saved search'), 'add-saved-search', parent)
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        self.searches = {}
        for name in db.saved_search_names():
            self.searches[name] = db.saved_search_lookup(name)
        self.search_names = {icu_lower(n) for n in db.saved_search_names()}

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
                _('You must specify a search name'),
                show=True)
        expression = self.search.text().strip()
        if not expression:
            return error_dialog(
                self,
                _('No search expression'),
                _('You must specify a search expression'),
                show=True)
        if icu_lower(name) in self.searches:
            self.searches.pop(icu_lower(name), None)
        self.searches[name] = expression
        commit_searches(self.searches)


class SavedSearchEditor(QDialog, Ui_SavedSearchEditor):

    def __init__(self, parent, initial_search=None):
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        QDialog.__init__(self, parent)
        Ui_SavedSearchEditor.__init__(self)
        self.setupUi(self)

        self.add_search_button.clicked.connect(self.add_search)
        self.search_name_box.currentIndexChanged[(
            int)].connect(self.current_index_changed)
        self.delete_search_button.clicked.connect(self.del_search)
        self.rename_button.clicked.connect(self.rename_search)

        self.current_search_name = None
        self.searches = {}
        for name in db.saved_search_names():
            self.searches[name] = db.saved_search_lookup(name)
        self.search_names = set([icu_lower(n) for n in db.saved_search_names()])

        self.populate_search_list()
        if initial_search is not None and initial_search in self.searches:
            self.select_search(initial_search)

    def populate_search_list(self):
        self.search_name_box.blockSignals(True)
        self.search_name_box.clear()
        self.search_name_box.addItem('')
        for name in sorted(self.searches.keys(), key=sort_key):
            self.search_name_box.addItem(name)
        self.search_names = set([icu_lower(n) for n in self.searches.keys()])
        self.search_name_box.blockSignals(False)

    def sanitize_name(self):
        n = unicode(self.input_box.text()).strip().replace('\\', '')
        self.input_box.setText(n)
        return n

    def add_search(self):
        self.save_current_search()
        search_name = self.sanitize_name()
        if search_name == '':
            return False
        if icu_lower(search_name) in self.search_names:
            error_dialog(
                self,
                _('Saved search already exists'),
                _(
                    'The saved search %s already exists, perhaps with '
                    'different case') % search_name).exec_()
            return False
        if search_name not in self.searches:
            self.searches[search_name] = ''
            self.populate_search_list()
            self.select_search(search_name)
        else:
            self.select_search(search_name)
        return True

    def del_search(self):
        if self.current_search_name is not None:
            if not confirm(
                '<p>' + _(
                    'The current saved search will be '
                    '<b>permanently deleted</b>. Are you sure?') + '</p>',
                'saved_search_editor_delete', self):
                return
            del self.searches[self.current_search_name]
            self.current_search_name = None
            self.search_name_box.removeItem(self.search_name_box.currentIndex())

    def rename_search(self):
        self.save_current_search()
        new_search_name = self.sanitize_name()
        if new_search_name == '':
            return False
        if icu_lower(new_search_name) in self.search_names:
            error_dialog(
                self,
                _('Saved search already exists'),
                _(
                    'The saved search %s already exists, perhaps with '
                    'different case') % new_search_name).exec_()
            return False
        if self.current_search_name in self.searches:
            self.searches[new_search_name] = self.searches[self.current_search_name]
            del self.searches[self.current_search_name]
            self.current_search_name = None
            self.populate_search_list()
            self.select_search(new_search_name)
        return True

    def select_search(self, name):
        self.search_name_box.setCurrentIndex(self.search_name_box.findText(name))

    def current_index_changed(self, idx):
        if self.current_search_name:
            self.searches[self.current_search_name] = unicode(
                self.search_text.toPlainText())
        name = unicode(self.search_name_box.itemText(idx))
        if name:
            self.current_search_name = name
            self.search_text.setPlainText(self.searches[name])
        else:
            self.current_search_name = None
            self.search_text.setPlainText('')

    def save_current_search(self):
        if self.current_search_name:
            self.searches[self.current_search_name] = unicode(
                self.search_text.toPlainText())

    def accept(self):
        self.save_current_search()
        ss = {name: self.searches[name] for name in self.searches}
        commit_searches(ss)
        QDialog.accept(self)
