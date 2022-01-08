#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import os
import sys
from contextlib import contextmanager
from optparse import OptionGroup, OptionValueError

from calibre import prints
from calibre.db.adding import (
    cdb_find_in_dir, cdb_recursive_find, compile_rule, create_format_map,
    run_import_plugins, run_import_plugins_before_metadata
)
from calibre.db.utils import find_identical_books
from calibre.ebooks.metadata import MetaInformation, string_to_authors
from calibre.ebooks.metadata.book.serialize import read_cover, serialize_cover
from calibre.ebooks.metadata.meta import get_metadata, metadata_from_formats
from calibre.ptempfile import TemporaryDirectory
from calibre.srv.changes import books_added, formats_added
from calibre.utils.localization import canonicalize_lang
from calibre.utils.short_uuid import uuid4

readonly = False
version = 0  # change this if you change signature of implementation()


def empty(db, notify_changes, is_remote, args):
    mi = args[0]
    ids, duplicates = db.add_books([(mi, {})])
    if is_remote:
        notify_changes(books_added(ids))
    db.dump_metadata()
    return ids, bool(duplicates)


def cached_identical_book_data(db, request_id):
    key = db.library_id, request_id
    if getattr(cached_identical_book_data, 'key', None) != key:
        cached_identical_book_data.key = key
        cached_identical_book_data.ans = db.data_for_find_identical_books()
    return cached_identical_book_data.ans


def do_adding(db, request_id, notify_changes, is_remote, mi, format_map, add_duplicates, oautomerge):
    identical_book_list, added_ids, updated_ids = set(), set(), set()
    duplicates = []
    identical_books_data = None

    def add_format(book_id, fmt):
        db.add_format(book_id, fmt, format_map[fmt], replace=True, run_hooks=False)
        updated_ids.add(book_id)

    def add_book():
        nonlocal added_ids
        added_ids_, duplicates_ = db.add_books(
            [(mi, format_map)], add_duplicates=True, run_hooks=False)
        added_ids |= set(added_ids_)
        duplicates.extend(duplicates_)

    if oautomerge != 'disabled' or not add_duplicates:
        identical_books_data = cached_identical_book_data(db, request_id)
        identical_book_list = find_identical_books(mi, identical_books_data)

    if oautomerge != 'disabled':
        if identical_book_list:
            needs_add = False
            duplicated_formats = set()
            for book_id in identical_book_list:
                book_formats = {q.upper() for q in db.formats(book_id)}
                input_formats = {q.upper():q for q in format_map}
                common_formats = book_formats & set(input_formats)
                if not common_formats:
                    for x in input_formats:
                        add_format(book_id, input_formats[x])
                else:
                    new_formats = set(input_formats) - book_formats
                    if new_formats:
                        for x in new_formats:
                            add_format(book_id, input_formats[x])
                    if oautomerge == 'overwrite':
                        for x in common_formats:
                            add_format(book_id, input_formats[x])
                    elif oautomerge == 'ignore':
                        for x in common_formats:
                            duplicated_formats.add(input_formats[x])
                    elif oautomerge == 'new_record':
                        needs_add = True
            if needs_add:
                add_book()
            if duplicated_formats:
                duplicates.append((mi, {x: format_map[x] for x in duplicated_formats}))
        else:
            add_book()
    else:
        if identical_book_list:
            duplicates.append((mi, format_map))
        else:
            add_book()
    if added_ids and identical_books_data is not None:
        for book_id in added_ids:
            db.update_data_for_find_identical_books(book_id, identical_books_data)

    if is_remote:
        notify_changes(books_added(added_ids))
        if updated_ids:
            notify_changes(formats_added({book_id: tuple(format_map) for book_id in updated_ids}))
    db.dump_metadata()
    return added_ids, updated_ids, duplicates


def book(db, notify_changes, is_remote, args):
    data, fname, fmt, add_duplicates, otitle, oauthors, oisbn, otags, oseries, oseries_index, ocover, oidentifiers, olanguages, oautomerge, request_id = args
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

        identical_book_list, added_ids, updated_ids = set(), set(), set()
        duplicates = []
        identical_books_data = None
        added_ids, updated_ids, duplicates = do_adding(
            db, request_id, notify_changes, is_remote, mi, {fmt: path}, add_duplicates, oautomerge)

    return added_ids, updated_ids, bool(duplicates), mi.title


def format_group(db, notify_changes, is_remote, args):
    formats, add_duplicates, oautomerge, request_id, cover_data = args
    with add_ctx(), TemporaryDirectory('add-multiple') as tdir, run_import_plugins_before_metadata(tdir):
        updated_ids = {}
        if is_remote:
            paths = []
            for name, data in formats:
                with lopen(os.path.join(tdir, os.path.basename(name)), 'wb') as f:
                    f.write(data)
                paths.append(f.name)
        else:
            paths = list(formats)
        paths = run_import_plugins(paths)
        mi = metadata_from_formats(paths)
        if mi.title is None:
            return None, set(), set(), False
        if cover_data and not mi.cover_data or not mi.cover_data[1]:
            mi.cover_data = 'jpeg', cover_data
        format_map = create_format_map(paths)
        added_ids, updated_ids, duplicates = do_adding(
            db, request_id, notify_changes, is_remote, mi, format_map, add_duplicates, oautomerge)
        return mi.title, set(added_ids), set(updated_ids), bool(duplicates)


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
    compiled_rules, oautomerge
):
    request_id = uuid4()
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

        file_duplicates, added_ids, merged_ids = [], set(), set()
        for book in files:
            fmt = os.path.splitext(book)[1]
            fmt = fmt[1:] if fmt else None
            if not fmt:
                continue
            aids, mids, dups, book_title = dbctx.run(
                'add', 'book', dbctx.path(book), os.path.basename(book), fmt, add_duplicates,
                otitle, oauthors, oisbn, otags, oseries, oseries_index, serialize_cover(ocover) if ocover else None,
                oidentifiers, olanguages, oautomerge, request_id
            )
            added_ids |= set(aids)
            merged_ids |= set(mids)

            if dups:
                file_duplicates.append((book_title, book))

        dir_dups = []
        scanner = cdb_recursive_find if recurse else cdb_find_in_dir
        for dpath in dirs:
            for formats in scanner(dpath, one_book_per_directory, compiled_rules):
                cover_data = None
                for fmt in formats:
                    if fmt.lower().endswith('.opf'):
                        with lopen(fmt, 'rb') as f:
                            mi = get_metadata(f, stream_type='opf')
                            if mi.cover_data and mi.cover_data[1]:
                                cover_data = mi.cover_data[1]
                            elif mi.cover:
                                try:
                                    with lopen(mi.cover, 'rb') as f:
                                        cover_data = f.read()
                                except OSError:
                                    pass

                book_title, ids, mids, dups = dbctx.run(
                        'add', 'format_group', tuple(map(dbctx.path, formats)), add_duplicates, oautomerge, request_id, cover_data)
                if book_title is not None:
                    added_ids |= set(ids)
                    merged_ids |= set(mids)
                    if dups:
                        dir_dups.append((book_title, formats))

        sys.stdout = sys.__stdout__

        if dir_dups or file_duplicates:
            prints(
                _(
                    'The following books were not added as '
                    'they already exist in the database '
                    '(see --duplicates option or --automerge option):'
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
            prints(_('Added book ids: %s') % (', '.join(map(str, added_ids))))
        if merged_ids:
            prints(_('Merged book ids: %s') % (', '.join(map(str, merged_ids))))


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog add [options] file1 file2 file3 ...

Add the specified files as books to the database. You can also specify folders, see
the folder related options below.
'''
        )
    )
    parser.add_option(
        '-d',
        '--duplicates',
        action='store_true',
        default=False,
        help=_(
            'Add books to database even if they already exist. Comparison is done based on book titles and authors.'
            ' Note that the {} option takes precedence.'
        ).format('--automerge')
    )
    parser.add_option(
        '-m',
        '--automerge',
        type='choice',
        choices=('disabled', 'ignore', 'overwrite', 'new_record'),
        default='disabled',
        help=_(
            'If books with similar titles and authors are found, merge the incoming formats (files) automatically into'
            ' existing book records. A value of "ignore" means duplicate formats are discarded. A value of'
            ' "overwrite" means duplicate formats in the library are overwritten with the newly added files.'
            ' A value of "new_record" means duplicate formats are placed into a new book record.'
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
        help=_('Set the identifiers for this book, e.g. -I asin:XXX -I isbn:YYY')
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
        _('ADDING FROM FOLDERS'),
        _(
            'Options to control the adding of books from folders. By default only files that have extensions of known e-book file types are added.'
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
            'Assume that each folder has only a single logical book and that all files in it are different e-book formats of that book'
        )
    )
    g.add_option(
        '-r',
        '--recurse',
        action='store_true',
        default=False,
        help=_('Process folders recursively')
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
            'A filename (glob) pattern, files matching this pattern will be ignored when scanning folders for files.'
            ' Can be specified multiple times for multiple patterns. For example: *.pdf will ignore all PDF files'
        )
    )
    fadd(
        '--add', 'add',
        _(
            'A filename (glob) pattern, files matching this pattern will be added when scanning folders for files,'
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
    identifiers = {k.strip(): v.strip() for k, v in identifiers
                       if k.strip() and v.strip()}
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
        identifiers, lcodes, opts.filters, opts.automerge
    )
    return 0
