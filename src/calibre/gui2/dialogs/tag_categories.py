__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import (Qt, QApplication, QDialog, QIcon, QListWidgetItem)

from collections import namedtuple

from calibre.constants import islinux
from calibre.gui2 import error_dialog, warning_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.tag_categories_ui import Ui_TagCategories
from calibre.utils.icu import primary_sort_key, strcmp, primary_contains


class TagCategories(QDialog, Ui_TagCategories):

    '''
    The structure of user_categories stored in preferences is
      {cat_name: [ [name, category, v], [], [] ]}, cat_name: [ [name, cat, v] ...]}
    where name is the item name, category is where it came from (series, etc),
    and v is a scratch area.

    If you add a category, set v to zero. If you delete a category, ensure that
    both the name and the category match.
    '''

    category_icons  = {'authors': QIcon.ic('user_profile.png'),
                       'series': QIcon.ic('series.png'),
                       'publisher': QIcon.ic('publisher.png'),
                       'tags': QIcon.ic('tags.png'),
                       'languages': QIcon.ic('languages.png')}

    ItemTuple = namedtuple('ItemTuple', 'v k')
    CategoryNameTuple = namedtuple('CategoryNameTuple', 'n k')

    def __init__(self, window, db, on_category=None, book_ids=None):
        QDialog.__init__(self, window)
        Ui_TagCategories.__init__(self)
        self.setupUi(self)

        # I can't figure out how to get these into the .ui file
        self.gridLayout_2.setColumnMinimumWidth(0, 50)
        self.gridLayout_2.setColumnStretch(0, 1)
        self.gridLayout_2.setColumnMinimumWidth(2, 50)
        self.gridLayout_2.setColumnStretch(2, 1)

        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.db = db
        self.applied_items = []
        self.book_ids = book_ids
        self.hide_hidden_categories = False
        self.filter_by_vl = False
        self.category_labels = []  # The label is the lookup key

        if self.book_ids is None:
            self.apply_vl_checkbox.setEnabled(False)

        self.cc_icon = QIcon.ic('column.png')

        # Build a dict of all available items, used when checking and building user cats
        self.all_items = {}
        db_categories = self.db.new_api.get_categories()
        for key, tag in db_categories.items():
            self.all_items[key] = {'icon': self.category_icons.get(key, self.cc_icon),
                                   'name': self.db.field_metadata[key]['name'],
                                   'values': {t.original_name for t in tag}
                                   }

        # build the list of all user categories. Filter out keys that no longer exist
        self.user_categories = {}
        for cat_name, values in db.new_api.pref('user_categories', {}).items():
            fv = set()
            for v in values:
                if v[1] in self.db.field_metadata:
                    fv.add(self.item_tuple(v[1], v[0]))
            self.user_categories[cat_name] = fv

        # get the hidden categories
        hidden_cats = self.db.new_api.pref('tag_browser_hidden_categories', None)
        self.hidden_categories = set()
        # strip non-existent field keys from hidden categories (just in case)
        for cat in hidden_cats:
            if cat in self.db.field_metadata:
                self.hidden_categories.add(cat)

        self.copy_category_name_to_clipboard.clicked.connect(self.copy_category_name_to_clipboard_clicked)
        self.apply_button.clicked.connect(self.apply_button_clicked)
        self.unapply_button.clicked.connect(self.unapply_button_clicked)
        self.add_category_button.clicked.connect(self.add_category)
        self.rename_category_button.clicked.connect(self.rename_category)
        self.category_box.currentIndexChanged.connect(self.select_category)
        self.category_filter_box.currentIndexChanged.connect(
                                                self.display_filtered_categories)
        self.item_filter_box.textEdited.connect(self.apply_filter)
        self.delete_category_button.clicked.connect(self.delete_category)
        if islinux:
            self.available_items_box.itemDoubleClicked.connect(self.apply_tags)
        else:
            self.available_items_box.itemActivated.connect(self.apply_tags)
        self.applied_items_box.itemActivated.connect(self.unapply_tags)
        self.apply_vl_checkbox.clicked.connect(self.apply_vl_clicked)
        self.hide_hidden_categories_checkbox.clicked.connect(self.hide_hidden_categories_clicked)

        self.current_cat_name = None
        self.initialize_category_lists()
        self.display_filtered_categories()
        self.populate_category_list()
        if on_category is not None:
            self.category_box.setCurrentIndex(self.category_box.findText(on_category))
        if self.current_cat_name is None:
            self.category_box.setCurrentIndex(0)
            self.select_category(0)

    def copy_category_name_to_clipboard_clicked(self):
        t = self.category_box.itemText(self.category_box.currentIndex())
        QApplication.clipboard().setText(t)

    def item_tuple(self, key, val):
        return self.ItemTuple(val, key)

    def category_name_tuple(self, key, name):
        return self.CategoryNameTuple(name, key)

    def initialize_category_lists(self):
        cfb = self.category_filter_box
        current_cat_filter = (self.category_labels[cfb.currentIndex()]
                              if self.category_labels and cfb.currentIndex() > 0
                              else '')

        # get the values for each category taking into account the VL, then
        # populate the lists taking hidden and filtered categories into account
        self.available_items = {}
        self.sorted_items = []
        sorted_categories = []
        item_filter = self.item_filter_box.text()
        db_categories = self.db.new_api.get_categories(book_ids=self.book_ids if
                                                       self.filter_by_vl else None)
        for key, tags in db_categories.items():
            if key == 'search' or key.startswith('@'):
                continue
            if self.hide_hidden_categories and key in self.hidden_categories:
                continue
            av = set()
            for t in tags:
                if item_filter and not primary_contains(item_filter, t.original_name):
                    continue
                av.add(t.original_name)
                self.sorted_items.append(self.item_tuple(key, t.original_name))
            self.available_items[key] = av
            sorted_categories.append(self.category_name_tuple(key, self.all_items[key]['name']))

        # Sort the items
        self.sorted_items.sort(key=lambda v: primary_sort_key(v.v + v.k))

        # Fill in the category names with visible (not hidden) lookup keys
        sorted_categories.sort(key=lambda v: primary_sort_key(v.n + v.k))
        cfb.blockSignals(True)
        cfb.clear()
        cfb.addItem('', '')
        for i,v in enumerate(sorted_categories):
            cfb.addItem(f'{v.n} ({v.k})', v.k)
            if current_cat_filter == v.k:
                cfb.setCurrentIndex(i+1)
        cfb.blockSignals(False)

    def populate_category_list(self):
        self.category_box.blockSignals(True)
        self.category_box.clear()
        self.category_box.addItems(sorted(self.user_categories.keys(), key=primary_sort_key))
        self.category_box.blockSignals(False)

    def make_available_list_item(self, key, val):
        w = QListWidgetItem(self.all_items[key]['icon'], val)
        w.setData(Qt.ItemDataRole.UserRole, self.item_tuple(key, val))
        w.setToolTip(_('Lookup name: {}').format(key))
        return w

    def make_applied_list_item(self, tup):
        if tup.v not in self.all_items[tup.k]['values']:
            t = tup.v + ' ' + _('(Not in library)')
        elif tup.k not in self.available_items:
            t = tup.v + ' ' + _('(Hidden in Tag browser)')
        elif tup.v not in self.available_items[tup.k]:
            t = tup.v + ' ' + _('(Hidden by Virtual library)')
        else:
            t = tup.v
        w = QListWidgetItem(self.all_items[tup.k]['icon'], t)
        w.setData(Qt.ItemDataRole.UserRole, tup)
        w.setToolTip(_('Lookup name: {}').format(tup.k))
        return w

    def hide_hidden_categories_clicked(self, checked):
        self.hide_hidden_categories = checked
        self.initialize_category_lists()
        self.display_filtered_categories()
        self.fill_applied_items()

    def apply_vl_clicked(self, checked):
        self.filter_by_vl = checked
        self.initialize_category_lists()
        self.fill_applied_items()

    def apply_filter(self, _):
        self.initialize_category_lists()
        self.display_filtered_categories()

    def display_filtered_categories(self):
        idx = self.category_filter_box.currentIndex()
        filter_key = self.category_filter_box.itemData(idx)
        self.available_items_box.clear()
        for it in self.sorted_items:
            if idx != 0 and it.k != filter_key:
                continue
            self.available_items_box.addItem(self.make_available_list_item(it.k, it.v))

    def fill_applied_items(self):
        ccn = self.current_cat_name
        if ccn:
            self.applied_items = [v for v in self.user_categories[ccn]]
            self.applied_items.sort(key=lambda x:primary_sort_key(x.v + x.k))
        else:
            self.applied_items = []
        self.applied_items_box.clear()
        for tup in self.applied_items:
            self.applied_items_box.addItem(self.make_applied_list_item(tup))

    def apply_button_clicked(self):
        self.apply_tags(node=None)

    def apply_tags(self, node=None):
        if self.current_cat_name is None:
            return
        nodes = self.available_items_box.selectedItems() if node is None else [node]
        if len(nodes) == 0:
            warning_dialog(self, _('No items selected'),
                           _('You must select items to apply'),
                           show=True, show_copy_button=False)
            return
        for node in nodes:
            tup = node.data(Qt.ItemDataRole.UserRole)
            self.user_categories[self.current_cat_name].add(tup)
        self.fill_applied_items()

    def unapply_button_clicked(self):
        self.unapply_tags(node=None)

    def unapply_tags(self, node=None):
        if self.current_cat_name is None:
            return
        nodes = self.applied_items_box.selectedItems() if node is None else [node]
        if len(nodes) == 0:
            warning_dialog(self, _('No items selected'),
                           _('You must select items to unapply'),
                           show=True, show_copy_button=False)
            return
        for node in nodes:
            tup = node.data(Qt.ItemDataRole.UserRole)
            self.user_categories[self.current_cat_name].discard(tup)
        self.fill_applied_items()

    def add_category(self):
        cat_name = str(self.input_box.text()).strip()
        if cat_name == '':
            return
        comps = [c.strip() for c in cat_name.split('.') if c.strip()]
        if len(comps) == 0 or '.'.join(comps) != cat_name:
            error_dialog(self, _('Invalid name'),
                    _('That name contains leading or trailing periods, '
                      'multiple periods in a row or spaces before '
                      'or after periods.')).exec()
            return False
        for c in sorted(self.user_categories.keys(), key=primary_sort_key):
            if strcmp(c, cat_name) == 0 or \
                    (icu_lower(cat_name).startswith(icu_lower(c) + '.') and
                     not cat_name.startswith(c + '.')):
                error_dialog(self, _('Name already used'),
                        _('That name is already used, perhaps with different case.')).exec()
                return False
        if cat_name not in self.user_categories:
            self.user_categories[cat_name] = set()
            self.category_box.clear()
            self.current_cat_name = cat_name
            self.populate_category_list()
            self.fill_applied_items()
        self.input_box.clear()
        self.category_box.setCurrentIndex(self.category_box.findText(cat_name))

    def rename_category(self):
        cat_name = str(self.input_box.text()).strip()
        if cat_name == '':
            return
        if not self.current_cat_name:
            return
        comps = [c.strip() for c in cat_name.split('.') if c.strip()]
        if len(comps) == 0 or '.'.join(comps) != cat_name:
            error_dialog(self, _('Invalid name'),
                    _('That name contains leading or trailing periods, '
                      'multiple periods in a row or spaces before '
                      'or after periods.')).exec()
            return

        for c in self.user_categories:
            if strcmp(c, cat_name) == 0:
                error_dialog(self, _('Name already used'),
                        _('That name is already used, perhaps with different case.')).exec()
                return
        # The order below is important because of signals
        self.user_categories[cat_name] = self.user_categories[self.current_cat_name]
        del self.user_categories[self.current_cat_name]
        self.current_cat_name = None
        self.populate_category_list()
        self.input_box.clear()
        self.category_box.setCurrentIndex(self.category_box.findText(cat_name))
        return

    def delete_category(self):
        if self.current_cat_name is not None:
            if not confirm('<p>'+_('The current User category will be '
                           '<b>permanently deleted</b>. Are you sure?') +
                           '</p>', 'tag_category_delete', self):
                return
            del self.user_categories[self.current_cat_name]
            # self.category_box.removeItem(self.category_box.currentIndex())
            self.populate_category_list()
            if self.category_box.count():
                self.current_cat_name = self.category_box.itemText(0)
            else:
                self.current_cat_name = None
            self.fill_applied_items()

    def select_category(self, idx):
        s = self.category_box.itemText(idx)
        if s:
            self.current_cat_name = str(s)
        else:
            self.current_cat_name  = None
        self.fill_applied_items()

    def accept(self):
        # Reconstruct the pref value
        self.categories = {}
        for cat in self.user_categories:
            cat_values = []
            for tup in self.user_categories[cat]:
                cat_values.append([tup.v, tup.k, 0])
            self.categories[cat] = cat_values
        QDialog.accept(self)
