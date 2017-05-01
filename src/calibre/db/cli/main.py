#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import httplib
import json
import os
import sys
from urllib import urlencode
from urlparse import urlparse, urlunparse

from calibre import browser, prints
from calibre.constants import __appname__, __version__
from calibre.db.cli import module_for_cmd
from calibre.db.legacy import LibraryDatabase
from calibre.utils.config import OptionParser, prefs
from calibre.utils.serialize import MSGPACK_MIME

COMMANDS = (
    'list', 'add', 'remove', 'add_format', 'remove_format', 'show_metadata',
    'set_metadata', 'export', 'catalog', 'saved_searches', 'add_custom_column',
    'custom_columns', 'remove_custom_column', 'set_custom', 'restore_database',
    'check_library', 'list_categories', 'backup_metadata', 'clone', 'embed_metadata',
    'search'
)


def option_parser_for(cmd, args=()):

    def cmd_option_parser():
        return module_for_cmd(cmd).option_parser(get_parser, args)

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


def run_cmd(cmd, opts, args, dbctx):
    m = module_for_cmd(cmd)
    ret = m.main(opts, args, dbctx)
    if not dbctx.is_remote and not opts.dont_notify_gui and not getattr(m, 'readonly', False):
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
            ' You can also connect to a calibre Content server to perform actions on'
            ' remote libraries. To do so use a URL of the form: http://hostname:port/#library_id'
            ' for example, http://localhost:8080/#mylibrary. library_id is the library id'
            ' of the library you want to connect to on the Content server. You can use'
            ' the special library_id value of - to get a list of library ids available'
            ' on the server.'
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
    go.add_option(
        '--username',
        help=_('Username for connecting to a calibre Content server')
    )
    go.add_option(
        '--password',
        help=_('Password for connecting to a calibre Content server.'
               ' To read the password from standard input, use the special value: {}.'
               ' To read the password from a file, use: {}.)').format(
                   '<stdin>', '<f:/path/to/file>')
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


def read_credetials(opts):
    username = opts.username
    pw = opts.password
    if pw:
        if pw == '<stdin>':
            import getpass
            pw = getpass.getpass(_('Enter the password: '))
        elif pw.startswith('<f:') and pw.endswith('>'):
            with lopen(pw[3:-1], 'rb') as f:
                pw = f.read().decode('utf-8')
    return username, pw


class DBCtx(object):

    def __init__(self, opts):
        self.library_path = opts.library_path or prefs['library_path']
        self.url = None
        if self.library_path is None:
            raise SystemExit(
                'No saved library path, either run the GUI or use the'
                ' --with-library option'
            )
        if self.library_path.partition(':')[0] in ('http', 'https'):
            parts = urlparse(self.library_path)
            self.library_id = parts.fragment or None
            self.url = urlunparse(parts._replace(fragment='')).rstrip('/')
            self.br = browser(handle_refresh=False, user_agent='{} {}'.format(__appname__, __version__))
            self.is_remote = True
            username, password = read_credetials(opts)
            self.has_credentials = False
            if username and password:
                self.br.add_password(self.url, username, password)
                self.has_credentials = True
            if self.library_id == '-':
                self.list_libraries()
                raise SystemExit()
        else:
            self.library_path = os.path.expanduser(self.library_path)
            self._db = None
            self.is_remote = False

    @property
    def db(self):
        if self._db is None:
            self._db = LibraryDatabase(self.library_path).new_api
        return self._db

    def path(self, path):
        if self.is_remote:
            with lopen(path, 'rb') as f:
                return path, f.read()
        return path

    def run(self, name, *args):
        m = module_for_cmd(name)
        if self.is_remote:
            return self.remote_run(name, m, *args)
        return m.implementation(self.db, None, *args)

    def interpret_http_error(self, err):
        if err.code == httplib.UNAUTHORIZED:
            raise SystemExit('A username and password is required to access this server')
        if err.code == httplib.FORBIDDEN:
            raise SystemExit('The username/password combination is incorrect')
        if err.code == httplib.NOT_FOUND:
            raise SystemExit(err.reason)

    def remote_run(self, name, m, *args):
        from mechanize import HTTPError, Request
        from calibre.utils.serialize import msgpack_loads, msgpack_dumps
        url = self.url + '/cdb/cmd/{}/{}'.format(name, getattr(m, 'version', 0))
        if self.library_id:
            url += '?' + urlencode({'library_id':self.library_id})
        rq = Request(url, data=msgpack_dumps(args),
                     headers={'Accept': MSGPACK_MIME, 'Content-Type': MSGPACK_MIME})
        try:
            res = self.br.open_novisit(rq)
            ans = msgpack_loads(res.read())
        except HTTPError as err:
            self.interpret_http_error(err)
            raise
        if 'err' in ans:
            prints(ans['tb'])
            raise SystemExit(ans['err'])
        return ans['result']

    def list_libraries(self):
        from mechanize import HTTPError
        url = self.url + '/ajax/library-info'
        try:
            res = self.br.open_novisit(url)
            ans = json.loads(res.read())
        except HTTPError as err:
            self.interpret_http_error(err)
            raise
        library_map, default_library = ans['library_map'], ans['default_library']
        for lid in sorted(library_map, key=lambda lid: (lid != default_library, lid)):
            prints(lid)


def main(args=sys.argv):
    parser = option_parser()
    if len(args) < 2:
        parser.print_help()
        return 1
    if args[1] == '--version':
        parser.print_version()
        return 0
    for i, x in enumerate(args):
        if i > 0 and x in COMMANDS:
            cmd = x
            break
    else:
        parser.print_help()
        return 1
    del args[i]
    parser = option_parser_for(cmd, args[1:])()
    opts, args = parser.parse_args(args)
    return run_cmd(cmd, opts, args[1:], DBCtx(opts))


if __name__ == '__main__':
    main()
