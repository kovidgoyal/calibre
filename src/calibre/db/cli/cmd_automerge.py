#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
from contextlib import contextmanager
from optparse import OptionGroup, OptionValueError

from calibre import prints
from calibre.db.utils import find_identical_books
from calibre.utils.config import tweaks
from calibre.db.copy_to_library import automerge_book
from calibre.db.adding import (
    cdb_find_in_dir, cdb_recursive_find, compile_rule, create_format_map,
    run_import_plugins, run_import_plugins_before_metadata
)
from calibre.ebooks.metadata import MetaInformation, string_to_authors
from calibre.ebooks.metadata.book.serialize import read_cover, serialize_cover
from calibre.ebooks.metadata.meta import get_metadata, metadata_from_formats
from calibre.ptempfile import TemporaryDirectory
from calibre.srv.changes import books_added
from calibre.utils.localization import canonicalize_lang
from polyglot.builtins import unicode_type


readonly = False
version = 0  # change this if you change signature of implementation()


def book(db, notify_changes, is_remote, args):
    #print(f'ARGS {args}')
    data, fname, fmt, identical_books_data, duplicate_action, automerge_action, preserve_date, identical_books_data, preserve_uuid = args
    with automerge_ctx(), TemporaryDirectory('add-single') as tdir, run_import_plugins_before_metadata(tdir):
        if is_remote:
            with lopen(os.path.join(tdir, fname), 'wb') as f:
                f.write(data[1])
            path = f.name
        else:
            path = data
        path = run_import_plugins([path])[0]
        fmt = os.path.splitext(path)[1]
        fmt = (fmt[1:] if fmt else None) or 'unknown'
        with lopen(path, 'rb') as stream:
            mi = get_metadata(stream, stream_type=fmt, use_libprs_metadata=True)
        if not mi.title:
            mi.title = os.path.splitext(os.path.basename(path))[0]
        if not mi.authors:
            mi.authors = [_('Unknown')]
        # Scanning for dupes can be slow on a large library so
        # only do it if the option is set #author_map, aid_map, title_map, lang_map = data
        if identical_books_data is None:
            identical_books_data = identical_books_data = db.data_for_find_identical_books()
        identical_book_list = find_identical_books(mi, identical_books_data)
        id_added={}
        id_merged={}
        if identical_book_list:  # books with same author and nearly same title exist in db
            if duplicate_action == 'add_formats_to_existing':
                if automerge_action == 'overwrite':
                    #merge with automerge
                    format_map = {}
                    format_map[fmt]=path
                    automerge_book(automerge_action, identical_book_list, mi, identical_book_list, db, format_map)
                    id_merged=identical_book_list
                    if is_remote:
                        notify_changes(books_added(id_merged))
                    return id_added,id_merged,False,mi.title
            return id_added,id_merged,True,mi.title
        #add as ussual
        id_added, duplicates = db.add_books(
            [(mi, {fmt: path})], add_duplicates=True, apply_import_tags=tweaks['add_new_book_tags_when_importing_books'],
            preserve_uuid=preserve_uuid, run_hooks=False)
    if is_remote:
        notify_changes(books_added(id_added))
    db.dump_metadata()
    return id_added,id_merged, bool(duplicates), mi.title


def implementation(db, notify_changes, action, *args):
    is_remote = notify_changes is not None
    func = globals()[action]
    return func(db, notify_changes, is_remote, args)


@contextmanager
def automerge_ctx():
    orig = sys.stdout
    yield
    sys.stdout = orig


def do_automerge(
    dbctx, paths
):
    with automerge_ctx():
        files, dirs = [], []
        for path in paths:
            path = os.path.abspath(path)
            if os.path.isdir(path):
                dirs.append(path)
            else:
                if os.path.exists(path):
                    files.append(path)
                else:
                    prints(path, 'not found')
        file_duplicates, added_ids, merged_ids = [], set(), set()
        identical_books_data = None
        duplicate_action = "add_formats_to_existing"
        automerge_action = "overwrite"
        preserve_date = True
        identical_books_data = None
        preserve_uuid=False
        for book in files:
            fmt = os.path.splitext(book)[1]
            fmt = fmt[1:] if fmt else None
            if not fmt:
                continue
            ids_add,ids_merge, dups, book_title = dbctx.run(
                'automerge', 'book', dbctx.path(book), os.path.basename(
                    book), fmt, identical_books_data, duplicate_action, automerge_action,  preserve_date, identical_books_data, preserve_uuid
            )
            added_ids |= set(ids_add)
            merged_ids |= set(ids_merge)

            if dups:
                file_duplicates.append((book_title, book))

        dir_dups = []

        sys.stdout = sys.__stdout__

        if added_ids:
            prints(_('Added book ids: %s') % (', '.join(map(unicode_type, added_ids))))
        if merged_ids:
            prints(_('Updated book ids: %s') % (', '.join(map(unicode_type, merged_ids))))


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog automerge file1 file2 file3 ...
automerge the specifies files as books to the database. 
Search the library for the specified book and decide:
- To update its format and language on the library if the book is newer than the existing one in the library.
- To add to the library if the format and language does not exist.
- To discard action if none of the above.
'''
        )
    )
    return parser


def main(opts, args, dbctx):
    if len(args) < 1:
        raise SystemExit(_('You must specify at least one file to automerge'))
    do_automerge(
        dbctx, args
    )
    return 0
