#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

readonly = False
version = 0  # change this if you change signature of implementation()

from calibre import prints
from calibre.srv.changes import saved_searches


def implementation(db, notify_changes, action, *args):
    if action == 'list':
        with db.safe_read_lock:
            names = db.saved_search_names()
            return {n: db.saved_search_lookup(n) for n in names}
    if action == 'add':
        name, val = args
        db.saved_search_add(name, val)
        if notify_changes is not None:
            notify_changes(saved_searches([('add', name)]))
        return
    if action == 'remove':
        name = args[0]
        db.saved_search_delete(name)
        if notify_changes is not None:
            notify_changes(saved_searches([('remove', name)]))
        return


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog saved_searches [options] (list|add|remove)

Manage the saved searches stored in this database.
If you try to add a query with a name that already exists, it will be
replaced.

Syntax for adding:

%prog saved_searches add search_name search_expression

Syntax for removing:

%prog saved_searches remove search_name
    '''
        )
    )
    return parser


def main(opts, args, dbctx):
    args = args or ['list']
    if args[0] == 'list':
        for name, value in dbctx.run('saved_searches', 'list').iteritems():
            prints(_('Name:'), name)
            prints(_('Search string:'), value)
            print()
    elif args[0] == 'add':
        if len(args) < 3:
            raise SystemExit(_('Error: You must specify a name and a search string'))
        dbctx.run('saved_searches', 'add', args[1], args[2])
        prints(args[1], _('added'))
    elif args[0] == 'remove':
        if len(args) < 2:
            raise SystemExit(_('Error: You must specify a name'))
        dbctx.run('saved_searches', 'remove', args[1])
        prints(args[1], _('removed'))
    else:
        raise SystemExit(
            _(
                'Error: Action %s not recognized, must be one '
                'of: (add|remove|list)'
            ) % args[0]
        )

    return 0
