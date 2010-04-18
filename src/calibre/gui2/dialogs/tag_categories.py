__license__   = 'GPL v3'

__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog, QDialogButtonBox, QLineEdit, QComboBox
from PyQt4.Qt import QString

from calibre.gui2.dialogs.tag_categories_ui import Ui_TagCategories
from calibre.gui2 import qstring_to_unicode, config
from calibre.gui2 import question_dialog, error_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.constants import islinux

class TagCategories(QDialog, Ui_TagCategories):
    category_names  = [_('Authors'), _('Series'), _('Publishers'), _('Tags')]
    category_labels =   ['author',     'series',    'publisher',     'tag']


    def __init__(self, window, db, index=None):
        QDialog.__init__(self, window)
        Ui_TagCategories.__init__(self)
        self.setupUi(self)

        self.db = db
        self.index = index
        self.tags = []

        self.all_items = {}
        self.all_items['tag'] = sorted(self.db.all_tags(), cmp=lambda x,y: cmp(x.lower(), y.lower()))
        self.all_items['author'] = sorted([i[1].replace('|', ',') for i in self.db.all_authors()],
                                          cmp=lambda x,y: cmp(x.lower(), y.lower()))
        self.all_items['publisher'] = sorted([i[1] for i in self.db.all_publishers()],
                                             cmp=lambda x,y: cmp(x.lower(), y.lower()))
        self.all_items['series'] = sorted([i[1] for i in self.db.all_series()],
                                          cmp=lambda x,y: cmp(x.lower(), y.lower()))
        self.current_cat_name = None
        self.current_cat_label= None
        self.category_label_to_name = {}
        self.category_name_to_label = {}
        for i in range(len(self.category_labels)):
            self.category_label_to_name[self.category_labels[i]] = self.category_names[i]
            self.category_name_to_label[self.category_names[i]] = self.category_labels[i]

        self.connect(self.apply_button,   SIGNAL('clicked()'), self.apply_tags)
        self.connect(self.unapply_button, SIGNAL('clicked()'), self.unapply_tags)
        self.connect(self.add_category_button, SIGNAL('clicked()'), self.add_category)
        self.connect(self.category_box, SIGNAL('currentIndexChanged(int)'), self.select_category)
        self.connect(self.delete_category_button, SIGNAL('clicked()'), self.del_category)
        if islinux:
            self.available_tags.itemDoubleClicked.connect(self.apply_tags)
        else:
            self.connect(self.available_tags, SIGNAL('itemActivated(QListWidgetItem*)'), self.apply_tags)
        self.connect(self.applied_tags,   SIGNAL('itemActivated(QListWidgetItem*)'), self.unapply_tags)

        self.categories = dict.copy(config['tag_categories'])
        if self.categories is None:
            self.categories = {}
        self.populate_category_list()
        self.category_kind_box.clear()
        for i in range(len(self.category_names)):
            self.category_kind_box.addItem(self.category_names[i])
        self.select_category(0)

    def apply_tags(self, item=None):
        if self.current_cat_name[0] is None:
            return
        items = self.available_tags.selectedItems() if item is None else [item]
        for item in items:
            tag = qstring_to_unicode(item.text())
            if tag not in self.tags:
                self.tags.append(tag)
                self.available_tags.takeItem(self.available_tags.row(item))
        self.tags.sort()
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)
    def unapply_tags(self, item=None):
        items = self.applied_tags.selectedItems() if item is None else [item]
        for item in items:
            tag = qstring_to_unicode(item.text())
            self.tags.remove(tag)
            self.available_tags.addItem(tag)
        self.tags.sort()
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)
        self.available_tags.sortItems()

    def add_category(self):
        self.save_category()
        cat_name = qstring_to_unicode(self.input_box.text()).strip()
        if cat_name == '':
            return
        cat_kind = unicode(self.category_kind_box.currentText())
        r_cat_kind = self.category_name_to_label[cat_kind]
        if r_cat_kind not in self.categories:
            self.categories[r_cat_kind] = {}
        if cat_name not in self.categories[r_cat_kind]:
            self.category_box.clear()
            self.category_kind_label.setText(cat_kind)
            self.current_cat_name = cat_name
            self.current_cat_label = r_cat_kind
            self.categories[r_cat_kind][cat_name] = []
            if len(self.tags):
                self.clear_boxes(item_label=self.current_cat_label)
            self.populate_category_list()
            self.category_box.setCurrentIndex(self.category_box.findText(cat_name))
        else:
            self.select_category(self.category_box.findText(cat_name))
        return True

    def del_category(self):
        if not confirm('<p>'+_('The current tag category will be '
                       '<b>permanently deleted</b>. Are you sure?')
                    +'</p>', 'tag_category_delete', self):
            return
        print 'here', self.current_category
        if self.current_cat_name is not None:
            if self.current_cat_name == unicode(self.category_box.currentText()):
                del self.categories[self.current_cat_label][self.current_cat_name]
                self.current_category = [None, None] ## order here is important. RemoveItem will put it back
                self.category_box.removeItem(self.category_box.currentIndex())

    def select_category(self, idx):
        self.save_category()
        s = self.category_box.itemText(idx)
        if s:
            self.current_cat_name = unicode(s)
            self.current_cat_label = str(self.category_box.itemData(idx).toString())
        else:
            self.current_cat_name  = None
            self.current_cat_label = None
        self.clear_boxes(item_label=False)
        if self.current_cat_label:
            self.category_kind_label.setText(self.category_label_to_name[self.current_cat_label])
            self.tags = self.categories[self.current_cat_label].get(self.current_cat_name, [])
            # Must do two loops because obsolete values can be saved
            # We need to show these to the user so they can be deleted if desired
            for t in self.tags:
                self.applied_tags.addItem(t)
            for t in self.all_items[self.current_cat_label]:
                if t not in self.tags:
                    self.available_tags.addItem(t)
        else:
            self.category_kind_label.setText('')


    def clear_boxes(self, item_label = None):
        self.tags = []
        self.applied_tags.clear()
        self.available_tags.clear()
        if item_label:
             for item in self.all_items[item_label]:
                 self.available_tags.addItem(item)

    def accept(self):
        self.save_category()
        config['tag_categories'] = self.categories
        QDialog.accept(self)

    def save_category(self):
        if self.current_cat_name is not None:
            self.categories[self.current_cat_label][self.current_cat_name] = self.tags

    def populate_category_list(self):
        cat_list = {}
        for c in self.categories:
            for n in self.categories[c]:
                if n.strip():
                    cat_list[n] = c
        for n in sorted(cat_list.keys(), cmp=lambda x,y: cmp(x.lower(), y.lower())):
            self.category_box.addItem(n, cat_list[n])