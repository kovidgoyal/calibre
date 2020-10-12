#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from collections import OrderedDict

from PyQt5.Qt import (QTimer, QDialog, QGridLayout, QCheckBox, QLabel,
                      QDialogButtonBox, QIcon)

from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.actions import InterfaceAction
from calibre.utils.monotonic import monotonic
from polyglot.builtins import iteritems, unicode_type

SUPPORTED = {'EPUB', 'AZW3'}


class ChooseFormat(QDialog):  # {{{

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
        self.formats = gprefs.get('edit_toc_last_selected_formats', ['EPUB',])
        bb = self.bb = QDialogButtonBox(
            QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.addButton(_('&All formats'),
                     bb.ActionRole).clicked.connect(self.do_all)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, l.rowCount(), 0, 1, -1)
        self.resize(self.sizeHint())
        connect_lambda(self.finished, self, lambda self, code:gprefs.set('edit_toc_last_selected_formats', list(self.formats)))

    def do_all(self):
        for b in self.buttons:
            b.setChecked(True)
        self.accept()

    @property
    def formats(self):
        for b in self.buttons:
            if b.isChecked():
                yield unicode_type(b.text())[1:]

    @formats.setter
    def formats(self, formats):
        formats = {x.upper() for x in formats}
        for b in self.buttons:
            b.setChecked(b.text()[1:] in formats)

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
            self.dropped_ids = tuple(map(int, mime_data.data(mime).data().split()))
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
        self.jobs = []

    def get_supported_books(self, book_ids):
        db = self.gui.library_view.model().db
        supported = set(SUPPORTED)
        ans = [(x, set((db.formats(x, index_is_id=True) or '').split(','))
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
        for book_id, fmts in iteritems(book_id_map):
            if len(fmts) > 1:
                d = ChooseFormat(fmts, self.gui)
                if d.exec_() != d.Accepted:
                    return
                fmts = d.formats
            for fmt in fmts:
                self.do_one(book_id, fmt)

    def do_one(self, book_id, fmt):
        db = self.gui.current_db
        path = db.format(book_id, fmt, index_is_id=True, as_path=True)
        title = db.title(book_id, index_is_id=True) + ' [%s]'%fmt
        data = {'path': path, 'title': title}
        self.gui.job_manager.launch_gui_app('toc-dialog', kwargs=data)
        job = data.copy()
        job.update({'book_id': book_id, 'fmt': fmt, 'library_id': db.new_api.library_id, 'started': False, 'start_time': monotonic()})
        self.jobs.append(job)
        self.check_for_completions()

    def check_for_completions(self):
        from calibre.utils.lock import lock_file
        for job in tuple(self.jobs):
            lock_path = job['path'] + '.lock'
            if job['started']:
                if not os.path.exists(lock_path):
                    self.jobs.remove(job)
                    continue
                try:
                    lf = lock_file(lock_path, timeout=0.01, sleep_time=0.005)
                except EnvironmentError:
                    continue
                else:
                    self.jobs.remove(job)
                    ret = int(lf.read().decode('ascii'))
                    lf.close()
                    os.remove(lock_path)
                    if ret == 0:
                        db = self.gui.current_db
                        if db.new_api.library_id != job['library_id']:
                            error_dialog(self.gui, _('Library changed'), _(
                                'Cannot save changes made to {0} by the ToC editor as'
                                ' the calibre library has changed.').format(job['title']), show=True)
                        else:
                            db.new_api.add_format(job['book_id'], job['fmt'], job['path'], run_hooks=False)
                    os.remove(job['path'])
            else:
                if monotonic() - job['start_time'] > 10:
                    self.jobs.remove(job)
                    continue
                if os.path.exists(lock_path):
                    job['started'] = True
        if self.jobs:
            QTimer.singleShot(100, self.check_for_completions)

    def edit_books(self):
        book_id_map = self.get_books_for_editing()
        if not book_id_map:
            return
        self.do_edit(book_id_map)
