#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from io import BytesIO

from calibre.srv.changes import formats_added

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, book_id, data, fmt, replace):
    is_remote = notify_changes is not None
    if is_remote:
        data = BytesIO(data[1])
    added = db.add_format(book_id, fmt, data, replace=replace)
    if is_remote and added:
        notify_changes(formats_added({book_id: (fmt,)}))
    return added


def option_parser(get_parser):
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
        help=_('Do not replace the format if it already exists')
    )
    return parser


def main(opts, args, dbctx):
    if len(args) < 2:
        raise SystemExit(_('You must specify an id and an e-book file'))

    id, path, fmt = int(args[0]), args[1], os.path.splitext(args[1])[-1]
    if not fmt:
        raise SystemExit(_('e-book file must have an extension'))
    fmt = fmt[1:].upper()
    if not dbctx.run('add_format', id, dbctx.path(path), fmt, opts.replace):
        raise SystemExit(_('A %(fmt)s file already exists for book: %(id)d, not replacing')%dict(fmt=fmt, id=id))
    return 0
