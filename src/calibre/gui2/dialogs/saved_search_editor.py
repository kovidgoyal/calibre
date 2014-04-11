__license__   = 'GPL v3'

__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


from PyQt5.QtGui import QDialog

from calibre.gui2.dialogs.saved_search_editor_ui import Ui_SavedSearchEditor
from calibre.utils.icu import sort_key
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.confirm_delete import confirm

class SavedSearchEditor(QDialog, Ui_SavedSearchEditor):

    def __init__(self, parent, initial_search=None):
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        QDialog.__init__(self, parent)
        Ui_SavedSearchEditor.__init__(self)
        self.setupUi(self)

        self.add_search_button.clicked[()].connect(self.add_search)
        self.search_name_box.currentIndexChanged[(int)].connect(self.current_index_changed)
        self.delete_search_button.clicked[()].connect(self.del_search)
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
        self.search_name_box.clear()
        for name in sorted(self.searches.keys(), key=sort_key):
            self.search_name_box.addItem(name)

    def add_search(self):
        search_name = unicode(self.input_box.text()).strip()
        if search_name == '':
            return False
        if icu_lower(search_name) in self.search_names:
            error_dialog(self, _('Saved search already exists'),
                     _('The saved search %s already exists, perhaps with '
                       'different case')%search_name).exec_()
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
            if not confirm('<p>'+_('The current saved search will be '
                           '<b>permanently deleted</b>. Are you sure?')
                        +'</p>', 'saved_search_editor_delete', self):
                return
            del self.searches[self.current_search_name]
            self.current_search_name = None
            self.search_name_box.removeItem(self.search_name_box.currentIndex())

    def rename_search(self):
        new_search_name = unicode(self.input_box.text()).strip()
        if new_search_name == '':
            return False
        if icu_lower(new_search_name) in self.search_names:
            error_dialog(self, _('Saved search already exists'),
                    _('The saved search %s already exists, perhaps with '
                      'different case')%new_search_name).exec_()
            return False
        if self.current_search_name in self.searches:
            self.searches[new_search_name] = self.searches[self.current_search_name]
            del self.searches[self.current_search_name]
            self.populate_search_list()
            self.select_search(new_search_name)
        return True

    def select_search(self, name):
        self.search_name_box.setCurrentIndex(self.search_name_box.findText(name))

    def current_index_changed(self, idx):
        if self.current_search_name:
            self.searches[self.current_search_name] = unicode(self.search_text.toPlainText())
        name = unicode(self.search_name_box.itemText(idx))
        if name:
            self.current_search_name = name
            self.search_text.setPlainText(self.searches[name])
        else:
            self.current_search_name  = None
            self.search_text.setPlainText('')

    def accept(self):
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        if self.current_search_name:
            self.searches[self.current_search_name] = unicode(self.search_text.toPlainText())
        ss = {name:self.searches[name] for name in self.searches}
        db.saved_search_set_all(ss)
        QDialog.accept(self)
