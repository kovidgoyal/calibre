#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, traceback

from calibre import isbytestring
from calibre.constants import filesystem_encoding
from calibre.ebooks import BOOK_EXTENSIONS

EBOOK_EXTENSIONS = frozenset(BOOK_EXTENSIONS)

NORMALS = frozenset(['metadata.opf', 'cover.jpg'])

CHECKS = [('invalid_titles',    _('Invalid titles')),
          ('extra_titles',      _('Extra titles')),
          ('invalid_authors',   _('Invalid authors')),
          ('extra_authors',     _('Extra authors')),
          ('missing_formats',   _('Missing book formats')),
          ('extra_formats',     _('Extra book formats')),
          ('extra_files',       _('Unknown files in book')),
          ('failed_folders',    _('Folders raising exception'))
      ]


class CheckLibrary(object):

    def __init__(self, library_path, db):
        if isbytestring(library_path):
            library_path = library_path.decode(filesystem_encoding)
        self.src_library_path = os.path.abspath(library_path)
        self.db = db

        self.is_case_sensitive = db.is_case_sensitive

        self.all_authors = frozenset([x[1] for x in db.all_authors()])
        self.all_ids = frozenset([id for id in db.all_ids()])
        self.all_dbpaths = frozenset(self.dbpath(id) for id in self.all_ids)
        self.all_lc_dbpaths = frozenset([f.lower() for f in self.all_dbpaths])

        self.db_id_regexp = re.compile(r'^.* \((\d+)\)$')
        self.bad_ext_pat = re.compile(r'[^a-z]+')

        self.dirs = []
        self.book_dirs = []

        self.potential_authors = {}
        self.invalid_authors = []
        self.extra_authors = []

        self.invalid_titles = []
        self.extra_titles = []

        self.unknown_book_files = []
        self.missing_formats = []
        self.extra_formats = []
        self.extra_files = []


    def dbpath(self, id):
        return self.db.path(id, index_is_id=True)

    @property
    def errors_occurred(self):
        return self.failed_folders or self.mismatched_dirs or \
                self.conflicting_custom_cols or self.failed_restores

    def scan_library(self):
        lib = self.src_library_path
        for auth_dir in os.listdir(lib):
            auth_path = os.path.join(lib, auth_dir)
            # First check: author must be a directory
            if not os.path.isdir(auth_path):
                self.invalid_authors.append((auth_dir, auth_dir, []))
                continue

            self.potential_authors[auth_dir] = {}

            # Look for titles in the author directories
            found_titles = False
            for title_dir in os.listdir(auth_path):
                title_path = os.path.join(auth_path, title_dir)
                db_path = os.path.join(auth_dir, title_dir)
                m = self.db_id_regexp.search(title_dir)
                # Second check: title must have an ID and must be a directory
                if m is None or not os.path.isdir(title_path):
                    self.invalid_titles.append((auth_dir, db_path, [title_dir]))
                    continue

                id = m.group(1)
                # Third check: the id must be in the DB and the paths must match
                if self.is_case_sensitive:
                    if int(id) not in self.all_ids or \
                            db_path not in self.all_dbpaths:
                        self.extra_titles.append((title_dir, db_path, []))
                        continue
                else:
                    if int(id) not in self.all_ids or \
                            db_path.lower() not in self.all_lc_dbpaths:
                        self.extra_titles.append((title_dir, db_path, []))
                        continue

                # Record the book to check its formats
                self.book_dirs.append((db_path, title_dir, id))
                found_titles = True

            # Fourth check: author directories that contain no titles
            if not found_titles:
                self.extra_authors.append((auth_dir, auth_dir, []))

        for x in self.book_dirs:
            try:
                self.process_book(lib, x)
            except:
                traceback.print_exc()
                # Sort-of check: exception processing directory
                self.failed_folders.append((title_path, traceback.format_exc(), []))

    def is_ebook_file(self, filename):
        ext = os.path.splitext(filename)[1]
        if not ext:
            return False
        ext = ext[1:].lower()
        if ext not in EBOOK_EXTENSIONS or \
                self.bad_ext_pat.search(ext) is not None:
            return False
        return True

    def process_book(self, lib, book_info):
        (db_path, title_dir, book_id) = book_info
        filenames = frozenset(os.listdir(os.path.join(lib, db_path)))
        book_id = int(book_id)
        formats = frozenset(filter(self.is_ebook_file, filenames))
        book_formats = frozenset([x[0]+'.'+x[1].lower() for x in
                            self.db.format_files(book_id, index_is_id=True)])

        if self.is_case_sensitive:
            unknowns = frozenset(filenames-formats-NORMALS)
            # Check: any books that aren't formats or normally there?
            if unknowns:
                self.extra_files.append((title_dir, db_path, unknowns))

            # Check: any book formats that should be there?
            missing = book_formats - formats
            if missing:
                self.missing_formats.append((title_dir, db_path, missing))

            # Check: any book formats that shouldn't be there?
            extra = formats - book_formats
            if extra:
                self.extra_formats.append((title_dir, db_path, extra))
        else:
            def lc_map(fnames, fset):
                m = {}
                for f in fnames:
                    m[f.lower()] = f
                return [m[f] for f in fset]

            filenames_lc = frozenset([f.lower() for f in filenames])
            formats_lc = frozenset([f.lower() for f in formats])
            unknowns = frozenset(filenames_lc-formats_lc-NORMALS)
            # Check: any books that aren't formats or normally there?
            if unknowns:
                self.extra_files.append((title_dir, db_path,
                                         lc_map(filenames, unknowns)))

            book_formats_lc = frozenset([f.lower() for f in book_formats])
            # Check: any book formats that should be there?
            missing = book_formats_lc - formats_lc
            if missing:
                self.missing_formats.append((title_dir, db_path,
                                             lc_map(book_formats, missing)))

            # Check: any book formats that shouldn't be there?
            extra = formats_lc - book_formats_lc
            if extra:
                self.extra_formats.append((title_dir, db_path,
                                           lc_map(formats, extra)))
