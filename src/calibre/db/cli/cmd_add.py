#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
from io import BytesIO
from optparse import OptionGroup, OptionValueError

from calibre import prints
from calibre.db.adding import compile_rule, recursive_import, import_book_directory, import_book_directory_multiple
from calibre.ebooks.metadata import MetaInformation, string_to_authors
from calibre.ebooks.metadata.book.serialize import read_cover
from calibre.ebooks.metadata.meta import get_metadata
from calibre.srv.changes import books_added
from calibre.utils.localization import canonicalize_lang

readonly = False
version = 0  # change this if you change signature of implementation()

def to_stream(data):
    ans = BytesIO(data[1])
    ans.name = data[0]
    return ans


def empty(db, notify_changes, is_remote, args):
    mi = args[0]
    ids, duplicates = db.add_books([(mi, {})])
    if is_remote:
        notify_changes(books_added(ids))
    db.dump_metadata()
    return ids, bool(duplicates)


def book(db, notify_changes, is_remote, args):
    data, fmt, mi, add_duplicates = args
    if is_remote:
        data = to_stream(data)
    ids, duplicates = db.add_books(
        [(mi, {fmt: data})], add_duplicates=add_duplicates)
    if is_remote:
        notify_changes(books_added(ids))
    db.dump_metadata()
    return ids, bool(duplicates)


def add_books(db, notify_changes, is_remote, args):
    books, kwargs = args
    if is_remote:
        books = [(mi, {k:to_stream(v) for k, v in fmt_map.iteritems()}) for mi, fmt_map in books]
    ids, duplicates = db.add_books(books, **kwargs)
    if is_remote:
        notify_changes(books_added(ids))
    db.dump_metadata()
    return ids, [(mi.title, [getattr(x, 'name', '<stream>') for x in format_map.itervalues()]) for mi, format_map in duplicates]


def implementation(db, notify_changes, action, *args):
    is_remote = notify_changes is not None
    func = globals()[action]
    return func(db, notify_changes, is_remote, args)


class DBProxy(object):
    # Allows dbctx to be used with the directory adding API that expects a
    # normal db object. Fortunately that API only calls one method,
    # add_books()

    def __init__(self, dbctx):
        self.new_api = self
        self.dbctx = dbctx

    def add_books(self, books, **kwargs):
        books = [(read_cover(mi), {k:self.dbctx.path(v) for k, v in fmt_map.iteritems()}) for mi, fmt_map in books]
        return self.dbctx.run('add', 'add_books', books, kwargs)


def do_add_empty(
    dbctx, title, authors, isbn, tags, series, series_index, cover, identifiers,
    languages
):
    mi = MetaInformation(None)
    if title is not None:
        mi.title = title
    if authors:
        mi.authors = authors
    if identifiers:
        mi.set_identifiers(identifiers)
    if isbn:
        mi.isbn = isbn
    if tags:
        mi.tags = tags
    if series:
        mi.series, mi.series_index = series, series_index
    if cover:
        mi.cover = cover
    if languages:
        mi.languages = languages
    ids, duplicates = dbctx.run('add', 'empty', read_cover(mi))
    prints(_('Added book ids: %s') % ','.join(map(str, ids)))


def do_add(
    dbctx, paths, one_book_per_directory, recurse, add_duplicates, otitle, oauthors,
    oisbn, otags, oseries, oseries_index, ocover, oidentifiers, olanguages,
    compiled_rules
):
    orig = sys.stdout
    try:
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

        file_duplicates, added_ids = [], set()
        for book in files:
            fmt = os.path.splitext(book)[1]
            fmt = fmt[1:] if fmt else None
            if not fmt:
                continue
            with lopen(book, 'rb') as stream:
                mi = get_metadata(stream, stream_type=fmt, use_libprs_metadata=True)
            if not mi.title:
                mi.title = os.path.splitext(os.path.basename(book))[0]
            if not mi.authors:
                mi.authors = [_('Unknown')]
            if oidentifiers:
                ids = mi.get_identifiers()
                ids.update(oidentifiers)
                mi.set_identifiers(ids)
            for x in ('title', 'authors', 'isbn', 'tags', 'series', 'languages'):
                val = locals()['o' + x]
                if val:
                    setattr(mi, x, val)
            if oseries:
                mi.series_index = oseries_index
            if ocover:
                mi.cover = ocover
                mi.cover_data = (None, None)

            ids, dups = dbctx.run(
                'add', 'book', dbctx.path(book), fmt, read_cover(mi), add_duplicates
            )
            added_ids |= set(ids)
            if dups:
                file_duplicates.append((mi.title, book))

        dir_dups = []
        dbproxy = DBProxy(dbctx)

        for dpath in dirs:
            if recurse:
                dups = recursive_import(
                    dbproxy,
                    dpath,
                    single_book_per_directory=one_book_per_directory,
                    added_ids=added_ids,
                    compiled_rules=compiled_rules,
                    add_duplicates=add_duplicates
                ) or []
            else:
                func = import_book_directory if one_book_per_directory else import_book_directory_multiple
                dups = func(
                    dbproxy,
                    dpath,
                    added_ids=added_ids,
                    compiled_rules=compiled_rules,
                    add_duplicates=add_duplicates
                ) or []
            dir_dups.extend(dups)

        sys.stdout = sys.__stdout__

        if dir_dups or file_duplicates:
            prints(
                _(
                    'The following books were not added as '
                    'they already exist in the database '
                    '(see --duplicates option):'
                ),
                file=sys.stderr
            )
            for title, formats in dir_dups:
                prints(' ', title, file=sys.stderr)
                for path in formats:
                    prints('   ', path)
            if file_duplicates:
                for title, path in file_duplicates:
                    prints(' ', title, file=sys.stderr)
                    prints('   ', path)

        if added_ids:
            prints(_('Added book ids: %s') % (', '.join(map(type(u''), added_ids))))
    finally:
        sys.stdout = orig


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog add [options] file1 file2 file3 ...

Add the specified files as books to the database. You can also specify directories, see
the directory related options below.
'''
        )
    )
    parser.add_option(
        '-d',
        '--duplicates',
        action='store_true',
        default=False,
        help=_(
            'Add books to database even if they already exist. Comparison is done based on book titles.'
        )
    )
    parser.add_option(
        '-e',
        '--empty',
        action='store_true',
        default=False,
        help=_('Add an empty book (a book with no formats)')
    )
    parser.add_option(
        '-t', '--title', default=None, help=_('Set the title of the added book(s)')
    )
    parser.add_option(
        '-a',
        '--authors',
        default=None,
        help=_('Set the authors of the added book(s)')
    )
    parser.add_option(
        '-i', '--isbn', default=None, help=_('Set the ISBN of the added book(s)')
    )
    parser.add_option(
        '-I',
        '--identifier',
        default=[],
        action='append',
        help=_('Set the identifiers for this book, for e.g. -I asin:XXX -I isbn:YYY')
    )
    parser.add_option(
        '-T', '--tags', default=None, help=_('Set the tags of the added book(s)')
    )
    parser.add_option(
        '-s',
        '--series',
        default=None,
        help=_('Set the series of the added book(s)')
    )
    parser.add_option(
        '-S',
        '--series-index',
        default=1.0,
        type=float,
        help=_('Set the series number of the added book(s)')
    )
    parser.add_option(
        '-c',
        '--cover',
        default=None,
        help=_('Path to the cover to use for the added book')
    )
    parser.add_option(
        '-l',
        '--languages',
        default=None,
        help=_(
            'A comma separated list of languages (best to use ISO639 language codes, though some language names may also be recognized)'
        )
    )

    g = OptionGroup(
        parser,
        _('ADDING FROM DIRECTORIES'),
        _(
            'Options to control the adding of books from directories. By default only files that have extensions of known e-book file types are added.'
        )
    )

    def filter_pat(option, opt, value, parser, action):
        try:
            getattr(parser.values, option.dest).append(
                compile_rule({
                    'match_type': 'glob',
                    'query': value,
                    'action': action
                })
            )
        except Exception:
            raise OptionValueError('%r is not a valid filename pattern' % value)

    g.add_option(
        '-1',
        '--one-book-per-directory',
        action='store_true',
        default=False,
        help=_(
            'Assume that each directory has only a single logical book and that all files in it are different e-book formats of that book'
        )
    )
    g.add_option(
        '-r',
        '--recurse',
        action='store_true',
        default=False,
        help=_('Process directories recursively')
    )

    def fadd(opt, action, help):
        g.add_option(
            opt,
            action='callback',
            type='string',
            nargs=1,
            default=[],
            callback=filter_pat,
            dest='filters',
            callback_args=(action, ),
            metavar=_('GLOB PATTERN'),
            help=help
        )

    fadd(
        '--ignore', 'ignore',
        _(
            'A filename (glob) pattern, files matching this pattern will be ignored when scanning directories for files.'
            ' Can be specified multiple times for multiple patterns. For e.g.: *.pdf will ignore all pdf files'
        )
    )
    fadd(
        '--add', 'add',
        _(
            'A filename (glob) pattern, files matching this pattern will be added when scanning directories for files,'
            ' even if they are not of a known e-book file type. Can be specified multiple times for multiple patterns.'
        )
    )
    parser.add_option_group(g)

    return parser


def main(opts, args, dbctx):
    aut = string_to_authors(opts.authors) if opts.authors else []
    tags = [x.strip() for x in opts.tags.split(',')] if opts.tags else []
    lcodes = [canonicalize_lang(x) for x in (opts.languages or '').split(',')]
    lcodes = [x for x in lcodes if x]
    identifiers = (x.partition(':')[::2] for x in opts.identifier)
    identifiers = dict((k.strip(), v.strip()) for k, v in identifiers
                       if k.strip() and v.strip())
    if opts.empty:
        do_add_empty(
            dbctx, opts.title, aut, opts.isbn, tags, opts.series, opts.series_index,
            opts.cover, identifiers, lcodes
        )
        return 0
    if len(args) < 1:
        raise SystemExit(_('You must specify at least one file to add'))
    do_add(
        dbctx, args, opts.one_book_per_directory, opts.recurse, opts.duplicates,
        opts.title, aut, opts.isbn, tags, opts.series, opts.series_index, opts.cover,
        identifiers, lcodes, opts.filters
    )
    return 0
