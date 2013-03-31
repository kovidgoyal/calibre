#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict

from PyQt4.Qt import (QTimer, QDialog, QGridLayout, QCheckBox, QLabel,
                      QDialogButtonBox, QIcon)

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction

SUPPORTED = {'EPUB', 'AZW3'}

class ChooseFormat(QDialog): # {{{

    def __init__(self, formats, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Choose format to edit'))
        self.setWindowIcon(QIcon(I('dialog_question.png')))
        l = self.l = QGridLayout()
        self.setLayout(l)
        la = self.la = QLabel(_('Choose which format you want to edit:'))
        formats = sorted(formats)
        l.addWidget(la, 0, 0, 1, -1)
        self.buttons = []
        for i, f in enumerate(formats):
            b = QCheckBox('&' + f, self)
            l.addWidget(b, 1, i)
            self.buttons.append(b)
            if i == 0:
                b.setChecked(True)
        bb = self.bb = QDialogButtonBox(
            QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.addButton(_('&All formats'),
                     bb.ActionRole).clicked.connect(self.do_all)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, l.rowCount(), 0, 1, -1)
        self.resize(self.sizeHint())

    def do_all(self):
        for b in self.buttons:
            b.setChecked(True)
        self.accept()

    @property
    def formats(self):
        for b in self.buttons:
            if b.isChecked():
                yield unicode(b.text())[1:]
# }}}

class ToCEditAction(InterfaceAction):

    name = 'Edit ToC'
    action_spec = (_('Edit ToC'), 'toc.png',
                   _('Edit the Table of Contents in your books'), _('K'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'
    accepts_drops = True

    def accept_enter_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def accept_drag_move_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def drop_event(self, event, mime_data):
        mime = 'application/calibre+from_library'
        if mime_data.hasFormat(mime):
            self.dropped_ids = tuple(map(int, str(mime_data.data(mime)).split()))
            QTimer.singleShot(1, self.do_drop)
            return True
        return False

    def do_drop(self):
        book_id_map = self.get_supported_books(self.dropped_ids)
        del self.dropped_ids
        if book_id_map:
            self.do_edit(book_id_map)

    def genesis(self):
        self.qaction.triggered.connect(self.edit_books)

    def get_supported_books(self, book_ids):
        db = self.gui.library_view.model().db
        supported = set(SUPPORTED)
        ans = [(x, set( (db.formats(x, index_is_id=True) or '').split(',') )
               .intersection(supported)) for x in book_ids]
        ans = [x for x in ans if x[1]]
        if not ans:
            error_dialog(self.gui, _('Cannot edit ToC'),
                _('Editing Table of Contents is only supported for books in the %s'
                  ' formats. Convert to one of those formats before polishing.')
                         %_(' or ').join(sorted(supported)), show=True)
        ans = OrderedDict(ans)
        return ans

    def get_books_for_editing(self):
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot edit ToC'),
                    _('No books selected'))
            d.exec_()
            return None
        db = self.gui.current_db
        ans = (db.id(r) for r in rows)
        return self.get_supported_books(ans)

    def do_edit(self, book_id_map):
        for book_id, fmts in book_id_map.iteritems():
            if len(fmts) > 1:
                d = ChooseFormat(fmts, self.gui)
                if d.exec_() != d.Accepted:
                    return
                fmts = d.formats
            for fmt in fmts:
                self.do_one(book_id, fmt)

    def do_one(self, book_id, fmt):
        from calibre.gui2.toc.main import TOCEditor
        db = self.gui.current_db
        path = db.format(book_id, fmt, index_is_id=True, as_path=True)
        title = db.title(book_id, index_is_id=True) + ' [%s]'%fmt
        d = TOCEditor(path, title=title, parent=self.gui)
        d.start()
        if d.exec_() == d.Accepted:
            with open(path, 'rb') as f:
                db.add_format(book_id, fmt, f, index_is_id=True)

    def edit_books(self):
        book_id_map = self.get_books_for_editing()
        if not book_id_map:
            return
        self.do_edit(book_id_map)


