#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import shutil, os, weakref, traceback
from threading import Thread
from collections import OrderedDict
from Queue import Empty
from io import BytesIO

from PyQt5.Qt import QObject, Qt, pyqtSignal

from calibre import prints
from calibre.customize.ui import run_plugins_on_postimport
from calibre.db.adding import find_books_in_directory
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import OPF
from calibre.gui2 import error_dialog, warning_dialog
from calibre.gui2.dialogs.duplicates import DuplicatesQuestion
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils import join_with_timeout
from calibre.utils.config import prefs
from calibre.utils.ipc.pool import Pool, Failure

def validate_source(source, parent=None):  # {{{
    if isinstance(source, basestring):
        if not os.path.exists(source):
            error_dialog(parent, _('Cannot add books'), _(
                'The path %s does not exist') % source, show=True)
            return False
        if os.path.isdir(source):
            if not os.access(source, os.X_OK|os.R_OK):
                error_dialog(parent, _('Cannot add books'), _(
                    'You do not have permission to read %s') % source, show=True)
                return False
        else:
            if not os.access(source, os.R_OK):
                error_dialog(parent, _('Cannot add books'), _(
                    'You do not have permission to read %s') % source, show=True)
                return False
            if not source.lower().rpartition(os.extsep)[-1] in {'zip', 'rar'}:
                error_dialog(parent, _('Cannot add books'), _(
                    'The file %s is not a recognized archive format') % source, show=True)
                return False

    return True
# }}}

class Adder(QObject):

    do_one_signal = pyqtSignal()

    def __init__(self, source, single_book_per_directory=True, db=None, parent=None, callback=None, pool=None):
        if not validate_source(source, parent):
            return
        QObject.__init__(self, parent)
        self.single_book_per_directory = single_book_per_directory
        self.callback = callback
        self.add_formats_to_existing = prefs['add_formats_to_existing']
        self.do_one_signal.connect(self.tick, type=Qt.QueuedConnection)
        self.tdir = PersistentTemporaryDirectory('_add_books')
        self.pool = pool
        self.pd = ProgressDialog(_('Adding books...'), _('Scanning for files...'), min=0, max=0, parent=parent, icon='add_book.png')
        self.db = getattr(db, 'new_api', None)
        if self.db is not None:
            self.dbref = weakref.ref(db)
        self.source = source
        self.tdir = PersistentTemporaryDirectory('_add_books')
        self.scan_error = None
        self.file_groups = OrderedDict()
        self.abort_scan = False
        self.duplicates = []
        self.report = []
        self.items = []
        self.added_book_ids = set()
        self.added_duplicate_info = ({}, {}, {}) if self.add_formats_to_existing else set()
        self.pd.show()

        self.scan_thread = Thread(target=self.scan, name='ScanBooks')
        self.scan_thread.daemon = True
        self.scan_thread.start()
        self.do_one = self.monitor_scan
        self.do_one_signal.emit()

    def break_cycles(self):
        self.abort_scan = True
        self.pd.close()
        self.pd.deleteLater()
        shutil.rmtree(self.tdir, ignore_errors=True)
        if self.pool is not None:
            self.pool.shutdown()
        if not self.items:
            shutil.rmtree(self.tdir, ignore_errors=True)
        self.setParent(None)
        self.added_duplicate_info = self.pool = self.items = self.duplicates = self.pd = self.db = self.dbref = self.tdir = self.file_groups = self.scan_thread = None  # noqa
        self.deleteLater()

    def tick(self):
        if self.pd.canceled:
            try:
                if callable(self.callback):
                    self.callback(self)
            finally:
                self.break_cycles()
            return
        self.do_one()

    # Filesystem scan {{{
    def scan(self):
        try:
            if isinstance(self.source, basestring):
                if os.path.isdir(self.source):
                    root = self.source
                else:
                    root = self.extract()
                for dirpath, dirnames, filenames in os.walk(root):
                    for files in find_books_in_directory(dirpath, self.single_book_per_directory):
                        if self.abort_scan:
                            return
                        if files:
                            self.file_groups[len(self.file_groups)] = files
            else:
                unreadable_files = []
                for path in self.source:
                    if self.abort_scan:
                        return
                    if os.access(path, os.R_OK):
                        self.file_groups[len(self.file_groups)] = [path]
                    else:
                        unreadable_files.append(path)
                if unreadable_files:
                    if not self.file_groups:
                        self.scan_error = _('You do not have permission to read the selected file(s).') + '\n'
                        self.scan_error += '\n'.join(unreadable_files)
                    else:
                        a = self.report.append
                        for f in unreadable_files:
                            a(_('Could not add %s as you do not have permission to read the file' % f))
                            a('')
        except Exception:
            self.scan_error = traceback.format_exc()

    def extract(self):
        tdir = os.path.join(self.tdir, 'archive')
        if self.source.lower().endswith('.zip'):
            from calibre.utils.zipfile import ZipFile
            try:
                with ZipFile(self.source) as zf:
                    zf.extractall(tdir)
            except Exception:
                prints('Corrupt ZIP file, trying to use local headers')
                from calibre.utils.localunzip import extractall
                extractall(self.source, tdir)
        elif self.path.lower().endswith('.rar'):
            from calibre.utils.unrar import extract
            extract(self.source, tdir)
        return tdir

    def monitor_scan(self):
        self.scan_thread.join(0.05)
        if self.scan_thread.is_alive():
            self.do_one_signal.emit()
            return
        if self.scan_error is not None:
            error_dialog(self.pd, _('Cannot add books'), _(
                'Failed to add any books, click "Show details" for more information.'),
                         det_msg=self.scan_error, show=True)
            self.break_cycles()
            return
        if not self.file_groups:
            error_dialog(self.pd, _('Could not add'), _(
                'No ebook files were found in %s') % self.source, show=True)
            self.break_cycles()
            return
        self.pd.max = len(self.file_groups)
        self.pd.title = _('Reading metadata and adding to library (%d books)...') % self.pd.max
        self.pd.msg = ''
        self.pd.value = 0
        self.pool = Pool(name='AddBooks') if self.pool is None else self.pool
        if self.db is not None:
            data = self.db.data_for_find_identical_books() if self.add_formats_to_existing else self.db.data_for_has_book()
            try:
                self.pool.set_common_data(data)
            except Failure as err:
                error_dialog(self.pd, _('Cannot add books'), _(
                'Failed to add any books, click "Show details" for more information.'),
                det_msg=unicode(err.failure_message) + '\n' + unicode(err.details), show=True)
                self.pd.canceled = True
        self.groups_to_add = iter(self.file_groups)
        self.do_one = self.do_one_group
        self.do_one_signal.emit()
    # }}}

    def do_one_group(self):
        try:
            group_id = next(self.groups_to_add)
        except StopIteration:
            self.do_one = self.monitor_pool
            self.do_one_signal.emit()
            return
        try:
            self.pool(group_id, 'calibre.ebooks.metadata.worker', 'read_metadata',
                      self.file_groups[group_id], group_id, self.tdir)
        except Failure as err:
            error_dialog(self.pd, _('Cannot add books'), _(
            'Failed to add any books, click "Show details" for more information.'),
            det_msg=unicode(err.failure_message) + '\n' + unicode(err.details), show=True)
            self.pd.canceled = True
        self.do_one_signal.emit()

    def monitor_pool(self):
        try:
            worker_result = self.pool.results.get(True, 0.05)
            self.pool.results.task_done()
        except Empty:
            try:
                self.pool.wait_for_tasks(timeout=0.01)
            except RuntimeError:
                pass  # Tasks still remaining
            except Failure as err:
                error_dialog(self.pd, _('Cannot add books'), _(
                'Failed to add some books, click "Show details" for more information.'),
                det_msg=unicode(err.failure_message) + '\n' + unicode(err.details), show=True)
                self.pd.canceled = True
            else:
                # All tasks completed
                try:
                    join_with_timeout(self.pool.results, 0.01)
                except RuntimeError:
                    pass  # There are results remaining
                else:
                    # No results left
                    self.process_duplicates()
                    return
        else:
            group_id = worker_result.id
            if worker_result.is_terminal_failure:
                error_dialog(self.pd, _('Critical failure'), _(
                    'The read metadata worker process crashed while processing'
                    ' some files. Adding of books is aborted. Click "Show details"'
                    ' to see which files caused the problem.'), show=True,
                    det_msg='\n'.join(self.file_groups[group_id]))
                self.pd.canceled = True
            else:
                try:
                    self.process_result(group_id, worker_result.result)
                except Exception:
                    self.report_metadata_failure(group_id, traceback.format_exc())
                self.pd.value += 1

        self.do_one_signal.emit()

    def report_metadata_failure(self, group_id, details):
        a = self.report.append
        paths = self.file_groups[group_id]
        a(''), a('-' * 70)
        a(_('Failed to read metadata from the file(s):'))
        [a('\t' + f) for f in paths]
        a(_('With error:')), a(details)
        mi = Metadata(_('Unknown'))
        mi.read_metadata_failed = False
        return mi

    def process_result(self, group_id, result):
        if result.err:
            mi = self.report_metadata_failure(group_id, result.traceback)
            paths = self.file_groups[group_id]
            has_cover = False
            duplicate_info = set() if self.add_formats_to_existing else False
        else:
            paths, opf, has_cover, duplicate_info = result.value
            try:
                mi = OPF(BytesIO(opf), basedir=self.tdir, populate_spine=False, try_to_guess_cover=False).to_book_metadata()
                mi.read_metadata_failed = False
            except Exception:
                mi = self.report_metadata_failure(group_id, traceback.format_exc())

        if mi.is_null('title'):
            for path in paths:
                mi.title = os.path.splitext(os.path.basename(path))[0]
                break
        if mi.application_id == '__calibre_dummy__':
            mi.application_id = None

        self.pd.msg = mi.title

        cover_path = os.path.join(self.tdir, '%s.cdata' % group_id) if has_cover else None

        if self.db is None:
            if paths:
                self.items.append((mi, cover_path, paths))
            return

        if self.add_formats_to_existing:
            pass  # TODO: Implement this
        else:
            if duplicate_info or icu_lower(mi.title or _('Unknown')) in self.added_duplicate_info:
                self.duplicates.append((mi, cover_path, paths))
            else:
                self.add_book(mi, cover_path, paths)

    def add_book(self, mi, cover_path, paths):
        try:
            cdata = None
            if cover_path:
                with open(cover_path, 'rb') as f:
                    cdata = f.read()
            book_id = self.dbref().create_book_entry(mi, cover=cdata)
            self.added_book_ids.add(book_id)
        except Exception:
            a = self.report.append
            a(''), a('-' * 70)
            a(_('Failed to add the book: ') + mi.title)
            [a('\t' + f) for f in paths]
            a(_('With error:')), a(traceback.format_exc())
            return
        else:
            self.add_formats(book_id, paths, mi)
        if self.add_formats_to_existing:
            pass  # TODO: Implement this
        else:
            self.added_duplicate_info.add(icu_lower(mi.title or _('Unknown')))

    def add_formats(self, book_id, paths, mi):
        fmap = {p.rpartition(os.path.extsep)[-1].lower():p for p in paths}
        for fmt, path in fmap.iteritems():
            # The onimport plugins have already been run by the read metadata
            # worker
            try:
                if self.db.add_format(book_id, fmt, path, run_hooks=False):
                    run_plugins_on_postimport(self.dbref(), book_id, fmt)
            except Exception:
                a = self.report.append
                a(''), a('-' * 70)
                a(_('Failed to add the file {0} to the book: {1}').format(path, mi.title))
                a(_('With error:')), a(traceback.format_exc())

    def process_duplicates(self):
        if self.duplicates:
            d = DuplicatesQuestion(self.dbref(), self.duplicates, self.pd)
            duplicates = tuple(d.duplicates)
            d.deleteLater()
            if duplicates:
                self.do_one = self.process_duplicate
                self.duplicates_to_process = iter(duplicates)
                self.do_one_signal.emit()
                return
        self.finish()

    def process_duplicate(self):
        try:
            mi, cover_path, paths = next(self.duplicates_to_process)
        except StopIteration:
            self.finish()
            return
        self.add_book(mi, cover_path, paths)
        self.do_one_signal.emit()

    def finish(self):
        if self.report:
            added_some = self.items or self.added_book_ids
            d = warning_dialog if added_some else error_dialog
            msg = _('There were problems adding some files, click "Show details" for more information') if added_some else _(
                'Failed to add any books, click "Show details" for more information')
            d(self.pd, _('Errors while adding'), msg, det_msg='\n'.join(self.report), show=True)

        try:
            if callable(self.callback):
                self.callback(self)
        finally:
            self.break_cycles()

    @property
    def number_of_books_added(self):
        return len(self.added_book_ids)

# TODO: Duplicates and auto-merge (in particular adding duplicated files as well as adding files already in the db)
# TODO: Test importing with filetype plugin (archive, de-obfuscate)
# TODO: Test handling of exception in metadata read function
# TODO: Report terminal erros where some books have been added better
# TODO: Test direct add of books to device
# TODO: Test adding form device to library
# TODO: Check aborting after a few books have been added
