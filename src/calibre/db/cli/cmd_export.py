#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import os
from typing import TYPE_CHECKING, cast

from calibre.db.cli import integers_from_string
from calibre.db.constants import DATA_FILE_PATTERN
from calibre.db.errors import NoSuchFormat
from calibre.library.save_to_disk import config, do_save_book_to_disk, get_formats, sanitize_args
from calibre.utils.formatter_functions import load_user_template_functions
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence
    from optparse import Values

    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBContext
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser
    from calibre.utils.formatter_functions import UserFunctionPref

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(
    db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, action: str, *args: object
) -> frozenset[int] | tuple[Metadata, object, set[str], str, object] | bytes | None:
    is_remote = notify_changes is not None
    if action == 'all_ids':
        return db.all_book_ids()
    if action == 'setup':
        book_id, formats = cast('tuple[int, str | None]', args)
        if not db.has_id(book_id):
            raise KeyError(f'No book with id {book_id} present')
        mi = db.get_metadata(book_id)
        plugboards = db.pref('plugboards', {})
        formats = get_formats(db.formats(book_id), formats)
        extra_files_for_export = tuple(ef.relpath for ef in db.list_extra_files(book_id, pattern=DATA_FILE_PATTERN))
        plugboards['extra_files_for_export'] = extra_files_for_export
        return mi, plugboards, formats, db.library_id, db.pref('user_template_functions', [])
    if action == 'cover':
        return db.cover(cast('int', args[0]))
    if action == 'fmt':
        book_id, fmt, dest = cast('tuple[int, str, str]', args)
        if is_remote:
            return db.format(book_id, fmt)
        db.copy_format_to(book_id, fmt, dest)
    if action == 'extra_file':
        book_id, relpath, dest = cast('tuple[int, str, str]', args)
        if is_remote:
            from io import BytesIO

            output = BytesIO()
            db.copy_extra_file_to(book_id, relpath, output)
            return output.getvalue()
        db.copy_extra_file_to(book_id, relpath, dest)


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''\
%prog export [options] ids

Export the books specified by ids (a comma separated list) to the filesystem.
The export operation saves all formats of the book, its cover and metadata (in
an OPF file). Any extra data files associated with the book are also saved.
You can get id numbers from the search command.
'''
        )
    )
    parser.add_option('--all', default=False, action='store_true', help=_('Export all books in database, ignoring the list of ids.'))
    parser.add_option('--to-dir', default='.', help=(_('Export books to the specified folder. Default is') + ' %default'))
    parser.add_option('--single-dir', default=False, action='store_true', help=_('Export all books into a single folder'))
    parser.add_option('--progress', default=False, action='store_true', help=_('Report progress'))
    c = config()
    for pref in ['asciiize', 'update_metadata', 'write_opf', 'save_cover', 'save_extra_files']:
        opt = c.get_option(pref)
        switch = '--dont-' + pref.replace('_', '-')
        parser.add_option(
            switch,
            default=True,
            action='store_false',
            help=opt.help + ' ' + _('Specifying this switch will turn this behavior off.'),
            dest=pref,
        )

    for pref in ['timefmt', 'template', 'formats']:
        opt = c.get_option(pref)
        switch = '--' + pref
        parser.add_option(switch, default=opt.default, help=opt.help, dest=pref)

    for pref in ('replace_whitespace', 'to_lowercase'):
        opt = c.get_option(pref)
        switch = '--' + pref.replace('_', '-')
        parser.add_option(switch, default=False, action='store_true', help=opt.help)

    return parser


class DBProxy:
    # Proxy to allow do_save_book_to_disk() to work with remote database

    def __init__(self, dbctx: DBContext) -> None:
        self.dbctx = dbctx

    def cover(self, book_id: int) -> bytes | None:
        return cast('bytes | None', self.dbctx.run('export', 'cover', book_id))

    def copy_format_to(self, book_id: int, fmt: str, path: str) -> None:
        fdata = cast('bytes | None', self.dbctx.run('export', 'fmt', book_id, fmt, path))
        if self.dbctx.is_remote:
            if fdata is None:
                raise NoSuchFormat(fmt)
            with open(path, 'wb') as f:
                f.write(fdata)

    def copy_extra_file_to(self, book_id: int, relpath: str, path: str) -> None:
        fdata = cast('bytes | None', self.dbctx.run('export', 'extra_file', book_id, relpath, path))
        if self.dbctx.is_remote:
            if fdata is None:
                raise FileNotFoundError(relpath)
            with open(path, 'wb') as f:
                f.write(fdata)


def export(opts: Values, dbctx: DBContext, book_id: int, dest: str, dbproxy: DBProxy, length: int, first: bool) -> tuple[bool, int, str]:
    mi, plugboards, formats, library_id, template_funcs = cast(
        'tuple[Metadata, dict[str, object], list[str] | set[str], str, list[UserFunctionPref]]',
        dbctx.run('export', 'setup', book_id, opts.formats),
    )
    extra_files = plugboards.pop('extra_files_for_export', ())
    if dbctx.is_remote and first:
        load_user_template_functions(library_id, template_funcs)
    return do_save_book_to_disk(dbproxy, book_id, mi, plugboards, formats, dest, opts, length, extra_files)


def main(opts: Values, args: list[str], dbctx: DBContext) -> int:
    if len(args) < 1 and not opts.all:
        raise SystemExit(_('You must specify some ids or the %s option') % '--all')
    if opts.all:
        book_ids = cast('Collection[int]', dbctx.run('export', 'all_ids'))
    else:
        book_ids = set()
        for arg in args:
            book_ids |= set(integers_from_string(arg))
    dest = os.path.abspath(os.path.expanduser(opts.to_dir))
    dbproxy = DBProxy(dbctx)
    dest, opts, length = sanitize_args(dest, opts)
    total = len(book_ids)
    for i, book_id in enumerate(book_ids):
        export(opts, dbctx, book_id, dest, dbproxy, length, i == 0)
        if opts.progress:
            num = i + 1
            print(f'\r  {num / total:.1%} [{num}/{total}]', end=' ' * 20)
    if opts.progress:
        print()
    return 0
