#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import (
    QDialog, QFormLayout, QIcon, QLineEdit, QSize, Qt, QVBoxLayout, QWidget, pyqtSlot,
)

from calibre.gui2 import Application
from calibre.gui2.comments_editor import Editor, EditorWidget
from calibre.gui2.widgets2 import Dialog


class AskLink(Dialog):  # {{{

    def __init__(self, initial_name='', parent=None):
        super().__init__(_('Create link'), 'create-link-for-notes', parent=parent)
        self.setWindowIcon(QIcon.ic('insert-link.png'))
        if initial_name:
            self.name_edit.setText(initial_name)

    def setup_ui(self):
        self.v = v = QVBoxLayout(self)
        self.f = f = QFormLayout()
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        v.addLayout(f)
        v.addWidget(self.bb)

        self.url_edit = u = QLineEdit(self)
        u.setPlaceholderText(_('The URL for this link'))
        u.setMinimumWidth(400)
        f.addRow(_('&URL:'), u)

        self.name_edit = n = QLineEdit(self)
        n.setPlaceholderText(_('The name (optional) for this link'))
        f.addRow(_('&Name:'), n)

        self.url_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    @property
    def link_name(self):
        return self.name_edit.text().strip()

    @property
    def url(self):
        return self.url_edit.text().strip()
# }}}


class NoteEditorWidget(EditorWidget):

    load_resource = None
    insert_images_separately = True

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

    @pyqtSlot(int, 'QUrl', result='QVariant')
    def loadResource(self, rtype, qurl):
        if self.load_resource is not None:
            return self.load_resource(rtype, qurl)

    def get_html_callback(self, root):
        self.searchable_text = ''
        self.referenced_resources = set()

    def ask_link(self):
        c = self.textCursor()
        selected_text = c.selection().toPlainText().replace('\n', ' ')
        d = AskLink(selected_text, parent=self)
        if d.exec() == QDialog.DialogCode.Accepted:
            return d.url, d.link_name, False
        return '', '', False


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

    def sizeHint(self):
        return QSize(800, 620)

    def accept(self):
        if self.edit_note_widget.commit():
            super().accept()


if __name__ == '__main__':
    from calibre.library import db as dbc
    app = Application([])
    d = EditNoteDialog('authors', 1, dbc(os.path.expanduser('~/test library')))
    d.exec()
    del d, app
