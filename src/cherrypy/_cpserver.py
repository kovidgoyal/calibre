"""Manage HTTP servers with CherryPy."""

import warnings

import cherrypy
from cherrypy.lib import attributes

# We import * because we want to export check_port
# et al as attributes of this module.
from cherrypy.process.servers import *


class Server(ServerAdapter):
    """An adapter for an HTTP server.
    
    You can set attributes (like socket_host and socket_port)
    on *this* object (which is probably cherrypy.server), and call
    quickstart. For example:
    
        cherrypy.server.socket_port = 80
        cherrypy.quickstart()
    """
    
    socket_port = 8080
    
    _socket_host = '127.0.0.1'
    def _get_socket_host(self):
        return self._socket_host
    def _set_socket_host(self, value):
        if not value:
            raise ValueError("Host values of '' or None are not allowed. "
                             "Use '0.0.0.0' instead to listen on all active "
                             "interfaces (INADDR_ANY).")
        self._socket_host = value
    socket_host = property(_get_socket_host, _set_socket_host,
        doc="""The hostname or IP address on which to listen for connections.
        
        Host values may be any IPv4 or IPv6 address, or any valid hostname.
        The string 'localhost' is a synonym for '127.0.0.1' (or '::1', if
        your hosts file prefers IPv6). The string '0.0.0.0' is a special
        IPv4 entry meaning "any active interface" (INADDR_ANY), and '::'
        is the similar IN6ADDR_ANY for IPv6. The empty string or None are
        not allowed.""")
    
    socket_file = ''
    socket_queue_size = 5
    socket_timeout = 10
    shutdown_timeout = 5
    protocol_version = 'HTTP/1.1'
    reverse_dns = False
    thread_pool = 10
    thread_pool_max = -1
    max_request_header_size = 500 * 1024
    max_request_body_size = 100 * 1024 * 1024
    instance = None
    ssl_certificate = None
    ssl_private_key = None
    nodelay = True
    
    def __init__(self):
        ServerAdapter.__init__(self, cherrypy.engine)
    
    def quickstart(self, server=None):
        """This does nothing now and will be removed in 3.2."""
        warnings.warn('quickstart does nothing now and will be removed in '
                      '3.2. Call cherrypy.engine.start() instead.',
                      DeprecationWarning)
    
    def httpserver_from_self(self, httpserver=None):
        """Return a (httpserver, bind_addr) pair based on self attributes."""
        if httpserver is None:
            httpserver = self.instance
        if httpserver is None:
            from cherrypy import _cpwsgi_server
            httpserver = _cpwsgi_server.CPWSGIServer()
        if isinstance(httpserver, basestring):
            httpserver = attributes(httpserver)()
        
        if self.socket_file:
            return httpserver, self.socket_file
        
        host = self.socket_host
        port = self.socket_port
        return httpserver, (host, port)
    
    def start(self):
        """Start the HTTP server."""
        if not self.httpserver:
            self.httpserver, self.bind_addr = self.httpserver_from_self()
        ServerAdapter.start(self)
    start.priority = 75
    
    def base(self):
        """Return the base (scheme://host) for this server."""
        if self.socket_file:
            return self.socket_file
        
        host = self.socket_host
        if host in ('0.0.0.0', '::'):
            # 0.0.0.0 is INADDR_ANY and :: is IN6ADDR_ANY.
            # Look up the host name, which should be the
            # safest thing to spit out in a URL.
            import socket
            host = socket.gethostname()
        
        port = self.socket_port
        
        if self.ssl_certificate:
            scheme = "https"
            if port != 443:
                host += ":%s" % port
        else:
            scheme = "http"
            if port != 80:
                host += ":%s" % port
        
        return "%s://%s" % (scheme, host)

