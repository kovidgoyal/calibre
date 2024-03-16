#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
from qt.core import (
    QButtonGroup, QByteArray, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QIcon, QLabel, QLineEdit, QPixmap, QPushButton, QRadioButton, QSize, QSpinBox, Qt,
    QTextDocument, QTextFrameFormat, QTextImageFormat, QUrl, QVBoxLayout, QWidget,
    pyqtSlot,
)
from typing import NamedTuple

from calibre import sanitize_file_name, fit_image
from calibre.db.constants import RESOURCE_URL_SCHEME
from calibre.db.notes.connect import hash_data
from calibre.db.notes.exim import export_note, import_note
from calibre.gui2 import (
    Application, choose_files, choose_images, choose_save_file, error_dialog,
)
from calibre.gui2.comments_editor import OBJECT_REPLACEMENT_CHAR, Editor, EditorWidget
from calibre.gui2.widgets import ImageView
from calibre.gui2.widgets2 import Dialog
from calibre.utils.short_uuid import uuid4

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
        ip.draw_empty_border = True
        h.addWidget(ip)

        self.vr = vr = QVBoxLayout()
        h.addLayout(vr)

        self.la = la = QLabel(_('Choose an image:'))
        vr.addWidget(la)

        self.name_edit = ne = QLineEdit(self)
        ne.setPlaceholderText(_('Filename for the image'))
        vr.addWidget(ne)

        self.hb = hb = QHBoxLayout()
        vr.addLayout(hb)
        self.add_file_button = b = QPushButton(QIcon.ic('document_open.png'), _('Choose image &file'), self)
        b.clicked.connect(self.add_file)
        hb.addWidget(b)
        self.paste_button = b = QPushButton(QIcon.ic('edit-paste.png'), _('&Paste from clipboard'), self)
        b.clicked.connect(self.paste_image)
        hb.addWidget(b)

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

        self.la2 = la = QLabel(_('Shrink image to fit within:'))
        vr.addWidget(la)
        self.hr2 = h = QHBoxLayout()
        vr.addLayout(h)
        la = QLabel(_('&Width:'))
        h.addWidget(la)
        self.width = w = QSpinBox(self)
        w.setRange(0, 10000), w.setSuffix(' px')
        h.addWidget(w), la.setBuddy(w)
        w.setSpecialValueText(' ')
        la = QLabel(_('&Height:'))
        h.addWidget(la)
        self.height = w = QSpinBox(self)
        w.setRange(0, 10000), w.setSuffix(' px')
        h.addWidget(w), la.setBuddy(w)
        w.setSpecialValueText(' ')
        h.addStretch(10)

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
                'No image is present in the system clipboard'), show=True)

    @property
    def image_layout(self) -> 'QTextFrameFormat.Position':
        b = self.image_layout_group.checkedButton()
        if b is self.inline:
            return QTextFrameFormat.Position.InFlow
        if b is self.float_left:
            return QTextFrameFormat.Position.FloatLeft
        return QTextFrameFormat.Position.FloatRight

    @property
    def image_size(self) -> tuple[int, int]:
        s = self.image_preview.pixmap().size()
        return s.width(), s.height()

    @property
    def bounding_size(self) -> tuple[int, int]:
        return (self.width.value() or sys.maxsize), (self.height.value() or sys.maxsize)
# }}}



class NoteEditorWidget(EditorWidget):

    insert_images_separately = True
    db = field = item_id = item_val = None
    images = None
    can_store_images = True

    def resource_digest_from_qurl(self, qurl):
        alg = qurl.host()
        digest = qurl.path()[1:]
        return f'{alg}:{digest}'

    def get_resource(self, digest):
        ir = self.images.get(digest)
        if ir is not None:
            if ir.data:
                return {'name': ir.name, 'data': ir.data}
            elif ir.path:
                with open(ir.path, 'rb') as f:
                    return {'name': ir.name, 'data': f.read()}
        return self.db.get_notes_resource(digest)

    def add_resource(self, path_or_data, name):
        if isinstance(path_or_data, str):
            with open(path_or_data, 'rb') as f:
                data = f.read()
        else:
            data = path_or_data
        digest = hash_data(data)
        ir = ImageResource(name, digest, data=data)
        self.images[digest] = ir
        return digest

    @pyqtSlot(int, 'QUrl', result='QVariant')
    def loadResource(self, rtype, qurl):
        if self.db is None or self.images is None or qurl.scheme() != RESOURCE_URL_SCHEME or int(rtype) != int(QTextDocument.ResourceType.ImageResource):
            return
        digest = self.resource_digest_from_qurl(qurl)
        ans = self.get_resource(digest)
        if ans is not None:
            r = QByteArray(ans['data'])
            self.document().addResource(rtype, qurl, r)  # cache the resource
            return r

    def commit_downloaded_image(self, data, suggested_filename):
        digest = hash_data(data)
        if digest in self.images:
            ir = self.images[digest]
        else:
            self.images[digest] = ir = ImageResource(suggested_filename, digest, data=data)
        alg, digest = ir.digest.split(':', 1)
        return RESOURCE_URL_SCHEME + f'://{alg}/{digest}?placement={uuid4()}'

    def get_html_callback(self, root, text):
        self.searchable_text = text.replace(OBJECT_REPLACEMENT_CHAR, '')
        self.referenced_resources = set()
        for fmt in self.document().allFormats():
            if fmt.isImageFormat():
                qurl = QUrl(fmt.toImageFormat().name())
                if qurl.scheme() == RESOURCE_URL_SCHEME:
                    digest = self.resource_digest_from_qurl(qurl)
                    self.referenced_resources.add(digest)

    def ask_link(self):
        c = self.textCursor()
        selected_text = c.selection().toPlainText().replace('\n', ' ')
        d = AskLink(selected_text, parent=self)
        if d.exec() == QDialog.DialogCode.Accepted:
            return d.url, d.link_name, False
        return '', '', False

    def do_insert_image(self):
        # See https://bugreports.qt.io/browse/QTBUG-118537
        # for why we cant have a nice margin for floating images
        d = AskImage(self.images, self.db)
        if d.exec() == QDialog.DialogCode.Accepted and d.current_digest:
            ir = self.images[d.current_digest]
            self.focus_self()
            c = self.textCursor()
            fmt = QTextImageFormat()
            alg, digest = ir.digest.split(':', 1)
            fmt.setName(RESOURCE_URL_SCHEME + f'://{alg}/{digest}?placement={uuid4()}')
            page_width, page_height = d.bounding_size
            w, h = d.image_size
            resized, nw, nh = fit_image(w, h, page_width, page_height)
            if resized:
                fmt.setWidth(nw)
                fmt.setHeight(nh)
            c.insertImage(fmt, d.image_layout)


class NoteEditor(Editor):

    editor_class = NoteEditorWidget

    def get_doc(self):
        self.editor.referenced_resources = set()
        self.editor.searchable_text = ''
        idx = self.tabs.currentIndex()
        self.tabs.setCurrentIndex(0)
        html = self.editor.html
        self.tabs.setCurrentIndex(idx)
        return html, self.editor.searchable_text, self.editor.referenced_resources, self.editor.images.values()

    def export_note(self):
        html = self.get_doc()[0]
        return export_note(html, self.editor.get_resource)

    def import_note(self, path_to_html_file):
        self.editor.images = {}
        self.editor.setPlainText('')
        with open(path_to_html_file, 'rb') as f:
            html, _, _ = import_note(f.read(), os.path.dirname(os.path.abspath(path_to_html_file)), self.editor.add_resource)
        self.editor.html = html


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
        doc, searchable_text, resources, resources_to_add = self.editor.get_doc()
        s = self.editor.editor
        for ir in resources_to_add:
            s.db.add_notes_resource(ir.data or ir.path, ir.name)
        s.db.set_notes_for(s.field, s.item_id, doc, searchable_text, resources)
        return True


class EditNoteDialog(Dialog):

    def __init__(self, field, item_id, db, parent=None):
        self.db = db.new_api
        self.field, self.item_id = field, item_id
        self.item_val = self.db.get_item_name(field, item_id)
        super().__init__(_('Edit notes for {}').format(self.item_val), 'edit-notes-for-category', parent=parent)
        self.setWindowIcon(QIcon.ic('notes.png'))

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.edit_note_widget = EditNoteWidget(self.db, self.field, self.item_id, self.item_val, self)
        l.addWidget(self.edit_note_widget)
        self.bb.addButton(_('E&xport'), QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.export_note)
        self.bb.addButton(_('&Import'), QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.import_note)

        l.addWidget(self.bb)

    def export_note(self):
        dest = choose_save_file(self, 'save-exported-note', _('Export note to a file'), filters=[(_('HTML files'), ['html'])],
                         initial_filename=f'{sanitize_file_name(self.item_val)}.html', all_files=False)
        if dest:
            html = self.edit_note_widget.editor.export_note()
            with open(dest, 'wb') as f:
                f.write(html.encode('utf-8'))

    def import_note(self):
        dest = choose_files(self, 'load-imported-note', _('Import note from a file'), filters=[(_('HTML files'), ['html'])],
                            all_files=False, select_only_single_file=True)
        if dest:
            self.edit_note_widget.editor.import_note(dest[0])

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
