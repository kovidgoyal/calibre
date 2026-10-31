#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from pprint import pformat
from typing import TYPE_CHECKING, cast

from calibre import prints
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from optparse import Values

    from calibre.db.backend import CustomColumnData
    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBContext
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, *args: object) -> dict[str, CustomColumnData]:
    return db.backend.custom_column_label_map


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''\
%prog custom_columns [options]

List available custom columns. Shows column labels and ids.
    '''
        )
    )
    parser.add_option('-d', '--details', default=False, action='store_true', help=_('Show details for each column.'))
    return parser


def main(opts: Values, args: list[str], dbctx: DBContext) -> int:
    for col, data in cast('dict[str, CustomColumnData]', dbctx.run('custom_columns')).items():
        if opts.details:
            prints(col)
            print()
            prints(pformat(data))
            print('\n')
        else:
            prints(col, f"({data['num']})")
    return 0
