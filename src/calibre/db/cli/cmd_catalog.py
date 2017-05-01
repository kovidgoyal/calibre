#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from calibre.customize.ui import available_catalog_formats, plugin_for_catalog_format
from calibre.db.cli import integers_from_string

readonly = True
version = 0  # change this if you change signature of implementation()
needs_srv_ctx = True
no_remote = True


def implementation(db, notify_changes, ctx):
    raise NotImplementedError()


def option_parser(get_parser, args):  # {{{

    def add_plugin_parser_options(fmt, parser):
        # Fetch the extension-specific CLI options from the plugin
        # library.catalogs.<format>.py
        plugin = plugin_for_catalog_format(fmt)
        for option in plugin.cli_options:
            if option.action:
                parser.add_option(
                    option.option,
                    default=option.default,
                    dest=option.dest,
                    action=option.action,
                    help=option.help
                )
            else:
                parser.add_option(
                    option.option,
                    default=option.default,
                    dest=option.dest,
                    help=option.help
                )

    # Entry point
    parser = get_parser(
        _(
            '''\
%prog catalog /path/to/destination.(csv|epub|mobi|xml...) [options]

Export a catalog in format specified by path/to/destination extension.
Options control how entries are displayed in the generated catalog output.
'''
        )
    )

    # Add options common to all catalog plugins
    parser.add_option(
        '-i',
        '--ids',
        default=None,
        dest='ids',
        help=_(
            "Comma-separated list of database IDs to catalog.\n"
            "If declared, --search is ignored.\n"
            "Default: all"
        )
    )
    parser.add_option(
        '-s',
        '--search',
        default=None,
        dest='search_text',
        help=_(
            "Filter the results by the search query. "
            "For the format of the search query, please see "
            "the search-related documentation in the User Manual.\n"
            "Default: no filtering"
        )
    )
    parser.add_option(
        '-v',
        '--verbose',
        default=False,
        action='store_true',
        dest='verbose',
        help=_('Show detailed output information. Useful for debugging')
    )
    fmt = 'epub'
    if args and '.' in args[0]:
        fmt = args[0].rpartition('.')[-1].lower()
        if fmt not in available_catalog_formats():
            fmt = 'epub'

    # Add options specific to fmt plugin
    add_plugin_parser_options(fmt, parser)

    return parser


# }}}


def main(opts, args, dbctx):
    if len(args) < 1:
        raise SystemExit(_('You must specify a catalog output file'))
    if opts.ids:
        opts.ids = list(integers_from_string(opts.ids))
    fmt = args[0].rpartition('.')[-1]
    if fmt not in available_catalog_formats():
        raise SystemExit(
            _('Cannot generate a catalog in the {} format').format(fmt.upper())
        )

    # No support for connected device in CLI environment
    # Parallel initialization in calibre.gui2.tools:generate_catalog()
    opts.connected_device = {
        'is_device_connected': False,
        'kind': None,
        'name': None,
        'save_template': None,
        'serial': None,
        'storage': None,
    }
    dest = os.path.abspath(os.path.expanduser(args[0]))
    plugin = plugin_for_catalog_format(fmt)
    with plugin:
        plugin.run(dest, opts, dbctx.db)
    return 0
