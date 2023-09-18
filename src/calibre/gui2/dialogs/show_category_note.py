#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import (
    QByteArray, QDialogButtonBox, QIcon, QSize, Qt, QTextDocument, QVBoxLayout,
)

from calibre.db.constants import RESOURCE_URL_SCHEME
from calibre.ebooks.metadata.book.render import render_author_link
from calibre.gui2 import Application, default_author_link
from calibre.gui2.book_details import resolved_css
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
        self.author_search_link = self.author_search_tooltip = ''
        if field == 'authors':
            lk = default_author_link()
            if lk != 'calibre':
                self.author_search_link, self.author_search_tooltip = render_author_link(lk, self.item_val)
        self.field, self.item_id = field, item_id
        super().__init__(self.item_val, 'show-notes-for-category', parent=parent)
        self.setWindowIcon(QIcon.ic('tag.png'))
        self.display.setHtml(self.db.notes_for(self.field, self.item_id))

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)

        self.display = d = Display(self)
        l.addWidget(d)

        self.bb.clear()
        self.bb.addButton(QDialogButtonBox.StandardButton.Close)
        l.addWidget(self.bb)

    def sizeHint(self):
        return QSize(800, 620)


def develop_show_note():
    from calibre.library import db as dbc
    app = Application([])
    d = ShowNoteDialog('authors', 1, dbc(os.path.expanduser('~/test library')))
    d.exec()
    del d, app


if __name__ == '__main__':
    develop_show_note()
