#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import (
    QApplication, QByteArray, QDialog, QDialogButtonBox, QIcon, QLabel, QMimeData,
    QSize, Qt, QTextDocument, QUrl, QVBoxLayout,
)

from calibre import prepare_string_for_xml
from calibre.db.constants import RESOURCE_URL_SCHEME
from calibre.ebooks.metadata.book.render import render_author_link
from calibre.gui2 import Application, default_author_link, safe_open_url
from calibre.gui2.book_details import resolved_css
from calibre.gui2.dialogs.edit_category_notes import EditNoteDialog
from calibre.gui2.ui import get_gui
from calibre.gui2.widgets2 import Dialog, HTMLDisplay


class Display(HTMLDisplay):
    notes_resource_scheme = RESOURCE_URL_SCHEME

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document().setDefaultStyleSheet(resolved_css() + '\n\nli { margin-top: 0.5ex; margin-bottom: 0.5ex; }')
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.anchor_clicked.connect(self.handle_link_click)

    def handle_link_click(self, qurl):
        safe_open_url(qurl)

    def loadResource(self, rtype, qurl):
        if qurl.scheme() == RESOURCE_URL_SCHEME and int(rtype) == int(QTextDocument.ResourceType.ImageResource):
            db = self.parent().db
            resource = db.get_notes_resource(f'{qurl.host()}:{qurl.path()[1:]}')
            if resource is not None:
                return QByteArray(resource['data'])
            return
        return super().loadResource(rtype, qurl)


class ShowNoteDialog(Dialog):

    def __init__(self, field, item_id, db, parent=None):
        self.db = db.new_api
        self.item_val = self.db.get_item_name(field, item_id)
        self.has_links = self.db.has_link_map(field)
        self.item_link = (self.db.link_for(field, item_id) or '') if self.has_links else ''
        self.extra_link = self.extra_link_tooltip = ''
        if field == 'authors':
            lk = default_author_link()
            if lk != 'calibre':
                self.extra_link, self.extra_link_tooltip = render_author_link(lk, self.item_val)
        self.field, self.item_id = field, item_id
        super().__init__(self.item_val, 'show-notes-for-category', parent=parent)
        self.setWindowIcon(QIcon.ic('notes.png'))
        self.refresh()

    def refresh(self):
        self.display.setHtml(self.db.notes_for(self.field, self.item_id))

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)

        x = prepare_string_for_xml
        src = x(self.item_val)
        l1 = l2 = l1tt = l2tt = ''
        if self.extra_link and self.item_link:
            l1 = self.extra_link
            l1tt = self.extra_link_tooltip
            l2 = self.item_link
        else:
            if self.item_link:
                l1 = self.item_link
            else:
                l2, l2tt = self.extra_link, self.extra_link_tooltip
        if l1:
            src = f'<a href="{x(l1, True)}" style="text-decoration: none" title="{x(l1tt, True)}">{src}</a>'
        if l2:
            link_markup = '<img valign="bottom" src="calibre-icon:///external-link.png" width=24 height=24>'
            src += f' <a style="text-decoration: none" href="{x(l2, True)}" title="{x(l2tt, True)}">{link_markup}</a>'
        self.title = t = QLabel(f'<h2>{src}</h2>')
        t.setResourceProvider(lambda qurl: QIcon.icon_as_png(qurl.path().lstrip('/'), as_bytearray=True))
        t.setOpenExternalLinks(False)
        t.linkActivated.connect(self.open_item_link)
        l.addWidget(t)

        self.display = d = Display(self)
        l.addWidget(d)

        self.bb.clear()
        self.bb.addButton(QDialogButtonBox.StandardButton.Close)
        b = self.bb.addButton(_('&Edit'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('edit_input.png'))
        b.clicked.connect(self.edit)
        b.setToolTip(_('Edit this note'))
        b = self.bb.addButton(_('Find &books'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('search.png'))
        b.clicked.connect(self.find_books)
        if self.field == 'authors':
            b.setToolTip(_('Search the calibre library for books by: {}').format(self.item_val))
        else:
            b.setToolTip(_('Search the calibre library for books with: {}').format(self.item_val))
        b = self.bb.addButton(_('Copy &URL'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('insert-link.png'))
        b.clicked.connect(self.copy_url)
        b.setToolTip(_('Copy a calibre:// URL to the clipboard that can be used to link to this note from other programs'))

        l.addWidget(self.bb)

    def sizeHint(self):
        return QSize(800, 620)

    def open_item_link(self, url):
        safe_open_url(url)

    def copy_url(self):
        f = self.field
        if f.startswith('#'):
            f = '_' + f[1:]
        url = f'calibre://show-note/{self.db.server_library_id}/{f}/id_{self.item_id}'
        cb = QApplication.instance().clipboard()
        md = QMimeData()
        md.setText(url)
        md.setUrls([QUrl(url)])
        cb.setMimeData(md)

    def edit(self):
        d = EditNoteDialog(self.field, self.item_id, self.db, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            # Tell the rest of calibre that the note has changed
            gui = get_gui()
            if gui is not None:
                gui.do_field_item_value_changed()
            self.refresh()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def find_books(self):
        q = self.item_val.replace('"', r'\"')
        search_string = f'{self.field}:"={q}"'
        gui = get_gui()
        if gui is not None:
            gui.apply_virtual_library()
            gui.search.set_search_string(search_string)


def develop_show_note():
    from calibre.library import db as dbc
    app = Application([])
    d = ShowNoteDialog('authors', 1, dbc(os.path.expanduser('~/test library')))
    d.exec()
    del d, app


if __name__ == '__main__':
    develop_show_note()
