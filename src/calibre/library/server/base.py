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
from calibre.library.server.utils import expose, AuthController
from calibre.utils.mdns import publish as publish_zeroconf, \
            stop_server as stop_zeroconf, get_external_ip
from calibre.library.server.content import ContentServer
from calibre.library.server.mobile import MobileServer
from calibre.library.server.xml import XMLServer
from calibre.library.server.opds import OPDSServer
from calibre.library.server.cache import Cache
from calibre.library.server.browse import BrowseServer
from calibre.library.server.ajax import AjaxServer
from calibre.utils.search_query_parser import saved_searches
from calibre import prints, as_unicode


class DispatchController(object): # {{{

    def __init__(self, prefix, wsgi=False, auth_controller=None):
        self.dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.funcs = []
        self.seen = set()
        self.auth_controller = auth_controller
        self.prefix = prefix if prefix else ''
        if wsgi:
            self.prefix = ''

    def __call__(self, name, route, func, **kwargs):
        if name in self.seen:
            raise NameError('Route name: '+ repr(name) + ' already used')
        self.seen.add(name)
        kwargs['action'] = 'f_%d'%len(self.funcs)
        aw = kwargs.pop('android_workaround', False)
        if route != '/':
            route = self.prefix + route
        elif self.prefix:
            self.dispatcher.connect(name+'prefix_extra', self.prefix, self,
                    **kwargs)
            self.dispatcher.connect(name+'prefix_extra_trailing',
                    self.prefix+'/', self, **kwargs)
        self.dispatcher.connect(name, route, self, **kwargs)
        if self.auth_controller is not None:
            func = self.auth_controller(func, aw)
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

    def __init__(self, engine, port=8080, prefix=''):
        SimplePlugin.__init__(self, engine)
        self.port = port
        self.prefix = prefix

    def start(self):
        try:
            publish_zeroconf('Books in calibre', '_stanza._tcp',
                            self.port, {'path':self.prefix+'/stanza'})
            publish_zeroconf('Books in calibre', '_calibre._tcp',
                    self.port, {'path':self.prefix+'/opds'})
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
        BrowseServer, AjaxServer):

    server_name = __appname__ + '/' + __version__

    def __init__(self, db, opts, embedded=False, show_tracebacks=True,
            wsgi=False):
        self.is_wsgi = bool(wsgi)
        self.opts = opts
        self.embedded = embedded
        self.state_callback = None
        self.start_failure_callback = None
        try:
            self.max_cover_width, self.max_cover_height = \
                        map(int, self.opts.max_cover.split('x'))
        except:
            self.max_cover_width = 1200
            self.max_cover_height = 1600
        path = P('content_server')
        self.build_time = fromtimestamp(os.stat(path).st_mtime)
        self.default_cover = open(P('content_server/default_cover.jpg'), 'rb').read()
        if not opts.url_prefix:
            opts.url_prefix = ''

        cherrypy.engine.bonjour.port = opts.port
        cherrypy.engine.bonjour.prefix = opts.url_prefix

        Cache.__init__(self)

        self.set_database(db)

        st = 0.1 if opts.develop else 1

        cherrypy.config.update({
            'log.screen'             : opts.develop,
            'engine.autoreload_on'   : getattr(opts,
                                        'auto_reload', False),
            'tools.log_headers.on'   : opts.develop,
            'tools.encode.encoding'  : 'UTF-8',
            'checker.on'             : opts.develop,
            'request.show_tracebacks': show_tracebacks,
            'server.socket_host'     : listen_on,
            'server.socket_port'     : opts.port,
            'server.socket_timeout'  : opts.timeout, #seconds
            'server.thread_pool'     : opts.thread_pool, # number of threads
            'server.shutdown_timeout': st, # minutes
        })
        if embedded or wsgi:
            cherrypy.config.update({'engine.SIGHUP'          : None,
                                    'engine.SIGTERM'         : None,})
        self.config = {}
        self.is_running = False
        self.exception = None
        auth_controller = None
        self.users_dict = {}
        #self.config['/'] = {
        #    'tools.sessions.on' : True,
        #    'tools.sessions.timeout': 60, # Session times out after 60 minutes
        #}

        if not wsgi:
            self.setup_loggers()
            cherrypy.engine.bonjour.subscribe()
            self.config['global'] = {
                'tools.gzip.on'        : True,
                'tools.gzip.mime_types': ['text/html', 'text/plain',
                    'text/xml', 'text/javascript', 'text/css'],
            }

            if opts.password:
                self.users_dict[opts.username.strip()] = opts.password.strip()
                auth_controller = AuthController('Your calibre library',
                        self.users_dict)

        self.__dispatcher__ = DispatchController(self.opts.url_prefix,
                wsgi=wsgi, auth_controller=auth_controller)
        for x in self.__class__.__bases__:
            if hasattr(x, 'add_routes'):
                x.__init__(self)
                x.add_routes(self, self.__dispatcher__)
        root_conf = self.config.get('/', {})
        root_conf['request.dispatch'] = self.__dispatcher__.dispatcher
        self.config['/'] = root_conf

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
            if restriction not in saved_searches().names():
                prints('WARNING: Content server: search restriction ',
                       restriction, ' does not exist')
                self.search_restriction = ''
            else:
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

    def start_cherrypy(self):
        try:
            cherrypy.engine.start()
        except:
            ip = get_external_ip()
            if not ip or ip.startswith('127.'):
                raise
            cherrypy.log('Trying to bind to single interface: '+ip)
            # Change the host we listen on
            cherrypy.config.update({'server.socket_host' : ip})
            # This ensures that the change is actually applied
            cherrypy.server.socket_host = ip
            cherrypy.server.httpserver = cherrypy.server.instance = None

            cherrypy.engine.start()

    def start(self):
        self.is_running = False
        self.exception = None
        cherrypy.tree.mount(root=None, config=self.config)
        try:
            self.start_cherrypy()
        except Exception as e:
            self.exception = e
            import traceback
            traceback.print_exc()
            if callable(self.start_failure_callback):
                try:
                    self.start_failure_callback(as_unicode(e))
                except:
                    pass
            return

        try:
            self.is_running = True
            self.notify_listener()
            cherrypy.engine.block()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.exception = e
        finally:
            self.is_running = False
            self.notify_listener()

    def notify_listener(self):
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
            self.notify_listener()

    def threaded_exit(self):
        from threading import Thread
        t = Thread(target=self.exit)
        t.daemon = True
        t.start()

