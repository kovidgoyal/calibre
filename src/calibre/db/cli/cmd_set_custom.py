#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre import prints
from calibre.db import _get_series_values
from calibre.srv.changes import metadata

readonly = False
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, col, book_id, val, append):
    is_remote = notify_changes is not None
    field = db.field_metadata.custom_field_prefix + col
    with db.write_lock:
        if not db.has_id(book_id):
            return False, _('No book with id {} exists').format(book_id)
        try:
            fm = db.field_metadata[field]
        except KeyError:
            return False, _('No column with name {} exists').format(col)
        if fm['datatype'] == 'series':
            val, s_index = _get_series_values(val)
            if s_index is None:
                s_index = db.get_next_series_num_for(val, field=field)
            db.set_field(field, {book_id: val}), db.set_field(field + '_index', {book_id: s_index})
            msg = _('Data set to: {} [{}]').format(db.field_for(field, book_id), db.field_for(field + '_index', book_id))
        else:
            if append and fm['is_multiple']:
                val = list(db.field_for(field, book_id)) + [val]
            db.set_field(field, {book_id: val})
            val = db.field_for(field, book_id)
            if isinstance(val, (tuple, list)):
                val = fm['is_multiple']['list_to_ui'].join(val)
            msg = _('Data set to: {}').format(val)
    if is_remote:
        notify_changes(metadata((book_id,)))
    return True, msg


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog set_custom [options] column id value

Set the value of a custom column for the book identified by id.
You can get a list of ids using the search command.
You can get a list of custom column names using the custom_columns
command.
    '''
        )
    )

    parser.add_option(
        '-a',
        '--append',
        default=False,
        action='store_true',
        help=_(
            'If the column stores multiple values, append the specified '
            'values to the existing ones, instead of replacing them.'
        )
    )
    return parser


def main(opts, args, dbctx):
    if len(args) < 3:
        raise SystemExit(_('Error: You must specify a field name, id and value'))
    ok, msg = dbctx.run('set_custom', args[0], int(args[1]), args[2], opts.append)
    if ok:
        prints(msg)
    else:
        raise SystemExit(msg)
    return 0
