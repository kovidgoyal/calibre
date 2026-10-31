#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import os
from io import BytesIO
from typing import TYPE_CHECKING

from calibre.srv.changes import formats_added
from calibre.srv.utils import is_recipe_fmt
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from optparse import Values

    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBContext
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(
    db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, book_id: int, data: str | tuple[str, bytes], fmt: str, replace: bool
) -> bool:
    is_remote = notify_changes is not None
    if is_remote:
        if is_recipe_fmt(fmt):
            raise ValueError('Cannot use the add format interface to add recipe files, as they allow code execution')
        data = BytesIO(data[1])  # ty: ignore[invalid-assignment, invalid-argument-type]
    relpath = ''
    if fmt.startswith('.EXTRA_DATA_FILE:'):
        relpath = fmt[len('.EXTRA_DATA_FILE:') :]
    if relpath:
        added = db.add_extra_files(book_id, {relpath: data}, replace=replace)[relpath]  # ty: ignore[invalid-argument-type]
    else:
        added = db.add_format(book_id, fmt, data, replace=replace)  # ty: ignore[invalid-argument-type]
    if is_remote and added and not relpath:
        notify_changes(formats_added({book_id: (fmt,)}))
    return added


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''\
%prog add_format [options] id ebook_file

Add the e-book in ebook_file to the available formats for the logical book identified \
by id. You can get id by using the search command. If the format already exists, \
it is replaced, unless the do not replace option is specified.\
'''
        )
    )
    parser.add_option(
        '--dont-replace',
        dest='replace',
        default=True,
        action='store_false',
        help=_('Do not replace the format if it already exists'),
    )
    parser.add_option(
        '--as-extra-data-file',
        default=False,
        action='store_true',
        help=_('Add the file as an extra data file to the book, not an ebook format'),
    )

    return parser


def main(opts: Values, args: list[str], dbctx: DBContext) -> int:
    if len(args) < 2:
        raise SystemExit(_('You must specify an id and an e-book file'))

    id, path, fmt = int(args[0]), args[1], os.path.splitext(args[1])[-1]
    if opts.as_extra_data_file:
        fmt = '.EXTRA_DATA_FILE:' + 'data/' + os.path.basename(args[1])
    else:
        fmt = fmt[1:].upper()
    if not fmt:
        raise SystemExit(_('e-book file must have an extension'))
    if not dbctx.run('add_format', id, dbctx.path(path), fmt, opts.replace):
        if opts.as_extra_data_file:
            raise SystemExit(f'An extra data file with the filename {os.path.basename(args[1])} already exists')
        raise SystemExit(_('A %(fmt)s file already exists for book: %(id)d, not replacing') % dict(fmt=fmt, id=id))
    return 0
