#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre import prints

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, query):
    return db.search(query)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog search [options] search expression

Search the library for the specified search term, returning a comma separated
list of book ids matching the search expression. The output format is useful
to feed into other commands that accept a list of ids as input.

The search expression can be anything from calibre's powerful search query
language, for example: {0}
'''
        ).format('author:asimov title:robot')
    )
    parser.add_option(
        '-l',
        '--limit',
        default=-1,
        type=int,
        help=_('The maximum number of results to return. Default is all results.')
    )
    return parser


def main(opts, args, dbctx):
    if len(args) < 1:
        raise SystemExit(_('Error: You must specify the search expression'))
    q = ' '.join(args)
    ids = dbctx.run('search', q)
    if not ids:
        raise SystemExit(_('No books matching the search expression:') + ' ' + q)
    ids = sorted(ids)
    if opts.limit > -1:
        ids = ids[:opts.limit]
    prints(','.join(map(str, ids)), end='')
    return 0
