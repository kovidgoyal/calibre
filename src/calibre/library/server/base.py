#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import logging
from logging.handlers import RotatingFileHandler

import cherrypy
from cherrypy.process.plugins import SimplePlugin

from calibre.constants import __appname__, __version__
from calibre.utils.date import fromtimestamp
from calibre.library.server import listen_on, log_access_file, log_error_file
from calibre.library.server.utils import expose
from calibre.utils.mdns import publish as publish_zeroconf, \
            stop_server as stop_zeroconf, get_external_ip
from calibre.library.server.content import ContentServer
from calibre.library.server.mobile import MobileServer
from calibre.library.server.xml import XMLServer
from calibre.library.server.opds import OPDSServer
from calibre.library.server.cache import Cache
from calibre.library.server.browse import BrowseServer


class DispatchController(object): # {{{

    def __init__(self, prefix):
        self.dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.funcs = []
        self.seen = set([])
        self.prefix = prefix if prefix else ''

    def __call__(self, name, route, func, **kwargs):
        if name in self.seen:
            raise NameError('Route name: '+ repr(name) + ' already used')
        self.seen.add(name)
        kwargs['action'] = 'f_%d'%len(self.funcs)
        if route != '/':
            route = self.prefix + route
        self.dispatcher.connect(name, route, self, **kwargs)
        self.funcs.append(expose(func))

    def __getattr__(self, attr):
        if not attr.startswith('f_'):
            raise AttributeError(attr + ' not found')
        num = attr.rpartition('_')[-1]
        try:
            num = int(num)
        except:
            raise AttributeError(attr + ' not found')
        if num < 0 or num >= len(self.funcs):
            raise AttributeError(attr + ' not found')
        return self.funcs[num]

# }}}

class BonJour(SimplePlugin): # {{{

    def __init__(self, engine, port=8080):
        SimplePlugin.__init__(self, engine)
        self.port = port

    def start(self):
        try:
            publish_zeroconf('Books in calibre', '_stanza._tcp',
                            self.port, {'path':'/stanza'})
        except:
            import traceback
            cherrypy.log.error('Failed to start BonJour:')
            cherrypy.log.error(traceback.format_exc())

    start.priority = 90

    def stop(self):
        try:
            stop_zeroconf()
        except:
            import traceback
            cherrypy.log.error('Failed to stop BonJour:')
            cherrypy.log.error(traceback.format_exc())


    stop.priority = 10

cherrypy.engine.bonjour = BonJour(cherrypy.engine)

# }}}

class LibraryServer(ContentServer, MobileServer, XMLServer, OPDSServer, Cache,
        BrowseServer):

    server_name = __appname__ + '/' + __version__

    def __init__(self, db, opts, embedded=False, show_tracebacks=True):
        self.opts = opts
        self.embedded = embedded
        self.state_callback = None
        self.max_cover_width, self.max_cover_height = \
                        map(int, self.opts.max_cover.split('x'))
        path = P('content_server')
        self.build_time = fromtimestamp(os.stat(path).st_mtime)
        self.default_cover = open(P('content_server/default_cover.jpg'), 'rb').read()

        cherrypy.engine.bonjour.port = opts.port

        Cache.__init__(self)

        self.set_database(db)

        cherrypy.config.update({
                                'log.screen'             : opts.develop,
                                'engine.autoreload_on'   : opts.develop,
                                'tools.log_headers.on'   : opts.develop,
                                'checker.on'             : opts.develop,
                                'request.show_tracebacks': show_tracebacks,
                                'server.socket_host'     : listen_on,
                                'server.socket_port'     : opts.port,
                                'server.socket_timeout'  : opts.timeout, #seconds
                                'server.thread_pool'     : opts.thread_pool, # number of threads
                               })
        if embedded:
            cherrypy.config.update({'engine.SIGHUP'          : None,
                                    'engine.SIGTERM'         : None,})
        self.config = {'global': {
            'tools.gzip.on'        : True,
            'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/xml', 'text/javascript', 'text/css'],
        }}
        if opts.password:
            self.config['/'] = {
                      'tools.digest_auth.on'    : True,
                      'tools.digest_auth.realm' : (_('Password to access your calibre library. Username is ') + opts.username.strip()).encode('ascii', 'replace'),
                      'tools.digest_auth.users' : {opts.username.strip():opts.password.strip()},
                      }


        self.is_running = False
        self.exception = None
        self.setup_loggers()
        cherrypy.engine.bonjour.subscribe()

    def set_database(self, db):
        self.db = db
        sr = getattr(self.opts, 'restriction', None)
        sr = db.prefs.get('cs_restriction', '') if sr is None else sr
        self.set_search_restriction(sr)

    def graceful(self):
        cherrypy.engine.graceful()

    def set_search_restriction(self, restriction):
        self.search_restriction_name = restriction
        if restriction:
            self.search_restriction = 'search:"%s"'%restriction
        else:
            self.search_restriction = ''
        self.reset_caches()

    def setup_loggers(self):
        access_file = log_access_file
        error_file  = log_error_file
        log = cherrypy.log

        maxBytes = getattr(log, "rot_maxBytes", 10000000)
        backupCount = getattr(log, "rot_backupCount", 1000)

        # Make a new RotatingFileHandler for the error log.
        h = RotatingFileHandler(error_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.error_log.addHandler(h)

        # Make a new RotatingFileHandler for the access log.
        h = RotatingFileHandler(access_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.access_log.addHandler(h)

    def start(self):
        self.is_running = False
        d = DispatchController(self.opts.url_prefix)
        for x in self.__class__.__bases__:
            if hasattr(x, 'add_routes'):
                x.add_routes(self, d)
        root_conf = self.config.get('/', {})
        root_conf['request.dispatch'] = d.dispatcher
        self.config['/'] = root_conf

        cherrypy.tree.mount(root=None, config=self.config)
        try:
            try:
                cherrypy.engine.start()
            except:
                ip = get_external_ip()
                if not ip or ip == '127.0.0.1':
                    raise
                cherrypy.log('Trying to bind to single interface: '+ip)
                cherrypy.config.update({'server.socket_host' : ip})
                cherrypy.engine.start()

            self.is_running = True
            #if hasattr(cherrypy.engine, 'signal_handler'):
            #    cherrypy.engine.signal_handler.subscribe()

            cherrypy.engine.block()
        except Exception, e:
            self.exception = e
        finally:
            self.is_running = False
            try:
                if callable(self.state_callback):
                    self.state_callback(self.is_running)
            except:
                pass

    def exit(self):
        try:
            cherrypy.engine.exit()
        finally:
            cherrypy.server.httpserver = None
            self.is_running = False
            try:
                if callable(self.state_callback):
                    self.state_callback(self.is_running)
            except:
                pass


