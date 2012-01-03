"""Manage HTTP servers with CherryPy."""

import warnings

import cherrypy
from cherrypy.lib import attributes
from cherrypy._cpcompat import basestring, py3k

# We import * because we want to export check_port
# et al as attributes of this module.
from cherrypy.process.servers import *


class Server(ServerAdapter):
    """An adapter for an HTTP server.
    
    You can set attributes (like socket_host and socket_port)
    on *this* object (which is probably cherrypy.server), and call
    quickstart. For example::
    
        cherrypy.server.socket_port = 80
        cherrypy.quickstart()
    """
    
    socket_port = 8080
    """The TCP port on which to listen for connections."""
    
    _socket_host = '127.0.0.1'
    def _get_socket_host(self):
        return self._socket_host
    def _set_socket_host(self, value):
        if value == '':
            raise ValueError("The empty string ('') is not an allowed value. "
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
    
    socket_file = None
    """If given, the name of the UNIX socket to use instead of TCP/IP.
    
    When this option is not None, the `socket_host` and `socket_port` options
    are ignored."""
    
    socket_queue_size = 5
    """The 'backlog' argument to socket.listen(); specifies the maximum number
    of queued connections (default 5)."""
    
    socket_timeout = 10
    """The timeout in seconds for accepted connections (default 10)."""
    
    shutdown_timeout = 5
    """The time to wait for HTTP worker threads to clean up."""
    
    protocol_version = 'HTTP/1.1'
    """The version string to write in the Status-Line of all HTTP responses,
    for example, "HTTP/1.1" (the default). Depending on the HTTP server used,
    this should also limit the supported features used in the response."""
    
    thread_pool = 10
    """The number of worker threads to start up in the pool."""
    
    thread_pool_max = -1
    """The maximum size of the worker-thread pool. Use -1 to indicate no limit."""
    
    max_request_header_size = 500 * 1024
    """The maximum number of bytes allowable in the request headers. If exceeded,
    the HTTP server should return "413 Request Entity Too Large"."""
    
    max_request_body_size = 100 * 1024 * 1024
    """The maximum number of bytes allowable in the request body. If exceeded,
    the HTTP server should return "413 Request Entity Too Large"."""
    
    instance = None
    """If not None, this should be an HTTP server instance (such as
    CPWSGIServer) which cherrypy.server will control. Use this when you need
    more control over object instantiation than is available in the various
    configuration options."""
    
    ssl_context = None
    """When using PyOpenSSL, an instance of SSL.Context."""
    
    ssl_certificate = None
    """The filename of the SSL certificate to use."""
    
    ssl_certificate_chain = None
    """When using PyOpenSSL, the certificate chain to pass to
    Context.load_verify_locations."""
    
    ssl_private_key = None
    """The filename of the private key to use with SSL."""
    
    if py3k:
        ssl_module = 'builtin'
        """The name of a registered SSL adaptation module to use with the builtin
        WSGI server. Builtin options are: 'builtin' (to use the SSL library built
        into recent versions of Python). You may also register your
        own classes in the wsgiserver.ssl_adapters dict."""
    else:
        ssl_module = 'pyopenssl'
        """The name of a registered SSL adaptation module to use with the builtin
        WSGI server. Builtin options are 'builtin' (to use the SSL library built
        into recent versions of Python) and 'pyopenssl' (to use the PyOpenSSL
        project, which you must install separately). You may also register your
        own classes in the wsgiserver.ssl_adapters dict."""
    
    statistics = False
    """Turns statistics-gathering on or off for aware HTTP servers."""
    
    nodelay = True
    """If True (the default since 3.1), sets the TCP_NODELAY socket option."""
    
    wsgi_version = (1, 0)
    """The WSGI version tuple to use with the builtin WSGI server.
    The provided options are (1, 0) [which includes support for PEP 3333,
    which declares it covers WSGI version 1.0.1 but still mandates the
    wsgi.version (1, 0)] and ('u', 0), an experimental unicode version.
    You may create and register your own experimental versions of the WSGI
    protocol by adding custom classes to the wsgiserver.wsgi_gateways dict."""
    
    def __init__(self):
        self.bus = cherrypy.engine
        self.httpserver = None
        self.interrupt = None
        self.running = False
    
    def httpserver_from_self(self, httpserver=None):
        """Return a (httpserver, bind_addr) pair based on self attributes."""
        if httpserver is None:
            httpserver = self.instance
        if httpserver is None:
            from cherrypy import _cpwsgi_server
            httpserver = _cpwsgi_server.CPWSGIServer(self)
        if isinstance(httpserver, basestring):
            # Is anyone using this? Can I add an arg?
            httpserver = attributes(httpserver)(self)
        return httpserver, self.bind_addr
    
    def start(self):
        """Start the HTTP server."""
        if not self.httpserver:
            self.httpserver, self.bind_addr = self.httpserver_from_self()
        ServerAdapter.start(self)
    start.priority = 75
    
    def _get_bind_addr(self):
        if self.socket_file:
            return self.socket_file
        if self.socket_host is None and self.socket_port is None:
            return None
        return (self.socket_host, self.socket_port)
    def _set_bind_addr(self, value):
        if value is None:
            self.socket_file = None
            self.socket_host = None
            self.socket_port = None
        elif isinstance(value, basestring):
            self.socket_file = value
            self.socket_host = None
            self.socket_port = None
        else:
            try:
                self.socket_host, self.socket_port = value
                self.socket_file = None
            except ValueError:
                raise ValueError("bind_addr must be a (host, port) tuple "
                                 "(for TCP sockets) or a string (for Unix "
                                 "domain sockets), not %r" % value)
    bind_addr = property(_get_bind_addr, _set_bind_addr,
        doc='A (host, port) tuple for TCP sockets or a str for Unix domain sockets.')
    
    def base(self):
        """Return the base (scheme://host[:port] or sock file) for this server."""
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

