__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
from PyQt4.QtCore import SIGNAL
from PyQt4.QtGui import QDialog

from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2 import question_dialog, error_dialog

class TagListEditor(QDialog, Ui_TagListEditor):

    def tag_cmp(self, x, y):
        return cmp(x.lower(), y.lower())

    def __init__(self, window, db):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)

        self.to_delete = []
        self.db = db
        all_tags = [tag for tag in self.db.all_tags()]
        all_tags = list(set(all_tags))
        all_tags.sort(cmp=self.tag_cmp)
        for tag in all_tags:
            self.available_tags.addItem(tag)

        self.connect(self.delete_button,  SIGNAL('clicked()'), self.delete_tags)

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
            self.to_delete.append(item)
            self.available_tags.takeItem(self.available_tags.row(item))

    def accept(self):
        for item in self.to_delete:
            self.db.delete_tag(unicode(item.text()))
        QDialog.accept(self)

