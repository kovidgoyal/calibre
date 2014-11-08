#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback, errno, os, time, shutil
from collections import namedtuple, defaultdict
from tempfile import SpooledTemporaryFile
from Queue import Empty

from PyQt5.Qt import QObject, Qt, pyqtSignal

from calibre import prints
from calibre.constants import DEBUG
from calibre.customize.ui import can_set_metadata
from calibre.db.errors import NoSuchFormat
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.gui2 import error_dialog, warning_dialog, gprefs, open_local_file
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.utils.formatter_functions import load_user_template_functions
from calibre.utils.ipc.job import ParallelJob
from calibre.utils.ipc.server import Server
from calibre.library.save_to_disk import sanitize_args, get_path_components, find_plugboard, plugboard_save_to_disk_value

BookId = namedtuple('BookId', 'title authors')

def ensure_unique_components(data):  # {{{
    cmap = {}
    for book_id, (mi, components) in data.iteritems():
        c = tuple(components)
        if c in cmap:
            cmap[c].add(book_id)
        else:
            cmap[c] = {book_id}

    for book_ids in cmap.itervalues():
        if len(book_ids) > 1:
            for i, book_id in enumerate(sorted(book_ids)[1:]):
                suffix = ' (%d)' % (i + 1)
                components[-1] = components[-1] + suffix
# }}}

class SpooledFile(SpooledTemporaryFile):  # {{{

    def __init__(self, file_obj, max_size=50*1024*1024):
        self._file_obj = file_obj
        SpooledTemporaryFile.__init__(self, max_size)

    def rollover(self):
        if self._rolled:
            return
        orig = self._file
        newfile = self._file = self._file_obj
        del self._TemporaryFileArgs

        newfile.write(orig.getvalue())
        newfile.seek(orig.tell(), 0)

        self._rolled = True

    def truncate(self, *args):
        # The stdlib SpooledTemporaryFile implementation of truncate() doesn't
        # allow specifying a size.
        self._file.truncate(*args)
# }}}

class Saver(QObject):

    do_one_signal = pyqtSignal()

    def __init__(self, book_ids, db, opts, root, parent=None, spare_server=None):
        QObject.__init__(self, parent)
        if parent is not None:
            setattr(parent, 'no_gc_%s' % id(self), self)
        self.db = db.new_api
        self.plugboards = self.db.pref('plugboards', {})
        self.template_functions = self.db.pref('user_template_functions', [])
        load_user_template_functions('', self.template_functions)
        self.collected_data = {}
        self.metadata_data = {}
        self.errors = defaultdict(list)
        self._book_id_data = {}
        self.all_book_ids = frozenset(book_ids)
        self.pd = ProgressDialog(_('Saving %d books...') % len(self.all_book_ids), _('Collecting metadata...'), min=0, max=0, parent=parent, icon='save.png')
        self.do_one_signal.connect(self.tick, type=Qt.QueuedConnection)
        self.do_one = self.do_one_collect
        self.ids_to_collect = iter(self.all_book_ids)
        self.plugboard_cache = {}
        self.tdir = PersistentTemporaryDirectory('_save_to_disk')
        self.server = spare_server

        self.pd.show()
        self.root, self.opts, self.path_length = sanitize_args(root, opts)
        self.do_one_signal.emit()
        if DEBUG:
            self.start_time = time.time()

    def tick(self):
        if self.pd.canceled:
            self.pd.close()
            self.pd.deleteLater()
            self.break_cycles()
            return
        self.do_one()

    def break_cycles(self):
        shutil.rmtree(self.tdir, ignore_errors=True)
        p = self.parent()
        if p is not None:
            setattr(p, 'no_gc_%s' % id(self), None)
        if self.server is not None:
            self.server.close()
        self.jobs = self.server = self.metadata_data = self.plugboard_cache = self.plugboards = self.template_functions = self.collected_data = self.all_book_ids = self.pd = self.db = None  # noqa

    def book_id_data(self, book_id):
        ans = self._book_id_data.get(book_id)
        if ans is None:
            try:
                ans = BookId(self.db.field_for('title', book_id), self.db.field_for('authors', book_id))
            except Exception:
                ans = BookId((_('Unknown') + ' (%d)' % book_id), (_('Unknown'),))
            self._book_id_data[book_id] = ans
        return ans

    def do_one_collect(self):
        try:
            book_id = next(self.ids_to_collect)
        except StopIteration:
            self.collection_finished()
            return
        try:
            self.collect_data(book_id)
        except Exception:
            self.errors[book_id].append(('critical', traceback.format_exc()))
        self.do_one_signal.emit()

    def collect_data(self, book_id):
        mi = self.db.get_metadata(book_id)
        self._book_id_data[book_id] = BookId(mi.title, mi.authors)
        components = get_path_components(self.opts, mi, book_id, self.path_length)
        self.collected_data[book_id] = (mi, components)

    def collection_finished(self):
        self.do_one = self.do_one_write
        ensure_unique_components(self.collected_data)
        self.ids_to_write = iter(self.collected_data)
        self.pd.title = _('Copying files from calibre library to disk...')
        self.pd.max = len(self.collected_data)
        self.pd.value = 0
        self.do_one_signal.emit()

    def do_one_write(self):
        try:
            book_id = next(self.ids_to_write)
        except StopIteration:
            self.writing_finished()
            return
        self.pd.msg = self.book_id_data(book_id).title
        self.pd.value += 1
        try:
            self.write_book(book_id, *self.collected_data[book_id])
        except Exception:
            self.errors[book_id].append(('critical', traceback.format_exc()))
        self.do_one_signal.emit()

    def write_book(self, book_id, mi, components):
        base_path = os.path.join(self.root, *components)
        base_dir = os.path.dirname(base_path)
        fmts = {f.lower() for f in self.db.formats(book_id)}
        if self.opts.formats != 'all':
            asked_formats = {x.lower().strip() for x in self.opts.formats.split(',')}
            fmts = asked_formats.intersection(fmts)
            if not fmts:
                self.errors[book_id] = ('critical', _('Requested formats not available'))
                return

        if not fmts and not self.opts.write_opf and not self.opts.save_cover:
            return

        try:
            os.makedirs(base_dir)
        except EnvironmentError as err:
            if err.errno != errno.EEXIST:
                raise

        if self.opts.update_metadata:
            self.metadata_data[book_id] = d = {}
            d['last_modified'] = mi.last_modified.isoformat()

        cdata = self.db.cover(book_id)
        mi.cover, mi.cover_data = None, (None, None)

        if cdata:
            fname = None
            if self.opts.save_cover:
                fname = base_path + os.extsep + 'jpg'
                mi.cover = os.path.basename(fname)
            elif self.opts.update_metadata:
                fname = os.path.join(self.tdir, '%d.jpg' % book_id)

            if fname:
                with lopen(fname, 'wb') as f:
                    f.write(cdata)
                if self.opts.update_metadata:
                    d['cover'] = fname

        fname = None
        if self.opts.write_opf:
            fname = base_path + os.extsep + 'opf'
        elif self.opts.update_metadata:
            fname = os.path.join(self.tdir, '%d.opf' % book_id)
        if fname:
            opf = metadata_to_opf(mi)
            with lopen(fname, 'wb') as f:
                f.write(opf)
            if self.opts.update_metadata:
                d['opf'] = fname
        mi.cover, mi.cover_data = None, (None, None)
        if self.opts.update_metadata:
            d['fmts'] = []
        for fmt in fmts:
            try:
                fmtpath = self.write_fmt(book_id, fmt, base_path)
                if fmtpath and self.opts.update_metadata and can_set_metadata(fmt):
                    d['fmts'].append(fmtpath)
            except Exception:
                self.errors[book_id].append(('fmt', (fmt, traceback.format_exc())))
        if self.opts.update_metadata and not d['fmts']:
            self.metadata_data.pop(book_id, None)

    def write_fmt(self, book_id, fmt, base_path):
        fmtpath = base_path + os.extsep + fmt
        written = False
        with lopen(fmtpath, 'w+b') as f:
            try:
                self.db.copy_format_to(book_id, fmt, f)
                written = True
            except NoSuchFormat:
                self.errors[book_id].append(('fmt', (fmt, _('No %s format file present') % fmt.upper())))
        if not written:
            os.remove(fmtpath)
        if written:
            return fmtpath

    def writing_finished(self):
        if not self.opts.update_metadata:
            self.metadata_data = {}
        if not self.metadata_data:
            self.updating_metadata_finished()
            return
        self.pd.title = _('Updating metadata...')
        self.pd.max = len(self.metadata_data)
        self.pd.value = 0

        all_fmts = {path.rpartition(os.extsep)[-1] for d in self.metadata_data.itervalues() for path in d['fmts']}
        plugboards_cache = {fmt:find_plugboard(plugboard_save_to_disk_value, fmt, self.plugboards) for fmt in all_fmts}
        self.server = server = Server() if self.server is None else self.server
        tasks = server.split(list(self.metadata_data))
        self.jobs = set()
        for i, book_ids in enumerate(tasks):
            data = {book_id:self.metadata_data[book_id] for j, book_id in book_ids}
            job = ParallelJob('save_book', 'Save books (job %d of %d)' % (i+1, len(tasks)), lambda x, y:x, args=(data, plugboards_cache))
            self.jobs.add(job)
            server.add_job(job)
        self.do_one = self.do_one_update
        self.do_one_signal.emit()

    def do_one_update(self):
        running = False
        for job in self.jobs:
            if not job.is_finished:
                running = True
                job.update(consume_notifications=False)
                while True:
                    try:
                        book_id = job.notifications.get_nowait()[0]
                        self.pd.value += 1
                        self.pd.msg = self.book_id_data(book_id).title
                    except Empty:
                        break
        if running:
            self.do_one_signal.emit()
        else:
            for job in self.jobs:
                for book_id, fmt, tb in (job.result or ()):
                    self.errors[book_id].append(('metadata', (fmt, tb)))
            self.updating_metadata_finished()

    def updating_metadata_finished(self):
        if DEBUG:
            prints('Saved %d books in %.1f seconds' % (len(self.all_book_ids), time.time() - self.start_time))
        self.pd.close()
        self.pd.deleteLater()
        self.report()
        self.break_cycles()
        if gprefs['show_files_after_save']:
            open_local_file(self.root)

    def format_report(self):
        report = []
        a = report.append

        def indent(text):
            return '\xa0\xa0\xa0\xa0' + '\n\xa0\xa0\xa0\xa0'.join(text.splitlines())

        for book_id, errors in self.errors.iteritems():
            types = {t for t, data in errors}
            title, authors = self.book_id_data(book_id).title, authors_to_string(self.book_id_data(book_id).authors[:1])
            if report:
                a('\n' + ('_'*80) + '\n')
            if 'critical' in types:
                a(_('Failed to save: {0} by {1} to disk, with error:').format(title, authors))
                for t, tb in errors:
                    if t == 'critical':
                        a(indent(tb))
            else:
                errs = defaultdict(list)
                for t, data in errors:
                    errs[t].append(data)
                for fmt, tb in errs['fmt']:
                    a(_('Failed to save the {2} format of: {0} by {1} to disk, with error:').format(title, authors, fmt.upper()))
                    a(indent(tb)), a('')
                for fmt, tb in errs['metadata']:
                    a(_('Failed to update the metadata in the {2} format of: {0} by {1} to disk, with error:').format(title, authors, fmt.upper()))
                    a(indent(tb)), a('')
        return '\n'.join(report)

    def report(self):
        if not self.errors:
            return
        err_types = {e[0] for errors in self.errors.itervalues() for e in errors}
        if err_types == {'metadata'}:
            msg = _('Failed to update metadata in some books, click "Show details" for more information')
            d = warning_dialog
        elif len(self.errors) == len(self.all_book_ids):
            msg = _('Failed to save any books to disk, click "Show details" for more information')
            d = error_dialog
        else:
            msg = _('Failed to save some books to disk, click "Show details" for more information')
            d = warning_dialog
        d(self.parent(), _('Error while saving'), msg, det_msg=self.format_report(), show=True)
