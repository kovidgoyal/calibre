#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import os
from typing import TYPE_CHECKING, cast

from calibre import prints
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from optparse import Values

    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBCtx
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, book_id: int) -> Metadata | None:
    with db.safe_read_lock:
        if not db.has_id(book_id):
            return
        return db.get_metadata(book_id)


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''
%prog show_metadata [options] id

Show the metadata stored in the calibre database for the book identified by id.
id is an id number from the search command.
'''
        )
    )
    parser.add_option('--as-opf', default=False, action='store_true', help=_('Print metadata in OPF form (XML)'))
    return parser


def main(opts: Values, args: list[str], dbctx: DBCtx) -> int:
    if len(args) < 1:
        raise SystemExit(_('You must specify an id'))
    book_id = int(args[0])
    mi = cast('Metadata | None', dbctx.run('show_metadata', book_id))
    if mi is None:
        raise SystemExit(f'Id #{book_id} is not present in database.')
    if opts.as_opf:
        mi = OPFCreator(os.getcwd(), mi)
        mi.render(mark_fallback_language=False)
    else:
        prints(str(mi))

    return 0
