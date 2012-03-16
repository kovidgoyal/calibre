"""A library for integrating pyOpenSSL with CherryPy.

The OpenSSL module must be importable for SSL functionality.
You can obtain it from http://pyopenssl.sourceforge.net/

To use this module, set CherryPyWSGIServer.ssl_adapter to an instance of
SSLAdapter. There are two ways to use SSL:

Method One
----------

 * ``ssl_adapter.context``: an instance of SSL.Context.

If this is not None, it is assumed to be an SSL.Context instance,
and will be passed to SSL.Connection on bind(). The developer is
responsible for forming a valid Context object. This approach is
to be preferred for more flexibility, e.g. if the cert and key are
streams instead of files, or need decryption, or SSL.SSLv3_METHOD
is desired instead of the default SSL.SSLv23_METHOD, etc. Consult
the pyOpenSSL documentation for complete options.

Method Two (shortcut)
---------------------

 * ``ssl_adapter.certificate``: the filename of the server SSL certificate.
 * ``ssl_adapter.private_key``: the filename of the server's private key file.

Both are None by default. If ssl_adapter.context is None, but .private_key
and .certificate are both given and valid, they will be read, and the
context will be automatically created from them.
"""

import socket
import threading
import time

from cherrypy import wsgiserver

try:
    from OpenSSL import SSL
    from OpenSSL import crypto
except ImportError:
    SSL = None


class SSL_fileobject(wsgiserver.CP_fileobject):
    """SSL file object attached to a socket object."""
    
    ssl_timeout = 3
    ssl_retry = .01
    
    def _safe_call(self, is_reader, call, *args, **kwargs):
        """Wrap the given call with SSL error-trapping.
        
        is_reader: if False EOF errors will be raised. If True, EOF errors
        will return "" (to emulate normal sockets).
        """
        start = time.time()
        while True:
            try:
                return call(*args, **kwargs)
            except SSL.WantReadError:
                # Sleep and try again. This is dangerous, because it means
                # the rest of the stack has no way of differentiating
                # between a "new handshake" error and "client dropped".
                # Note this isn't an endless loop: there's a timeout below.
                time.sleep(self.ssl_retry)
            except SSL.WantWriteError:
                time.sleep(self.ssl_retry)
            except SSL.SysCallError, e:
                if is_reader and e.args == (-1, 'Unexpected EOF'):
                    return ""
                
                errnum = e.args[0]
                if is_reader and errnum in wsgiserver.socket_errors_to_ignore:
                    return ""
                raise socket.error(errnum)
            except SSL.Error, e:
                if is_reader and e.args == (-1, 'Unexpected EOF'):
                    return ""
                
                thirdarg = None
                try:
                    thirdarg = e.args[0][0][2]
                except IndexError:
                    pass
                
                if thirdarg == 'http request':
                    # The client is talking HTTP to an HTTPS server.
                    raise wsgiserver.NoSSLError()
                
                raise wsgiserver.FatalSSLAlert(*e.args)
            except:
                raise
            
            if time.time() - start > self.ssl_timeout:
                raise socket.timeout("timed out")
    
    def recv(self, *args, **kwargs):
        buf = []
        r = super(SSL_fileobject, self).recv
        while True:
            data = self._safe_call(True, r, *args, **kwargs)
            buf.append(data)
            p = self._sock.pending()
            if not p:
                return "".join(buf)
    
    def sendall(self, *args, **kwargs):
        return self._safe_call(False, super(SSL_fileobject, self).sendall,
                               *args, **kwargs)

    def send(self, *args, **kwargs):
        return self._safe_call(False, super(SSL_fileobject, self).send,
                               *args, **kwargs)


class SSLConnection:
    """A thread-safe wrapper for an SSL.Connection.
    
    ``*args``: the arguments to create the wrapped ``SSL.Connection(*args)``.
    """
    
    def __init__(self, *args):
        self._ssl_conn = SSL.Connection(*args)
        self._lock = threading.RLock()
    
    for f in ('get_context', 'pending', 'send', 'write', 'recv', 'read',
              'renegotiate', 'bind', 'listen', 'connect', 'accept',
              'setblocking', 'fileno', 'close', 'get_cipher_list',
              'getpeername', 'getsockname', 'getsockopt', 'setsockopt',
              'makefile', 'get_app_data', 'set_app_data', 'state_string',
              'sock_shutdown', 'get_peer_certificate', 'want_read',
              'want_write', 'set_connect_state', 'set_accept_state',
              'connect_ex', 'sendall', 'settimeout', 'gettimeout'):
        exec("""def %s(self, *args):
        self._lock.acquire()
        try:
            return self._ssl_conn.%s(*args)
        finally:
            self._lock.release()
""" % (f, f))
    
    def shutdown(self, *args):
        self._lock.acquire()
        try:
            # pyOpenSSL.socket.shutdown takes no args
            return self._ssl_conn.shutdown()
        finally:
            self._lock.release()


class pyOpenSSLAdapter(wsgiserver.SSLAdapter):
    """A wrapper for integrating pyOpenSSL with CherryPy."""
    
    context = None
    """An instance of SSL.Context."""
    
    certificate = None
    """The filename of the server SSL certificate."""
    
    private_key = None
    """The filename of the server's private key file."""
    
    certificate_chain = None
    """Optional. The filename of CA's intermediate certificate bundle.
    
    This is needed for cheaper "chained root" SSL certificates, and should be
    left as None if not required."""
    
    def __init__(self, certificate, private_key, certificate_chain=None):
        if SSL is None:
            raise ImportError("You must install pyOpenSSL to use HTTPS.")
        
        self.context = None
        self.certificate = certificate
        self.private_key = private_key
        self.certificate_chain = certificate_chain
        self._environ = None
    
    def bind(self, sock):
        """Wrap and return the given socket."""
        if self.context is None:
            self.context = self.get_context()
        conn = SSLConnection(self.context, sock)
        self._environ = self.get_environ()
        return conn
    
    def wrap(self, sock):
        """Wrap and return the given socket, plus WSGI environ entries."""
        return sock, self._environ.copy()
    
    def get_context(self):
        """Return an SSL.Context from self attributes."""
        # See http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/442473
        c = SSL.Context(SSL.SSLv23_METHOD)
        c.use_privatekey_file(self.private_key)
        if self.certificate_chain:
            c.load_verify_locations(self.certificate_chain)
        c.use_certificate_file(self.certificate)
        return c
    
    def get_environ(self):
        """Return WSGI environ entries to be merged into each request."""
        ssl_environ = {
            "HTTPS": "on",
            # pyOpenSSL doesn't provide access to any of these AFAICT
##            'SSL_PROTOCOL': 'SSLv2',
##            SSL_CIPHER 	string 	The cipher specification name
##            SSL_VERSION_INTERFACE 	string 	The mod_ssl program version
##            SSL_VERSION_LIBRARY 	string 	The OpenSSL program version
            }
        
        if self.certificate:
            # Server certificate attributes
            cert = open(self.certificate, 'rb').read()
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
            ssl_environ.update({
                'SSL_SERVER_M_VERSION': cert.get_version(),
                'SSL_SERVER_M_SERIAL': cert.get_serial_number(),
##                'SSL_SERVER_V_START': Validity of server's certificate (start time),
##                'SSL_SERVER_V_END': Validity of server's certificate (end time),
                })
            
            for prefix, dn in [("I", cert.get_issuer()),
                               ("S", cert.get_subject())]:
                # X509Name objects don't seem to have a way to get the
                # complete DN string. Use str() and slice it instead,
                # because str(dn) == "<X509Name object '/C=US/ST=...'>"
                dnstr = str(dn)[18:-2]
                
                wsgikey = 'SSL_SERVER_%s_DN' % prefix
                ssl_environ[wsgikey] = dnstr
                
                # The DN should be of the form: /k1=v1/k2=v2, but we must allow
                # for any value to contain slashes itself (in a URL).
                while dnstr:
                    pos = dnstr.rfind("=")
                    dnstr, value = dnstr[:pos], dnstr[pos + 1:]
                    pos = dnstr.rfind("/")
                    dnstr, key = dnstr[:pos], dnstr[pos + 1:]
                    if key and value:
                        wsgikey = 'SSL_SERVER_%s_DN_%s' % (prefix, key)
                        ssl_environ[wsgikey] = value
        
        return ssl_environ
    
    def makefile(self, sock, mode='r', bufsize=-1):
        if SSL and isinstance(sock, SSL.ConnectionType):
            timeout = sock.gettimeout()
            f = SSL_fileobject(sock, mode, bufsize)
            f.ssl_timeout = timeout
            return f
        else:
            return wsgiserver.CP_fileobject(sock, mode, bufsize)

