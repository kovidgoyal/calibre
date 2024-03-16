#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import re
import shutil
import sys
import time
import traceback
from contextlib import suppress
from operator import itemgetter
from threading import Thread

from calibre import force_unicode, isbytestring
from calibre.constants import filesystem_encoding, iswindows
from calibre.db.backend import DB, DBPrefs
from calibre.db.constants import METADATA_FILE_NAME, TRASH_DIR_NAME, NOTES_DIR_NAME, NOTES_DB_NAME
from calibre.db.cache import Cache
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.date import utcfromtimestamp

NON_EBOOK_EXTENSIONS = frozenset((
    'jpg', 'jpeg', 'gif', 'png', 'bmp',
    'opf', 'swp', 'swo'
))


def read_opf(dirpath, read_annotations=True):
    opf = os.path.join(dirpath, METADATA_FILE_NAME)
    parsed_opf = OPF(opf, basedir=dirpath)
    mi = parsed_opf.to_book_metadata()
    annotations = tuple(parsed_opf.read_annotations()) if read_annotations else ()
    timestamp = os.path.getmtime(opf)
    return mi, timestamp, annotations


def is_ebook_file(filename):
    ext = os.path.splitext(filename)[1]
    if not ext:
        return False
    ext = ext[1:].lower()
    bad_ext_pat = re.compile(r'[^a-z0-9_]+')
    if ext in NON_EBOOK_EXTENSIONS or bad_ext_pat.search(ext) is not None:
        return False
    return True


class Restorer(Cache):

    def __init__(self, library_path, default_prefs=None, restore_all_prefs=False, progress_callback=lambda x, y:True):
        backend = DB(
            library_path, default_prefs=default_prefs, restore_all_prefs=restore_all_prefs, progress_callback=progress_callback
        )
        Cache.__init__(self, backend)
        for x in ('update_path', 'mark_as_dirty'):
            setattr(self, x, self.no_op)
            setattr(self, '_' + x, self.no_op)
        self.init()

    def no_op(self, *args, **kwargs):
        pass


class Restore(Thread):

    def __init__(self, library_path, progress_callback=None):
        super().__init__()
        if isbytestring(library_path):
            library_path = library_path.decode(filesystem_encoding)
        self.src_library_path = os.path.abspath(library_path)
        self.progress_callback = progress_callback
        self.db_id_regexp = re.compile(r'^.* \((\d+)\)$')
        if not callable(self.progress_callback):
            self.progress_callback = lambda x, y: x
        self.dirs = []
        self.failed_dirs = []
        self.books = []
        self.conflicting_custom_cols = {}
        self.failed_restores = []
        self.mismatched_dirs = []
        self.notes_errors = []
        self.successes = 0
        self.tb = None
        self.link_maps = {}

    @property
    def errors_occurred(self):
        return (self.failed_dirs or self.mismatched_dirs or
                self.conflicting_custom_cols or self.failed_restores or self.notes_errors)

    @property
    def report(self):
        ans = ''
        failures = list(self.failed_dirs) + [(x['dirpath'], tb) for x, tb in
                self.failed_restores]
        if failures:
            ans += 'Failed to restore the books in the following folders:\n'
            for dirpath, tb in failures:
                ans += '\t' + force_unicode(dirpath, filesystem_encoding) + ' with error:\n'
                ans += '\n'.join('\t\t'+force_unicode(x, filesystem_encoding) for x in tb.splitlines())
                ans += '\n\n'

        if self.conflicting_custom_cols:
            ans += '\n\n'
            ans += 'The following custom columns have conflicting definitions ' \
                    'and were not fully restored:\n'
            for x in self.conflicting_custom_cols:
                ans += '\t#'+x+'\n'
                ans += '\tused:\t%s, %s, %s, %s\n'%(self.custom_columns[x][1],
                                                    self.custom_columns[x][2],
                                                    self.custom_columns[x][3],
                                                    self.custom_columns[x][5])
                for coldef in self.conflicting_custom_cols[x]:
                    ans += '\tother:\t%s, %s, %s, %s\n'%(coldef[1], coldef[2],
                                                         coldef[3], coldef[5])

        if self.mismatched_dirs:
            ans += '\n\n'
            ans += 'The following folders were ignored:\n'
            for x in self.mismatched_dirs:
                ans += '\t' + force_unicode(x, filesystem_encoding) + '\n'

        if self.notes_errors:
            ans += '\n\n'
            ans += 'Failed to restore notes for the following items:\n'
            for x in self.notes_errors:
                ans += '\t' + x
        return ans

    def run(self):
        try:
            basedir = os.path.dirname(self.src_library_path)
            try:
                tdir = TemporaryDirectory('_rlib', dir=basedir)
                tdir.__enter__()
            except OSError:
                # In case we dont have permissions to create directories in the
                # parent folder of the src library
                tdir = TemporaryDirectory('_rlib')

            with tdir as tdir:
                self.library_path = tdir
                self.scan_library()
                if not self.load_preferences():
                    # Something went wrong with preferences restore. Start over
                    # with a new database and attempt to rebuild the structure
                    # from the metadata in the opf
                    dbpath = os.path.join(self.library_path, 'metadata.db')
                    if os.path.exists(dbpath):
                        os.remove(dbpath)
                    self.create_cc_metadata()
                self.restore_books()
                if self.successes == 0 and len(self.dirs) > 0:
                    raise Exception('Something bad happened')
                self.replace_db()
        except:
            self.tb = traceback.format_exc()
            if self.failed_dirs:
                for x in self.failed_dirs:
                    for (dirpath, tb) in self.failed_dirs:
                        self.tb += f'\n\n-------------\nFailed to restore: {dirpath}\n{tb}'
            if self.failed_restores:
                for (book, tb) in self.failed_restores:
                    self.tb += f'\n\n-------------\nFailed to restore: {book["path"]}\n{tb}'

    def load_preferences(self):
        self.progress_callback(None, 1)
        self.progress_callback(_('Starting restoring preferences and column metadata'), 0)
        prefs_path = os.path.join(self.src_library_path, 'metadata_db_prefs_backup.json')
        if not os.path.exists(prefs_path):
            self.progress_callback(_('Cannot restore preferences. Backup file not found.'), 1)
            return False
        try:
            prefs = DBPrefs.read_serialized(self.src_library_path, recreate_prefs=False)
            db = Restorer(self.library_path, default_prefs=prefs,
                                 restore_all_prefs=True,
                                 progress_callback=self.progress_callback)
            db.close()
            self.progress_callback(None, 1)
            if 'field_metadata' in prefs:
                self.progress_callback(_('Finished restoring preferences and column metadata'), 1)
                return True
            self.progress_callback(_('Finished restoring preferences'), 1)
            return False
        except:
            traceback.print_exc()
            self.progress_callback(None, 1)
            self.progress_callback(_('Restoring preferences and column metadata failed'), 0)
        return False

    def scan_library(self):
        for dirpath, dirnames, filenames in os.walk(self.src_library_path):
            with suppress(ValueError):
                dirnames.remove(TRASH_DIR_NAME)
            leaf = os.path.basename(dirpath)
            m = self.db_id_regexp.search(leaf)
            if m is None or METADATA_FILE_NAME not in filenames:
                continue
            self.dirs.append((dirpath, list(dirnames), filenames, m.group(1)))
            del dirnames[:]

        self.progress_callback(None, len(self.dirs))
        for i, (dirpath, dirnames, filenames, book_id) in enumerate(self.dirs):
            try:
                self.process_dir(dirpath, dirnames, filenames, book_id)
            except Exception:
                self.failed_dirs.append((dirpath, traceback.format_exc()))
                traceback.print_exc()
            self.progress_callback(_('Processed') + ' ' + dirpath, i+1)

    def process_dir(self, dirpath, dirnames, filenames, book_id):
        book_id = int(book_id)
        def safe_mtime(path):
            with suppress(OSError):
                return os.path.getmtime(path)
            return sys.maxsize

        filenames.sort(key=lambda f: safe_mtime(os.path.join(dirpath, f)))
        fmt_map = {}
        fmts, formats, sizes, names = [], [], [], []
        for x in filenames:
            if is_ebook_file(x):
                fmt = os.path.splitext(x)[1][1:].upper()
                if fmt and fmt_map.setdefault(fmt, x) is x:
                    formats.append(x)
                    sizes.append(os.path.getsize(os.path.join(dirpath, x)))
                    names.append(os.path.splitext(x)[0])
                    fmts.append(fmt)

        mi, timestamp, annotations = read_opf(dirpath)
        path = os.path.relpath(dirpath, self.src_library_path).replace(os.sep, '/')

        if int(mi.application_id) == book_id:
            self.books.append({
                'mi': mi,
                'timestamp': timestamp,
                'formats': list(zip(fmts, sizes, names)),
                'id': book_id,
                'dirpath': dirpath,
                'path': path,
                'annotations': annotations
            })
        else:
            self.mismatched_dirs.append(dirpath)

        alm = mi.get('link_maps', {})
        for field, lmap in alm.items():
            dest = self.link_maps.setdefault(field, {})
            for item, link in lmap.items():
                existing_link, timestamp = dest.get(item, (None, None))
                if existing_link is None or existing_link != link and timestamp < mi.timestamp:
                    dest[item] = link, mi.timestamp

    def create_cc_metadata(self):
        self.books.sort(key=itemgetter('timestamp'))
        self.custom_columns = {}
        fields = ('label', 'name', 'datatype', 'is_multiple', 'is_editable',
                    'display')
        for b in self.books:
            for key in b['mi'].custom_field_keys():
                cfm = b['mi'].metadata_for_field(key)
                args = []
                for x in fields:
                    if x in cfm:
                        if x == 'is_multiple':
                            args.append(bool(cfm[x]))
                        else:
                            args.append(cfm[x])
                if len(args) == len(fields):
                    # TODO: Do series type columns need special handling?
                    label = cfm['label']
                    if label in self.custom_columns and args != self.custom_columns[label]:
                        if label not in self.conflicting_custom_cols:
                            self.conflicting_custom_cols[label] = []
                        if self.custom_columns[label] not in self.conflicting_custom_cols[label]:
                            self.conflicting_custom_cols[label].append(self.custom_columns[label])
                    self.custom_columns[label] = args

        db = Restorer(self.library_path)
        self.progress_callback(None, len(self.custom_columns))
        if len(self.custom_columns):
            for i, args in enumerate(self.custom_columns.values()):
                db.create_custom_column(*args)
                self.progress_callback(_('Creating custom column ')+args[0], i+1)
        db.close()

    def restore_books(self):
        self.progress_callback(None, len(self.books))
        self.books.sort(key=itemgetter('id'))

        notes_dest = os.path.join(self.library_path, NOTES_DIR_NAME)
        if os.path.exists(notes_dest):  # created by load_preferences()
            shutil.rmtree(notes_dest)
        shutil.copytree(os.path.join(self.src_library_path, NOTES_DIR_NAME), notes_dest)
        with suppress(FileNotFoundError):
            os.remove(os.path.join(notes_dest, NOTES_DB_NAME))
        db = Restorer(self.library_path)

        for i, book in enumerate(self.books):
            try:
                db.restore_book(book['id'], book['mi'], utcfromtimestamp(book['timestamp']), book['path'], book['formats'], book['annotations'])
                self.successes += 1
            except:
                self.failed_restores.append((book, traceback.format_exc()))
                traceback.print_exc()
            self.progress_callback(book['mi'].title, i+1)

        for field, lmap in self.link_maps.items():
            with suppress(Exception):
                db.set_link_map(field, {k:v[0] for k, v in lmap.items()})
        self.notes_errors = db.backend.restore_notes(self.progress_callback)
        db.close()

    def replace_db(self):
        dbpath = os.path.join(self.src_library_path, 'metadata.db')
        ndbpath = os.path.join(self.library_path, 'metadata.db')
        sleep_time = 30 if iswindows else 0

        save_path = self.olddb = os.path.splitext(dbpath)[0]+'_pre_restore.db'
        if os.path.exists(save_path):
            os.remove(save_path)
        if os.path.exists(dbpath):
            try:
                os.replace(dbpath, save_path)
            except OSError:
                if iswindows:
                    time.sleep(sleep_time)  # Wait a little for dropbox or the antivirus or whatever to release the file
                shutil.copyfile(dbpath, save_path)
                os.remove(dbpath)
        shutil.copyfile(ndbpath, dbpath)

        old_notes_path = os.path.join(self.src_library_path, NOTES_DIR_NAME)
        new_notes_path = os.path.join(self.library_path, NOTES_DIR_NAME)
        temp = old_notes_path + '-staging'
        try:
            shutil.move(new_notes_path, temp)
        except OSError:
            if not iswindows:
                raise
            time.sleep(sleep_time)  # Wait a little for dropbox or the antivirus or whatever to release the file
            shutil.move(new_notes_path, temp)
        try:
            shutil.rmtree(old_notes_path)
        except OSError:
            if not iswindows:
                raise
            time.sleep(sleep_time)  # Wait a little for dropbox or the antivirus or whatever to release the file
            shutil.rmtree(old_notes_path)
        try:
            shutil.move(temp, old_notes_path)
        except OSError:
            if not iswindows:
                raise
            time.sleep(sleep_time)  # Wait a little for dropbox or the antivirus or whatever to release the file
            shutil.move(temp, old_notes_path)
