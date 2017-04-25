#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, time, re
from collections import defaultdict
from future_builtins import map

from calibre import prints
from calibre.constants import iswindows, isosx, filesystem_encoding
from calibre.ebooks import BOOK_EXTENSIONS


def splitext(path):
    key, ext = os.path.splitext(path)
    return key, ext[1:].lower()


def formats_ok(formats):
    return len(formats) > 0


def path_ok(path):
    return not os.path.isdir(path) and os.access(path, os.R_OK)


def compile_glob(pat):
    import fnmatch
    return re.compile(fnmatch.translate(pat), flags=re.I)


def compile_rule(rule):
    mt = rule['match_type']
    if 'with' in mt:
        q = icu_lower(rule['query'])
        if 'startswith' in mt:
            func = lambda filename: icu_lower(filename).startswith(q)
        else:
            func = lambda filename: icu_lower(filename).endswith(q)
    elif 'glob' in mt:
        q = compile_glob(rule['query'])
        func  = lambda filename: q.match(filename) is not None
    else:
        q = re.compile(rule['query'])
        func  = lambda filename: q.match(filename) is not None
    ans = func
    if mt.startswith('not_'):
        ans = lambda filename: not func(filename)
    return ans, rule['action'] == 'add'


def filter_filename(compiled_rules, filename):
    for q, action in compiled_rules:
        if q(filename):
            return action


_metadata_extensions = None


def metadata_extensions():
    # Set of all known book extensions + OPF (the OPF is used to read metadata,
    # but not actually added)
    global _metadata_extensions
    if _metadata_extensions is None:
        _metadata_extensions =  frozenset(map(unicode, BOOK_EXTENSIONS)) | {'opf'}
    return _metadata_extensions


if iswindows or isosx:
    unicode_listdir = os.listdir
else:
    def unicode_listdir(root):
        root = root.encode(filesystem_encoding)
        for x in os.listdir(root):
            try:
                yield x.decode(filesystem_encoding)
            except UnicodeDecodeError:
                prints('Ignoring un-decodable file:', x)


def listdir(root, sort_by_mtime=False):
    items = (os.path.join(root, x) for x in unicode_listdir(root))
    if sort_by_mtime:
        def safe_mtime(x):
            try:
                return os.path.getmtime(x)
            except EnvironmentError:
                return time.time()
        items = sorted(items, key=safe_mtime)

    for path in items:
        if path_ok(path):
            yield path


def allow_path(path, ext, compiled_rules):
    ans = filter_filename(compiled_rules, os.path.basename(path))
    if ans is None:
        ans = ext in metadata_extensions()
    return ans


def find_books_in_directory(dirpath, single_book_per_directory, compiled_rules=(), listdir_impl=listdir):
    dirpath = os.path.abspath(dirpath)
    if single_book_per_directory:
        formats = {}
        for path in listdir_impl(dirpath):
            key, ext = splitext(path)
            if allow_path(path, ext, compiled_rules):
                formats[ext] = path
        if formats_ok(formats):
            yield list(formats.itervalues())
    else:
        books = defaultdict(dict)
        for path in listdir_impl(dirpath, sort_by_mtime=True):
            key, ext = splitext(path)
            if allow_path(path, ext, compiled_rules):
                books[icu_lower(key) if isinstance(key, unicode) else key.lower()][ext] = path

        for formats in books.itervalues():
            if formats_ok(formats):
                yield list(formats.itervalues())


def import_book_directory_multiple(db, dirpath, callback=None,
        added_ids=None, compiled_rules=()):
    from calibre.ebooks.metadata.meta import metadata_from_formats

    duplicates = []
    for formats in find_books_in_directory(dirpath, False, compiled_rules=compiled_rules):
        mi = metadata_from_formats(formats)
        if mi.title is None:
            continue
        if db.has_book(mi):
            duplicates.append((mi, formats))
            continue
        book_id = db.import_book(mi, formats)
        if added_ids is not None:
            added_ids.add(book_id)
        if callable(callback):
            if callback(mi.title):
                break
    return duplicates


def import_book_directory(db, dirpath, callback=None, added_ids=None, compiled_rules=()):
    from calibre.ebooks.metadata.meta import metadata_from_formats
    dirpath = os.path.abspath(dirpath)
    formats = None
    for formats in find_books_in_directory(dirpath, True, compiled_rules=compiled_rules):
        break
    if not formats:
        return
    mi = metadata_from_formats(formats)
    if mi.title is None:
        return
    if db.has_book(mi):
        return [(mi, formats)]
    book_id = db.import_book(mi, formats)
    if added_ids is not None:
        added_ids.add(book_id)
    if callable(callback):
        callback(mi.title)


def recursive_import(db, root, single_book_per_directory=True,
        callback=None, added_ids=None, compiled_rules=()):
    root = os.path.abspath(root)
    duplicates  = []
    for dirpath in os.walk(root):
        res = (import_book_directory(db, dirpath[0], callback=callback,
            added_ids=added_ids, compiled_rules=compiled_rules) if single_book_per_directory else
            import_book_directory_multiple(db, dirpath[0],
                callback=callback, added_ids=added_ids, compiled_rules=compiled_rules))
        if res is not None:
            duplicates.extend(res)
        if callable(callback):
            if callback(''):
                break
    return duplicates


def add_catalog(cache, path, title, dbapi=None):
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.utils.date import utcnow

    fmt = os.path.splitext(path)[1][1:].lower()
    new_book_added = False
    with lopen(path, 'rb') as stream:
        with cache.write_lock:
            matches = cache._search('title:="%s" and tags:="%s"' % (title.replace('"', '\\"'), _('Catalog')), None)
            db_id = None
            if matches:
                db_id = list(matches)[0]
            try:
                mi = get_metadata(stream, fmt)
                mi.authors = ['calibre']
            except:
                mi = Metadata(title, ['calibre'])
            mi.title, mi.authors = title, ['calibre']
            mi.author_sort = 'calibre'  # The MOBI/AZW3 format sets author sort to date
            mi.tags = [_('Catalog')]
            mi.pubdate = mi.timestamp = utcnow()
            if fmt == 'mobi':
                mi.cover, mi.cover_data = None, (None, None)
            if db_id is None:
                db_id = cache._create_book_entry(mi, apply_import_tags=False)
                new_book_added = True
            else:
                cache._set_metadata(db_id, mi)
        cache.add_format(db_id, fmt, stream, dbapi=dbapi)  # Cant keep write lock since post-import hooks might run

    return db_id, new_book_added


def add_news(cache, path, arg, dbapi=None):
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.utils.date import utcnow

    fmt = os.path.splitext(getattr(path, 'name', path))[1][1:].lower()
    stream = path if hasattr(path, 'read') else lopen(path, 'rb')
    stream.seek(0)
    mi = get_metadata(stream, fmt, use_libprs_metadata=False,
            force_read_metadata=True)
    # Force the author to calibre as the auto delete of old news checks for
    # both the author==calibre and the tag News
    mi.authors = ['calibre']
    stream.seek(0)
    with cache.write_lock:
        if mi.series_index is None:
            mi.series_index = cache._get_next_series_num_for(mi.series)
        mi.tags = [_('News')]
        if arg['add_title_tag']:
            mi.tags += [arg['title']]
        if arg['custom_tags']:
            mi.tags += arg['custom_tags']
        if mi.pubdate is None:
            mi.pubdate = utcnow()
        if mi.timestamp is None:
            mi.timestamp = utcnow()

        db_id = cache._create_book_entry(mi, apply_import_tags=False)
    cache.add_format(db_id, fmt, stream, dbapi=dbapi)  # Cant keep write lock since post-import hooks might run

    if not hasattr(path, 'read'):
        stream.close()
    return db_id
