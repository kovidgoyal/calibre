__license__   = 'GPL v3'

__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog, QIcon, QListWidgetItem

from calibre.gui2.dialogs.tag_categories_ui import Ui_TagCategories
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.constants import islinux
from calibre.utils.icu import sort_key

class Item:
    def __init__(self, name, label, index, icon, exists):
        self.name = name
        self.label = label
        self.index = index
        self.icon = icon
        self.exists = exists
    def __str__(self):
        return 'name=%s, label=%s, index=%s, exists='%(self.name, self.label, self.index, self.exists)

class TagCategories(QDialog, Ui_TagCategories):
    '''
    The structure of user_categories stored in preferences is
      {cat_name: [ [name, category, v], [], []}, cat_name [ [name, cat, v] ...}
    where name is the item name, category is where it came from (series, etc),
    and v is a scratch area that this editor uses to keep track of categories.

    If you add a category, it is permissible to set v to zero. If you delete
    a category, ensure that both the name and the category match.
    '''
    category_labels_orig =   ['', 'authors', 'series', 'publisher', 'tags']

    def __init__(self, window, db, on_category=None):
        QDialog.__init__(self, window)
        Ui_TagCategories.__init__(self)
        self.setupUi(self)

        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.db = db
        self.applied_items = []

        cc_icon = QIcon(I('column.png'))

        self.category_labels = self.category_labels_orig[:]
        category_icons  = [None, QIcon(I('user_profile.png')), QIcon(I('series.png')),
                           QIcon(I('publisher.png')), QIcon(I('tags.png'))]
        category_values = [None,
                           lambda: [n.replace('|', ',') for (id, n) in self.db.all_authors()],
                           lambda: [n for (id, n) in self.db.all_series()],
                           lambda: [n for (id, n) in self.db.all_publishers()],
                           lambda: self.db.all_tags()
                          ]
        category_names  = ['', _('Authors'), _('Series'), _('Publishers'), _('Tags')]

        cc_map = self.db.custom_column_label_map
        for cc in cc_map:
            if cc_map[cc]['datatype'] in ['text', 'series']:
                self.category_labels.append(db.field_metadata.label_to_key(cc))
                category_icons.append(cc_icon)
                category_values.append(lambda col=cc: self.db.all_custom(label=col))
                category_names.append(cc_map[cc]['name'])

        self.all_items = []
        self.all_items_dict = {}
        for idx,label in enumerate(self.category_labels):
            if idx == 0:
                continue
            for n in category_values[idx]():
                t = Item(name=n, label=label, index=len(self.all_items),icon=category_icons[idx], exists=True)
                self.all_items.append(t)
                self.all_items_dict[label+':'+n] = t

        self.categories = dict.copy(db.prefs.get('user_categories', {}))
        if self.categories is None:
            self.categories = {}
        for cat in self.categories:
            for item,l in enumerate(self.categories[cat]):
                key = ':'.join([l[1], l[0]])
                t = self.all_items_dict.get(key, None)
                if l[1] in self.category_labels:
                    if t is None:
                        t = Item(name=l[0], label=l[1], index=len(self.all_items),
                                 icon=category_icons[self.category_labels.index(l[1])], exists=False)
                        self.all_items.append(t)
                        self.all_items_dict[key] = t
                    l[2] = t.index
                else:
                    # remove any references to a category that no longer exists
                    del self.categories[cat][item]

        self.all_items_sorted = sorted(self.all_items, key=lambda x: sort_key(x.name))
        self.display_filtered_categories(0)

        for v in category_names:
            self.category_filter_box.addItem(v)
        self.current_cat_name = None

        self.connect(self.apply_button,   SIGNAL('clicked()'), self.apply_tags)
        self.connect(self.unapply_button, SIGNAL('clicked()'), self.unapply_tags)
        self.connect(self.add_category_button, SIGNAL('clicked()'), self.add_category)
        self.connect(self.category_box, SIGNAL('currentIndexChanged(int)'), self.select_category)
        self.connect(self.category_filter_box, SIGNAL('currentIndexChanged(int)'), self.display_filtered_categories)
        self.connect(self.delete_category_button, SIGNAL('clicked()'), self.del_category)
        if islinux:
            self.available_items_box.itemDoubleClicked.connect(self.apply_tags)
        else:
            self.connect(self.available_items_box, SIGNAL('itemActivated(QListWidgetItem*)'), self.apply_tags)
        self.connect(self.applied_items_box,   SIGNAL('itemActivated(QListWidgetItem*)'), self.unapply_tags)

        self.populate_category_list()
        if on_category is not None:
            l = self.category_box.findText(on_category)
            if l >= 0:
                self.category_box.setCurrentIndex(l)

    def make_list_widget(self, item):
        n = item.name if item.exists else item.name + _(' (not on any book)')
        w = QListWidgetItem(item.icon, n)
        w.setData(Qt.UserRole, item.index)
        return w

    def display_filtered_categories(self, idx):
        idx = idx if idx is not None else self.category_filter_box.currentIndex()
        self.available_items_box.clear()
        self.applied_items_box.clear()
        for item in self.all_items_sorted:
            if idx == 0 or item.label == self.category_labels[idx]:
                if item.index not in self.applied_items and item.exists:
                    self.available_items_box.addItem(self.make_list_widget(item))
        for index in self.applied_items:
            self.applied_items_box.addItem(self.make_list_widget(self.all_items[index]))

    def apply_tags(self, node=None):
        if self.current_cat_name is None:
            return
        nodes = self.available_items_box.selectedItems() if node is None else [node]
        for node in nodes:
            index = self.all_items[node.data(Qt.UserRole).toPyObject()].index
            if index not in self.applied_items:
                self.applied_items.append(index)
        self.applied_items.sort(key=lambda x:sort_key(self.all_items[x]))
        self.display_filtered_categories(None)

    def unapply_tags(self, node=None):
        nodes = self.applied_items_box.selectedItems() if node is None else [node]
        for node in nodes:
            index = self.all_items[node.data(Qt.UserRole).toPyObject()].index
            self.applied_items.remove(index)
        self.display_filtered_categories(None)

    def add_category(self):
        self.save_category()
        cat_name = unicode(self.input_box.text()).strip()
        if cat_name == '':
            return False
        if cat_name not in self.categories:
            self.category_box.clear()
            self.current_cat_name = cat_name
            self.categories[cat_name] = []
            self.applied_items = []
            self.populate_category_list()
            self.category_box.setCurrentIndex(self.category_box.findText(cat_name))
        else:
            self.select_category(self.category_box.findText(cat_name))
        return True

    def del_category(self):
        if self.current_cat_name is not None:
            if not confirm('<p>'+_('The current tag category will be '
                           '<b>permanently deleted</b>. Are you sure?')
                        +'</p>', 'tag_category_delete', self):
                return
            del self.categories[self.current_cat_name]
            self.current_cat_name = None
            self.category_box.removeItem(self.category_box.currentIndex())

    def select_category(self, idx):
        self.save_category()
        s = self.category_box.itemText(idx)
        if s:
            self.current_cat_name = unicode(s)
        else:
            self.current_cat_name  = None
        if self.current_cat_name:
            self.applied_items = [cat[2] for cat in self.categories.get(self.current_cat_name, [])]
        else:
            self.applied_items = []
        self.display_filtered_categories(None)

    def accept(self):
        self.save_category()
        self.db.prefs['user_categories'] = self.categories
        QDialog.accept(self)

    def save_category(self):
        if self.current_cat_name is not None:
            l = []
            for index in self.applied_items:
                item = self.all_items[index]
                l.append([item.name, item.label, item.index])
            self.categories[self.current_cat_name] = l

    def populate_category_list(self):
        for n in sorted(self.categories.keys(), key=sort_key):
            self.category_box.addItem(n)
