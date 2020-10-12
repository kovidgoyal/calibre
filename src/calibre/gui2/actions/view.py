#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
import os
import time
from functools import partial
from PyQt5.Qt import QAction, QIcon, Qt, pyqtSignal

from calibre.constants import ismacos, iswindows, plugins
from calibre.gui2 import (
    Dispatcher, config, elided_text, error_dialog, info_dialog, open_local_file,
    question_dialog
)
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import prefs, tweaks
from polyglot.builtins import as_bytes, unicode_type


class HistoryAction(QAction):

    view_historical = pyqtSignal(object)

    def __init__(self, id_, title, parent):
        QAction.__init__(self, title, parent)
        self.id = id_
        self.triggered.connect(self._triggered)

    def _triggered(self):
        self.view_historical.emit(self.id)


class ViewAction(InterfaceAction):

    name = 'View'
    action_spec = (_('View'), 'view.png', _('Read books'), _('V'))
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = True
    force_internal_viewer = False

    def genesis(self):
        self.persistent_files = []
        self.qaction.triggered.connect(self.view_book)
        self.view_action = self.menuless_qaction
        self.view_menu = self.qaction.menu()
        cm = partial(self.create_menu_action, self.view_menu)
        self.view_specific_action = cm('specific', _('View specific format'),
                shortcut='Alt+V', triggered=self.view_specific_format)
        self.internal_view_action = cm('internal', _('View with calibre E-book viewer'), triggered=self.view_internal)
        self.action_pick_random = cm('pick random', _('Read a random book'),
                icon='random.png', triggered=self.view_random)
        self.view_menu.addAction(QIcon(I('highlight.png')), _('Browse annotations'), self.browse_annots)
        self.clear_sep1 = self.view_menu.addSeparator()
        self.clear_sep2 = self.view_menu.addSeparator()
        self.clear_history_action = cm('clear history',
                _('Clear recently viewed list'), triggered=self.clear_history)
        self.history_actions = [self.clear_sep1]
        self.action_view_last_read = ac = self.create_action(
            spec=(_('Continue reading previous book'), None, _('Continue reading the last opened book'), 'shift+v'), attr='action_view_last_read')
        ac.triggered.connect(self.view_last_read)
        self.gui.addAction(ac)

    def initialization_complete(self):
        self.build_menus(self.gui.current_db)

    def build_menus(self, db):
        for ac in self.history_actions:
            self.view_menu.removeAction(ac)
        self.history_actions = []
        history = db.new_api.pref('gui_view_history', [])
        if history:
            self.view_menu.insertAction(self.clear_sep2, self.clear_sep1)
            self.history_actions.append(self.clear_sep1)
            fm = self.gui.fontMetrics()
            for id_, title in history:
                ac = HistoryAction(id_, elided_text(title, font=fm, pos='right'), self.view_menu)
                self.view_menu.insertAction(self.clear_sep2, ac)
                ac.view_historical.connect(self.view_historical)
                self.history_actions.append(ac)

    def view_last_read(self):
        history = self.gui.current_db.new_api.pref('gui_view_history', [])
        for book_id, title in history:
            self.view_historical(book_id)
            break

    def browse_annots(self):
        self.gui.iactions['Browse Annotations'].show_browser()

    def clear_history(self):
        db = self.gui.current_db
        db.new_api.set_pref('gui_view_history', [])
        self.build_menus(db)

    def view_historical(self, id_):
        self._view_calibre_books([id_])

    def library_changed(self, db):
        self.build_menus(db)

    def location_selected(self, loc):
        enabled = loc == 'library'
        for action in list(self.view_menu.actions())[1:]:
            action.setEnabled(enabled)

    def view_format(self, row, format):
        id_ = self.gui.library_view.model().id(row)
        self.view_format_by_id(id_, format)

    def calibre_book_data(self, book_id, fmt):
        from calibre.db.annotations import merge_annotations
        from calibre.gui2.viewer.config import get_session_pref, vprefs
        vprefs.refresh()
        sync_annots_user = get_session_pref('sync_annots_user', default='')
        db = self.gui.current_db.new_api
        annotations_map = db.annotations_map_for_book(book_id, fmt)
        if sync_annots_user:
            other_annotations_map = db.annotations_map_for_book(book_id, fmt, user_type='web', user=sync_annots_user)
            if other_annotations_map:
                merge_annotations(other_annotations_map, annotations_map, merge_last_read=False)
        return {
            'book_id': book_id, 'uuid': db.field_for('uuid', book_id), 'fmt': fmt.upper(),
            'annotations_map': annotations_map,
        }

    def view_format_by_id(self, id_, format, open_at=None):
        db = self.gui.current_db
        fmt_path = db.format_abspath(id_, format,
                index_is_id=True)
        if fmt_path:
            title = db.title(id_, index_is_id=True)
            self._view_file(fmt_path, calibre_book_data=self.calibre_book_data(id_, format), open_at=open_at)
            self.update_history([(id_, title)])

    def book_downloaded_for_viewing(self, job):
        if job.failed:
            self.gui.device_job_exception(job)
            return
        self._view_file(job.result)

    def _launch_viewer(self, name=None, viewer='ebook-viewer', internal=True, calibre_book_data=None, open_at=None):
        self.gui.setCursor(Qt.BusyCursor)
        try:
            if internal:
                args = [viewer]
                if ismacos and 'ebook' in viewer:
                    args.append('--raise-window')

                if name is not None:
                    args.append(name)
                    if open_at is not None:
                        args.append('--open-at=' + open_at)
                    if calibre_book_data is not None:
                        with PersistentTemporaryFile('.json') as ptf:
                            ptf.write(as_bytes(json.dumps(calibre_book_data)))
                            args.append('--internal-book-data=' + ptf.name)
                self.gui.job_manager.launch_gui_app(viewer,
                        kwargs=dict(args=args))
            else:
                if iswindows:
                    winutil = plugins['winutil'][0]
                    ext = name.rpartition('.')[-1]
                    if ext:
                        try:
                            prog = winutil.file_association(unicode_type('.' + ext))
                        except Exception:
                            prog = None
                        if prog and prog.lower().endswith('calibre.exe'):
                            name = os.path.basename(name)
                            return error_dialog(
                                self.gui, _('No associated program'), _(
                                    'Windows will try to open %s with calibre itself'
                                    ' resulting in a duplicate in your calibre library. You'
                                    ' should install some program capable of viewing this'
                                    ' file format and tell Windows to use that program to open'
                                    ' files of this type.') % name, show=True)

                open_local_file(name)
                time.sleep(2)  # User feedback
        finally:
            self.gui.unsetCursor()

    def _view_file(self, name, calibre_book_data=None, open_at=None):
        ext = os.path.splitext(name)[1].upper().replace('.',
                '').replace('ORIGINAL_', '')
        viewer = 'lrfviewer' if ext == 'LRF' else 'ebook-viewer'
        internal = self.force_internal_viewer or ext in config['internally_viewed_formats'] or open_at is not None
        self._launch_viewer(name, viewer, internal, calibre_book_data=calibre_book_data, open_at=open_at)

    def view_specific_format(self, triggered):
        rows = list(self.gui.library_view.selectionModel().selectedRows())
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot view'), _('No book selected'))
            d.exec_()
            return

        db = self.gui.library_view.model().db
        rows = [r.row() for r in rows]
        book_ids = [db.id(r) for r in rows]
        formats = [[x.upper() for x in db.new_api.formats(book_id)] for book_id in book_ids]
        all_fmts = set()
        for x in formats:
            if x:
                for f in x:
                    all_fmts.add(f)
        if not all_fmts:
            error_dialog(self.gui,  _('Format unavailable'),
                    _('Selected books have no formats'), show=True)
            return
        d = ChooseFormatDialog(self.gui, _('Choose the format to view'),
                list(sorted(all_fmts)), show_open_with=True)
        self.gui.book_converted.connect(d.book_converted)
        if d.exec_() == d.Accepted:
            formats = [[x.upper() for x in db.new_api.formats(book_id)] for book_id in book_ids]
            fmt = d.format()
            orig_num = len(rows)
            rows = [rows[i] for i in range(len(rows)) if formats[i] and fmt in
                    formats[i]]
            if self._view_check(len(rows)):
                for row in rows:
                    if d.open_with_format is None:
                        self.view_format(row, fmt)
                    else:
                        self.open_fmt_with(row, *d.open_with_format)
                if len(rows) < orig_num:
                    info_dialog(self.gui, _('Format unavailable'),
                            _('Not all the selected books were available in'
                                ' the %s format. You should convert'
                                ' them first.')%fmt, show=True)
        self.gui.book_converted.disconnect(d.book_converted)

    def open_fmt_with(self, row, fmt, entry):
        book_id = self.gui.library_view.model().id(row)
        self.gui.book_details.open_fmt_with.emit(book_id, fmt, entry)

    def _view_check(self, num, max_=5, skip_dialog_name=None):
        if num <= max_:
            return True
        return question_dialog(self.gui, _('Multiple books selected'),
                _('You are attempting to open %d books. Opening too many '
                'books at once can be slow and have a negative effect on the '
                'responsiveness of your computer. Once started the process '
                'cannot be stopped until complete. Do you wish to continue?'
                ) % num, show_copy_button=False, skip_dialog_name=skip_dialog_name)

    def view_folder(self, *args):
        rows = self.gui.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot open folder'),
                    _('No book selected'))
            d.exec_()
            return
        if not self._view_check(len(rows), max_=10, skip_dialog_name='open-folder-many-check'):
            return
        for i, row in enumerate(rows):
            path = self.gui.library_view.model().db.abspath(row.row())
            open_local_file(path)
            if ismacos and i < len(rows) - 1:
                time.sleep(0.1)  # Finder cannot handle multiple folder opens

    def view_folder_for_id(self, id_):
        path = self.gui.library_view.model().db.abspath(id_, index_is_id=True)
        open_local_file(path)

    def view_book(self, triggered):
        rows = self.gui.current_view().selectionModel().selectedRows()
        self._view_books(rows)

    def view_internal(self, triggered):
        try:
            self.force_internal_viewer = True
            self.view_book(triggered)
        finally:
            self.force_internal_viewer = False

    def view_triggered(self, index):
        self._view_books([index])

    def view_specific_book(self, index):
        self._view_books([index])

    def view_random(self, *args):
        self.gui.iactions['Pick Random Book'].pick_random()
        self._view_books([self.gui.library_view.currentIndex()])

    def _view_calibre_books(self, ids):
        db = self.gui.current_db
        views = []
        for id_ in ids:
            try:
                title = db.title(id_, index_is_id=True)
            except:
                error_dialog(self.gui, _('Cannot view'),
                    _('This book no longer exists in your library'), show=True)
                self.update_history([], remove={id_})
                continue

            formats = db.formats(id_, index_is_id=True)
            if not formats:
                error_dialog(self.gui, _('Cannot view'),
                    _('%s has no available formats.')%(title,), show=True)
                continue

            formats = formats.upper().split(',')

            fmt = formats[0]
            for format in prefs['input_format_order']:
                if format in formats:
                    fmt = format
                    break
            views.append((id_, title))
            self.view_format_by_id(id_, fmt)

        self.update_history(views)

    def update_history(self, views, remove=frozenset()):
        db = self.gui.current_db
        vh = tweaks['gui_view_history_size']
        if views:
            seen = set()
            history = []
            for id_, title in views + db.new_api.pref('gui_view_history', []):
                if title not in seen:
                    seen.add(title)
                    history.append((id_, title))

            db.new_api.set_pref('gui_view_history', history[:vh])
            self.build_menus(db)
        if remove:
            history = db.new_api.pref('gui_view_history', [])
            history = [x for x in history if x[0] not in remove]
            db.new_api.set_pref('gui_view_history', history[:vh])
            self.build_menus(db)

    def view_device_book(self, path):
        pt = PersistentTemporaryFile('_view_device_book'+
                os.path.splitext(path)[1])
        self.persistent_files.append(pt)
        pt.close()
        self.gui.device_manager.view_book(
                Dispatcher(self.book_downloaded_for_viewing), path, pt.name)

    def _view_books(self, rows):
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot view'),
                             _('No books selected'), show=True)

        if not self._view_check(len(rows)):
            return

        if self.gui.current_view() is self.gui.library_view:
            ids = []
            m = self.gui.library_view.model().id
            for r in rows:
                try:
                    ids.append(m(r))
                except Exception:
                    pass
            if ids:
                self._view_calibre_books(ids)
        else:
            paths = self.gui.current_view().model().paths(rows)
            for path in paths:
                self.view_device_book(path)
