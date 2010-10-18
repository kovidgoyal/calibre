#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys
from threading import Thread

from calibre.library.server import server_config as config
from calibre.library.server.base import LibraryServer
from calibre.constants import iswindows
import cherrypy

def start_threaded_server(db, opts):
    server = LibraryServer(db, opts, embedded=True)
    server.thread = Thread(target=server.start)
    server.thread.setDaemon(True)
    server.thread.start()
    return server

def stop_threaded_server(server):
    server.exit()
    server.thread = None

def option_parser():
    parser = config().option_parser('%prog '+ _('[options]\n\nStart the calibre content server.'))
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
    return parser


def main(args=sys.argv):
    from calibre.library.database2 import LibraryDatabase2
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if opts.daemonize and not iswindows:
        from cherrypy.process.plugins import Daemonizer
        d = Daemonizer(cherrypy.engine)
        d.subscribe()
    if opts.pidfile is not None:
        with open(opts.pidfile, 'wb') as f:
            f.write(str(os.getpid()))
    cherrypy.log.screen = True
    from calibre.utils.config import prefs
    if opts.with_library is None:
        opts.with_library = prefs['library_path']
    db = LibraryDatabase2(opts.with_library)
    server = LibraryServer(db, opts)
    server.start()
    return 0

if __name__ == '__main__':
    sys.exit(main())
