__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog, QListWidgetItem

from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2 import question_dialog, error_dialog

class ListWidgetItem(QListWidgetItem):

    def __init__(self, txt):
        QListWidgetItem.__init__(self, txt)
        self.old_value = txt
        self.cur_value = txt

    def data(self, role):
        if role == Qt.DisplayRole:
            if self.old_value != self.cur_value:
                return _('%s (was %s)')%(self.cur_value, self.old_value)
            else:
                return self.cur_value
        elif role == Qt.EditRole:
            return self.cur_value
        else:
            return QListWidgetItem.data(self, role)

    def setData(self, role, data):
        if role == Qt.EditRole:
            self.cur_value = data.toString()
        QListWidgetItem.setData(self, role, data)

    def text(self):
        return self.cur_value

    def setText(self, txt):
        self.cur_value = txt
        QListWidgetItem.setText(txt)

class TagListEditor(QDialog, Ui_TagListEditor):

    def __init__(self, window, tag_to_match, data, key):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.to_rename = {}
        self.to_delete = []
        self.all_tags = {}

        for k,v in data:
            self.all_tags[v] = k
        for tag in sorted(self.all_tags.keys(), key=key):
            item = ListWidgetItem(tag)
            item.setData(Qt.UserRole, self.all_tags[tag])
            self.available_tags.addItem(item)

        if tag_to_match is not None:
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
            (id,ign) = self.item_before_editing.data(Qt.UserRole).toInt()
            if item.text() not in self.to_rename:
                self.to_rename[item.text()] = [id]
            else:
                self.to_rename[item.text()].append(id)

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
        row = self.available_tags.row(deletes[0])
        for item in deletes:
            (id,ign) = item.data(Qt.UserRole).toInt()
            self.to_delete.append(id)
            self.available_tags.takeItem(self.available_tags.row(item))

        if row >= self.available_tags.count():
            row = self.available_tags.count() - 1
        if row >= 0:
            self.available_tags.scrollToItem(self.available_tags.item(row))
