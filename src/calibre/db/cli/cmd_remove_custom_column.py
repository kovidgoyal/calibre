#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre import prints
from calibre.db.legacy import LibraryDatabase

readonly = False
version = 0  # change this if you change signature of implementation()
no_remote = True


def implementation(db, notify_changes, *args):
    raise NotImplementedError()


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog remove_custom_column [options] label

Remove the custom column identified by label. You can see available
columns with the custom_columns command.
    '''
        )
    )
    parser.add_option(
        '-f',
        '--force',
        default=False,
        action='store_true',
        help=_('Do not ask for confirmation')
    )
    return parser


def do_remove_custom_column(db, label, force):
    if not force:
        q = raw_input(
            _('You will lose all data in the column: %s.'
              ' Are you sure (y/n)? ') % label
        )
        if q.lower().strip() != _('y'):
            return
    try:
        db.delete_custom_column(label=label)
    except KeyError:
        raise SystemExit(
            _(
                'No column named %s found. You must use column labels, not titles.'
                ' Use calibredb custom_columns to get a list of labels.'
            ) % label
        )
    prints('Column %r removed.' % label)


def main(opts, args, dbctx):
    if len(args) < 1:
        raise SystemExit(_('Error: You must specify a column label'))

    do_remove_custom_column(dbctx.db, args[0], opts.force)
    # Update the stored field_metadata
    dbctx.db.close()
    db = LibraryDatabase(dbctx.db.library_path)
    m = db.field_metadata.all_metadata()
    db.new_api.set_pref('field_metadata', m)
    return 0
