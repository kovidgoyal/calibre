"""A library for integrating Python's builtin ``ssl`` library with CherryPy.

The ssl module must be importable for SSL functionality.

To use this module, set ``CherryPyWSGIServer.ssl_adapter`` to an instance of
``BuiltinSSLAdapter``.
"""

try:
    import ssl
except ImportError:
    ssl = None

try:
    from _pyio import DEFAULT_BUFFER_SIZE
except ImportError:
    try:
        from io import DEFAULT_BUFFER_SIZE
    except ImportError:
        DEFAULT_BUFFER_SIZE = -1

import sys

from cherrypy import wsgiserver


class BuiltinSSLAdapter(wsgiserver.SSLAdapter):
    """A wrapper for integrating Python's builtin ssl module with CherryPy."""
    
    certificate = None
    """The filename of the server SSL certificate."""
    
    private_key = None
    """The filename of the server's private key file."""
    
    def __init__(self, certificate, private_key, certificate_chain=None):
        if ssl is None:
            raise ImportError("You must install the ssl module to use HTTPS.")
        self.certificate = certificate
        self.private_key = private_key
        self.certificate_chain = certificate_chain
    
    def bind(self, sock):
        """Wrap and return the given socket."""
        return sock
    
    def wrap(self, sock):
        """Wrap and return the given socket, plus WSGI environ entries."""
        try:
            s = ssl.wrap_socket(sock, do_handshake_on_connect=True,
                    server_side=True, certfile=self.certificate,
                    keyfile=self.private_key, ssl_version=ssl.PROTOCOL_SSLv23)
        except ssl.SSLError:
            e = sys.exc_info()[1]
            if e.errno == ssl.SSL_ERROR_EOF:
                # This is almost certainly due to the cherrypy engine
                # 'pinging' the socket to assert it's connectable;
                # the 'ping' isn't SSL.
                return None, {}
            elif e.errno == ssl.SSL_ERROR_SSL:
                if e.args[1].endswith('http request'):
                    # The client is speaking HTTP to an HTTPS server.
                    raise wsgiserver.NoSSLError
                elif e.args[1].endswith('unknown protocol'):
                    # The client is speaking some non-HTTP protocol.
                    # Drop the conn.
                    return None, {}
            raise
        return s, self.get_environ(s)
    
    # TODO: fill this out more with mod ssl env
    def get_environ(self, sock):
        """Create WSGI environ entries to be merged into each request."""
        cipher = sock.cipher()
        ssl_environ = {
            "wsgi.url_scheme": "https",
            "HTTPS": "on",
            'SSL_PROTOCOL': cipher[1],
            'SSL_CIPHER': cipher[0]
##            SSL_VERSION_INTERFACE 	string 	The mod_ssl program version
##            SSL_VERSION_LIBRARY 	string 	The OpenSSL program version
            }
        return ssl_environ
    
    if sys.version_info >= (3, 0):
        def makefile(self, sock, mode='r', bufsize=DEFAULT_BUFFER_SIZE):
            return wsgiserver.CP_makefile(sock, mode, bufsize)
    else:
        def makefile(self, sock, mode='r', bufsize=DEFAULT_BUFFER_SIZE):
            return wsgiserver.CP_fileobject(sock, mode, bufsize)

