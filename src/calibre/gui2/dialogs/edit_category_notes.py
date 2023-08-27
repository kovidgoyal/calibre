#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QIcon, QSize, QVBoxLayout, QWidget, pyqtSlot

from calibre.gui2.comments_editor import Editor, EditorWidget
from calibre.gui2.widgets2 import Dialog


class NoteEditorWidget(EditorWidget):

    load_resource = None

    @pyqtSlot(int, 'QUrl', result='QVariant')
    def loadResource(self, rtype, qurl):
        if self.load_resource is not None:
            return self.load_resource(rtype, qurl)

    def get_html_callback(self, root):
        self.searchable_text = ''
        self.referenced_resources = set()



class NoteEditor(Editor):
    editor_class = NoteEditorWidget

    def get_doc(self):
        html = self.editor.html
        return html, self.editor.searchable_text, self.editor.referenced_resources



class EditNoteWidget(QWidget):

    def __init__(self, db, field, item_id, item_val, parent=None):
        super().__init__(parent)
        self.db, self.field, self.item_id, self.item_val = db, field, item_id, item_val
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.editor = e = NoteEditor(self, toolbar_prefs_name='edit-notes-for-category-ce')
        e.editor.load_resource = self.load_resource
        l.addWidget(e)
        e.html = self.db.notes_for(field, item_id) or ''

    def load_resource(self, resource_type, qurl):
        pass

    def sizeHint(self):
        return QSize(800, 600)

    def commit(self):
        doc, searchable_text, resources = self.editor.get_doc()
        self.db.set_notes_for(self.field, self.item_id, doc, searchable_text, resources, remove_unused_resources=True)
        return True


class EditNoteDialog(Dialog):

    def __init__(self, field, item_id, db, parent=None):
        self.db = db.new_api
        self.field, self.item_id = field, item_id
        self.item_val = self.db.get_item_name(field, item_id)
        super().__init__(_('Edit notes for {}').format(self.item_val), 'edit-notes-for-category', parent=parent)
        self.setWindowIcon(QIcon.ic('edit_input.png'))

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.edit_note_widget = EditNoteWidget(self.db, self.field, self.item_id, self.item_val, self)
        l.addWidget(self.edit_note_widget)
        l.addWidget(self.bb)

    def accept(self):
        if self.edit_note_widget.commit():
            super().accept()
