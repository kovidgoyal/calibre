#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import (
    QByteArray, QDialog, QDialogButtonBox, QIcon, QLabel, QSize, Qt, QTextDocument,
    QVBoxLayout,
)

from calibre import prepare_string_for_xml
from calibre.db.constants import RESOURCE_URL_SCHEME
from calibre.ebooks.metadata.book.render import render_author_link
from calibre.gui2 import Application, default_author_link, safe_open_url
from calibre.gui2.book_details import resolved_css
from calibre.gui2.dialogs.edit_category_notes import EditNoteDialog
from calibre.gui2.widgets2 import Dialog, HTMLDisplay


class Display(HTMLDisplay):
    notes_resource_scheme = RESOURCE_URL_SCHEME

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document().setDefaultStyleSheet(resolved_css() + '\n\nli { margin-top: 0.5ex; margin-bottom: 0.5ex; }')
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

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
        self.setWindowIcon(QIcon.ic('tag.png'))
        self.refresh()

    def refresh(self):
        self.display.setHtml(self.db.notes_for(self.field, self.item_id))

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)

        x = prepare_string_for_xml
        src = x(self.item_val)
        if self.item_link:
            src = f'<a href="{x(self.item_link, True)}">{src}</a>'
        if self.extra_link:
            link_markup = '<img valign="bottom" src="calibre-icon:///external-link.png" width=24 height=24>'
            src += f' <a style="text-decoration: none" href="{x(self.extra_link, True)}" title="{x(self.extra_link_tooltip, True)}">{link_markup}</a>'
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
        b.clicked.connect(self.edit)
        b.setToolTip(_('Edit this note'))
        l.addWidget(self.bb)

    def sizeHint(self):
        return QSize(800, 620)

    def open_item_link(self, url):
        safe_open_url(url)

    def edit(self):
        d = EditNoteDialog(self.field, self.item_id, self.db, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.refresh()


def develop_show_note():
    from calibre.library import db as dbc
    app = Application([])
    d = ShowNoteDialog('authors', 1, dbc(os.path.expanduser('~/test library')))
    d.exec()
    del d, app


if __name__ == '__main__':
    develop_show_note()
