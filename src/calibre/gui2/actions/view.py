#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time
from functools import partial

from PyQt4.Qt import Qt, QMenu

from calibre.constants import isosx
from calibre.gui2 import error_dialog, Dispatcher, question_dialog, config, \
        open_local_file, info_dialog
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.utils.config import prefs
from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2.actions import InterfaceAction

class ViewAction(InterfaceAction):

    name = 'View'
    action_spec = (_('View'), 'view.png', None, _('V'))
    action_type = 'current'

    def genesis(self):
        self.persistent_files = []
        self.qaction.triggered.connect(self.view_book)
        self.view_menu = QMenu()
        self.view_menu.addAction(_('View'), partial(self.view_book, False))
        ac = self.view_menu.addAction(_('View specific format'))
        ac.setShortcut((Qt.ControlModifier if isosx else Qt.AltModifier)+Qt.Key_V)
        self.qaction.setMenu(self.view_menu)
        ac.triggered.connect(self.view_specific_format, type=Qt.QueuedConnection)

    def location_selected(self, loc):
        enabled = loc == 'library'
        for action in list(self.view_menu.actions())[1:]:
            action.setEnabled(enabled)

    def view_format(self, row, format):
        fmt_path = self.gui.library_view.model().db.format_abspath(row, format)
        if fmt_path:
            self._view_file(fmt_path)

    def view_format_by_id(self, id_, format):
        fmt_path = self.gui.library_view.model().db.format_abspath(id_, format,
                index_is_id=True)
        if fmt_path:
            self._view_file(fmt_path)

    def book_downloaded_for_viewing(self, job):
        if job.failed:
            self.gui.device_job_exception(job)
            return
        self._view_file(job.result)

    def _launch_viewer(self, name=None, viewer='ebook-viewer', internal=True):
        self.gui.setCursor(Qt.BusyCursor)
        try:
            if internal:
                args = [viewer]
                if isosx and 'ebook' in viewer:
                    args.append('--raise-window')
                if name is not None:
                    args.append(name)
                self.gui.job_manager.launch_gui_app(viewer,
                        kwargs=dict(args=args))
            else:
                open_local_file(name)
                time.sleep(2) # User feedback
        finally:
            self.gui.unsetCursor()

    def _view_file(self, name):
        ext = os.path.splitext(name)[1].upper().replace('.', '')
        viewer = 'lrfviewer' if ext == 'LRF' else 'ebook-viewer'
        internal = ext in config['internally_viewed_formats']
        self._launch_viewer(name, viewer, internal)

    def view_specific_format(self, triggered):
        rows = list(self.gui.library_view.selectionModel().selectedRows())
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot view'), _('No book selected'))
            d.exec_()
            return

        db = self.gui.library_view.model().db
        rows = [r.row() for r in rows]
        formats = [db.formats(row) for row in rows]
        formats = [list(f.upper().split(',')) if f else None for f in formats]
        all_fmts = set([])
        for x in formats:
            for f in x: all_fmts.add(f)
        d = ChooseFormatDialog(self.gui, _('Choose the format to view'),
                list(sorted(all_fmts)))
        if d.exec_() == d.Accepted:
            fmt = d.format()
            orig_num = len(rows)
            rows = [rows[i] for i in range(len(rows)) if formats[i] and fmt in
                    formats[i]]
            if self._view_check(len(rows)):
                for row in rows:
                    self.view_format(row, fmt)
                if len(rows) < orig_num:
                    info_dialog(self.gui, _('Format unavailable'),
                            _('Not all the selected books were available in'
                                ' the %s format. You should convert'
                                ' them first.')%fmt, show=True)

    def _view_check(self, num, max_=3):
        if num <= max_:
            return True
        return question_dialog(self.gui, _('Multiple Books Selected'),
                _('You are attempting to open %d books. Opening too many '
                'books at once can be slow and have a negative effect on the '
                'responsiveness of your computer. Once started the process '
                'cannot be stopped until complete. Do you wish to continue?'
                ) % num, show_copy_button=False)

    def view_folder(self, *args):
        rows = self.gui.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot open folder'),
                    _('No book selected'))
            d.exec_()
            return
        if not self._view_check(len(rows)):
            return
        for row in rows:
            path = self.gui.library_view.model().db.abspath(row.row())
            open_local_file(path)

    def view_folder_for_id(self, id_):
        path = self.gui.library_view.model().db.abspath(id_, index_is_id=True)
        open_local_file(path)

    def view_book(self, triggered):
        rows = self.gui.current_view().selectionModel().selectedRows()
        self._view_books(rows)

    def view_triggered(self, index):
        self._view_books([index])

    def view_specific_book(self, index):
        self._view_books([index])

    def _view_books(self, rows):
        if not rows or len(rows) == 0:
            self._launch_viewer()
            return

        if not self._view_check(len(rows)):
            return

        if self.gui.current_view() is self.gui.library_view:
            for row in rows:
                if hasattr(row, 'row'):
                    row = row.row()

                formats = self.gui.library_view.model().db.formats(row)
                title   = self.gui.library_view.model().db.title(row)
                if not formats:
                    error_dialog(self.gui, _('Cannot view'),
                        _('%s has no available formats.')%(title,), show=True)
                    continue

                formats = formats.upper().split(',')


                in_prefs = False
                for format in prefs['input_format_order']:
                    if format in formats:
                        in_prefs = True
                        self.view_format(row, format)
                        break
                if not in_prefs:
                    self.view_format(row, formats[0])
        else:
            paths = self.gui.current_view().model().paths(rows)
            for path in paths:
                pt = PersistentTemporaryFile('_viewer_'+\
                        os.path.splitext(path)[1])
                self.persistent_files.append(pt)
                pt.close()
                self.gui.device_manager.view_book(\
                        Dispatcher(self.book_downloaded_for_viewing),
                                              path, pt.name)


