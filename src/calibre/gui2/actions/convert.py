#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from qt.core import QModelIndex, QTimer

from calibre.gui2 import error_dialog, Dispatcher, gprefs
from calibre.gui2.tools import convert_single_ebook, convert_bulk_ebook
from calibre.utils.config import prefs, tweaks
from calibre.gui2.actions import InterfaceAction
from calibre.customize.ui import plugin_for_input_format


class ConvertAction(InterfaceAction):

    name = 'Convert Books'
    action_spec = (_('Convert books'), 'convert.png', _('Convert books between different e-book formats'), _('C'))
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'
    action_add_menu = True

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
        self.do_convert(book_ids)

    def genesis(self):
        m = self.convert_menu = self.qaction.menu()
        cm = partial(self.create_menu_action, self.convert_menu)
        cm('convert-individual', _('Convert individually'),
                icon=self.qaction.icon(), triggered=partial(self.convert_ebook,
            False, bulk=False))
        cm('convert-bulk', _('Bulk convert'),
                triggered=partial(self.convert_ebook, False, bulk=True))
        m.addSeparator()
        cm('create-catalog',
                _('Create a catalog of the books in your calibre library'),
                icon='catalog.png', shortcut=False,
                triggered=self.gui.iactions['Generate Catalog'].generate_catalog)
        self.qaction.triggered.connect(self.convert_ebook)
        self.conversion_jobs = {}

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)
        for action in list(self.convert_menu.actions()):
            action.setEnabled(enabled)

    def auto_convert(self, book_ids, on_card, format):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []:
            return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted, extra_job_args=[on_card])

    def auto_convert_auto_add(self, book_ids):
        previous = self.gui.library_view.currentIndex()
        db = self.gui.current_db
        needed = set()
        of = prefs['output_format'].lower()
        for book_id in book_ids:
            fmts = db.formats(book_id, index_is_id=True)
            fmts = {x.lower() for x in fmts.split(',')} if fmts else set()
            if gprefs['auto_convert_same_fmt'] or of not in fmts:
                needed.add(book_id)
        if needed:
            jobs, changed, bad = convert_single_ebook(self.gui,
                    self.gui.library_view.model().db, needed, True, of,
                    show_no_format_warning=False)
            if not jobs:
                return
            self.queue_convert_jobs(jobs, changed, bad, list(needed), previous,
                    self.book_converted, rows_are_ids=True)

    def auto_convert_mail(self, to, fmts, delete_from_library, book_ids, format, subject):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []:
            return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_mail,
                extra_job_args=[delete_from_library, to, fmts, subject])

    def auto_convert_multiple_mail(self, book_ids, data, ofmt, delete_from_library):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, ofmt)
        if jobs == []:
            return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_multiple_mail,
                extra_job_args=[delete_from_library, data])

    def auto_convert_news(self, book_ids, format):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []:
            return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_news)

    def auto_convert_catalogs(self, book_ids, format):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []:
            return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_catalogs)

    def get_books_for_conversion(self):
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot convert'),
                    _('No books selected'))
            d.exec()
            return None
        return [self.gui.library_view.model().db.id(r) for r in rows]

    def convert_ebook(self, checked, bulk=None):
        book_ids = self.get_books_for_conversion()
        if book_ids is None:
            return
        self.do_convert(book_ids, bulk=bulk)

    def convert_ebooks_to_format(self, book_ids, to_fmt):
        from calibre.customize.ui import available_output_formats
        to_fmt = to_fmt.upper()
        if to_fmt.lower() not in available_output_formats():
            return error_dialog(self.gui, _('Cannot convert'), _(
                'Conversion to the {} format is not supported').format(to_fmt), show=True)
        self.do_convert(book_ids, output_fmt=to_fmt, auto_conversion=True)

    def do_convert(self, book_ids, bulk=None, auto_conversion=False, output_fmt=None):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in
                self.gui.library_view.selectionModel().selectedRows()]
        num = 0
        if bulk or (bulk is None and len(book_ids) > 1):
            self.__bulk_queue = convert_bulk_ebook(self.gui, self.queue_convert_jobs,
                self.gui.library_view.model().db, book_ids,
                out_format=output_fmt or prefs['output_format'], args=(rows, previous,
                    self.book_converted))
            if self.__bulk_queue is None:
                return
            num = len(self.__bulk_queue.book_ids)
        else:
            jobs, changed, bad = convert_single_ebook(self.gui,
                self.gui.library_view.model().db, book_ids, out_format=output_fmt or prefs['output_format'], auto_conversion=auto_conversion)
            self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                    self.book_converted)
            num = len(jobs)

        if num > 0:
            self.gui.jobs_pointer.start()
            self.gui.status_bar.show_message(ngettext(
                'Starting conversion of the book', 'Starting conversion of {} books', num).format(num), 2000)

    def queue_convert_jobs(self, jobs, changed, bad, rows, previous,
            converted_func, extra_job_args=[], rows_are_ids=False):
        for func, args, desc, fmt, id, temp_files in jobs:
            func, _, parts = func.partition(':')
            parts = {x for x in parts.split(';')}
            input_file = args[0]
            input_fmt = os.path.splitext(input_file)[1]
            core_usage = 1
            if input_fmt:
                input_fmt = input_fmt[1:]
                plugin = plugin_for_input_format(input_fmt)
                if plugin is not None:
                    core_usage = plugin.core_usage

            if id not in bad:
                job = self.gui.job_manager.run_job(Dispatcher(converted_func),
                                            func, args=args, description=desc,
                                            core_usage=core_usage)
                job.conversion_of_same_fmt = 'same_fmt' in parts
                job.manually_fine_tune_toc = 'manually_fine_tune_toc' in parts
                args = [temp_files, fmt, id]+extra_job_args
                self.conversion_jobs[job] = tuple(args)

        if changed:
            m = self.gui.library_view.model()
            if rows_are_ids:
                m.refresh_ids(rows)
            else:
                m.refresh_rows(rows)
            current = self.gui.library_view.currentIndex()
            self.gui.library_view.model().current_changed(current, previous)

    def book_auto_converted(self, job):
        temp_files, fmt, book_id, on_card = self.conversion_jobs[job]
        self.book_converted(job)
        self.gui.sync_to_device(on_card, False, specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_mail(self, job):
        temp_files, fmt, book_id, delete_from_library, to, fmts, subject = self.conversion_jobs[job]
        self.book_converted(job)
        self.gui.send_by_mail(to, fmts, delete_from_library, subject=subject,
                specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_multiple_mail(self, job):
        temp_files, fmt, book_id, delete_from_library, data = self.conversion_jobs[job]
        self.book_converted(job)
        for to, subject in data:
            self.gui.send_by_mail(to, (fmt,), delete_from_library, subject=subject,
                    specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_news(self, job):
        temp_files, fmt, book_id = self.conversion_jobs[job]
        self.book_converted(job)
        self.gui.sync_news(send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_catalogs(self, job):
        temp_files, fmt, book_id = self.conversion_jobs[job]
        self.book_converted(job)
        self.gui.sync_catalogs(send_ids=[book_id], do_auto_convert=False)

    def book_converted(self, job):
        temp_files, fmt, book_id = self.conversion_jobs.pop(job)[:3]
        try:
            if job.failed:
                self.gui.job_exception(job)
                return
            db = self.gui.current_db
            if not db.new_api.has_id(book_id):
                return error_dialog(self.gui, _('Book deleted'), _(
                    'The book you were trying to convert has been deleted from the calibre library.'), show=True)
            same_fmt = getattr(job, 'conversion_of_same_fmt', False)
            manually_fine_tune_toc = getattr(job, 'manually_fine_tune_toc', False)
            fmtf = temp_files[-1].name
            if os.stat(fmtf).st_size < 1:
                raise Exception(_('Empty output file, '
                    'probably the conversion process crashed'))

            if same_fmt and tweaks['save_original_format']:
                db.save_original_format(book_id, fmt, notify=False)

            with open(temp_files[-1].name, 'rb') as data:
                db.add_format(book_id, fmt, data, index_is_id=True)
            self.gui.book_converted.emit(book_id, fmt)
            self.gui.status_bar.show_message(job.description + ' ' +
                    _('completed'), 2000)
        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f.name):
                        os.remove(f.name)
                except:
                    pass
        self.gui.tags_view.recount()
        if self.gui.current_view() is self.gui.library_view:
            lv = self.gui.library_view
            lv.model().refresh_ids((book_id,))
            current = lv.currentIndex()
            if current.isValid():
                lv.model().current_changed(current, QModelIndex())
        if manually_fine_tune_toc:
            self.gui.iactions['Edit ToC'].do_one(book_id, fmt.upper())
