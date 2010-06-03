__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog, QListWidgetItem

from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2 import question_dialog, error_dialog

class TagListEditor(QDialog, Ui_TagListEditor):

    def tag_cmp(self, x, y):
        return cmp(x.lower(), y.lower())

    def __init__(self, window, db, tag_to_match):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)

        self.to_rename = {}
        self.to_delete = []
        self.db = db
        self.all_tags = {}
        for k,v in db.get_tags_with_ids():
            self.all_tags[v] = k
        for tag in sorted(self.all_tags.keys(), cmp=self.tag_cmp):
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
                error_dialog(self, 'Tag is blank',
                             'A tag cannot be set to nothing. Delete it instead.'%(item.text())).exec_()
                item.setText(self.item_before_editing.text())
                return
        if item.text() != self.item_before_editing.text():
            if item.text() in self.all_tags.keys() or item.text() in self.to_rename.keys():
                error_dialog(self, 'Tag already used',
                             'The tag %s is already used.'%(item.text())).exec_()
                item.setText(self.item_before_editing.text())
                return
            (id,_) = self.item_before_editing.data(Qt.UserRole).toInt()
            self.to_rename[item.text()] = id

    def rename_tag(self):
        item = self.available_tags.currentItem()
        self._rename_tag(item)

    def _rename_tag(self, item):
        if item is None:
            error_dialog(self, 'No tag selected', 'You must select one tag from the list of Available tags.').exec_()
            return
        self.item_before_editing = item.clone()
        item.setFlags (item.flags() | Qt.ItemIsEditable);
        self.available_tags.editItem(item)

    def delete_tags(self, item=None):
        confirms, deletes = [], []
        items = self.available_tags.selectedItems() if item is None else [item]
        if not items:
            error_dialog(self, 'No tags selected', 'You must select at least one tag from the list of Available tags.').exec_()
            return
        for item in items:
            if self.db.is_tag_used(unicode(item.text())):
                confirms.append(item)
            else:
                deletes.append(item)
        if confirms:
            ct = ', '.join([unicode(item.text()) for item in confirms])
            if question_dialog(self, _('Are your sure?'),
                '<p>'+_('The following tags are used by one or more books. '
                    'Are you certain you want to delete them?')+'<br>'+ct):
                deletes += confirms

        for item in deletes:
            (id,_) = item.data(Qt.UserRole).toInt()
            self.to_delete.append(id)
            self.available_tags.takeItem(self.available_tags.row(item))

    def accept(self):
        for text in self.to_rename:
            self.db.rename_tag(id=self.to_rename[text], new_name=unicode(text))
        for item in self.to_delete:
            self.db.delete_tag_using_id(item)
        QDialog.accept(self)

