__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial
from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog, QListWidgetItem

from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2 import question_dialog, error_dialog
from calibre.ebooks.metadata import title_sort

class TagListEditor(QDialog, Ui_TagListEditor):

    def __init__(self, window, db, tag_to_match, category):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)

        self.to_rename = {}
        self.to_delete = []
        self.db = db
        self.all_tags = {}
        self.category = category
        if category == 'tags':
            result = db.get_tags_with_ids()
            compare = (lambda x,y:cmp(x.lower(), y.lower()))
        elif category == 'series':
            result = db.get_series_with_ids()
            compare = (lambda x,y:cmp(title_sort(x).lower(), title_sort(y).lower()))
        elif category == 'publisher':
            result = db.get_publishers_with_ids()
            compare = (lambda x,y:cmp(x.lower(), y.lower()))
        else: # should be a custom field
            self.cc_label = db.field_metadata[category]['label']
            print 'here', self.cc_label
            result = self.db.get_custom_items_with_ids(label=self.cc_label)
            compare = (lambda x,y:cmp(x.lower(), y.lower()))

        for k,v in result:
            self.all_tags[v] = k
        for tag in sorted(self.all_tags.keys(), cmp=compare):
            item = QListWidgetItem(tag)
            item.setData(Qt.UserRole, self.all_tags[tag])
            self.available_tags.addItem(item)

        items = self.available_tags.findItems(tag_to_match, Qt.MatchExactly)
        if len(items) == 1:
            self.available_tags.setCurrentItem(items[0])

        self.connect(self.delete_button,  SIGNAL('clicked()'), self.delete_tags)
        self.connect(self.rename_button,  SIGNAL('clicked()'), self.rename_tag)
        self.connect(self.available_tags, SIGNAL('itemDoubleClicked(QListWidgetItem *)'), self._rename_tag)
        self.connect(self.available_tags, SIGNAL('itemChanged(QListWidgetItem *)'), self.finish_editing)

    def finish_editing(self, item):
        if not item.text():
                error_dialog(self, _('Item is blank'),
                             _('An item cannot be set to nothing. Delete it instead.')).exec_()
                item.setText(self.item_before_editing.text())
                return
        if item.text() != self.item_before_editing.text():
            if item.text() in self.all_tags.keys() or item.text() in self.to_rename.keys():
                error_dialog(self, _('Item already used'),
                             _('The item %s is already used.')%(item.text())).exec_()
                item.setText(self.item_before_editing.text())
                return
            (id,ign) = self.item_before_editing.data(Qt.UserRole).toInt()
            self.to_rename[item.text()] = id

    def rename_tag(self):
        item = self.available_tags.currentItem()
        self._rename_tag(item)

    def _rename_tag(self, item):
        if item is None:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of Available items.')).exec_()
            return
        self.item_before_editing = item.clone()
        item.setFlags (item.flags() | Qt.ItemIsEditable);
        self.available_tags.editItem(item)

    def delete_tags(self, item=None):
        deletes = self.available_tags.selectedItems() if item is None else [item]
        if not deletes:
            error_dialog(self, _('No items selected'),
                         _('You must select at least one items from the list.')).exec_()
            return
        ct = ', '.join([unicode(item.text()) for item in deletes])
        if not question_dialog(self, _('Are your sure?'),
            '<p>'+_('Are you certain you want to delete the following items?')+'<br>'+ct):
            return

        for item in deletes:
            (id,ign) = item.data(Qt.UserRole).toInt()
            self.to_delete.append(id)
            self.available_tags.takeItem(self.available_tags.row(item))

    def accept(self):
        rename_func = None
        if self.category == 'tags':
            rename_func = self.db.rename_tag
            delete_func = self.db.delete_tag_using_id
        elif self.category == 'series':
            rename_func = self.db.rename_series
            delete_func = self.db.delete_series_using_id
        elif self.category == 'publisher':
            rename_func = self.db.rename_publisher
            delete_func = self.db.delete_publisher_using_id
        else:
            rename_func = partial(self.db.rename_custom_item, label=self.cc_label)
            delete_func = partial(self.db.delete_custom_item_using_id, label=self.cc_label)

        work_done = False
        if rename_func:
            for text in self.to_rename:
                work_done = True
                rename_func(id=self.to_rename[text], new_name=unicode(text))
            for item in self.to_delete:
                work_done = True
                delete_func(item)
        if not work_done:
            QDialog.reject(self)
        else:
            QDialog.accept(self)
