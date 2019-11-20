#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.db.delete_service import delete_service
from calibre.srv.changes import formats_removed

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, book_id, fmt):
    is_remote = notify_changes is not None
    fmt_map = {book_id: (fmt, )}
    db.remove_formats(fmt_map)
    delete_service().wait()
    if is_remote:
        notify_changes(formats_removed(fmt_map))


def option_parser(get_parser, args):
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


def main(opts, args, dbctx):
    if len(args) < 2:
        raise SystemExit(_('You must specify an id and a format'))
        return 1

    id, fmt = int(args[0]), args[1].upper()
    dbctx.run('remove_format', id, fmt)
    return 0
