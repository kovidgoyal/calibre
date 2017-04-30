#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys

from calibre import prints
from calibre.ebooks.metadata.opf2 import OPFCreator

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, book_id):
    with db.safe_read_lock:
        if not db.has_id(book_id):
            return
        return db.get_metadata(book_id)


def option_parser(get_parser):
    parser = get_parser(
        _(
            '''
%prog show_metadata [options] id

Show the metadata stored in the calibre database for the book identified by id.
id is an id number from the search command.
'''
        )
    )
    parser.add_option(
        '--as-opf',
        default=False,
        action='store_true',
        help=_('Print metadata in OPF form (XML)')
    )
    return parser


def main(opts, args, dbctx):
    if len(args) < 1:
        raise SystemExit(_('You must specify an id'))
    book_id = int(args[0])
    mi = dbctx.run('show_metadata', book_id)
    if mi is None:
        raise SystemExit('Id #%d is not present in database.' % id)
    if opts.as_opf:
        mi = OPFCreator(os.getcwdu(), mi)
        mi.render(sys.stdout)
    else:
        prints(unicode(mi))

    return 0
