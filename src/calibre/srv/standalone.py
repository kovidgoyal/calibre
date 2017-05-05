#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, signal

from calibre import as_unicode, prints
from calibre.constants import plugins, iswindows, preferred_encoding
from calibre.srv.loop import ServerLoop
from calibre.srv.bonjour import BonJour
from calibre.srv.opts import opts_to_parser
from calibre.srv.http_response import create_http_handler
from calibre.srv.handler import Handler
from calibre.srv.utils import RotatingLog
from calibre.utils.config import prefs
from calibre.db.legacy import LibraryDatabase


def daemonize():  # {{{
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError as e:
        raise SystemExit('fork #1 failed: %s' % as_unicode(e))

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as e:
        raise SystemExit('fork #2 failed: %s' % as_unicode(e))

    # Redirect standard file descriptors.
    try:
        plugins['speedup'][0].detach(os.devnull)
    except AttributeError:  # people running from source without updated binaries
        si = os.open(os.devnull, os.O_RDONLY)
        so = os.open(os.devnull, os.O_WRONLY)
        se = os.open(os.devnull, os.O_WRONLY)
        os.dup2(si, sys.stdin.fileno())
        os.dup2(so, sys.stdout.fileno())
        os.dup2(se, sys.stderr.fileno())
# }}}


class Server(object):

    def __init__(self, libraries, opts):
        log = access_log = None
        log_size = opts.max_log_size * 1024 * 1024
        if opts.log:
            log = RotatingLog(opts.log, max_size=log_size)
        if opts.access_log:
            access_log = RotatingLog(opts.access_log, max_size=log_size)
        self.handler = Handler(libraries, opts)
        plugins = []
        if opts.use_bonjour:
            plugins.append(BonJour())
        self.loop = ServerLoop(create_http_handler(self.handler.dispatch), opts=opts, log=log, access_log=access_log, plugins=plugins)
        self.handler.set_log(self.loop.log)
        self.handler.set_jobs_manager(self.loop.jobs_manager)
        self.serve_forever = self.loop.serve_forever
        self.stop = self.loop.stop
        _df = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        if _df and os.path.exists(_df):
            from calibre.utils.rapydscript import compile_srv
            compile_srv()

# Manage users CLI {{{


def manage_users(path=None):
    from calibre.srv.users import UserManager
    m = UserManager(path)
    enc = getattr(sys.stdin, 'encoding', preferred_encoding) or preferred_encoding

    def choice(question, choices, default=None, banner=''):
        prints(banner)
        for i, choice in enumerate(choices):
            prints('%d)' % (i+1), choice)
        print()
        while True:
            prompt = question + ' [1-%d]: ' % len(choices)
            if default is not None:
                prompt = question + ' [1-%d %s: %d]' % (len(choices), _('default'), default+1)
            reply = raw_input(prompt)
            if not reply and default is not None:
                reply = str(default + 1)
            if not reply:
                raise SystemExit(0)
            reply = reply.strip()
            try:
                num = int(reply) - 1
                if not (0 <= num < len(choices)):
                    raise Exception('bad num')
                return num
            except Exception:
                prints(_('%s is not a valid choice, try again') % reply)

    def get_valid(prompt, invalidq=lambda x: None):
        while True:
            ans = raw_input(prompt + ': ').strip().decode(enc)
            fail_message = invalidq(ans)
            if fail_message is None:
                return ans
            prints(fail_message)

    def get_valid_user():
        prints(_('Existing user names:'))
        users = sorted(m.all_user_names)
        if not users:
            raise SystemExit(_('There are no users, you must first add an user'))
        prints(', '.join(users))

        def validate(username):
            if not m.has_user(username):
                return _('The username %s does not exist') % username
        return get_valid(_('Enter the username'), validate)

    def get_pass(username):
        while True:
            from getpass import getpass
            one = getpass(_('Enter the new password for %s: ') % username).decode(enc)
            if not one:
                prints(_('Empty passwords are not allowed'))
                continue
            two = getpass(_('Re-enter the new password for %s, to verify: ') % username).decode(enc)
            if one != two:
                prints(_('Passwords do not match'))
                continue
            msg = m.validate_password(one)
            if msg is None:
                return one
            prints(msg)

    def add_user():
        username = get_valid(_('Enter the username'), m.validate_username)
        pw = get_pass(username)
        m.add_user(username, pw)
        prints(_('User %s added successfully!') % username)

    def remove_user():
        un = get_valid_user()
        if raw_input((_('Are you sure you want to remove the user %s?') % un) + ' [y/n]: ').decode(enc) != 'y':
            raise SystemExit(0)
        m.remove_user(un)
        prints(_('User %s successfully removed!') % un)

    def edit_user():
        username = get_valid_user()
        pw = get_pass(username)
        m.change_password(username, pw)
        prints(_('Password for %s successfully changed!') % username)

    def show_password():
        username = get_valid_user()
        pw = m.get(username)
        prints(_('Password for {0} is: {1}').format(username, pw))

    {0:add_user, 1:edit_user, 2:remove_user, 3:show_password}[choice(_('What do you want to do?'), [
        _('Add a new user'), _('Edit an existing user'), _('Remove a user'), _('Show the password for a user')])]()


# }}}

def create_option_parser():
    parser=opts_to_parser('%prog '+ _(
'''[options] [path to library folder...]

Start the calibre Content server. The calibre Content server
exposes your calibre libraries over the internet. You can specify
the path to the library folders as arguments to %prog. If you do
not specify any paths, the library last opened (if any) in the main calibre
program will be used.
'''
    ))
    parser.add_option(
        '--log', default=None,
        help=_('Path to log file for server log. This log contains server information and errors, not access logs. By default it is written to stdout.'))
    parser.add_option(
        '--access-log', default=None,
        help=_('Path to the access log file. This log contains information'
               ' about clients connecting to the server and making requests. By'
               ' default no access logging is done.'))
    parser.add_option('--daemonize', default=False, action='store_true',
        help=_('Run process in background as a daemon. No effect on Windows.'))
    parser.add_option('--pidfile', default=None,
        help=_('Write process PID to the specified file'))
    parser.add_option(
        '--auto-reload', default=False, action='store_true',
        help=_('Automatically reload server when source code changes. Useful'
               ' for development. You should also specify a small value for the'
               ' shutdown timeout.'))
    parser.add_option(
        '--manage-users', default=False, action='store_true',
        help=_('Manage the database of users allowed to connect to this server.'
               ' See also the %s option.') % '--userdb')

    return parser


def main(args=sys.argv):
    opts, args=create_option_parser().parse_args(args)
    if opts.manage_users:
        try:
            manage_users(opts.userdb)
        except (KeyboardInterrupt, EOFError):
            raise SystemExit(_('Interrupted by user'))
        raise SystemExit(0)

    libraries=args[1:]
    for lib in libraries:
        if not lib or not LibraryDatabase.exists_at(lib):
            raise SystemExit(_('There is no calibre library at: %s') % lib)
    if not libraries:
        if not prefs['library_path']:
            raise SystemExit(_('You must specify at least one calibre library'))
        libraries=[prefs['library_path']]

    if opts.auto_reload:
        if opts.daemonize:
            raise SystemExit('Cannot specify --auto-reload and --daemonize at the same time')
        from calibre.srv.auto_reload import auto_reload, NoAutoReload
        try:
            from calibre.utils.logging import default_log
            return auto_reload(default_log, listen_on=opts.listen_on)
        except NoAutoReload as e:
            raise SystemExit(e.message)
    opts.auto_reload_port=int(os.environ.get('CALIBRE_AUTORELOAD_PORT', 0))
    opts.allow_console_print = 'CALIBRE_ALLOW_CONSOLE_PRINT' in os.environ
    server=Server(libraries, opts)
    if opts.daemonize:
        if not opts.log and not iswindows:
            raise SystemExit('In order to daemonize you must specify a log file, you can use /dev/stdout to log to screen even as a daemon')
        daemonize()
    if opts.pidfile:
        with lopen(opts.pidfile, 'wb') as f:
            f.write(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda s,f: server.stop())
    if not opts.daemonize and not iswindows:
        signal.signal(signal.SIGHUP, lambda s,f: server.stop())
    # Needed for dynamic cover generation, which uses Qt for drawing
    from calibre.gui2 import ensure_app, load_builtin_fonts
    ensure_app(), load_builtin_fonts()
    server.serve_forever()
