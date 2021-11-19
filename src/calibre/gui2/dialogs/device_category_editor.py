__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import Qt, QDialog, QListWidgetItem

from calibre.gui2.dialogs.device_category_editor_ui import Ui_DeviceCategoryEditor
from calibre.gui2 import question_dialog, error_dialog


class ListWidgetItem(QListWidgetItem):

    def __init__(self, txt):
        QListWidgetItem.__init__(self, txt)
        self.initial_value = txt
        self.current_value = txt
        self.previous_value = txt

    def data(self, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if self.initial_value != self.current_value:
                return _('%(curr)s (was %(initial)s)')%dict(
                        curr=self.current_value, initial=self.initial_value)
            else:
                return self.current_value
        elif role == Qt.ItemDataRole.EditRole:
            return self.current_value
        else:
            return QListWidgetItem.data(self, role)

    def setData(self, role, data):
        if role == Qt.ItemDataRole.EditRole:
            self.previous_value = self.current_value
            self.current_value = data
        QListWidgetItem.setData(self, role, data)

    def text(self):
        return self.current_value

    def initial_text(self):
        return self.initial_value

    def previous_text(self):
        return self.previous_value

    def setText(self, txt):
        self.current_value = txt
        QListWidgetItem.setText(txt)


class DeviceCategoryEditor(QDialog, Ui_DeviceCategoryEditor):

    def __init__(self, window, tag_to_match, data, key):
        QDialog.__init__(self, window)
        Ui_DeviceCategoryEditor.__init__(self)
        self.setupUi(self)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.to_rename = {}
        self.to_delete = set()
        self.original_names = {}
        self.all_tags = {}

        for k,v in data:
            self.all_tags[v] = k
            self.original_names[k] = v
        for tag in sorted(self.all_tags.keys(), key=key):
            item = ListWidgetItem(tag)
            item.setData(Qt.ItemDataRole.UserRole, self.all_tags[tag])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.available_tags.addItem(item)

        if tag_to_match is not None:
            items = self.available_tags.findItems(tag_to_match, Qt.MatchFlag.MatchExactly)
            if len(items) == 1:
                self.available_tags.setCurrentItem(items[0])

        self.delete_button.clicked.connect(self.delete_tags)
        self.rename_button.clicked.connect(self.rename_tag)
        self.available_tags.itemDoubleClicked.connect(self._rename_tag)
        self.available_tags.itemChanged.connect(self.finish_editing)

    def finish_editing(self, item):
        if not item.text():
            error_dialog(self, _('Item is blank'),
                            _('An item cannot be set to nothing. Delete it instead.')).exec()
            item.setText(item.previous_text())
            return
        if item.text() != item.initial_text():
            id_ = int(item.data(Qt.ItemDataRole.UserRole))
            self.to_rename[id_] = str(item.text())

    def rename_tag(self):
        item = self.available_tags.currentItem()
        self._rename_tag(item)

    def _rename_tag(self, item):
        if item is None:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of available items.')).exec()
            return
        self.available_tags.editItem(item)

    def delete_tags(self):
        deletes = self.available_tags.selectedItems()
        if not deletes:
            error_dialog(self, _('No items selected'),
                         _('You must select at least one item from the list.')).exec()
            return
        ct = ', '.join([str(item.text()) for item in deletes])
        if not question_dialog(self, _('Are you sure?'),
            '<p>'+_('Are you sure you want to delete the following items?')+'<br>'+ct):
            return
        row = self.available_tags.row(deletes[0])
        for item in deletes:
            id = int(item.data(Qt.ItemDataRole.UserRole))
            self.to_delete.add(id)
            self.available_tags.takeItem(self.available_tags.row(item))

        if row >= self.available_tags.count():
            row = self.available_tags.count() - 1
        if row >= 0:
            self.available_tags.scrollToItem(self.available_tags.item(row))
