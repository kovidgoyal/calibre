#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from pprint import pformat

from calibre import prints

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, *args):
    return db.backend.custom_column_label_map


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog custom_columns [options]

List available custom columns. Shows column labels and ids.
    '''
        )
    )
    parser.add_option(
        '-d',
        '--details',
        default=False,
        action='store_true',
        help=_('Show details for each column.')
    )
    return parser


def main(opts, args, dbctx):
    for col, data in dbctx.run('custom_columns').iteritems():
        if opts.details:
            prints(col)
            print()
            prints(pformat(data))
            print('\n')
        else:
            prints(col, '(%d)'%data['num'])
    return 0
