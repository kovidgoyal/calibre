# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING, cast

from qt.core import QDialog, QListWidgetItem, Qt

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.dialogs.device_category_editor_ui import Ui_DeviceCategoryEditor
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from _typeshed import SupportsRichComparison
    from qt.core import QWidget


class ListWidgetItem(QListWidgetItem):
    def __init__(self, txt: str) -> None:
        QListWidgetItem.__init__(self, txt)
        self.initial_value: str = txt
        self.current_value: str = txt
        self.previous_value: str = txt

    def data(self, role: int) -> object:
        if role == Qt.ItemDataRole.DisplayRole:
            if self.initial_value != self.current_value:
                return _('%(curr)s (was %(initial)s)') % dict(curr=self.current_value, initial=self.initial_value)
            else:
                return self.current_value
        elif role == Qt.ItemDataRole.EditRole:
            return self.current_value
        else:
            return QListWidgetItem.data(self, role)

    def setData(self, role: int, value: object) -> None:
        if role == Qt.ItemDataRole.EditRole:
            self.previous_value = self.current_value
            self.current_value = cast('str', value)
        QListWidgetItem.setData(self, role, value)

    def text(self) -> str:
        return self.current_value

    def initial_text(self) -> str:
        return self.initial_value

    def previous_text(self) -> str:
        return self.previous_value

    def setText(self, atext: str | None) -> None:
        self.current_value = atext or ''
        QListWidgetItem.setText(self, atext)


class DeviceCategoryEditor(QDialog, Ui_DeviceCategoryEditor):
    def __init__(self, window: QWidget | None, tag_to_match: str | None, data: Iterable[tuple[int, str]], key: Callable[[str], SupportsRichComparison]) -> None:
        QDialog.__init__(self, window)
        Ui_DeviceCategoryEditor.__init__(self)
        self.setupUi(self)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags() & (~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.to_rename: dict[int, str] = {}
        self.to_delete: set[int] = set()
        self.original_names: dict[int, str] = {}
        self.all_tags: dict[str, int] = {}

        for k, v in data:
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

    def finish_editing(self, item: ListWidgetItem) -> None:
        if not item.text():
            error_dialog(self, _('Item is blank'), _('An item cannot be set to nothing. Delete it instead.')).exec()
            item.setText(item.previous_text())
            return
        if item.text() != item.initial_text():
            id_ = int(cast('int', item.data(Qt.ItemDataRole.UserRole)))
            self.to_rename[id_] = str(item.text())

    def rename_tag(self) -> None:
        item = self.available_tags.currentItem()
        self._rename_tag(item)

    def _rename_tag(self, item: QListWidgetItem | None) -> None:
        if item is None:
            error_dialog(self, _('No item selected'), _('You must select one item from the list of available items.')).exec()
            return
        self.available_tags.editItem(item)

    def delete_tags(self) -> None:
        deletes = self.available_tags.selectedItems()
        if not deletes:
            error_dialog(self, _('No items selected'), _('You must select at least one item from the list.')).exec()
            return
        ct = ', '.join([str(item.text()) for item in deletes])
        if not question_dialog(self, _('Are you sure?'), '<p>' + _('Are you sure you want to delete the following items?') + '<br>' + ct):
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
