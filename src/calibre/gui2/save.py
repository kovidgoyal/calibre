#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback, errno, os, time, shutil
from collections import namedtuple, defaultdict

from qt.core import QObject, Qt, pyqtSignal

from calibre import prints, force_unicode
from calibre.constants import DEBUG
from calibre.customize.ui import can_set_metadata
from calibre.db.errors import NoSuchFormat
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ptempfile import PersistentTemporaryDirectory, SpooledTemporaryFile
from calibre.gui2 import error_dialog, warning_dialog, gprefs, open_local_file
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.utils.formatter_functions import load_user_template_functions
from calibre.utils.ipc.pool import Pool, Failure
from calibre.library.save_to_disk import sanitize_args, get_path_components, find_plugboard, plugboard_save_to_disk_value
from polyglot.builtins import iteritems, itervalues
from polyglot.queue import Empty

BookId = namedtuple('BookId', 'title authors')


def ensure_unique_components(data):  # {{{
    cmap = defaultdict(set)
    bid_map = {}
    for book_id, (mi, components, fmts) in iteritems(data):
        cmap[tuple(components)].add(book_id)
        bid_map[book_id] = components

    for book_ids in itervalues(cmap):
        if len(book_ids) > 1:
            for i, book_id in enumerate(sorted(book_ids)[1:]):
                suffix = ' (%d)' % (i + 1)
                components = bid_map[book_id]
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

# }}}


class Saver(QObject):

    do_one_signal = pyqtSignal()

    def __init__(self, book_ids, db, opts, root, parent=None, pool=None):
        QObject.__init__(self, parent)
        self.db = db.new_api
        self.plugboards = self.db.pref('plugboards', {})
        self.template_functions = self.db.pref('user_template_functions', [])
        load_user_template_functions('', self.template_functions)
        self.collected_data = {}
        self.errors = defaultdict(list)
        self._book_id_data = {}
        self.all_book_ids = frozenset(book_ids)
        self.pd = ProgressDialog(_('Saving %d books...') % len(self.all_book_ids), _('Collecting metadata...'), min=0, max=0, parent=parent, icon='save.png')
        self.do_one_signal.connect(self.tick, type=Qt.ConnectionType.QueuedConnection)
        self.do_one = self.do_one_collect
        self.ids_to_collect = iter(self.all_book_ids)
        self.tdir = PersistentTemporaryDirectory('_save_to_disk')
        self.pool = pool

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
        if self.pool is not None:
            self.pool.shutdown()
        self.setParent(None)
        self.jobs = self.pool = self.plugboards = self.template_functions = self.collected_data = self.all_book_ids = self.pd = self.db = None  # noqa
        self.deleteLater()

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
        self.collected_data[book_id] = (mi, components, {fmt.lower() for fmt in self.db.formats(book_id)})

    def collection_finished(self):
        self.do_one = self.do_one_write
        ensure_unique_components(self.collected_data)
        self.ids_to_write = iter(self.collected_data)
        self.pd.title = _('Copying files and writing metadata...') if self.opts.update_metadata else _(
            'Copying files...')
        self.pd.max = len(self.collected_data)
        self.pd.value = 0
        if self.opts.update_metadata:
            all_fmts = {fmt for data in itervalues(self.collected_data) for fmt in data[2]}
            plugboards_cache = {fmt:find_plugboard(plugboard_save_to_disk_value, fmt, self.plugboards) for fmt in all_fmts}
            self.pool = Pool(name='SaveToDisk') if self.pool is None else self.pool
            try:
                self.pool.set_common_data(plugboards_cache)
            except Failure as err:
                error_dialog(self.pd, _('Critical failure'), _(
                    'Could not save books to disk, click "Show details" for more information'),
                    det_msg=force_unicode(err.failure_message) + '\n' + force_unicode(err.details), show=True)
                self.pd.canceled = True
        self.do_one_signal.emit()

    def do_one_write(self):
        try:
            book_id = next(self.ids_to_write)
        except StopIteration:
            self.writing_finished()
            return
        if not self.opts.update_metadata:
            self.pd.msg = self.book_id_data(book_id).title
            self.pd.value += 1
        try:
            self.write_book(book_id, *self.collected_data[book_id])
        except Exception:
            self.errors[book_id].append(('critical', traceback.format_exc()))
        self.consume_results()
        self.do_one_signal.emit()

    def consume_results(self):
        if self.pool is not None:
            while True:
                try:
                    worker_result = self.pool.results.get_nowait()
                except Empty:
                    break
                book_id = worker_result.id
                if worker_result.is_terminal_failure:
                    error_dialog(self.pd, _('Critical failure'), _(
                        'The update metadata worker process crashed while processing'
                        ' the book %s. Saving is aborted.') % self.book_id_data(book_id).title, show=True)
                    self.pd.canceled = True
                    return
                result = worker_result.result
                self.pd.value += 1
                self.pd.msg = self.book_id_data(book_id).title
                if result.err is not None:
                    self.errors[book_id].append(('metadata', (None, result.err + '\n' + result.traceback)))
                if result.value:
                    for fmt, tb in result.value:
                        self.errors[book_id].append(('metadata', (fmt, tb)))

    def write_book(self, book_id, mi, components, fmts):
        base_path = os.path.join(self.root, *components)
        base_dir = os.path.dirname(base_path)
        if self.opts.formats and self.opts.formats != 'all':
            asked_formats = {x.lower().strip() for x in self.opts.formats.split(',')}
            fmts = asked_formats.intersection(fmts)
            if not fmts:
                self.errors[book_id].append(('critical', _('Requested formats not available')))
                return

        if not fmts and not self.opts.write_opf and not self.opts.save_cover:
            return

        # On windows python incorrectly raises an access denied exception
        # when trying to create the root of a drive, like C:\
        if os.path.dirname(base_dir) != base_dir:
            try:
                os.makedirs(base_dir)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise

        if self.opts.update_metadata:
            d = {}
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
        if self.opts.update_metadata:
            if d['fmts']:
                try:
                    self.pool(book_id, 'calibre.library.save_to_disk', 'update_serialized_metadata', d)
                except Failure as err:
                    error_dialog(self.pd, _('Critical failure'), _(
                        'Could not save books to disk, click "Show details" for more information'),
                        det_msg=str(err.failure_message) + '\n' + str(err.details), show=True)
                    self.pd.canceled = True
            else:
                self.pd.value += 1
                self.pd.msg = self.book_id_data(book_id).title

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
            self.updating_metadata_finished()
        else:
            self.do_one = self.do_one_update
            self.do_one_signal.emit()

    def do_one_update(self):
        self.consume_results()
        try:
            self.pool.wait_for_tasks(0.1)
        except Failure as err:
            error_dialog(self.pd, _('Critical failure'), _(
                'Could not save books to disk, click "Show details" for more information'),
                det_msg=str(err.failure_message) + '\n' + str(err.details), show=True)
            self.pd.canceled = True
        except RuntimeError:
            pass  # tasks not completed
        else:
            self.consume_results()
            return self.updating_metadata_finished()
        self.do_one_signal.emit()

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
            text = force_unicode(text)
            return '\xa0\xa0\xa0\xa0' + '\n\xa0\xa0\xa0\xa0'.join(text.splitlines())

        for book_id, errors in iteritems(self.errors):
            types = {t for t, data in errors}
            title, authors = self.book_id_data(book_id).title, authors_to_string(self.book_id_data(book_id).authors[:1])
            if report:
                a('\n' + ('_'*70) + '\n')
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
                    if fmt:
                        a(_('Failed to update the metadata in the {2} format of: {0} by {1}, with error:').format(title, authors, fmt.upper()))
                    else:
                        a(_('Failed to update the metadata in all formats of: {0} by {1}, with error:').format(title, authors))
                    a(indent(tb)), a('')
        return '\n'.join(report)

    def report(self):
        if not self.errors:
            return
        err_types = {e[0] for errors in itervalues(self.errors) for e in errors}
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
