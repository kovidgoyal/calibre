#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.db.cli import integers_from_string
from calibre.db.errors import BooksNotRemoved
from calibre.srv.changes import books_deleted
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence
    from optparse import Values

    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBCtx
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, ids: Collection[int], permanent: bool) -> None:
    try:
        db.remove_books(ids, permanent=permanent)
    except BooksNotRemoved as err:
        if notify_changes is not None and err.removed:
            notify_changes(books_deleted(err.removed))
        raise
    if notify_changes is not None:
        notify_changes(books_deleted(ids))


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    p = get_parser(
        _(
            '''\
%prog remove ids

Remove the books identified by ids from the database. ids should be a comma separated \
list of id numbers (you can get id numbers by using the search command). For example, \
23,34,57-85 (when specifying a range, the last number in the range is not included).
'''
        )
    )
    p.add_option('--permanent', default=False, action='store_true', help=_('Do not use the trash bin'))
    return p


def main(opts: Values, args: list[str], dbctx: DBCtx) -> int:
    if len(args) < 1:
        raise SystemExit(_('You must specify at least one book to remove'))

    ids = set()
    for arg in args:
        ids |= set(integers_from_string(arg))

    dbctx.run('remove', ids, opts.permanent)

    return 0
