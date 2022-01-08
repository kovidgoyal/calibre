#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time

from qt.core import QTimer, QDialog, QDialogButtonBox, QCheckBox, QVBoxLayout, QLabel, Qt

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.actions import InterfaceAction


class Choose(QDialog):

    def __init__(self, fmts, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)
        self.setWindowTitle(_('Choose format to edit'))

        self.la = la = QLabel(_(
            'This book has multiple formats that can be edited. Choose the format you want to edit.'))
        l.addWidget(la)

        self.rem = QCheckBox(_('Always ask when more than one format is available'))
        self.rem.setChecked(True)
        l.addWidget(self.rem)

        self.bb = bb = QDialogButtonBox(self)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.buts = buts = []
        for fmt in fmts:
            b = bb.addButton(fmt.upper(), QDialogButtonBox.ButtonRole.AcceptRole)
            b.setObjectName(fmt)
            connect_lambda(b.clicked, self, lambda self: self.chosen(self.sender().objectName()))
            buts.append(b)

        self.fmt = None
        self.resize(self.sizeHint())

    def chosen(self, fmt):
        self.fmt = fmt

    def accept(self):
        from calibre.gui2.tweak_book import tprefs
        tprefs['choose_tweak_fmt'] = self.rem.isChecked()
        QDialog.accept(self)


class TweakEpubAction(InterfaceAction):

    name = 'Tweak ePub'
    action_spec = (_('Edit book'), 'edit_book.png', _('Edit books in the EPUB or AZW formats'), _('T'))
    dont_add_to = frozenset(('context-menu-device',))
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
            self.dropped_ids = tuple(map(int, mime_data.data(mime).data().split()))
            QTimer.singleShot(1, self.do_drop)
            return True
        return False

    def do_drop(self):
        book_ids = self.dropped_ids
        del self.dropped_ids
        if book_ids:
            self.do_tweak(book_ids[0])

    def genesis(self):
        self.qaction.triggered.connect(self.tweak_book)

    def tweak_book(self):
        row = self.gui.library_view.currentIndex()
        if not row.isValid():
            return error_dialog(self.gui, _('Cannot Edit book'),
                    _('No book selected'), show=True)

        book_id = self.gui.library_view.model().id(row)
        self.do_tweak(book_id)

    def do_tweak(self, book_id):
        if self.gui.current_view() is not self.gui.library_view:
            return error_dialog(self.gui, _('Cannot edit book'), _(
                'Editing of books on the device is not supported'), show=True)
        from calibre.ebooks.oeb.polish.main import SUPPORTED
        db = self.gui.library_view.model().db
        fmts = db.formats(book_id, index_is_id=True) or ''
        fmts = [x.upper().strip() for x in fmts.split(',') if x]
        tweakable_fmts = set(fmts).intersection(SUPPORTED)
        if not tweakable_fmts:
            if not fmts:
                if not question_dialog(self.gui, _('No editable formats'),
                    _('Do you want to create an empty EPUB file to edit?')):
                    return
                tweakable_fmts = {'EPUB'}
                self.gui.iactions['Add Books'].add_empty_format_to_book(book_id, 'EPUB')
                current_idx = self.gui.library_view.currentIndex()
                if current_idx.isValid():
                    self.gui.library_view.model().current_changed(current_idx, current_idx)
            else:
                return error_dialog(self.gui, _('Cannot edit book'), _(
                    'The book must be in the %s formats to edit.'
                    '\n\nFirst convert the book to one of these formats.'
                ) % (_(' or ').join(SUPPORTED)), show=True)
        from calibre.gui2.tweak_book import tprefs
        tprefs.refresh()  # In case they were changed in a Tweak Book process
        if len(tweakable_fmts) > 1:
            if tprefs['choose_tweak_fmt']:
                d = Choose(sorted(tweakable_fmts, key=tprefs.defaults['tweak_fmt_order'].index), self.gui)
                if d.exec() != QDialog.DialogCode.Accepted:
                    return
                tweakable_fmts = {d.fmt}
            else:
                fmts = [f for f in tprefs['tweak_fmt_order'] if f in tweakable_fmts]
                if not fmts:
                    fmts = [f for f in tprefs.defaults['tweak_fmt_order'] if f in tweakable_fmts]
                tweakable_fmts = {fmts[0]}

        fmt = tuple(tweakable_fmts)[0]
        self.ebook_edit_format(book_id, fmt)

    def ebook_edit_format(self, book_id, fmt):
        '''
        Also called from edit_metadata formats list.  In that context,
        SUPPORTED check was already done.
        '''
        db = self.gui.library_view.model().db
        from calibre.gui2.tweak_book import tprefs
        tprefs.refresh()  # In case they were changed in a Tweak Book process
        path = db.new_api.format_abspath(book_id, fmt)
        if path is None:
            return error_dialog(self.gui, _('File missing'), _(
                'The %s format is missing from the calibre library. You should run'
                ' library maintenance.') % fmt, show=True)
        tweak = 'ebook-edit'
        try:
            self.gui.setCursor(Qt.CursorShape.BusyCursor)
            if tprefs['update_metadata_from_calibre']:
                db.new_api.embed_metadata((book_id,), only_fmts={fmt})
            notify = '%d:%s:%s:%s' % (book_id, fmt, db.library_id, db.library_path)
            self.gui.job_manager.launch_gui_app(tweak, kwargs=dict(path=path, notify=notify))
            time.sleep(2)
        finally:
            self.gui.unsetCursor()
