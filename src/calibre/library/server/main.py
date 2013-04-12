#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os
from threading import Thread

from calibre.library.server import server_config as config
from calibre.library.server.base import LibraryServer
from calibre.constants import iswindows
import cherrypy

def start_threaded_server(db, opts):
    server = LibraryServer(db, opts, embedded=True, show_tracebacks=False)
    server.thread = Thread(target=server.start)
    server.thread.setDaemon(True)
    server.thread.start()
    return server

def stop_threaded_server(server):
    server.exit()
    server.thread = None

def create_wsgi_app(path_to_library=None, prefix='', virtual_library=None):
    'WSGI entry point'
    from calibre.library import db
    cherrypy.config.update({'environment': 'embedded'})
    db = db(path_to_library)
    parser = option_parser()
    opts, args = parser.parse_args(['calibre-server'])
    opts.url_prefix = prefix
    opts.restriction = virtual_library
    server = LibraryServer(db, opts, wsgi=True, show_tracebacks=True)
    return cherrypy.Application(server, script_name=None, config=server.config)

def option_parser():
    parser = config().option_parser('%prog '+ _(
'''[options]

Start the calibre content server. The calibre content server
exposes your calibre library over the internet. The default interface
allows you to browse you calibre library by categories. You can also
access an interface optimized for mobile browsers at /mobile and an
OPDS based interface for use with reading applications at /opds.

The OPDS interface is advertised via BonJour automatically.
'''
))
    parser.add_option('--with-library', default=None,
            help=_('Path to the library folder to serve with the content server'))
    parser.add_option('--pidfile', default=None,
            help=_('Write process PID to the specified file'))
    parser.add_option('--daemonize', default=False, action='store_true',
            help='Run process in background as a daemon. No effect on windows.')
    parser.add_option('--restriction', default=None,
            help=_('Specifies a restriction to be used for this invocation. '
                   'This option overrides any per-library settings specified'
                   ' in the GUI'))
    parser.add_option('--auto-reload', default=False, action='store_true',
            help=_('Auto reload server when source code changes. May not'
                ' work in all environments.'))
    return parser

def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError as e:
        print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

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
        print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    # Redirect standard file descriptors.
    si = file(stdin, 'r')
    so = file(stdout, 'a+')
    se = file(stderr, 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())


def main(args=sys.argv):
    from calibre.library.database2 import LibraryDatabase2
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if opts.daemonize and not iswindows:
        daemonize()
    if opts.pidfile is not None:
        from cherrypy.process.plugins import PIDFile
        PIDFile(cherrypy.engine, opts.pidfile).subscribe()
    cherrypy.log.screen = True
    from calibre.utils.config import prefs
    if opts.with_library is None:
        opts.with_library = prefs['library_path']
    if not opts.with_library:
        print('No saved library path. Use the --with-library option'
                ' to specify the path to the library you want to use.')
        return 1
    db = LibraryDatabase2(opts.with_library)
    server = LibraryServer(db, opts, show_tracebacks=opts.develop)
    server.start()
    return 0

if __name__ == '__main__':
    sys.exit(main())
