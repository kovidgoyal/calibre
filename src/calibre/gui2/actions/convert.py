#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import QModelIndex, QMenu

from calibre.gui2 import error_dialog, Dispatcher
from calibre.gui2.tools import convert_single_ebook, convert_bulk_ebook
from calibre.utils.config import prefs
from calibre.gui2.actions import InterfaceAction
from calibre.customize.ui import plugin_for_input_format

class ConvertAction(InterfaceAction):

    name = 'Convert Books'
    action_spec = (_('Convert books'), 'convert.png', None, _('C'))
    dont_add_to = frozenset(['toolbar-device', 'context-menu-device'])
    action_type = 'current'

    def genesis(self):
        cm = QMenu()
        cm.addAction(_('Convert individually'), partial(self.convert_ebook,
            False, bulk=False))
        cm.addAction(_('Bulk convert'),
                partial(self.convert_ebook, False, bulk=True))
        cm.addSeparator()
        ac = cm.addAction(
                _('Create catalog of books in your calibre library'))
        ac.triggered.connect(self.gui.iactions['Generate Catalog'].generate_catalog)
        self.qaction.setMenu(cm)
        self.qaction.triggered.connect(self.convert_ebook)
        self.convert_menu = cm
        self.conversion_jobs = {}

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def auto_convert(self, book_ids, on_card, format):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in \
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted, extra_job_args=[on_card])

    def auto_convert_mail(self, to, fmts, delete_from_library, book_ids, format):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in \
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_mail,
                extra_job_args=[delete_from_library, to, fmts])

    def auto_convert_news(self, book_ids, format):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in \
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_news)

    def auto_convert_catalogs(self, book_ids, format):
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in \
                self.gui.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self.gui, self.gui.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_catalogs)

    def get_books_for_conversion(self):
        rows = [r.row() for r in \
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot convert'),
                    _('No books selected'))
            d.exec_()
            return None
        return [self.gui.library_view.model().db.id(r) for r in rows]

    def convert_ebook(self, checked, bulk=None):
        book_ids = self.get_books_for_conversion()
        if book_ids is None: return
        previous = self.gui.library_view.currentIndex()
        rows = [x.row() for x in \
                self.gui.library_view.selectionModel().selectedRows()]
        num = 0
        if bulk or (bulk is None and len(book_ids) > 1):
            self.__bulk_queue = convert_bulk_ebook(self.gui, self.queue_convert_jobs,
                self.gui.library_view.model().db, book_ids,
                out_format=prefs['output_format'], args=(rows, previous,
                    self.book_converted))
            if self.__bulk_queue is None:
                return
            num = len(self.__bulk_queue.book_ids)
        else:
            jobs, changed, bad = convert_single_ebook(self.gui,
                self.gui.library_view.model().db, book_ids, out_format=prefs['output_format'])
            self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                    self.book_converted)
            num = len(jobs)

        if num > 0:
            self.gui.status_bar.show_message(_('Starting conversion of %d book(s)') %
                num, 2000)

    def queue_convert_jobs(self, jobs, changed, bad, rows, previous,
            converted_func, extra_job_args=[]):
        for func, args, desc, fmt, id, temp_files in jobs:
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
                args = [temp_files, fmt, id]+extra_job_args
                self.conversion_jobs[job] = tuple(args)

        if changed:
            self.gui.library_view.model().refresh_rows(rows)
            current = self.gui.library_view.currentIndex()
            self.gui.library_view.model().current_changed(current, previous)

    def book_auto_converted(self, job):
        temp_files, fmt, book_id, on_card = self.conversion_jobs[job]
        self.book_converted(job)
        self.gui.sync_to_device(on_card, False, specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_mail(self, job):
        temp_files, fmt, book_id, delete_from_library, to, fmts = self.conversion_jobs[job]
        self.book_converted(job)
        self.gui.send_by_mail(to, fmts, delete_from_library, specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

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
            data = open(temp_files[-1].name, 'rb')
            self.gui.library_view.model().db.add_format(book_id, \
                    fmt, data, index_is_id=True)
            data.close()
            self.gui.status_bar.show_message(job.description + \
                    (' completed'), 2000)
        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f.name):
                        os.remove(f.name)
                except:
                    pass
        self.gui.tags_view.recount()
        if self.gui.current_view() is self.gui.library_view:
            current = self.gui.library_view.currentIndex()
            self.gui.library_view.model().current_changed(current, QModelIndex())

