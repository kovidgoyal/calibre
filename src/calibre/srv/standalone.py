#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, signal

from calibre import as_unicode
from calibre.constants import plugins, iswindows
from calibre.srv.errors import InvalidCredentials
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
        log = None
        if opts.log:
            log = RotatingLog(opts.log, max_size=opts.max_log_size)
        self.handler = Handler(libraries, opts)
        plugins = []
        if opts.use_bonjour:
            plugins.append(BonJour())
        self.loop = ServerLoop(create_http_handler(self.handler.dispatch), opts=opts, log=log, plugins=plugins)
        self.handler.set_log(self.loop.log)
        self.serve_forever = self.loop.serve_forever
        self.stop = self.loop.stop
        _df = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        if _df and os.path.exists(_df):
            from calibre.utils.rapydscript import compile_srv
            compile_srv()


def create_option_parser():
    parser = opts_to_parser('%prog '+ _(
'''[options] [path to library folder ...]

Start the calibre content server. The calibre content server
exposes your calibre libraries over the internet. You can specify
the path to the library folders as arguments to %prog. If you do
not specify any paths, the library last opened (if any) in the main calibre
program will be used.
'''
    ))
    parser.add_option(
        '--log', default=None,
        help=_('Path to log file for server log'))
    parser.add_option('--daemonize', default=False, action='store_true',
        help=_('Run process in background as a daemon. No effect on Windows.'))
    parser.add_option('--pidfile', default=None,
        help=_('Write process PID to the specified file'))
    parser.add_option(
        '--auto-reload', default=False, action='store_true',
        help=_('Automatically reload server when source code changes. Useful'
               ' for development. You should also specify a small value for the'
               ' shutdown timeout.'))

    return parser

def main(args=sys.argv):
    opts, args = create_option_parser().parse_args(args)
    libraries = args[1:]
    for lib in libraries:
        if not lib or not LibraryDatabase.exists_at(lib):
            raise SystemExit(_('There is no calibre library at: %s') % lib)
    if not libraries:
        if not prefs['library_path']:
            raise SystemExit(_('You must specify at least one calibre library'))
        libraries = [prefs['library_path']]

    if opts.auto_reload:
        if opts.daemonize:
            raise SystemExit('Cannot specify --auto-reload and --daemonize at the same time')
        from calibre.srv.auto_reload import auto_reload, NoAutoReload
        try:
            from calibre.utils.logging import default_log
            return auto_reload(default_log)
        except NoAutoReload as e:
            raise SystemExit(e.message)
    try:
        server = Server(libraries, opts)
    except InvalidCredentials as e:
        raise SystemExit(e.message)
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
    server.serve_forever()
