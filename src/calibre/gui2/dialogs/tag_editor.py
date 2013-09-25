__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog

from calibre.gui2.dialogs.tag_editor_ui import Ui_TagEditor
from calibre.gui2 import question_dialog, error_dialog, gprefs
from calibre.constants import islinux
from calibre.utils.icu import sort_key

class TagEditor(QDialog, Ui_TagEditor):

    def __init__(self, window, db, id_=None, key=None):
        QDialog.__init__(self, window)
        Ui_TagEditor.__init__(self)
        self.setupUi(self)

        self.db = db
        if key:
            key = db.field_metadata.key_to_label(key)
        self.key = key
        self.index = db.row(id_) if id_ is not None else None
        if self.index is not None:
            if key is None:
                tags = self.db.tags(self.index)
                if tags:
                    tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
            else:
                tags = self.db.get_custom(self.index, label=key)
        else:
            tags = []
        if tags:
            tags.sort(key=sort_key)
            for tag in tags:
                self.applied_tags.addItem(tag)
        else:
            tags = []

        self.tags = tags

        if key:
            all_tags = [tag for tag in self.db.all_custom(label=key)]
        else:
            all_tags = [tag for tag in self.db.all_tags()]
        all_tags = list(set(all_tags))
        all_tags.sort(key=sort_key)
        for tag in all_tags:
            if tag not in tags:
                self.available_tags.addItem(tag)

        self.connect(self.apply_button,   SIGNAL('clicked()'), self.apply_tags)
        self.connect(self.unapply_button, SIGNAL('clicked()'), self.unapply_tags)
        self.connect(self.add_tag_button, SIGNAL('clicked()'), self.add_tag)
        self.connect(self.delete_button,  SIGNAL('clicked()'), self.delete_tags)
        self.connect(self.add_tag_input,  SIGNAL('returnPressed()'), self.add_tag)
        if islinux:
            self.available_tags.itemDoubleClicked.connect(self.apply_tags)
        else:
            self.connect(self.available_tags, SIGNAL('itemActivated(QListWidgetItem*)'), self.apply_tags)
        self.connect(self.applied_tags,   SIGNAL('itemActivated(QListWidgetItem*)'), self.unapply_tags)

        geom = gprefs.get('tag_editor_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)

    def delete_tags(self, item=None):
        confirms, deletes = [], []
        items = self.available_tags.selectedItems() if item is None else [item]
        if not items:
            error_dialog(self, 'No tags selected', 'You must select at least one tag from the list of Available tags.').exec_()
            return
        pos = self.available_tags.verticalScrollBar().value()
        for item in items:
            used = self.db.is_tag_used(unicode(item.text())) \
                if self.key is None else \
                self.db.is_item_used_in_multiple(unicode(item.text()), label=self.key)
            if used:
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
            if self.key is None:
                self.db.delete_tag(unicode(item.text()))
            else:
                bks = self.db.delete_item_from_multiple(unicode(item.text()),
                                                        label=self.key)
                self.db.refresh_ids(bks)
            self.available_tags.takeItem(self.available_tags.row(item))
        self.available_tags.verticalScrollBar().setValue(pos)

    def apply_tags(self, item=None):
        items = self.available_tags.selectedItems() if item is None else [item]
        rows = [self.available_tags.row(i) for i in items]
        row = max(rows)
        for item in items:
            tag = unicode(item.text())
            self.tags.append(tag)
            self.available_tags.takeItem(self.available_tags.row(item))

        self.tags.sort(key=sort_key)
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)

        if row >= self.available_tags.count():
            row = self.available_tags.count() - 1

        if row > 2:
            item = self.available_tags.item(row)
            self.available_tags.scrollToItem(item)

    def unapply_tags(self, item=None):
        items = self.applied_tags.selectedItems() if item is None else [item]
        for item in items:
            tag = unicode(item.text())
            self.tags.remove(tag)
            self.available_tags.addItem(tag)

        self.tags.sort(key=sort_key)
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)

        items = [unicode(self.available_tags.item(x).text()) for x in
                range(self.available_tags.count())]
        items.sort(key=sort_key)
        self.available_tags.clear()
        for item in items:
            self.available_tags.addItem(item)

    def add_tag(self):
        tags = unicode(self.add_tag_input.text()).split(',')
        for tag in tags:
            tag = tag.strip()
            if not tag:
                continue
            for item in self.available_tags.findItems(tag, Qt.MatchFixedString):
                self.available_tags.takeItem(self.available_tags.row(item))
            if tag not in self.tags:
                self.tags.append(tag)

        self.tags.sort(key=sort_key)
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)

        self.add_tag_input.setText('')

    def accept(self):
        self.save_state()
        return QDialog.accept(self)

    def reject(self):
        self.save_state()
        return QDialog.reject(self)

    def save_state(self):
        gprefs['tag_editor_geometry'] = bytearray(self.saveGeometry())

