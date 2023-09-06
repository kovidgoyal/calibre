#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import (
    QButtonGroup, QByteArray, QDialog, QFormLayout, QHBoxLayout, QIcon, QLabel,
    QLineEdit, QPixmap, QPushButton, QRadioButton, QSize, Qt, QTextFrameFormat,
    QTextImageFormat, QVBoxLayout, QWidget, pyqtSlot,
)
from typing import NamedTuple

from calibre.db.notes.connect import RESOURCE_URL_SCHEME, hash_data
from calibre.gui2 import Application, choose_images, error_dialog
from calibre.gui2.comments_editor import Editor, EditorWidget
from calibre.gui2.widgets import ImageView
from calibre.gui2.widgets2 import Dialog

IMAGE_EXTENSIONS = 'png', 'jpeg', 'jpg', 'gif', 'svg', 'webp'


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


# Images {{{
class ImageResource(NamedTuple):
    name: str
    digest: str
    path: str = ''
    data: bytes = b''
    from_db: bool = False


class AskImage(Dialog):

    def __init__(self, local_images, db, parent=None):
        self.local_images = local_images
        self.db = db
        self.current_digest = ''
        super().__init__(_('Insert image'), 'insert-image-for-notes', parent=parent)
        self.setWindowIcon(QIcon.ic('view-image.png'))

    def setup_ui(self):
        self.v = v = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        v.addLayout(h)
        v.addWidget(self.bb)

        self.image_preview = ip = ImageView(self, 'insert-image-for-notes-preview', True)
        ip.cover_changed.connect(self.image_pasted_or_dropped)
        h.addWidget(ip)

        self.vr = vr = QVBoxLayout()
        h.addLayout(vr)

        self.la = la = QLabel(_('Choose an image:'))
        vr.addWidget(la)

        self.name_edit = ne = QLineEdit(self)
        ne.setPlaceholderText(_('Filename for the image'))
        vr.addWidget(ne)

        self.la2 = la = QLabel(_('Place image:'))
        vr.addWidget(la)
        self.hr = hr = QHBoxLayout()
        vr.addLayout(hr)
        self.image_layout_group = bg = QButtonGroup(self)
        self.float_left = r = QRadioButton(_('Float &left'))
        bg.addButton(r), hr.addWidget(r)
        self.inline = r = QRadioButton(_('Inline'))
        bg.addButton(r), hr.addWidget(r)
        self.float_right = r = QRadioButton(_('Float &right'))
        bg.addButton(r), hr.addWidget(r)
        self.inline.setChecked(True)

        self.hb = hb = QHBoxLayout()
        vr.addLayout(hb)
        self.add_file_button = b = QPushButton(QIcon.ic('document_open.png'), _('Choose image &file'), self)
        b.clicked.connect(self.add_file)
        hb.addWidget(b)
        self.existing_button = b = QPushButton(QIcon.ic('view-image.png'), _('Browse &existing'), self)
        b.clicked.connect(self.browse_existing)
        hb.addWidget(b)
        self.paste_button = b = QPushButton(QIcon.ic('edit-paste.png'), _('&Paste from clipboard'), self)
        b.clicked.connect(self.paste_image)
        hb.addWidget(b)

        vr.addStretch(10)
        self.add_file_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def image_pasted_or_dropped(self, cover_data):
        digest = hash_data(cover_data)
        if digest in self.local_images:
            ir = self.local_images[digest]
        else:
            self.local_images[digest] = ir = ImageResource('unnamed.png', digest, data=cover_data)
        self.name_edit.setText(ir.name)
        self.current_digest = digest

    def browse_existing(self):
        raise NotImplementedError('TODO: Implement me')

    def add_file(self):
        files = choose_images(self, 'choose-image-for-notes', _('Choose image'), formats=IMAGE_EXTENSIONS)
        if files:
            with open(files[0], 'rb') as f:
                data = f.read()
            digest = hash_data(data)
            p = QPixmap()
            if not p.loadFromData(data) or p.isNull():
                return error_dialog(self, _('Bad image'), _(
                    'Failed to render the image in {}').format(files[0]), show=True)
            ir = ImageResource(os.path.basename(files[0]), digest, path=files[0])
            self.local_images[digest] = ir
            self.image_preview.set_pixmap(p)
            self.name_edit.setText(ir.name)
            self.current_digest = digest
            self.bb.setFocus(Qt.FocusReason.OtherFocusReason)

    def paste_image(self):
        if not self.image_preview.paste_from_clipboard():
            return error_dialog(self, _('Could not paste'), _(
                'No image is present int he system clipboard'), show=True)

    @property
    def image_layout(self) -> 'QTextFrameFormat.Position':
        b = self.image_layout_group.checkedButton()
        if b is self.inline:
            return QTextFrameFormat.Position.InFlow
        if b is self.float_left:
            return QTextFrameFormat.Position.FloatLeft
        return QTextFrameFormat.Position.FloatRight
# }}}



class NoteEditorWidget(EditorWidget):

    insert_images_separately = True
    db = field = item_id = item_val = None
    images = None

    @pyqtSlot(int, 'QUrl', result='QVariant')
    def loadResource(self, rtype, qurl):
        if self.db is None or self.images is None:
            return
        if qurl.scheme() != RESOURCE_URL_SCHEME:
            return
        digest = qurl.path()[1:]
        ir = self.images.get(digest)
        if ir is not None:
            if ir.data:
                return QByteArray(ir.data)
            if ir.path:
                with open(ir.path, 'rb') as f:
                    return QByteArray(f.read())

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

    def do_insert_image(self):
        d = AskImage(self.images, self.db)
        if d.exec() == QDialog.DialogCode.Accepted and d.current_digest:
            ir = self.images[d.current_digest]
            self.focus_self()
            c = self.textCursor()
            fmt = QTextImageFormat()
            fmt.setName(RESOURCE_URL_SCHEME + ':///' + ir.digest)
            c.insertImage(fmt, d.image_layout)


class NoteEditor(Editor):

    editor_class = NoteEditorWidget

    def get_doc(self):
        html = self.editor.html
        return html, self.editor.searchable_text, self.editor.referenced_resources



class EditNoteWidget(QWidget):

    def __init__(self, db, field, item_id, item_val, parent=None):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.editor = e = NoteEditor(self, toolbar_prefs_name='edit-notes-for-category-ce')
        e.editor.db, e.editor.field, e.editor.item_id, e.editor.item_val = db, field, item_id, item_val
        e.editor.images = {}
        l.addWidget(e)
        e.html = db.notes_for(field, item_id) or ''

    def sizeHint(self):
        return QSize(800, 600)

    def commit(self):
        doc, searchable_text, resources = self.editor.get_doc()
        s = self.editor.editor
        s.db.set_notes_for(s.field, s.item_id, doc, searchable_text, resources)
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


def develop_edit_note():
    from calibre.library import db as dbc
    app = Application([])
    d = EditNoteDialog('authors', 1, dbc(os.path.expanduser('~/test library')))
    d.exec()
    del d, app


def develop_ask_image():
    app = Application([])
    from calibre.library import db as dbc
    d = AskImage({},dbc(os.path.expanduser('~/test library')))
    d.exec()
    del d, app


if __name__ == '__main__':
    develop_edit_note()
    # develop_ask_image()
