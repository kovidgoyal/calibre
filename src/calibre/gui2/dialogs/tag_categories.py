__license__   = 'GPL v3'

__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (
    Qt, QDialog, QIcon, QListWidgetItem)

from calibre.gui2.dialogs.tag_categories_ui import Ui_TagCategories
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2 import error_dialog
from calibre.constants import islinux
from calibre.utils.icu import sort_key, strcmp


class Item(object):

    def __init__(self, name, label, index, icon, exists):
        self.name = name
        self.label = label
        self.index = index
        self.icon = icon
        self.exists = exists

    def __str__(self):
        return 'name=%s, label=%s, index=%s, exists=%s'%(self.name, self.label, self.index, self.exists)


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

    def __init__(self, window, db, on_category=None, book_ids=None):
        QDialog.__init__(self, window)
        Ui_TagCategories.__init__(self)
        self.setupUi(self)

        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.db = db
        self.applied_items = []
        self.book_ids = book_ids

        if self.book_ids is None:
            self.apply_vl_checkbox.setEnabled(False)

        cc_icon = QIcon(I('column.png'))

        self.category_labels = self.category_labels_orig[:]
        self.category_icons  = [None, QIcon(I('user_profile.png')), QIcon(I('series.png')),
                           QIcon(I('publisher.png')), QIcon(I('tags.png'))]
        self.category_values = [None,
                           lambda: [t.original_name.replace('|', ',') for t in self.db_categories['authors']],
                           lambda: [t.original_name for t in self.db_categories['series']],
                           lambda: [t.original_name for t in self.db_categories['publisher']],
                           lambda: [t.original_name for t in self.db_categories['tags']]
                          ]
        category_names  = ['', _('Authors'), ngettext('Series', 'Series', 2), _('Publishers'), _('Tags')]

        for key,cc in self.db.custom_field_metadata().iteritems():
            if cc['datatype'] in ['text', 'series', 'enumeration']:
                self.category_labels.append(key)
                self.category_icons.append(cc_icon)
                self.category_values.append(lambda col=key: [t.original_name for t in self.db_categories[col]])
                category_names.append(cc['name'])
            elif cc['datatype'] == 'composite' and \
                    cc['display'].get('make_category', False):
                self.category_labels.append(key)
                self.category_icons.append(cc_icon)
                category_names.append(cc['name'])
                self.category_values.append(lambda col=key: [t.original_name for t in self.db_categories[col]])
        self.categories = dict.copy(db.prefs.get('user_categories', {}))
        if self.categories is None:
            self.categories = {}
        self.initialize_category_lists(book_ids=None)

        self.display_filtered_categories(0)

        for v in category_names:
            self.category_filter_box.addItem(v)
        self.current_cat_name = None

        self.apply_button.clicked.connect(self.apply_button_clicked)
        self.unapply_button.clicked.connect(self.unapply_button_clicked)
        self.add_category_button.clicked.connect(self.add_category)
        self.rename_category_button.clicked.connect(self.rename_category)
        self.category_box.currentIndexChanged[int].connect(self.select_category)
        self.category_filter_box.currentIndexChanged[int].connect(
                                                self.display_filtered_categories)
        self.delete_category_button.clicked.connect(self.del_category)
        if islinux:
            self.available_items_box.itemDoubleClicked.connect(self.apply_tags)
        else:
            self.available_items_box.itemActivated.connect(self.apply_tags)
        self.applied_items_box.itemActivated.connect(self.unapply_tags)
        self.apply_vl_checkbox.clicked.connect(self.apply_vl)

        self.populate_category_list()
        if on_category is not None:
            l = self.category_box.findText(on_category)
            if l >= 0:
                self.category_box.setCurrentIndex(l)
        if self.current_cat_name is None:
            self.category_box.setCurrentIndex(0)
            self.select_category(0)

    def initialize_category_lists(self, book_ids):
        self.db_categories = self.db.new_api.get_categories(book_ids=book_ids)
        self.all_items = []
        self.all_items_dict = {}
        for idx,label in enumerate(self.category_labels):
            if idx == 0:
                continue
            for n in self.category_values[idx]():
                t = Item(name=n, label=label, index=len(self.all_items),
                         icon=self.category_icons[idx], exists=True)
                self.all_items.append(t)
                self.all_items_dict[icu_lower(label+':'+n)] = t

        for cat in self.categories:
            for item,l in enumerate(self.categories[cat]):
                key = icu_lower(':'.join([l[1], l[0]]))
                t = self.all_items_dict.get(key, None)
                if l[1] in self.category_labels:
                    if t is None:
                        t = Item(name=l[0], label=l[1], index=len(self.all_items),
                                 icon=self.category_icons[self.category_labels.index(l[1])],
                                 exists=False)
                        self.all_items.append(t)
                        self.all_items_dict[key] = t
                    l[2] = t.index
                else:
                    # remove any references to a category that no longer exists
                    del self.categories[cat][item]

        self.all_items_sorted = sorted(self.all_items, key=lambda x: sort_key(x.name))

    def apply_vl(self, checked):
        if checked:
            self.initialize_category_lists(self.book_ids)
        else:
            self.initialize_category_lists(None)
        self.fill_applied_items()

    def make_list_widget(self, item):
        n = item.name if item.exists else item.name + _(' (not on any book)')
        w = QListWidgetItem(item.icon, n)
        w.setData(Qt.UserRole, item.index)
        w.setToolTip(_('Category lookup name: ') + item.label)
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

    def apply_button_clicked(self):
        self.apply_tags(node=None)

    def apply_tags(self, node=None):
        if self.current_cat_name is None:
            return
        nodes = self.available_items_box.selectedItems() if node is None else [node]
        for node in nodes:
            index = self.all_items[node.data(Qt.UserRole)].index
            if index not in self.applied_items:
                self.applied_items.append(index)
        self.applied_items.sort(key=lambda x:sort_key(self.all_items[x].name))
        self.display_filtered_categories(None)

    def unapply_button_clicked(self):
        self.unapply_tags(node=None)

    def unapply_tags(self, node=None):
        nodes = self.applied_items_box.selectedItems() if node is None else [node]
        for node in nodes:
            index = self.all_items[node.data(Qt.UserRole)].index
            self.applied_items.remove(index)
        self.display_filtered_categories(None)

    def add_category(self):
        self.save_category()
        cat_name = unicode(self.input_box.text()).strip()
        if cat_name == '':
            return False
        comps = [c.strip() for c in cat_name.split('.') if c.strip()]
        if len(comps) == 0 or '.'.join(comps) != cat_name:
            error_dialog(self, _('Invalid name'),
                    _('That name contains leading or trailing periods, '
                      'multiple periods in a row or spaces before '
                      'or after periods.')).exec_()
            return False
        for c in sorted(self.categories.keys(), key=sort_key):
            if strcmp(c, cat_name) == 0 or \
                    (icu_lower(cat_name).startswith(icu_lower(c) + '.') and
                     not cat_name.startswith(c + '.')):
                error_dialog(self, _('Name already used'),
                        _('That name is already used, perhaps with different case.')).exec_()
                return False
        if cat_name not in self.categories:
            self.category_box.clear()
            self.current_cat_name = cat_name
            self.categories[cat_name] = []
            self.applied_items = []
            self.populate_category_list()
        self.input_box.clear()
        self.category_box.setCurrentIndex(self.category_box.findText(cat_name))
        return True

    def rename_category(self):
        self.save_category()
        cat_name = unicode(self.input_box.text()).strip()
        if cat_name == '':
            return False
        if not self.current_cat_name:
            return False
        comps = [c.strip() for c in cat_name.split('.') if c.strip()]
        if len(comps) == 0 or '.'.join(comps) != cat_name:
            error_dialog(self, _('Invalid name'),
                    _('That name contains leading or trailing periods, '
                      'multiple periods in a row or spaces before '
                      'or after periods.')).exec_()
            return False

        for c in self.categories:
            if strcmp(c, cat_name) == 0:
                error_dialog(self, _('Name already used'),
                        _('That name is already used, perhaps with different case.')).exec_()
                return False
        # The order below is important because of signals
        self.categories[cat_name] = self.categories[self.current_cat_name]
        del self.categories[self.current_cat_name]
        self.current_cat_name = None
        self.populate_category_list()
        self.input_box.clear()
        self.category_box.setCurrentIndex(self.category_box.findText(cat_name))
        return True

    def del_category(self):
        if self.current_cat_name is not None:
            if not confirm('<p>'+_('The current tag category will be '
                           '<b>permanently deleted</b>. Are you sure?') +
                           '</p>', 'tag_category_delete', self):
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
        self.fill_applied_items()

    def fill_applied_items(self):
        if self.current_cat_name:
            self.applied_items = [cat[2] for cat in self.categories.get(self.current_cat_name, [])]
        else:
            self.applied_items = []
        self.applied_items.sort(key=lambda x:sort_key(self.all_items[x].name))
        self.display_filtered_categories(None)

    def accept(self):
        self.save_category()
        for cat in sorted(self.categories.keys(), key=sort_key):
            components = cat.split('.')
            for i in range(0,len(components)):
                c = '.'.join(components[0:i+1])
                if c not in self.categories:
                    self.categories[c] = []
        QDialog.accept(self)

    def save_category(self):
        if self.current_cat_name is not None:
            l = []
            for index in self.applied_items:
                item = self.all_items[index]
                l.append([item.name, item.label, item.index])
            self.categories[self.current_cat_name] = l

    def populate_category_list(self):
        self.category_box.blockSignals(True)
        self.category_box.clear()
        self.category_box.addItems(sorted(self.categories.keys(), key=sort_key))
        self.category_box.blockSignals(False)
