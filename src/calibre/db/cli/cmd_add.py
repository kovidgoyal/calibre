#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
from contextlib import contextmanager
from optparse import OptionGroup, OptionValueError

from calibre import prints
from calibre.db.adding import (
    cdb_find_in_dir, cdb_recursive_find, compile_rule, create_format_map,
    run_import_plugins, run_import_plugins_before_metadata
)
from calibre.ebooks.metadata import MetaInformation, string_to_authors
from calibre.ebooks.metadata.book.serialize import read_cover
from calibre.ebooks.metadata.meta import get_metadata, metadata_from_formats
from calibre.ptempfile import TemporaryDirectory
from calibre.srv.changes import books_added
from calibre.utils.localization import canonicalize_lang

readonly = False
version = 0  # change this if you change signature of implementation()


def empty(db, notify_changes, is_remote, args):
    mi = args[0]
    ids, duplicates = db.add_books([(mi, {})])
    if is_remote:
        notify_changes(books_added(ids))
    db.dump_metadata()
    return ids, bool(duplicates)


def book(db, notify_changes, is_remote, args):
    data, fname, fmt, add_duplicates, otitle, oauthors, oisbn, otags, oseries, oseries_index, ocover, oidentifiers, olanguages = args
    with add_ctx(), TemporaryDirectory('add-single') as tdir, run_import_plugins_before_metadata(tdir):
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
            mi.cover = None
            mi.cover_data = ocover

        ids, duplicates = db.add_books(
            [(mi, {fmt: path})], add_duplicates=add_duplicates, run_hooks=False)

    if is_remote:
        notify_changes(books_added(ids))
    db.dump_metadata()
    return ids, bool(duplicates), mi.title


def format_group(db, notify_changes, is_remote, args):
    formats, add_duplicates = args
    with add_ctx(), TemporaryDirectory('add-multiple') as tdir, run_import_plugins_before_metadata(tdir):
        if is_remote:
            paths = []
            for name, data in formats:
                with lopen(os.path.join(tdir, name), 'wb') as f:
                    f.write(data)
                paths.append(f.name)
        else:
            paths = list(formats)
        paths = run_import_plugins(paths)
        mi = metadata_from_formats(paths)
        if mi.title is None:
            return None, set(), False
        ids, dups = db.add_books([(mi, create_format_map(paths))], add_duplicates=add_duplicates, run_hooks=False)
        if is_remote:
            notify_changes(books_added(ids))
        db.dump_metadata()
        return mi.title, ids, bool(dups)


def implementation(db, notify_changes, action, *args):
    is_remote = notify_changes is not None
    func = globals()[action]
    return func(db, notify_changes, is_remote, args)


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


@contextmanager
def add_ctx():
    orig = sys.stdout
    yield
    sys.stdout = orig


def do_add(
    dbctx, paths, one_book_per_directory, recurse, add_duplicates, otitle, oauthors,
    oisbn, otags, oseries, oseries_index, ocover, oidentifiers, olanguages,
    compiled_rules
):
    with add_ctx():
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
            ids, dups, book_title = dbctx.run(
                'add', 'book', dbctx.path(book), os.path.basename(book), fmt, add_duplicates,
                otitle, oauthors, oisbn, otags, oseries, oseries_index, read_cover(ocover) if ocover else None,
                oidentifiers, olanguages
            )
            added_ids |= set(ids)
            if dups:
                file_duplicates.append((book_title, book))

        dir_dups = []
        scanner = cdb_recursive_find if recurse else cdb_find_in_dir
        for dpath in dirs:
            for formats in scanner(dpath, one_book_per_directory, compiled_rules):
                book_title, ids, dups = dbctx.run(
                        'add', 'format_group', tuple(map(dbctx.path, formats)), add_duplicates)
                if book_title is not None:
                    added_ids |= set(ids)
                    if dups:
                        dir_dups.append((book_title, formats))

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
        rule = {'match_type': 'glob', 'query': value, 'action': action}
        try:
            getattr(parser.values, option.dest).append(compile_rule(rule))
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
