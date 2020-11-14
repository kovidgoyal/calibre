#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import signal
import sys

from calibre import as_unicode
from calibre.constants import is_running_from_develop, ismacos, iswindows
from calibre.db.delete_service import shutdown as shutdown_delete_service
from calibre.db.legacy import LibraryDatabase
from calibre.srv.bonjour import BonJour
from calibre.srv.handler import Handler
from calibre.srv.http_response import create_http_handler
from calibre.srv.library_broker import load_gui_libraries
from calibre.srv.loop import BadIPSpec, ServerLoop
from calibre.srv.manage_users_cli import manage_users_cli
from calibre.srv.opts import opts_to_parser
from calibre.srv.users import connect
from calibre.srv.utils import HandleInterrupt, RotatingLog
from calibre.utils.config import prefs
from calibre.utils.localization import localize_user_manual_link
from calibre.utils.lock import singleinstance
from polyglot.builtins import error_message, unicode_type
from calibre_extensions import speedup


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
    speedup.detach(os.devnull)


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
        if opts.custom_list_template:
            with lopen(os.path.expanduser(opts.custom_list_template), 'rb') as f:
                self.handler.router.ctx.custom_list_template = json.load(f)
        if opts.search_the_net_urls:
            with lopen(os.path.expanduser(opts.search_the_net_urls), 'rb') as f:
                self.handler.router.ctx.search_the_net_urls = json.load(f)
        plugins = []
        if opts.use_bonjour:
            plugins.append(BonJour(wait_for_stop=max(0, opts.shutdown_timeout - 0.2)))
        self.loop = ServerLoop(
            create_http_handler(self.handler.dispatch),
            opts=opts,
            log=log,
            access_log=access_log,
            plugins=plugins)
        self.handler.set_log(self.loop.log)
        self.handler.set_jobs_manager(self.loop.jobs_manager)
        self.serve_forever = self.loop.serve_forever
        self.stop = self.loop.stop
        if is_running_from_develop:
            from calibre.utils.rapydscript import compile_srv
            compile_srv()


def create_option_parser():
    parser = opts_to_parser(
        '%prog ' + _(
            '''[options] [path to library folder...]

Start the calibre Content server. The calibre Content server exposes your
calibre libraries over the internet. You can specify the path to the library
folders as arguments to %prog. If you do not specify any paths, all the
libraries that the main calibre program knows about will be used.
'''))
    parser.add_option(
        '--log',
        default=None,
        help=_(
            'Path to log file for server log. This log contains server information and errors, not access logs. By default it is written to stdout.'
        ))
    parser.add_option(
        '--access-log',
        default=None,
        help=_(
            'Path to the access log file. This log contains information'
            ' about clients connecting to the server and making requests. By'
            ' default no access logging is done.'))
    parser.add_option(
        '--custom-list-template', help=_(
            'Path to a JSON file containing a template for the custom book list mode.'
            ' The easiest way to create such a template file is to go to Preferences->'
            ' Sharing over the net-> Book list template in calibre, create the'
            ' template and export it.'
    ))
    parser.add_option(
        '--search-the-net-urls', help=_(
            'Path to a JSON file containing URLs for the "Search the internet" feature.'
            ' The easiest way to create such a file is to go to Preferences->'
            ' Sharing over the net->Search the internet in calibre, create the'
            ' URLs and export them.'
    ))

    if not iswindows and not ismacos:
        # Does not work on macOS because if we fork() we cannot connect to Core
        # Serives which is needed by the QApplication() constructor, which in
        # turn is needed by ensure_app()
        parser.add_option(
            '--daemonize',
            default=False,
            action='store_true',
            help=_('Run process in background as a daemon (Linux only).'))
    parser.add_option(
        '--pidfile', default=None, help=_('Write process PID to the specified file'))
    parser.add_option(
        '--auto-reload',
        default=False,
        action='store_true',
        help=_(
            'Automatically reload server when source code changes. Useful'
            ' for development. You should also specify a small value for the'
            ' shutdown timeout.'))
    parser.add_option(
        '--manage-users',
        default=False,
        action='store_true',
        help=_(
            'Manage the database of users allowed to connect to this server.'
            ' See also the %s option.') % '--userdb')
    parser.get_option('--userdb').help = _(
        'Path to the user database to use for authentication. The database'
        ' is a SQLite file. To create it use {0}. You can read more'
        ' about managing users at: {1}'
    ).format(
        '--manage-users',
        localize_user_manual_link(
            'https://manual.calibre-ebook.com/server.html#managing-user-accounts-from-the-command-line-only'
        ))

    return parser


option_parser = create_option_parser


def ensure_single_instance():
    if 'CALIBRE_NO_SI_DANGER_DANGER' not in os.environ and not singleinstance('db'):
        ext = '.exe' if iswindows else ''
        raise SystemExit(
            _(
                'Another calibre program such as another instance of {} or the main'
                ' calibre program is running. Having multiple programs that can make'
                ' changes to a calibre library running at the same time is not supported.'
            ).format('calibre-server' + ext))


def main(args=sys.argv):
    opts, args = create_option_parser().parse_args(args)
    if opts.auto_reload and not opts.manage_users:
        if getattr(opts, 'daemonize', False):
            raise SystemExit(
                'Cannot specify --auto-reload and --daemonize at the same time')
        from calibre.srv.auto_reload import NoAutoReload, auto_reload
        try:
            from calibre.utils.logging import default_log
            return auto_reload(default_log, listen_on=opts.listen_on)
        except NoAutoReload as e:
            raise SystemExit(error_message(e))

    ensure_single_instance()
    if opts.userdb:
        opts.userdb = os.path.abspath(os.path.expandvars(os.path.expanduser(opts.userdb)))
        connect(opts.userdb, exc_class=SystemExit).close()
    if opts.manage_users:
        try:
            manage_users_cli(opts.userdb)
        except (KeyboardInterrupt, EOFError):
            raise SystemExit(_('Interrupted by user'))
        raise SystemExit(0)

    libraries = args[1:]
    for lib in libraries:
        if not lib or not LibraryDatabase.exists_at(lib):
            raise SystemExit(_('There is no calibre library at: %s') % lib)
    libraries = libraries or load_gui_libraries()
    if not libraries:
        if not prefs['library_path']:
            raise SystemExit(_('You must specify at least one calibre library'))
        libraries = [prefs['library_path']]

    opts.auto_reload_port = int(os.environ.get('CALIBRE_AUTORELOAD_PORT', 0))
    opts.allow_console_print = 'CALIBRE_ALLOW_CONSOLE_PRINT' in os.environ
    if opts.log and os.path.isdir(opts.log):
        raise SystemExit('The --log option must point to a file, not a directory')
    if opts.access_log and os.path.isdir(opts.access_log):
        raise SystemExit('The --access-log option must point to a file, not a directory')
    try:
        server = Server(libraries, opts)
    except BadIPSpec as e:
        raise SystemExit('{}'.format(e))
    if getattr(opts, 'daemonize', False):
        if not opts.log and not iswindows:
            raise SystemExit(
                'In order to daemonize you must specify a log file, you can use /dev/stdout to log to screen even as a daemon'
            )
        daemonize()
    if opts.pidfile:
        with lopen(opts.pidfile, 'wb') as f:
            f.write(unicode_type(os.getpid()).encode('ascii'))
    signal.signal(signal.SIGTERM, lambda s, f: server.stop())
    if not getattr(opts, 'daemonize', False) and not iswindows:
        signal.signal(signal.SIGHUP, lambda s, f: server.stop())
    # Needed for dynamic cover generation, which uses Qt for drawing
    from calibre.gui2 import ensure_app, load_builtin_fonts
    ensure_app(), load_builtin_fonts()
    with HandleInterrupt(server.stop):
        try:
            server.serve_forever()
        finally:
            shutdown_delete_service()
