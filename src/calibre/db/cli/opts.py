#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre.utils.config import OptionParser

COMMANDS = (
    'list', 'add', 'remove', 'add_format', 'remove_format', 'show_metadata',
    'set_metadata', 'export', 'catalog', 'saved_searches', 'add_custom_column',
    'custom_columns', 'remove_custom_column', 'set_custom', 'restore_database',
    'check_library', 'list_categories', 'backup_metadata', 'clone', 'embed_metadata',
    'search'
)


def get_parser(usage):
    parser = OptionParser(usage)
    go = parser.add_option_group(_('GLOBAL OPTIONS'))
    go.is_global_options = True
    go.add_option(
        '--library-path',
        '--with-library',
        default=None,
        help=_(
            'Path to the calibre library. Default is to use the path stored in the settings.'
        )
    )
    go.add_option(
        '--dont-notify-gui',
        default=False,
        action='store_true',
        help=_(
            'Do not notify the running calibre GUI (if any) that the database has'
            ' changed. Use with care, as it can lead to database corruption!'
        )
    )
    go.add_option(
        '-h', '--help', help=_('show this help message and exit'), action='help'
    )
    go.add_option(
        '--version',
        help=_("show program's version number and exit"),
        action='version'
    )

    return parser


def option_parser():
    parser = OptionParser(
        _(
            '''\
%%prog command [options] [arguments]

%%prog is the command line interface to the calibre books database.

command is one of:
  %s

For help on an individual command: %%prog command --help
'''
        ) % '\n  '.join(COMMANDS)
    )
    return parser
