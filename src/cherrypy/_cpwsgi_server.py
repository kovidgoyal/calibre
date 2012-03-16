"""WSGI server interface (see PEP 333). This adds some CP-specific bits to
the framework-agnostic wsgiserver package.
"""
import sys

import cherrypy
from cherrypy import wsgiserver


class CPWSGIServer(wsgiserver.CherryPyWSGIServer):
    """Wrapper for wsgiserver.CherryPyWSGIServer.
    
    wsgiserver has been designed to not reference CherryPy in any way,
    so that it can be used in other frameworks and applications. Therefore,
    we wrap it here, so we can set our own mount points from cherrypy.tree
    and apply some attributes from config -> cherrypy.server -> wsgiserver.
    """
    
    def __init__(self, server_adapter=cherrypy.server):
        self.server_adapter = server_adapter
        self.max_request_header_size = self.server_adapter.max_request_header_size or 0
        self.max_request_body_size = self.server_adapter.max_request_body_size or 0
        
        server_name = (self.server_adapter.socket_host or
                       self.server_adapter.socket_file or
                       None)
        
        self.wsgi_version = self.server_adapter.wsgi_version
        s = wsgiserver.CherryPyWSGIServer
        s.__init__(self, server_adapter.bind_addr, cherrypy.tree,
                   self.server_adapter.thread_pool,
                   server_name,
                   max = self.server_adapter.thread_pool_max,
                   request_queue_size = self.server_adapter.socket_queue_size,
                   timeout = self.server_adapter.socket_timeout,
                   shutdown_timeout = self.server_adapter.shutdown_timeout,
                   )
        self.protocol = self.server_adapter.protocol_version
        self.nodelay = self.server_adapter.nodelay

        if sys.version_info >= (3, 0):
            ssl_module = self.server_adapter.ssl_module or 'builtin'
        else:
            ssl_module = self.server_adapter.ssl_module or 'pyopenssl'
        if self.server_adapter.ssl_context:
            adapter_class = wsgiserver.get_ssl_adapter_class(ssl_module)
            self.ssl_adapter = adapter_class(
                self.server_adapter.ssl_certificate,
                self.server_adapter.ssl_private_key,
                self.server_adapter.ssl_certificate_chain)
            self.ssl_adapter.context = self.server_adapter.ssl_context
        elif self.server_adapter.ssl_certificate:
            adapter_class = wsgiserver.get_ssl_adapter_class(ssl_module)
            self.ssl_adapter = adapter_class(
                self.server_adapter.ssl_certificate,
                self.server_adapter.ssl_private_key,
                self.server_adapter.ssl_certificate_chain)
        
        self.stats['Enabled'] = getattr(self.server_adapter, 'statistics', False)

    def error_log(self, msg="", level=20, traceback=False):
        cherrypy.engine.log(msg, level, traceback)

