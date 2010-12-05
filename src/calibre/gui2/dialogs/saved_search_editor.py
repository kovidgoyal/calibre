__license__   = 'GPL v3'

__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


from PyQt4.QtCore import SIGNAL
from PyQt4.QtGui import QDialog

from calibre.gui2.dialogs.saved_search_editor_ui import Ui_SavedSearchEditor
from calibre.utils.search_query_parser import saved_searches
from calibre.utils.icu import sort_key
from calibre.gui2.dialogs.confirm_delete import confirm

class SavedSearchEditor(QDialog, Ui_SavedSearchEditor):

    def __init__(self, window, initial_search=None):
        QDialog.__init__(self, window)
        Ui_SavedSearchEditor.__init__(self)
        self.setupUi(self)

        self.connect(self.add_search_button, SIGNAL('clicked()'), self.add_search)
        self.connect(self.search_name_box, SIGNAL('currentIndexChanged(int)'),
                                    self.current_index_changed)
        self.connect(self.delete_search_button, SIGNAL('clicked()'), self.del_search)

        self.current_search_name = None
        self.searches = {}
        self.searches_to_delete = []
        for name in saved_searches().names():
            self.searches[name] = saved_searches().lookup(name)

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
            self.searches_to_delete.append(self.current_search_name)
            self.current_search_name = None
            self.search_name_box.removeItem(self.search_name_box.currentIndex())

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
        if self.current_search_name:
            self.searches[self.current_search_name] = unicode(self.search_text.toPlainText())
        for name in self.searches_to_delete:
            saved_searches().delete(name)
        for name in self.searches:
            saved_searches().add(name, self.searches[name])
        QDialog.accept(self)
