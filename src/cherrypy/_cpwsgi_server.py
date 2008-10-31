"""WSGI server interface (see PEP 333). This adds some CP-specific bits to
the framework-agnostic wsgiserver package.
"""

import cherrypy
from cherrypy import wsgiserver


class CPHTTPRequest(wsgiserver.HTTPRequest):
    
    def __init__(self, sendall, environ, wsgi_app):
        s = cherrypy.server
        self.max_request_header_size = s.max_request_header_size or 0
        self.max_request_body_size = s.max_request_body_size or 0
        wsgiserver.HTTPRequest.__init__(self, sendall, environ, wsgi_app)


class CPHTTPConnection(wsgiserver.HTTPConnection):
    
    RequestHandlerClass = CPHTTPRequest


class CPWSGIServer(wsgiserver.CherryPyWSGIServer):
    """Wrapper for wsgiserver.CherryPyWSGIServer.
    
    wsgiserver has been designed to not reference CherryPy in any way,
    so that it can be used in other frameworks and applications. Therefore,
    we wrap it here, so we can set our own mount points from cherrypy.tree
    and apply some attributes from config -> cherrypy.server -> wsgiserver.
    """
    
    ConnectionClass = CPHTTPConnection
    
    def __init__(self):
        server = cherrypy.server
        sockFile = server.socket_file
        if sockFile:
            bind_addr = sockFile
        else:
            bind_addr = (server.socket_host, server.socket_port)
        
        s = wsgiserver.CherryPyWSGIServer
        s.__init__(self, bind_addr, cherrypy.tree,
                   server.thread_pool,
                   server.socket_host,
                   request_queue_size = server.socket_queue_size,
                   timeout = server.socket_timeout,
                   shutdown_timeout = server.shutdown_timeout,
                   )
        self.protocol = server.protocol_version
        self.nodelay = server.nodelay
        self.ssl_certificate = server.ssl_certificate
        self.ssl_private_key = server.ssl_private_key

