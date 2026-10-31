#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.srv.changes import formats_removed
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


def implementation(db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, book_id: int, fmt: str) -> None:
    is_remote = notify_changes is not None
    fmt_map = {book_id: (fmt,)}
    db.remove_formats(fmt_map)
    if is_remote:
        notify_changes(formats_removed(fmt_map))


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    return get_parser(
        _(
            '''
%prog remove_format [options] id fmt

Remove the format fmt from the logical book identified by id. \
You can get id by using the search command. fmt should be a file extension \
like LRF or TXT or EPUB. If the logical book does not have fmt available, \
do nothing.
'''
        )
    )


def main(opts: Values, args: list[str], dbctx: DBContext) -> int:
    if len(args) < 2:
        raise SystemExit(_('You must specify an id and a format'))
        return 1

    id, fmt = int(args[0]), args[1].upper()
    dbctx.run('remove_format', id, fmt)
    return 0
