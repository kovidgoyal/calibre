#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import shutil, os, weakref, traceback, tempfile, time
from threading import Thread
from collections import OrderedDict
from Queue import Empty
from io import BytesIO
from future_builtins import map

from PyQt5.Qt import QObject, Qt, pyqtSignal

from calibre import prints, as_unicode
from calibre.constants import DEBUG, iswindows, isosx, filesystem_encoding
from calibre.customize.ui import run_plugins_on_postimport, run_plugins_on_postadd
from calibre.db.adding import find_books_in_directory, compile_rule
from calibre.db.utils import find_identical_books
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import OPF
from calibre.gui2 import error_dialog, warning_dialog, gprefs
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
        if not os.access(source, os.X_OK|os.R_OK):
            error_dialog(parent, _('Cannot add books'), _(
                'You do not have permission to read %s') % source, show=True)
            return False
    else:
        ok = False
        for path in source:
            if os.access(path, os.R_OK):
                ok = True
                break
        if not ok:
            error_dialog(parent, _('Cannot add books'), _(
                'You do not have permission to read any of the selected files'),
                det_msg='\n'.join(source), show=True)
            return False
    return True
# }}}


class Adder(QObject):

    do_one_signal = pyqtSignal()

    def __init__(self, source, single_book_per_directory=True, db=None, parent=None, callback=None, pool=None, list_of_archives=False):
        if not validate_source(source, parent):
            return
        QObject.__init__(self, parent)
        self.single_book_per_directory = single_book_per_directory
        self.ignore_opf = False
        self.list_of_archives = list_of_archives
        self.callback = callback
        self.add_formats_to_existing = prefs['add_formats_to_existing']
        self.do_one_signal.connect(self.tick, type=Qt.QueuedConnection)
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
        self.merged_books = set()
        self.added_duplicate_info = set()
        self.pd.show()

        self.scan_thread = Thread(target=self.scan, name='ScanBooks')
        self.scan_thread.daemon = True
        self.scan_thread.start()
        self.do_one = self.monitor_scan
        self.do_one_signal.emit()
        if DEBUG:
            self.start_time = time.time()

    def break_cycles(self):
        self.abort_scan = True
        self.pd.close()
        self.pd.deleteLater()
        if self.pool is not None:
            self.pool.shutdown()
        if not self.items:
            shutil.rmtree(self.tdir, ignore_errors=True)
        self.setParent(None)
        self.find_identical_books_data = self.merged_books = self.added_duplicate_info = self.pool = self.items = self.duplicates = self.pd = self.db = self.dbref = self.tdir = self.file_groups = self.scan_thread = None  # noqa
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
            compiled_rules = tuple(map(compile_rule, gprefs.get('add_filter_rules', ())))
        except Exception:
            compiled_rules = ()
            import traceback
            traceback.print_exc()

        if iswindows or isosx:
            def find_files(root):
                for dirpath, dirnames, filenames in os.walk(root):
                    for files in find_books_in_directory(dirpath, self.single_book_per_directory, compiled_rules=compiled_rules):
                        if self.abort_scan:
                            return
                        self.file_groups[len(self.file_groups)] = files
        else:
            def find_files(root):
                if isinstance(root, type(u'')):
                    root = root.encode(filesystem_encoding)
                for dirpath, dirnames, filenames in os.walk(root):
                    try:
                        dirpath = dirpath.decode(filesystem_encoding)
                    except UnicodeDecodeError:
                        prints('Ignoring non-decodable directory:', dirpath)
                        continue
                    for files in find_books_in_directory(dirpath, self.single_book_per_directory, compiled_rules=compiled_rules):
                        if self.abort_scan:
                            return
                        self.file_groups[len(self.file_groups)] = files

        def extract(source):
            tdir = tempfile.mkdtemp(suffix='_archive', dir=self.tdir)
            if source.lower().endswith('.zip'):
                from calibre.utils.zipfile import ZipFile
                try:
                    with ZipFile(source) as zf:
                        zf.extractall(tdir)
                except Exception:
                    prints('Corrupt ZIP file, trying to use local headers')
                    from calibre.utils.localunzip import extractall
                    extractall(source, tdir)
            elif source.lower().endswith('.rar'):
                from calibre.utils.unrar import extract
                extract(source, tdir)
            return tdir

        try:
            if isinstance(self.source, basestring):
                find_files(self.source)
                self.ignore_opf = True
            else:
                unreadable_files = []
                for path in self.source:
                    if self.abort_scan:
                        return
                    if os.access(path, os.R_OK):
                        if self.list_of_archives:
                            find_files(extract(path))
                            self.ignore_opf = True
                        else:
                            self.file_groups[len(self.file_groups)] = [path]
                    else:
                        unreadable_files.append(path)
                if unreadable_files:
                    if not self.file_groups:
                        m = ngettext('You do not have permission to read the selected file.',
                                     'You do not have permission to read the selected files.', len(unreadable_files))
                        self.scan_error = m + '\n' + '\n'.join(unreadable_files)
                    else:
                        a = self.report.append
                        for f in unreadable_files:
                            a(_('Could not add %s as you do not have permission to read the file' % f))
                            a('')
        except Exception:
            self.scan_error = traceback.format_exc()

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
                'No e-book files were found in %s') % self.source, show=True)
            self.break_cycles()
            return
        self.pd.max = len(self.file_groups)
        self.pd.title = _('Reading metadata and adding to library (%d books)...') % self.pd.max
        self.pd.msg = ''
        self.pd.value = 0
        self.pool = Pool(name='AddBooks') if self.pool is None else self.pool
        if self.db is not None:
            if self.add_formats_to_existing:
                self.find_identical_books_data = self.db.data_for_find_identical_books()
            else:
                try:
                    self.pool.set_common_data(self.db.data_for_has_book())
                except Failure as err:
                    error_dialog(self.pd, _('Cannot add books'), _(
                    'Failed to add any books, click "Show details" for more information.'),
                    det_msg=as_unicode(err.failure_message) + '\n' + as_unicode(err.details), show=True)
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
            det_msg=as_unicode(err.failure_message) + '\n' + as_unicode(err.details), show=True)
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
        m = ngettext('Failed to read metadata from the file:', 'Failed to read metadata from the files:', len(paths))
        a(m)
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
        if gprefs.get('tag_map_on_add_rules'):
            from calibre.ebooks.metadata.tag_mapper import map_tags
            mi.tags = map_tags(mi.tags, gprefs['tag_map_on_add_rules'])

        self.pd.msg = mi.title

        cover_path = os.path.join(self.tdir, '%s.cdata' % group_id) if has_cover else None

        if self.db is None:
            if paths:
                self.items.append((mi, cover_path, paths))
            return

        if self.add_formats_to_existing:
            identical_book_ids = find_identical_books(mi, self.find_identical_books_data)
            if identical_book_ids:
                try:
                    self.merge_books(mi, cover_path, paths, identical_book_ids)
                except Exception:
                    a = self.report.append
                    a(''), a('-' * 70)
                    a(_('Failed to merge the book: ') + mi.title)
                    [a('\t' + f) for f in paths]
                    a(_('With error:')), a(traceback.format_exc())
            else:
                self.add_book(mi, cover_path, paths)
        else:
            if duplicate_info or icu_lower(mi.title or _('Unknown')) in self.added_duplicate_info:
                self.duplicates.append((mi, cover_path, paths))
            else:
                self.add_book(mi, cover_path, paths)

    def merge_books(self, mi, cover_path, paths, identical_book_ids):
        self.merged_books.add((mi.title, ' & '.join(mi.authors)))
        seen_fmts = set()
        replace = gprefs['automerge'] == 'overwrite'
        cover_removed = False
        for identical_book_id in identical_book_ids:
            ib_fmts = {fmt.upper() for fmt in self.db.formats(identical_book_id)}
            seen_fmts |= ib_fmts
            self.add_formats(identical_book_id, paths, mi, replace=replace)
        if gprefs['automerge'] == 'new record':
            incoming_fmts = {path.rpartition(os.extsep)[-1].upper() for path in paths}
            if incoming_fmts.intersection(seen_fmts):
                # There was at least one duplicate format so create a new
                # record and put the incoming formats into it We should
                # arguably put only the duplicate formats, but no real harm is
                # done by having all formats
                self.add_book(mi, cover_path, paths)
                cover_removed = True
        if not cover_removed and cover_path:
            try:
                os.remove(cover_path)
            except Exception:
                pass

    def add_book(self, mi, cover_path, paths):
        if DEBUG:
            st = time.time()
        try:
            cdata = None
            if cover_path:
                with open(cover_path, 'rb') as f:
                    cdata = f.read()
                try:
                    os.remove(cover_path)
                except Exception:
                    pass
            book_id = self.dbref().create_book_entry(mi, cover=cdata)
            self.added_book_ids.add(book_id)
        except Exception:
            a = self.report.append
            a(''), a('-' * 70)
            a(_('Failed to add the book: ') + mi.title)
            [a('\t' + f) for f in paths]
            a(_('With error:')), a(traceback.format_exc())
            return
        self.add_formats(book_id, paths, mi, is_an_add=True)
        try:
            if self.add_formats_to_existing:
                self.db.update_data_for_find_identical_books(book_id, self.find_identical_books_data)
            else:
                self.added_duplicate_info.add(icu_lower(mi.title or _('Unknown')))
        except Exception:
            # Ignore this exception since all it means is that duplicate
            # detection/automerge will fail for this book.
            traceback.print_exc()
        if DEBUG:
            prints('Added', mi.title, 'to db in: %.1f' % (time.time() - st))

    def add_formats(self, book_id, paths, mi, replace=True, is_an_add=False):
        fmap = {p.rpartition(os.path.extsep)[-1].lower():p for p in paths}
        fmt_map = {}
        for fmt, path in fmap.iteritems():
            # The onimport plugins have already been run by the read metadata
            # worker
            if self.ignore_opf and fmt.lower() == 'opf':
                continue
            try:
                if self.db.add_format(book_id, fmt, path, run_hooks=False, replace=replace):
                    run_plugins_on_postimport(self.dbref(), book_id, fmt)
                    fmt_map[fmt.lower()] = path
            except Exception:
                a = self.report.append
                a(''), a('-' * 70)
                a(_('Failed to add the file {0} to the book: {1}').format(path, mi.title))
                a(_('With error:')), a(traceback.format_exc())
        if is_an_add:
            run_plugins_on_postadd(self.dbref(), book_id, fmt_map)

    def process_duplicates(self):
        if self.duplicates:
            d = DuplicatesQuestion(self.dbref(), self.duplicates, self.pd)
            duplicates = tuple(d.duplicates)
            d.deleteLater()
            if duplicates:
                self.do_one = self.process_duplicate
                self.duplicates_to_process = iter(duplicates)
                self.pd.title = _('Adding duplicates')
                self.pd.msg = ''
                self.pd.max, self.pd.value = len(duplicates), 0
                self.do_one_signal.emit()
                return
        self.finish()

    def process_duplicate(self):
        try:
            mi, cover_path, paths = next(self.duplicates_to_process)
        except StopIteration:
            self.finish()
            return
        self.pd.value += 1
        self.pd.msg = mi.title
        self.add_book(mi, cover_path, paths)
        self.do_one_signal.emit()

    def finish(self):
        if DEBUG:
            prints('Added %s books in %.1f seconds' % (len(self.added_book_ids or self.items), time.time() - self.start_time))
        if self.report:
            added_some = self.items or self.added_book_ids
            d = warning_dialog if added_some else error_dialog
            msg = _('There were problems adding some files, click "Show details" for more information') if added_some else _(
                'Failed to add any books, click "Show details" for more information')
            d(self.pd, _('Errors while adding'), msg, det_msg='\n'.join(self.report), show=True)

        if gprefs['manual_add_auto_convert'] and self.added_book_ids and self.parent() is not None:
            self.parent().iactions['Convert Books'].auto_convert_auto_add(
                self.added_book_ids)

        try:
            if callable(self.callback):
                self.callback(self)
        finally:
            self.break_cycles()

    @property
    def number_of_books_added(self):
        return len(self.added_book_ids)
