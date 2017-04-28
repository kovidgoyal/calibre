#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import importlib
import os
import sys

from calibre import prints
from calibre.utils.config import OptionParser, prefs

COMMANDS = (
    'list', 'add', 'remove', 'add_format', 'remove_format', 'show_metadata',
    'set_metadata', 'export', 'catalog', 'saved_searches', 'add_custom_column',
    'custom_columns', 'remove_custom_column', 'set_custom', 'restore_database',
    'check_library', 'list_categories', 'backup_metadata', 'clone', 'embed_metadata',
    'search'
)


def module_for_cmd(cmd):
    return importlib.import_module('calibre.db.cli.cmd_' + cmd)


def option_parser_for(cmd):
    def cmd_option_parser():
        return module_for_cmd(cmd).option_parser(get_parser)
    return cmd_option_parser


def send_message(msg=''):
    prints('Notifying calibre of the change')
    from calibre.utils.ipc import RC
    t = RC(print_error=False)
    t.start()
    t.join(3)
    if t.done:
        t.conn.send('refreshdb:' + msg)
        t.conn.close()


def run_cmd(cmd, opts, args, db_ctx):
    m = module_for_cmd(cmd)
    ret = m.main(opts, args, db_ctx)
    if not opts.dont_notify_gui and not getattr(m, 'readonly', False):
        send_message()
    return ret


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


class DBCtx(object):

    def __init__(self, opts):
        self.library_path = opts.library_path or prefs['library_path']
        self.url = None
        if self.library_path is None:
            raise SystemExit('No saved library path, either run the GUI or use the'
                             ' --with-library option')
        if self.library_path.partition(':')[0] in ('http', 'https'):
            self.url = self.library_path
            self.is_remote = True
        else:
            self.library_path = os.path.expanduser(self.library_path)
            self._db = None
            self.is_remote = False

    @property
    def db(self):
        if self._db is None:
            from calibre.db.legacy import LibraryDatabase
            self._db = LibraryDatabase(self.library_path).new_api
        return self._db

    def run(self, name, *args):
        if self.is_remote:
            raise NotImplementedError()
        m = module_for_cmd(name)
        return m.implementation(self.db, False, *args)


def main(args=sys.argv):
    parser = option_parser()
    if len(args) < 2:
        parser.print_help()
        return 1
    cmd = args[1]
    if cmd not in COMMANDS:
        if cmd == '--version':
            parser.print_version()
            return 0
        parser.print_help()
        return 1

    parser = option_parser_for(cmd)()
    opts, args = parser.parse_args(args)
    return run_cmd(cmd, opts, args[2:], DBCtx(opts))


if __name__ == '__main__':
    main()
