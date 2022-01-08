#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from itertools import count
from collections import OrderedDict
from qt.core import (
    QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QIcon, QLabel, QTimer
)

from calibre.gui2 import error_dialog, gprefs, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.utils.monotonic import monotonic
from polyglot.builtins import iteritems

SUPPORTED = {'EPUB', 'AZW3'}


class ChooseFormat(QDialog):  # {{{

    def __init__(self, formats, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Choose format to edit'))
        self.setWindowIcon(QIcon.ic('dialog_question.png'))
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
            QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.addButton(_('&All formats'),
                     QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.do_all)
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
                yield str(b.text())[1:]

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
        self.shm_count = count()
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
        if len(ans) > 5:
            if not question_dialog(self.gui, _('Are you sure?'), _(
                'You have chosen to edit the Table of Contents of {} books at once.'
                ' Doing so will likely slow your computer to a crawl. Are you sure?'
            ).format(len(ans))):
                return
        return ans

    def get_books_for_editing(self):
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot edit ToC'),
                    _('No books selected'))
            d.exec()
            return None
        db = self.gui.current_db
        ans = (db.id(r) for r in rows)
        return self.get_supported_books(ans)

    def do_edit(self, book_id_map):
        for book_id, fmts in iteritems(book_id_map):
            if len(fmts) > 1:
                d = ChooseFormat(fmts, self.gui)
                if d.exec() != QDialog.DialogCode.Accepted:
                    return
                fmts = d.formats
            for fmt in fmts:
                self.do_one(book_id, fmt)

    def do_one(self, book_id, fmt):
        import struct, json, atexit
        from calibre.utils.shm import SharedMemory
        db = self.gui.current_db
        path = db.format(book_id, fmt, index_is_id=True, as_path=True)
        title = db.title(book_id, index_is_id=True) + ' [%s]'%fmt
        job = {'path': path, 'title': title}
        data = json.dumps(job).encode('utf-8')
        header = struct.pack('>II', 0, 0)
        shm = SharedMemory(prefix=f'c{os.getpid()}-{next(self.shm_count)}-', size=len(data) + len(header) + SharedMemory.num_bytes_for_size)
        shm.write(header)
        shm.write_data_with_size(data)
        shm.flush()
        atexit.register(shm.close)
        self.gui.job_manager.launch_gui_app('toc-dialog', kwargs={'shm_name': shm.name})
        job.update({
            'book_id': book_id, 'fmt': fmt, 'library_id': db.new_api.library_id, 'shm': shm, 'started': False, 'start_time': monotonic()})
        self.jobs.append(job)
        self.check_for_completions()

    def check_for_completions(self):
        import struct

        def remove_job(job):
            job['shm'].close()
            self.jobs.remove(job)

        for job in tuple(self.jobs):
            path = job['path']
            shm = job['shm']
            shm.seek(0)
            state, ok = struct.unpack('>II', shm.read(struct.calcsize('>II')))
            if state == 0:
                # not started
                if monotonic() - job['start_time'] > 120:
                    remove_job(job)
                    error_dialog(self.gui, _('Failed to start editor'), _(
                        'Could not edit: {}. The Table of Contents editor did not start in two minutes').format(job['title']), show=True)
            elif state == 1:
                # running
                pass
            elif state == 2:
                # finished
                job['shm'].already_unlinked = True
                remove_job(job)
                if ok == 1:
                    db = self.gui.current_db
                    if db.new_api.library_id != job['library_id']:
                        error_dialog(self.gui, _('Library changed'), _(
                            'Cannot save changes made to {0} by the ToC editor as'
                            ' the calibre library has changed.').format(job['title']), show=True)
                    else:
                        db.new_api.add_format(job['book_id'], job['fmt'], path, run_hooks=False)
        if self.jobs:
            QTimer.singleShot(100, self.check_for_completions)

    def edit_books(self):
        book_id_map = self.get_books_for_editing()
        if not book_id_map:
            return
        self.do_edit(book_id_map)
