#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json

from calibre import prints
from calibre.db.legacy import LibraryDatabase
from calibre.library.custom_columns import CustomColumns

readonly = False
version = 0  # change this if you change signature of implementation()
no_remote = True


def implementation(db, notify_changes, *args):
    raise NotImplementedError()


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog add_custom_column [options] label name datatype

Create a custom column. label is the machine friendly name of the column. Should
not contain spaces or colons. name is the human friendly name of the column.
datatype is one of: {0}
'''
        ).format(', '.join(sorted(CustomColumns.CUSTOM_DATA_TYPES)))
    )

    parser.add_option(
        '--is-multiple',
        default=False,
        action='store_true',
        help=_(
            'This column stores tag like data (i.e. '
            'multiple comma separated values). Only '
            'applies if datatype is text.'
        )
    )
    parser.add_option(
        '--display',
        default='{}',
        help=_(
            'A dictionary of options to customize how '
            'the data in this column will be interpreted. This is a JSON '
            ' string. For enumeration columns, use '
            '--display="{\\"enum_values\\":[\\"val1\\", \\"val2\\"]}"'
            '\n'
            'There are many options that can go into the display variable.'
            'The options by column type are:\n'
            'composite: composite_template, composite_sort, make_category,'
            'contains_html, use_decorations\n'
            'datetime: date_format\n'
            'enumeration: enum_values, enum_colors, use_decorations\n'
            'int, float: number_format\n'
            'text: is_names, use_decorations\n'
            '\n'
            'The best way to find legal combinations is to create a custom '
            'column of the appropriate type in the GUI then look at the '
            'backup OPF for a book (ensure that a new OPF has been created '
            'since the column was added). You will see the JSON for the '
            '"display" for the new column in the OPF.'
        )
    )
    return parser


def do_add_custom_column(db, label, name, datatype, is_multiple, display):
    num = db.create_custom_column(
        label, name, datatype, is_multiple, display=display
    )
    prints('Custom column created with id: %s' % num)


def main(opts, args, dbctx):
    if len(args) < 3:
        raise SystemExit(_('You must specify label, name and datatype'))
    do_add_custom_column(
        dbctx.db, args[0], args[1], args[2], opts.is_multiple,
        json.loads(opts.display)
    )
    # Update the stored field_metadata
    dbctx.db.close()
    db = LibraryDatabase(dbctx.db.library_path)
    m = db.field_metadata.all_metadata()
    db.new_api.set_pref('field_metadata', m)
    return 0
