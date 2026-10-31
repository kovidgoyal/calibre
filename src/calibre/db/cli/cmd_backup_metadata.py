#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre import prints
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from optparse import Values
    from typing import NoReturn

    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBCtx
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser

readonly = True
version = 0  # change this if you change signature of implementation()
no_remote = True


def implementation(db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, *args: object) -> NoReturn:
    raise NotImplementedError()


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''\
%prog backup_metadata [options]

Backup the metadata stored in the database into individual OPF files in each
books folder. This normally happens automatically, but you can run this
command to force re-generation of the OPF files, with the --all option.

Note that there is normally no need to do this, as the OPF files are backed up
automatically, every time metadata is changed.
'''
        )
    )
    parser.add_option(
        '--all',
        default=False,
        action='store_true',
        help=_('Normally, this command only operates on books that have out of date OPF files. This option makes it operate on all books.'),
    )
    return parser


class BackupProgress:
    def __init__(self) -> None:
        self.total = 0
        self.count = 0

    def __call__(self, book_id: int, mi: Metadata | bool | None, ok: bool) -> None:
        if mi is True:
            self.total = book_id
        else:
            self.count += 1
            if ok:
                prints('{:.1f}% {} - {}'.format((self.count * 100) / float(self.total), book_id, getattr(mi, 'title', 'Unknown')))
            else:
                prints(f'{(self.count * 100) / float(self.total):.1f}% {book_id} failed')


def main(opts: Values, args: list[str], dbctx: DBCtx) -> int:
    db = dbctx.db
    book_ids = None
    if opts.all:
        book_ids = db.new_api.all_book_ids()
        db.new_api.mark_as_dirty(book_ids)
    db.dump_metadata(book_ids=book_ids, callback=BackupProgress())
    return 0
