#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, signal
from functools import partial

from calibre import as_unicode, prints
from calibre.constants import plugins, iswindows, preferred_encoding, is_running_from_develop, isosx
from calibre.srv.loop import ServerLoop
from calibre.srv.library_broker import load_gui_libraries
from calibre.srv.bonjour import BonJour
from calibre.srv.opts import opts_to_parser
from calibre.srv.http_response import create_http_handler
from calibre.srv.handler import Handler
from calibre.srv.utils import RotatingLog
from calibre.utils.config import prefs
from calibre.utils.localization import localize_user_manual_link
from calibre.utils.lock import singleinstance
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
    plugins['speedup'][0].detach(os.devnull)
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
        if is_running_from_develop:
            from calibre.utils.rapydscript import compile_srv
            compile_srv()

# Manage users CLI {{{


def manage_users(path=None):
    from calibre.srv.users import UserManager
    m = UserManager(path)
    enc = getattr(sys.stdin, 'encoding', preferred_encoding) or preferred_encoding

    def get_input(prompt):
        prints(prompt, end=' ')
        return raw_input().decode(enc)

    def choice(question=_('What do you want to do?'), choices=(), default=None, banner=''):
        prints(banner)
        for i, choice in enumerate(choices):
            prints('%d)' % (i+1), choice)
        print()
        while True:
            prompt = question + ' [1-%d]:' % len(choices)
            if default is not None:
                prompt = question + ' [1-%d %s: %d]' % (len(choices), _('default'), default+1)
            reply = get_input(prompt)
            if not reply and default is not None:
                reply = str(default + 1)
            if not reply:
                prints(_('No choice selected, exiting...'))
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
            ans = get_input(prompt + ':').strip()
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
        if get_input((_('Are you sure you want to remove the user %s?') % un) + ' [y/n]:') != 'y':
            raise SystemExit(0)
        m.remove_user(un)
        prints(_('User %s successfully removed!') % un)

    def change_password(username):
        pw = get_pass(username)
        m.change_password(username, pw)
        prints(_('Password for %s successfully changed!') % username)

    def show_password(username):
        pw = m.get(username)
        prints(_('Current password for {0} is: {1}').format(username, pw))

    def change_readonly(username):
        readonly = m.is_readonly(username)
        if readonly:
            q = _('Allow {} to make changes (i.e. grant write access)?')
        else:
            q = _('Prevent {} from making changes (i.e. remove write access)?')
        if get_input(q.format(username) + ' [y/n]:').lower() == 'y':
            m.set_readonly(username, not readonly)

    def change_restriction(username):
        r = m.restrictions(username)
        if r is None:
            raise SystemExit('The user {} does not exist'.format(username))
        if r['allowed_library_names']:
            prints(_('{} is currently only allowed to access the libraries named: {}').format(
                username, ', '.join(r['allowed_library_names'])))
        if r['blocked_library_names']:
            prints(_('{} is currently not allowed to access the libraries named: {}').format(
                username, ', '.join(r['blocked_library_names'])))
        if r['library_restrictions']:
            prints(_('{} has the following additional per-library restrictions:').format(username))
            for k, v in r['library_restrictions'].iteritems():
                prints(k + ':', v)
        else:
            prints(_('{} has the no additional per-library restrictions'))
        c = choice(choices=[
            _('Allow access to all libraries'), _('Allow access to only specified libraries'),
            _('Allow access to all, except specified libraries'), _('Change per-library restrictions'),
            _('Cancel')])
        if c == 0:
            m.update_user_restrictions(username, {})
        elif c == 3:
            while True:
                library = get_input(_('Enter the name of the library:'))
                if not library:
                    break
                prints(_('Enter a search expression, access will be granted only to books matching this expression.'
                            ' An empty expression will grant access to all books.'))
                plr = get_input(_('Search expression:'))
                if plr:
                    r['library_restrictions'][library] = plr
                else:
                    r['library_restrictions'].pop(library, None)
                m.update_user_restrictions(username, r)
                if get_input(_('Another restriction?') + ' (y/n):') != 'y':
                    break
        elif c == 4:
            pass
        else:
            names = get_input(_('Enter a comma separated list of library names:'))
            names = filter(None, [x.strip() for x in names.split(',')])
            w = 'allowed_library_names' if c == 1 else 'blocked_library_names'
            t = _('Allowing access only to libraries: {}') if c == 1 else _(
                'Allowing access to all libraries, except: {}')
            prints(t.format(', '.join(names)))
            m.update_user_restrictions(username, {w:names})

    def edit_user(username=None):
        username = username or get_valid_user()
        c = choice(choices=[
            _('Show password for {}').format(username),
            _('Change password for {}').format(username),
            _('Change read/write permission for {}').format(username),
            _('Change the libraries {} is allowed to access').format(username),
            _('Cancel'),
        ], banner='\n' + _('{} has {} access').format(
            username, _('readonly') if m.is_readonly(username) else _('read-write'))
        )
        print()
        if c > 3:
            actions.append(toplevel)
            return
        {0: show_password, 1: change_password, 2: change_readonly, 3: change_restriction}[c](username)
        actions.append(partial(edit_user, username=username))

    def toplevel():
        {0:add_user, 1:edit_user, 2:remove_user, 3:lambda: None}[choice(choices=[
            _('Add a new user'), _('Edit an existing user'), _('Remove a user'),
            _('Cancel')])]()

    actions = [toplevel]
    while actions:
        actions[0]()
        del actions[0]


# }}}

def create_option_parser():
    parser=opts_to_parser('%prog '+ _(
'''[options] [path to library folder...]

Start the calibre Content server. The calibre Content server exposes your
calibre libraries over the internet. You can specify the path to the library
folders as arguments to %prog. If you do not specify any paths, all the
libraries that the main calibre program knows about will be used.
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
    if not iswindows and not isosx:
        # Does not work on OS X because we dont have a headless Qt backend
        parser.add_option('--daemonize', default=False, action='store_true',
            help=_('Run process in background as a daemon.'))
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
    parser.get_option('--userdb').help = _(
        'Path to the user database to use for authentication. The database'
        ' is a SQLite file. To create it use {0}. You can read more'
        ' about managing users at: {1}').format(
            '--manage-users', localize_user_manual_link(
                'https://manual.calibre-ebook.com/server.html#managing-user-accounts-from-the-command-line-only'
    ))

    return parser


option_parser = create_option_parser


def ensure_single_instance():
    if b'CALIBRE_NO_SI_DANGER_DANGER' not in os.environ and not singleinstance('db'):
        ext = '.exe' if iswindows else ''
        raise SystemExit(_(
            'Another calibre program such as another instance of {} or the main'
            ' calibre program is running. Having multiple programs that can make'
            ' changes to a calibre library running at the same time is not supported.'
        ).format('calibre-server' + ext)
        )


def main(args=sys.argv):
    opts, args=create_option_parser().parse_args(args)
    ensure_single_instance()
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
    libraries = libraries or load_gui_libraries()
    if not libraries:
        if not prefs['library_path']:
            raise SystemExit(_('You must specify at least one calibre library'))
        libraries=[prefs['library_path']]

    if opts.auto_reload:
        if getattr(opts, 'daemonize', False):
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
    if getattr(opts, 'daemonize', False):
        if not opts.log and not iswindows:
            raise SystemExit('In order to daemonize you must specify a log file, you can use /dev/stdout to log to screen even as a daemon')
        daemonize()
    if opts.pidfile:
        with lopen(opts.pidfile, 'wb') as f:
            f.write(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda s,f: server.stop())
    if not getattr(opts, 'daemonize', False) and not iswindows:
        signal.signal(signal.SIGHUP, lambda s,f: server.stop())
    # Needed for dynamic cover generation, which uses Qt for drawing
    from calibre.gui2 import ensure_app, load_builtin_fonts
    ensure_app(), load_builtin_fonts()
    server.serve_forever()
