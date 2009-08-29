"""A high-speed, production ready, thread pooled, generic WSGI server.

Simplest example on how to use this module directly
(without using CherryPy's application machinery):

    from cherrypy import wsgiserver
    
    def my_crazy_app(environ, start_response):
        status = '200 OK'
        response_headers = [('Content-type','text/plain')]
        start_response(status, response_headers)
        return ['Hello world!\n']
    
    server = wsgiserver.CherryPyWSGIServer(
                ('0.0.0.0', 8070), my_crazy_app,
                server_name='www.cherrypy.example')
    
The CherryPy WSGI server can serve as many WSGI applications 
as you want in one instance by using a WSGIPathInfoDispatcher:
    
    d = WSGIPathInfoDispatcher({'/': my_crazy_app, '/blog': my_blog_app})
    server = wsgiserver.CherryPyWSGIServer(('0.0.0.0', 80), d)
    
Want SSL support? Just set these attributes:
    
    server.ssl_certificate = <filename>
    server.ssl_private_key = <filename>
    
    if __name__ == '__main__':
        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()

This won't call the CherryPy engine (application side) at all, only the
WSGI server, which is independant from the rest of CherryPy. Don't
let the name "CherryPyWSGIServer" throw you; the name merely reflects
its origin, not its coupling.

For those of you wanting to understand internals of this module, here's the
basic call flow. The server's listening thread runs a very tight loop,
sticking incoming connections onto a Queue:

    server = CherryPyWSGIServer(...)
    server.start()
    while True:
        tick()
        # This blocks until a request comes in:
        child = socket.accept()
        conn = HTTPConnection(child, ...)
        server.requests.put(conn)

Worker threads are kept in a pool and poll the Queue, popping off and then
handling each connection in turn. Each connection can consist of an arbitrary
number of requests and their responses, so we run a nested loop:

    while True:
        conn = server.requests.get()
        conn.communicate()
        ->  while True:
                req = HTTPRequest(...)
                req.parse_request()
                ->  # Read the Request-Line, e.g. "GET /page HTTP/1.1"
                    req.rfile.readline()
                    req.read_headers()
                req.respond()
                ->  response = wsgi_app(...)
                    try:
                        for chunk in response:
                            if chunk:
                                req.write(chunk)
                    finally:
                        if hasattr(response, "close"):
                            response.close()
                if req.close_connection:
                    return
"""


import base64
import os
import Queue
import re
quoted_slash = re.compile("(?i)%2F")
import rfc822
import socket
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

_fileobject_uses_str_type = isinstance(socket._fileobject(None)._rbuf, basestring)

import sys
import threading
import time
import traceback
from urllib import unquote
from urlparse import urlparse
import warnings

try:
    from OpenSSL import SSL
    from OpenSSL import crypto
except ImportError:
    SSL = None

import errno

def plat_specific_errors(*errnames):
    """Return error numbers for all errors in errnames on this platform.
    
    The 'errno' module contains different global constants depending on
    the specific platform (OS). This function will return the list of
    numeric values for a given list of potential names.
    """
    errno_names = dir(errno)
    nums = [getattr(errno, k) for k in errnames if k in errno_names]
    # de-dupe the list
    return dict.fromkeys(nums).keys()

socket_error_eintr = plat_specific_errors("EINTR", "WSAEINTR")

socket_errors_to_ignore = plat_specific_errors(
    "EPIPE",
    "EBADF", "WSAEBADF",
    "ENOTSOCK", "WSAENOTSOCK",
    "ETIMEDOUT", "WSAETIMEDOUT",
    "ECONNREFUSED", "WSAECONNREFUSED",
    "ECONNRESET", "WSAECONNRESET",
    "ECONNABORTED", "WSAECONNABORTED",
    "ENETRESET", "WSAENETRESET",
    "EHOSTDOWN", "EHOSTUNREACH",
    )
socket_errors_to_ignore.append("timed out")

socket_errors_nonblocking = plat_specific_errors(
    'EAGAIN', 'EWOULDBLOCK', 'WSAEWOULDBLOCK')

comma_separated_headers = ['ACCEPT', 'ACCEPT-CHARSET', 'ACCEPT-ENCODING',
    'ACCEPT-LANGUAGE', 'ACCEPT-RANGES', 'ALLOW', 'CACHE-CONTROL',
    'CONNECTION', 'CONTENT-ENCODING', 'CONTENT-LANGUAGE', 'EXPECT',
    'IF-MATCH', 'IF-NONE-MATCH', 'PRAGMA', 'PROXY-AUTHENTICATE', 'TE',
    'TRAILER', 'TRANSFER-ENCODING', 'UPGRADE', 'VARY', 'VIA', 'WARNING',
    'WWW-AUTHENTICATE']


class WSGIPathInfoDispatcher(object):
    """A WSGI dispatcher for dispatch based on the PATH_INFO.
    
    apps: a dict or list of (path_prefix, app) pairs.
    """
    
    def __init__(self, apps):
        try:
            apps = apps.items()
        except AttributeError:
            pass
        
        # Sort the apps by len(path), descending
        apps.sort()
        apps.reverse()
        
        # The path_prefix strings must start, but not end, with a slash.
        # Use "" instead of "/".
        self.apps = [(p.rstrip("/"), a) for p, a in apps]
    
    def __call__(self, environ, start_response):
        path = environ["PATH_INFO"] or "/"
        for p, app in self.apps:
            # The apps list should be sorted by length, descending.
            if path.startswith(p + "/") or path == p:
                environ = environ.copy()
                environ["SCRIPT_NAME"] = environ["SCRIPT_NAME"] + p
                environ["PATH_INFO"] = path[len(p):]
                return app(environ, start_response)
        
        start_response('404 Not Found', [('Content-Type', 'text/plain'),
                                         ('Content-Length', '0')])
        return ['']


class MaxSizeExceeded(Exception):
    pass

class SizeCheckWrapper(object):
    """Wraps a file-like object, raising MaxSizeExceeded if too large."""
    
    def __init__(self, rfile, maxlen):
        self.rfile = rfile
        self.maxlen = maxlen
        self.bytes_read = 0
    
    def _check_length(self):
        if self.maxlen and self.bytes_read > self.maxlen:
            raise MaxSizeExceeded()
    
    def read(self, size=None):
        data = self.rfile.read(size)
        self.bytes_read += len(data)
        self._check_length()
        return data
    
    def readline(self, size=None):
        if size is not None:
            data = self.rfile.readline(size)
            self.bytes_read += len(data)
            self._check_length()
            return data
        
        # User didn't specify a size ...
        # We read the line in chunks to make sure it's not a 100MB line !
        res = []
        while True:
            data = self.rfile.readline(256)
            self.bytes_read += len(data)
            self._check_length()
            res.append(data)
            # See http://www.cherrypy.org/ticket/421
            if len(data) < 256 or data[-1:] == "\n":
                return ''.join(res)
    
    def readlines(self, sizehint=0):
        # Shamelessly stolen from StringIO
        total = 0
        lines = []
        line = self.readline()
        while line:
            lines.append(line)
            total += len(line)
            if 0 < sizehint <= total:
                break
            line = self.readline()
        return lines
    
    def close(self):
        self.rfile.close()
    
    def __iter__(self):
        return self
    
    def next(self):
        data = self.rfile.next()
        self.bytes_read += len(data)
        self._check_length()
        return data


class HTTPRequest(object):
    """An HTTP Request (and response).
    
    A single HTTP connection may consist of multiple request/response pairs.
    
    send: the 'send' method from the connection's socket object.
    wsgi_app: the WSGI application to call.
    environ: a partial WSGI environ (server and connection entries).
        The caller MUST set the following entries:
        * All wsgi.* entries, including .input
        * SERVER_NAME and SERVER_PORT
        * Any SSL_* entries
        * Any custom entries like REMOTE_ADDR and REMOTE_PORT
        * SERVER_SOFTWARE: the value to write in the "Server" response header.
        * ACTUAL_SERVER_PROTOCOL: the value to write in the Status-Line of
            the response. From RFC 2145: "An HTTP server SHOULD send a
            response version equal to the highest version for which the
            server is at least conditionally compliant, and whose major
            version is less than or equal to the one received in the
            request.  An HTTP server MUST NOT send a version for which
            it is not at least conditionally compliant."
    
    outheaders: a list of header tuples to write in the response.
    ready: when True, the request has been parsed and is ready to begin
        generating the response. When False, signals the calling Connection
        that the response should not be generated and the connection should
        close.
    close_connection: signals the calling Connection that the request
        should close. This does not imply an error! The client and/or
        server may each request that the connection be closed.
    chunked_write: if True, output will be encoded with the "chunked"
        transfer-coding. This value is set automatically inside
        send_headers.
    """
    
    max_request_header_size = 0
    max_request_body_size = 0
    
    def __init__(self, wfile, environ, wsgi_app):
        self.rfile = environ['wsgi.input']
        self.wfile = wfile
        self.environ = environ.copy()
        self.wsgi_app = wsgi_app
        
        self.ready = False
        self.started_response = False
        self.status = ""
        self.outheaders = []
        self.sent_headers = False
        self.close_connection = False
        self.chunked_write = False
    
    def parse_request(self):
        """Parse the next HTTP request start-line and message-headers."""
        self.rfile.maxlen = self.max_request_header_size
        self.rfile.bytes_read = 0
        
        try:
            self._parse_request()
        except MaxSizeExceeded:
            self.simple_response("413 Request Entity Too Large")
            return
    
    def _parse_request(self):
        # HTTP/1.1 connections are persistent by default. If a client
        # requests a page, then idles (leaves the connection open),
        # then rfile.readline() will raise socket.error("timed out").
        # Note that it does this based on the value given to settimeout(),
        # and doesn't need the client to request or acknowledge the close
        # (although your TCP stack might suffer for it: cf Apache's history
        # with FIN_WAIT_2).
        request_line = self.rfile.readline()
        if not request_line:
            # Force self.ready = False so the connection will close.
            self.ready = False
            return
        
        if request_line == "\r\n":
            # RFC 2616 sec 4.1: "...if the server is reading the protocol
            # stream at the beginning of a message and receives a CRLF
            # first, it should ignore the CRLF."
            # But only ignore one leading line! else we enable a DoS.
            request_line = self.rfile.readline()
            if not request_line:
                self.ready = False
                return
        
        environ = self.environ
        
        try:
            method, path, req_protocol = request_line.strip().split(" ", 2)
        except ValueError:
            self.simple_response(400, "Malformed Request-Line")
            return
        
        environ["REQUEST_METHOD"] = method
        
        # path may be an abs_path (including "http://host.domain.tld");
        scheme, location, path, params, qs, frag = urlparse(path)
        
        if frag:
            self.simple_response("400 Bad Request",
                                 "Illegal #fragment in Request-URI.")
            return
        
        if scheme:
            environ["wsgi.url_scheme"] = scheme
        if params:
            path = path + ";" + params
        
        environ["SCRIPT_NAME"] = ""
        
        # Unquote the path+params (e.g. "/this%20path" -> "this path").
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5.1.2
        #
        # But note that "...a URI must be separated into its components
        # before the escaped characters within those components can be
        # safely decoded." http://www.ietf.org/rfc/rfc2396.txt, sec 2.4.2
        atoms = [unquote(x) for x in quoted_slash.split(path)]
        path = "%2F".join(atoms)
        environ["PATH_INFO"] = path
        
        # Note that, like wsgiref and most other WSGI servers,
        # we unquote the path but not the query string.
        environ["QUERY_STRING"] = qs
        
        # Compare request and server HTTP protocol versions, in case our
        # server does not support the requested protocol. Limit our output
        # to min(req, server). We want the following output:
        #     request    server     actual written   supported response
        #     protocol   protocol  response protocol    feature set
        # a     1.0        1.0           1.0                1.0
        # b     1.0        1.1           1.1                1.0
        # c     1.1        1.0           1.0                1.0
        # d     1.1        1.1           1.1                1.1
        # Notice that, in (b), the response will be "HTTP/1.1" even though
        # the client only understands 1.0. RFC 2616 10.5.6 says we should
        # only return 505 if the _major_ version is different.
        rp = int(req_protocol[5]), int(req_protocol[7])
        server_protocol = environ["ACTUAL_SERVER_PROTOCOL"]
        sp = int(server_protocol[5]), int(server_protocol[7])
        if sp[0] != rp[0]:
            self.simple_response("505 HTTP Version Not Supported")
            return
        # Bah. "SERVER_PROTOCOL" is actually the REQUEST protocol.
        environ["SERVER_PROTOCOL"] = req_protocol
        self.response_protocol = "HTTP/%s.%s" % min(rp, sp)
        
        # If the Request-URI was an absoluteURI, use its location atom.
        if location:
            environ["SERVER_NAME"] = location
        
        # then all the http headers
        try:
            self.read_headers()
        except ValueError, ex:
            self.simple_response("400 Bad Request", repr(ex.args))
            return
        
        mrbs = self.max_request_body_size
        if mrbs and int(environ.get("CONTENT_LENGTH", 0)) > mrbs:
            self.simple_response("413 Request Entity Too Large")
            return
        
        # Persistent connection support
        if self.response_protocol == "HTTP/1.1":
            # Both server and client are HTTP/1.1
            if environ.get("HTTP_CONNECTION", "") == "close":
                self.close_connection = True
        else:
            # Either the server or client (or both) are HTTP/1.0
            if environ.get("HTTP_CONNECTION", "") != "Keep-Alive":
                self.close_connection = True
        
        # Transfer-Encoding support
        te = None
        if self.response_protocol == "HTTP/1.1":
            te = environ.get("HTTP_TRANSFER_ENCODING")
            if te:
                te = [x.strip().lower() for x in te.split(",") if x.strip()]
        
        self.chunked_read = False
        
        if te:
            for enc in te:
                if enc == "chunked":
                    self.chunked_read = True
                else:
                    # Note that, even if we see "chunked", we must reject
                    # if there is an extension we don't recognize.
                    self.simple_response("501 Unimplemented")
                    self.close_connection = True
                    return
        
        # From PEP 333:
        # "Servers and gateways that implement HTTP 1.1 must provide
        # transparent support for HTTP 1.1's "expect/continue" mechanism.
        # This may be done in any of several ways:
        #   1. Respond to requests containing an Expect: 100-continue request
        #      with an immediate "100 Continue" response, and proceed normally.
        #   2. Proceed with the request normally, but provide the application
        #      with a wsgi.input stream that will send the "100 Continue"
        #      response if/when the application first attempts to read from
        #      the input stream. The read request must then remain blocked
        #      until the client responds.
        #   3. Wait until the client decides that the server does not support
        #      expect/continue, and sends the request body on its own.
        #      (This is suboptimal, and is not recommended.)
        #
        # We used to do 3, but are now doing 1. Maybe we'll do 2 someday,
        # but it seems like it would be a big slowdown for such a rare case.
        if environ.get("HTTP_EXPECT", "") == "100-continue":
            self.simple_response(100)
        
        self.ready = True
    
    def read_headers(self):
        """Read header lines from the incoming stream."""
        environ = self.environ
        
        while True:
            line = self.rfile.readline()
            if not line:
                # No more data--illegal end of headers
                raise ValueError("Illegal end of headers.")
            
            if line == '\r\n':
                # Normal end of headers
                break
            
            if line[0] in ' \t':
                # It's a continuation line.
                v = line.strip()
            else:
                k, v = line.split(":", 1)
                k, v = k.strip().upper(), v.strip()
                envname = "HTTP_" + k.replace("-", "_")
            
            if k in comma_separated_headers:
                existing = environ.get(envname)
                if existing:
                    v = ", ".join((existing, v))
            environ[envname] = v
        
        ct = environ.pop("HTTP_CONTENT_TYPE", None)
        if ct is not None:
            environ["CONTENT_TYPE"] = ct
        cl = environ.pop("HTTP_CONTENT_LENGTH", None)
        if cl is not None:
            environ["CONTENT_LENGTH"] = cl
    
    def decode_chunked(self):
        """Decode the 'chunked' transfer coding."""
        cl = 0
        data = StringIO.StringIO()
        while True:
            line = self.rfile.readline().strip().split(";", 1)
            chunk_size = int(line.pop(0), 16)
            if chunk_size <= 0:
                break
##            if line: chunk_extension = line[0]
            cl += chunk_size
            data.write(self.rfile.read(chunk_size))
            crlf = self.rfile.read(2)
            if crlf != "\r\n":
                self.simple_response("400 Bad Request",
                                     "Bad chunked transfer coding "
                                     "(expected '\\r\\n', got %r)" % crlf)
                return
        
        # Grab any trailer headers
        self.read_headers()
        
        data.seek(0)
        self.environ["wsgi.input"] = data
        self.environ["CONTENT_LENGTH"] = str(cl) or ""
        return True
    
    def respond(self):
        """Call the appropriate WSGI app and write its iterable output."""
        # Set rfile.maxlen to ensure we don't read past Content-Length.
        # This will also be used to read the entire request body if errors
        # are raised before the app can read the body.
        if self.chunked_read:
            # If chunked, Content-Length will be 0.
            self.rfile.maxlen = self.max_request_body_size
        else:
            cl = int(self.environ.get("CONTENT_LENGTH", 0))
            if self.max_request_body_size:
                self.rfile.maxlen = min(cl, self.max_request_body_size)
            else:
                self.rfile.maxlen = cl
        self.rfile.bytes_read = 0
        
        try:
            self._respond()
        except MaxSizeExceeded:
            if not self.sent_headers:
                self.simple_response("413 Request Entity Too Large")
            return
    
    def _respond(self):
        if self.chunked_read:
            if not self.decode_chunked():
                self.close_connection = True
                return
        
        response = self.wsgi_app(self.environ, self.start_response)
        try:
            for chunk in response:
                # "The start_response callable must not actually transmit
                # the response headers. Instead, it must store them for the
                # server or gateway to transmit only after the first
                # iteration of the application return value that yields
                # a NON-EMPTY string, or upon the application's first
                # invocation of the write() callable." (PEP 333)
                if chunk:
                    self.write(chunk)
        finally:
            if hasattr(response, "close"):
                response.close()
        
        if (self.ready and not self.sent_headers):
            self.sent_headers = True
            self.send_headers()
        if self.chunked_write:
            self.wfile.sendall("0\r\n\r\n")
    
    def simple_response(self, status, msg=""):
        """Write a simple response back to the client."""
        status = str(status)
        buf = ["%s %s\r\n" % (self.environ['ACTUAL_SERVER_PROTOCOL'], status),
               "Content-Length: %s\r\n" % len(msg),
               "Content-Type: text/plain\r\n"]
        
        if status[:3] == "413" and self.response_protocol == 'HTTP/1.1':
            # Request Entity Too Large
            self.close_connection = True
            buf.append("Connection: close\r\n")
        
        buf.append("\r\n")
        if msg:
            buf.append(msg)
        
        try:
            self.wfile.sendall("".join(buf))
        except socket.error, x:
            if x.args[0] not in socket_errors_to_ignore:
                raise
    
    def start_response(self, status, headers, exc_info = None):
        """WSGI callable to begin the HTTP response."""
        # "The application may call start_response more than once,
        # if and only if the exc_info argument is provided."
        if self.started_response and not exc_info:
            raise AssertionError("WSGI start_response called a second "
                                 "time with no exc_info.")
        
        # "if exc_info is provided, and the HTTP headers have already been
        # sent, start_response must raise an error, and should raise the
        # exc_info tuple."
        if self.sent_headers:
            try:
                raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None
        
        self.started_response = True
        self.status = status
        self.outheaders.extend(headers)
        return self.write
    
    def write(self, chunk):
        """WSGI callable to write unbuffered data to the client.
        
        This method is also used internally by start_response (to write
        data from the iterable returned by the WSGI application).
        """
        if not self.started_response:
            raise AssertionError("WSGI write called before start_response.")
        
        if not self.sent_headers:
            self.sent_headers = True
            self.send_headers()
        
        if self.chunked_write and chunk:
            buf = [hex(len(chunk))[2:], "\r\n", chunk, "\r\n"]
            self.wfile.sendall("".join(buf))
        else:
            self.wfile.sendall(chunk)
    
    def send_headers(self):
        """Assert, process, and send the HTTP response message-headers."""
        hkeys = [key.lower() for key, value in self.outheaders]
        status = int(self.status[:3])
        
        if status == 413:
            # Request Entity Too Large. Close conn to avoid garbage.
            self.close_connection = True
        elif "content-length" not in hkeys:
            # "All 1xx (informational), 204 (no content),
            # and 304 (not modified) responses MUST NOT
            # include a message-body." So no point chunking.
            if status < 200 or status in (204, 205, 304):
                pass
            else:
                if (self.response_protocol == 'HTTP/1.1'
                    and self.environ["REQUEST_METHOD"] != 'HEAD'):
                    # Use the chunked transfer-coding
                    self.chunked_write = True
                    self.outheaders.append(("Transfer-Encoding", "chunked"))
                else:
                    # Closing the conn is the only way to determine len.
                    self.close_connection = True
        
        if "connection" not in hkeys:
            if self.response_protocol == 'HTTP/1.1':
                # Both server and client are HTTP/1.1 or better
                if self.close_connection:
                    self.outheaders.append(("Connection", "close"))
            else:
                # Server and/or client are HTTP/1.0
                if not self.close_connection:
                    self.outheaders.append(("Connection", "Keep-Alive"))
        
        if (not self.close_connection) and (not self.chunked_read):
            # Read any remaining request body data on the socket.
            # "If an origin server receives a request that does not include an
            # Expect request-header field with the "100-continue" expectation,
            # the request includes a request body, and the server responds
            # with a final status code before reading the entire request body
            # from the transport connection, then the server SHOULD NOT close
            # the transport connection until it has read the entire request,
            # or until the client closes the connection. Otherwise, the client
            # might not reliably receive the response message. However, this
            # requirement is not be construed as preventing a server from
            # defending itself against denial-of-service attacks, or from
            # badly broken client implementations."
            size = self.rfile.maxlen - self.rfile.bytes_read
            if size > 0:
                self.rfile.read(size)
        
        if "date" not in hkeys:
            self.outheaders.append(("Date", rfc822.formatdate()))
        
        if "server" not in hkeys:
            self.outheaders.append(("Server", self.environ['SERVER_SOFTWARE']))
        
        buf = [self.environ['ACTUAL_SERVER_PROTOCOL'], " ", self.status, "\r\n"]
        try:
            buf += [k + ": " + v + "\r\n" for k, v in self.outheaders]
        except TypeError:
            if not isinstance(k, str):
                raise TypeError("WSGI response header key %r is not a string.")
            if not isinstance(v, str):
                raise TypeError("WSGI response header value %r is not a string.")
            else:
                raise
        buf.append("\r\n")
        self.wfile.sendall("".join(buf))


class NoSSLError(Exception):
    """Exception raised when a client speaks HTTP to an HTTPS socket."""
    pass


class FatalSSLAlert(Exception):
    """Exception raised when the SSL implementation signals a fatal alert."""
    pass


if not _fileobject_uses_str_type:
    class CP_fileobject(socket._fileobject):
        """Faux file object attached to a socket object."""

        def sendall(self, data):
            """Sendall for non-blocking sockets."""
            while data:
                try:
                    bytes_sent = self.send(data)
                    data = data[bytes_sent:]
                except socket.error, e:
                    if e.args[0] not in socket_errors_nonblocking:
                        raise

        def send(self, data):
            return self._sock.send(data)

        def flush(self):
            if self._wbuf:
                buffer = "".join(self._wbuf)
                self._wbuf = []
                self.sendall(buffer)

        def recv(self, size):
            while True:
                try:
                    return self._sock.recv(size)
                except socket.error, e:
                    if (e.args[0] not in socket_errors_nonblocking
                        and e.args[0] not in socket_error_eintr):
                        raise

        def read(self, size=-1):
            # Use max, disallow tiny reads in a loop as they are very inefficient.
            # We never leave read() with any leftover data from a new recv() call
            # in our internal buffer.
            rbufsize = max(self._rbufsize, self.default_bufsize)
            # Our use of StringIO rather than lists of string objects returned by
            # recv() minimizes memory usage and fragmentation that occurs when
            # rbufsize is large compared to the typical return value of recv().
            buf = self._rbuf
            buf.seek(0, 2)  # seek end
            if size < 0:
                # Read until EOF
                self._rbuf = StringIO.StringIO()  # reset _rbuf.  we consume it via buf.
                while True:
                    data = self.recv(rbufsize)
                    if not data:
                        break
                    buf.write(data)
                return buf.getvalue()
            else:
                # Read until size bytes or EOF seen, whichever comes first
                buf_len = buf.tell()
                if buf_len >= size:
                    # Already have size bytes in our buffer?  Extract and return.
                    buf.seek(0)
                    rv = buf.read(size)
                    self._rbuf = StringIO.StringIO()
                    self._rbuf.write(buf.read())
                    return rv

                self._rbuf = StringIO.StringIO()  # reset _rbuf.  we consume it via buf.
                while True:
                    left = size - buf_len
                    # recv() will malloc the amount of memory given as its
                    # parameter even though it often returns much less data
                    # than that.  The returned data string is short lived
                    # as we copy it into a StringIO and free it.  This avoids
                    # fragmentation issues on many platforms.
                    data = self.recv(left)
                    if not data:
                        break
                    n = len(data)
                    if n == size and not buf_len:
                        # Shortcut.  Avoid buffer data copies when:
                        # - We have no data in our buffer.
                        # AND
                        # - Our call to recv returned exactly the
                        #   number of bytes we were asked to read.
                        return data
                    if n == left:
                        buf.write(data)
                        del data  # explicit free
                        break
                    assert n <= left, "recv(%d) returned %d bytes" % (left, n)
                    buf.write(data)
                    buf_len += n
                    del data  # explicit free
                    #assert buf_len == buf.tell()
                return buf.getvalue()

        def readline(self, size=-1):
            buf = self._rbuf
            buf.seek(0, 2)  # seek end
            if buf.tell() > 0:
                # check if we already have it in our buffer
                buf.seek(0)
                bline = buf.readline(size)
                if bline.endswith('\n') or len(bline) == size:
                    self._rbuf = StringIO.StringIO()
                    self._rbuf.write(buf.read())
                    return bline
                del bline
            if size < 0:
                # Read until \n or EOF, whichever comes first
                if self._rbufsize <= 1:
                    # Speed up unbuffered case
                    buf.seek(0)
                    buffers = [buf.read()]
                    self._rbuf = StringIO.StringIO()  # reset _rbuf.  we consume it via buf.
                    data = None
                    recv = self.recv
                    while data != "\n":
                        data = recv(1)
                        if not data:
                            break
                        buffers.append(data)
                    return "".join(buffers)

                buf.seek(0, 2)  # seek end
                self._rbuf = StringIO.StringIO()  # reset _rbuf.  we consume it via buf.
                while True:
                    data = self.recv(self._rbufsize)
                    if not data:
                        break
                    nl = data.find('\n')
                    if nl >= 0:
                        nl += 1
                        buf.write(data[:nl])
                        self._rbuf.write(data[nl:])
                        del data
                        break
                    buf.write(data)
                return buf.getvalue()
            else:
                # Read until size bytes or \n or EOF seen, whichever comes first
                buf.seek(0, 2)  # seek end
                buf_len = buf.tell()
                if buf_len >= size:
                    buf.seek(0)
                    rv = buf.read(size)
                    self._rbuf = StringIO.StringIO()
                    self._rbuf.write(buf.read())
                    return rv
                self._rbuf = StringIO.StringIO()  # reset _rbuf.  we consume it via buf.
                while True:
                    data = self.recv(self._rbufsize)
                    if not data:
                        break
                    left = size - buf_len
                    # did we just receive a newline?
                    nl = data.find('\n', 0, left)
                    if nl >= 0:
                        nl += 1
                        # save the excess data to _rbuf
                        self._rbuf.write(data[nl:])
                        if buf_len:
                            buf.write(data[:nl])
                            break
                        else:
                            # Shortcut.  Avoid data copy through buf when returning
                            # a substring of our first recv().
                            return data[:nl]
                    n = len(data)
                    if n == size and not buf_len:
                        # Shortcut.  Avoid data copy through buf when
                        # returning exactly all of our first recv().
                        return data
                    if n >= left:
                        buf.write(data[:left])
                        self._rbuf.write(data[left:])
                        break
                    buf.write(data)
                    buf_len += n
                    #assert buf_len == buf.tell()
                return buf.getvalue()

else:
    class CP_fileobject(socket._fileobject):
        """Faux file object attached to a socket object."""

        def sendall(self, data):
            """Sendall for non-blocking sockets."""
            while data:
                try:
                    bytes_sent = self.send(data)
                    data = data[bytes_sent:]
                except socket.error, e:
                    if e.args[0] not in socket_errors_nonblocking:
                        raise

        def send(self, data):
            return self._sock.send(data)

        def flush(self):
            if self._wbuf:
                buffer = "".join(self._wbuf)
                self._wbuf = []
                self.sendall(buffer)

        def recv(self, size):
            while True:
                try:
                    return self._sock.recv(size)
                except socket.error, e:
                    if (e.args[0] not in socket_errors_nonblocking
                        and e.args[0] not in socket_error_eintr):
                        raise

        def read(self, size=-1):
            if size < 0:
                # Read until EOF
                buffers = [self._rbuf]
                self._rbuf = ""
                if self._rbufsize <= 1:
                    recv_size = self.default_bufsize
                else:
                    recv_size = self._rbufsize

                while True:
                    data = self.recv(recv_size)
                    if not data:
                        break
                    buffers.append(data)
                return "".join(buffers)
            else:
                # Read until size bytes or EOF seen, whichever comes first
                data = self._rbuf
                buf_len = len(data)
                if buf_len >= size:
                    self._rbuf = data[size:]
                    return data[:size]
                buffers = []
                if data:
                    buffers.append(data)
                self._rbuf = ""
                while True:
                    left = size - buf_len
                    recv_size = max(self._rbufsize, left)
                    data = self.recv(recv_size)
                    if not data:
                        break
                    buffers.append(data)
                    n = len(data)
                    if n >= left:
                        self._rbuf = data[left:]
                        buffers[-1] = data[:left]
                        break
                    buf_len += n
                return "".join(buffers)

        def readline(self, size=-1):
            data = self._rbuf
            if size < 0:
                # Read until \n or EOF, whichever comes first
                if self._rbufsize <= 1:
                    # Speed up unbuffered case
                    assert data == ""
                    buffers = []
                    while data != "\n":
                        data = self.recv(1)
                        if not data:
                            break
                        buffers.append(data)
                    return "".join(buffers)
                nl = data.find('\n')
                if nl >= 0:
                    nl += 1
                    self._rbuf = data[nl:]
                    return data[:nl]
                buffers = []
                if data:
                    buffers.append(data)
                self._rbuf = ""
                while True:
                    data = self.recv(self._rbufsize)
                    if not data:
                        break
                    buffers.append(data)
                    nl = data.find('\n')
                    if nl >= 0:
                        nl += 1
                        self._rbuf = data[nl:]
                        buffers[-1] = data[:nl]
                        break
                return "".join(buffers)
            else:
                # Read until size bytes or \n or EOF seen, whichever comes first
                nl = data.find('\n', 0, size)
                if nl >= 0:
                    nl += 1
                    self._rbuf = data[nl:]
                    return data[:nl]
                buf_len = len(data)
                if buf_len >= size:
                    self._rbuf = data[size:]
                    return data[:size]
                buffers = []
                if data:
                    buffers.append(data)
                self._rbuf = ""
                while True:
                    data = self.recv(self._rbufsize)
                    if not data:
                        break
                    buffers.append(data)
                    left = size - buf_len
                    nl = data.find('\n', 0, left)
                    if nl >= 0:
                        nl += 1
                        self._rbuf = data[nl:]
                        buffers[-1] = data[:nl]
                        break
                    n = len(data)
                    if n >= left:
                        self._rbuf = data[left:]
                        buffers[-1] = data[:left]
                        break
                    buf_len += n
                return "".join(buffers)
    

class SSL_fileobject(CP_fileobject):
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
                if is_reader and errnum in socket_errors_to_ignore:
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
                    raise NoSSLError()
                raise FatalSSLAlert(*e.args)
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
        return self._safe_call(False, super(SSL_fileobject, self).sendall, *args, **kwargs)

    def send(self, *args, **kwargs):
        return self._safe_call(False, super(SSL_fileobject, self).send, *args, **kwargs)


class HTTPConnection(object):
    """An HTTP connection (active socket).
    
    socket: the raw socket object (usually TCP) for this connection.
    wsgi_app: the WSGI application for this server/connection.
    environ: a WSGI environ template. This will be copied for each request.
    
    rfile: a fileobject for reading from the socket.
    send: a function for writing (+ flush) to the socket.
    """
    
    rbufsize = -1
    RequestHandlerClass = HTTPRequest
    environ = {"wsgi.version": (1, 0),
               "wsgi.url_scheme": "http",
               "wsgi.multithread": True,
               "wsgi.multiprocess": False,
               "wsgi.run_once": False,
               "wsgi.errors": sys.stderr,
               }
    
    def __init__(self, sock, wsgi_app, environ):
        self.socket = sock
        self.wsgi_app = wsgi_app
        
        # Copy the class environ into self.
        self.environ = self.environ.copy()
        self.environ.update(environ)
        
        if SSL and isinstance(sock, SSL.ConnectionType):
            timeout = sock.gettimeout()
            self.rfile = SSL_fileobject(sock, "rb", self.rbufsize)
            self.rfile.ssl_timeout = timeout
            self.wfile = SSL_fileobject(sock, "wb", -1)
            self.wfile.ssl_timeout = timeout
        else:
            self.rfile = CP_fileobject(sock, "rb", self.rbufsize)
            self.wfile = CP_fileobject(sock, "wb", -1)
        
        # Wrap wsgi.input but not HTTPConnection.rfile itself.
        # We're also not setting maxlen yet; we'll do that separately
        # for headers and body for each iteration of self.communicate
        # (if maxlen is 0 the wrapper doesn't check length).
        self.environ["wsgi.input"] = SizeCheckWrapper(self.rfile, 0)
    
    def communicate(self):
        """Read each request and respond appropriately."""
        try:
            while True:
                # (re)set req to None so that if something goes wrong in
                # the RequestHandlerClass constructor, the error doesn't
                # get written to the previous request.
                req = None
                req = self.RequestHandlerClass(self.wfile, self.environ,
                                               self.wsgi_app)
                
                # This order of operations should guarantee correct pipelining.
                req.parse_request()
                if not req.ready:
                    return
                
                req.respond()
                if req.close_connection:
                    return
        
        except socket.error, e:
            errnum = e.args[0]
            if errnum == 'timed out':
                if req and not req.sent_headers:
                    req.simple_response("408 Request Timeout")
            elif errnum not in socket_errors_to_ignore:
                if req and not req.sent_headers:
                    req.simple_response("500 Internal Server Error",
                                        format_exc())
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except FatalSSLAlert, e:
            # Close the connection.
            return
        except NoSSLError:
            if req and not req.sent_headers:
                # Unwrap our wfile
                req.wfile = CP_fileobject(self.socket._sock, "wb", -1)
                req.simple_response("400 Bad Request",
                    "The client sent a plain HTTP request, but "
                    "this server only speaks HTTPS on this port.")
                self.linger = True
        except Exception, e:
            if req and not req.sent_headers:
                req.simple_response("500 Internal Server Error", format_exc())
    
    linger = False
    
    def close(self):
        """Close the socket underlying this connection."""
        self.rfile.close()
        
        if not self.linger:
            # Python's socket module does NOT call close on the kernel socket
            # when you call socket.close(). We do so manually here because we
            # want this server to send a FIN TCP segment immediately. Note this
            # must be called *before* calling socket.close(), because the latter
            # drops its reference to the kernel socket.
            self.socket._sock.close()
            self.socket.close()
        else:
            # On the other hand, sometimes we want to hang around for a bit
            # to make sure the client has a chance to read our entire
            # response. Skipping the close() calls here delays the FIN
            # packet until the socket object is garbage-collected later.
            # Someday, perhaps, we'll do the full lingering_close that
            # Apache does, but not today.
            pass


def format_exc(limit=None):
    """Like print_exc() but return a string. Backport for Python 2.3."""
    try:
        etype, value, tb = sys.exc_info()
        return ''.join(traceback.format_exception(etype, value, tb, limit))
    finally:
        etype = value = tb = None


_SHUTDOWNREQUEST = None

class WorkerThread(threading.Thread):
    """Thread which continuously polls a Queue for Connection objects.
    
    server: the HTTP Server which spawned this thread, and which owns the
        Queue and is placing active connections into it.
    ready: a simple flag for the calling server to know when this thread
        has begun polling the Queue.
    
    Due to the timing issues of polling a Queue, a WorkerThread does not
    check its own 'ready' flag after it has started. To stop the thread,
    it is necessary to stick a _SHUTDOWNREQUEST object onto the Queue
    (one for each running WorkerThread).
    """
    
    conn = None
    
    def __init__(self, server):
        self.ready = False
        self.server = server
        threading.Thread.__init__(self)
    
    def run(self):
        try:
            self.ready = True
            while True:
                conn = self.server.requests.get()
                if conn is _SHUTDOWNREQUEST:
                    return
                
                self.conn = conn
                try:
                    conn.communicate()
                finally:
                    conn.close()
                    self.conn = None
        except (KeyboardInterrupt, SystemExit), exc:
            self.server.interrupt = exc


class ThreadPool(object):
    """A Request Queue for the CherryPyWSGIServer which pools threads.
    
    ThreadPool objects must provide min, get(), put(obj), start()
    and stop(timeout) attributes.
    """
    
    def __init__(self, server, min=10, max=-1):
        self.server = server
        self.min = min
        self.max = max
        self._threads = []
        self._queue = Queue.Queue()
        self.get = self._queue.get
    
    def start(self):
        """Start the pool of threads."""
        for i in xrange(self.min):
            self._threads.append(WorkerThread(self.server))
        for worker in self._threads:
            worker.setName("CP WSGIServer " + worker.getName())
            worker.start()
        for worker in self._threads:
            while not worker.ready:
                time.sleep(.1)
    
    def _get_idle(self):
        """Number of worker threads which are idle. Read-only."""
        return len([t for t in self._threads if t.conn is None])
    idle = property(_get_idle, doc=_get_idle.__doc__)
    
    def put(self, obj):
        self._queue.put(obj)
        if obj is _SHUTDOWNREQUEST:
            return
    
    def grow(self, amount):
        """Spawn new worker threads (not above self.max)."""
        for i in xrange(amount):
            if self.max > 0 and len(self._threads) >= self.max:
                break
            worker = WorkerThread(self.server)
            worker.setName("CP WSGIServer " + worker.getName())
            self._threads.append(worker)
            worker.start()
    
    def shrink(self, amount):
        """Kill off worker threads (not below self.min)."""
        # Grow/shrink the pool if necessary.
        # Remove any dead threads from our list
        for t in self._threads:
            if not t.isAlive():
                self._threads.remove(t)
                amount -= 1
        
        if amount > 0:
            for i in xrange(min(amount, len(self._threads) - self.min)):
                # Put a number of shutdown requests on the queue equal
                # to 'amount'. Once each of those is processed by a worker,
                # that worker will terminate and be culled from our list
                # in self.put.
                self._queue.put(_SHUTDOWNREQUEST)
    
    def stop(self, timeout=5):
        # Must shut down threads here so the code that calls
        # this method can know when all threads are stopped.
        for worker in self._threads:
            self._queue.put(_SHUTDOWNREQUEST)
        
        # Don't join currentThread (when stop is called inside a request).
        current = threading.currentThread()
        while self._threads:
            worker = self._threads.pop()
            if worker is not current and worker.isAlive():
                try:
                    if timeout is None or timeout < 0:
                        worker.join()
                    else:
                        worker.join(timeout)
                        if worker.isAlive():
                            # We exhausted the timeout.
                            # Forcibly shut down the socket.
                            c = worker.conn
                            if c and not c.rfile.closed:
                                if SSL and isinstance(c.socket, SSL.ConnectionType):
                                    # pyOpenSSL.socket.shutdown takes no args
                                    c.socket.shutdown()
                                else:
                                    c.socket.shutdown(socket.SHUT_RD)
                            worker.join()
                except (AssertionError,
                        # Ignore repeated Ctrl-C.
                        # See http://www.cherrypy.org/ticket/691.
                        KeyboardInterrupt), exc1:
                    pass



class SSLConnection:
    """A thread-safe wrapper for an SSL.Connection.
    
    *args: the arguments to create the wrapped SSL.Connection(*args).
    """
    
    def __init__(self, *args):
        self._ssl_conn = SSL.Connection(*args)
        self._lock = threading.RLock()
    
    for f in ('get_context', 'pending', 'send', 'write', 'recv', 'read',
              'renegotiate', 'bind', 'listen', 'connect', 'accept',
              'setblocking', 'fileno', 'shutdown', 'close', 'get_cipher_list',
              'getpeername', 'getsockname', 'getsockopt', 'setsockopt',
              'makefile', 'get_app_data', 'set_app_data', 'state_string',
              'sock_shutdown', 'get_peer_certificate', 'want_read',
              'want_write', 'set_connect_state', 'set_accept_state',
              'connect_ex', 'sendall', 'settimeout'):
        exec """def %s(self, *args):
        self._lock.acquire()
        try:
            return self._ssl_conn.%s(*args)
        finally:
            self._lock.release()
""" % (f, f)


try:
    import fcntl
except ImportError:
    try:
        from ctypes import windll, WinError
    except ImportError:
        def prevent_socket_inheritance(sock):
            """Dummy function, since neither fcntl nor ctypes are available."""
            pass
    else:
        def prevent_socket_inheritance(sock):
            """Mark the given socket fd as non-inheritable (Windows)."""
            if not windll.kernel32.SetHandleInformation(sock.fileno(), 1, 0):
                raise WinError()
else:
    def prevent_socket_inheritance(sock):
        """Mark the given socket fd as non-inheritable (POSIX)."""
        fd = sock.fileno()
        old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)


class CherryPyWSGIServer(object):
    """An HTTP server for WSGI.
    
    bind_addr: The interface on which to listen for connections.
        For TCP sockets, a (host, port) tuple. Host values may be any IPv4
        or IPv6 address, or any valid hostname. The string 'localhost' is a
        synonym for '127.0.0.1' (or '::1', if your hosts file prefers IPv6).
        The string '0.0.0.0' is a special IPv4 entry meaning "any active
        interface" (INADDR_ANY), and '::' is the similar IN6ADDR_ANY for
        IPv6. The empty string or None are not allowed.
        
        For UNIX sockets, supply the filename as a string.
    wsgi_app: the WSGI 'application callable'; multiple WSGI applications
        may be passed as (path_prefix, app) pairs.
    numthreads: the number of worker threads to create (default 10).
    server_name: the string to set for WSGI's SERVER_NAME environ entry.
        Defaults to socket.gethostname().
    max: the maximum number of queued requests (defaults to -1 = no limit).
    request_queue_size: the 'backlog' argument to socket.listen();
        specifies the maximum number of queued connections (default 5).
    timeout: the timeout in seconds for accepted connections (default 10).
    
    nodelay: if True (the default since 3.1), sets the TCP_NODELAY socket
        option.
    
    protocol: the version string to write in the Status-Line of all
        HTTP responses. For example, "HTTP/1.1" (the default). This
        also limits the supported features used in the response.
    
    
    SSL/HTTPS
    ---------
    The OpenSSL module must be importable for SSL functionality.
    You can obtain it from http://pyopenssl.sourceforge.net/
    
    ssl_certificate: the filename of the server SSL certificate.
    ssl_privatekey: the filename of the server's private key file.
    
    If either of these is None (both are None by default), this server
    will not use SSL. If both are given and are valid, they will be read
    on server start and used in the SSL context for the listening socket.
    """
    
    protocol = "HTTP/1.1"
    _bind_addr = "127.0.0.1"
    version = "CherryPy/3.1.2"
    ready = False
    _interrupt = None
    
    nodelay = True
    
    ConnectionClass = HTTPConnection
    environ = {}
    
    # Paths to certificate and private key files
    ssl_certificate = None
    ssl_private_key = None
    
    def __init__(self, bind_addr, wsgi_app, numthreads=10, server_name=None,
                 max=-1, request_queue_size=5, timeout=10, shutdown_timeout=5):
        self.requests = ThreadPool(self, min=numthreads or 1, max=max)
        
        if callable(wsgi_app):
            # We've been handed a single wsgi_app, in CP-2.1 style.
            # Assume it's mounted at "".
            self.wsgi_app = wsgi_app
        else:
            # We've been handed a list of (path_prefix, wsgi_app) tuples,
            # so that the server can call different wsgi_apps, and also
            # correctly set SCRIPT_NAME.
            warnings.warn("The ability to pass multiple apps is deprecated "
                          "and will be removed in 3.2. You should explicitly "
                          "include a WSGIPathInfoDispatcher instead.",
                          DeprecationWarning)
            self.wsgi_app = WSGIPathInfoDispatcher(wsgi_app)
        
        self.bind_addr = bind_addr
        if not server_name:
            server_name = socket.gethostname()
        self.server_name = server_name
        self.request_queue_size = request_queue_size
        
        self.timeout = timeout
        self.shutdown_timeout = shutdown_timeout
    
    def _get_numthreads(self):
        return self.requests.min
    def _set_numthreads(self, value):
        self.requests.min = value
    numthreads = property(_get_numthreads, _set_numthreads)
    
    def __str__(self):
        return "%s.%s(%r)" % (self.__module__, self.__class__.__name__,
                              self.bind_addr)
    
    def _get_bind_addr(self):
        return self._bind_addr
    def _set_bind_addr(self, value):
        if isinstance(value, tuple) and value[0] in ('', None):
            # Despite the socket module docs, using '' does not
            # allow AI_PASSIVE to work. Passing None instead
            # returns '0.0.0.0' like we want. In other words:
            #     host    AI_PASSIVE     result
            #      ''         Y         192.168.x.y
            #      ''         N         192.168.x.y
            #     None        Y         0.0.0.0
            #     None        N         127.0.0.1
            # But since you can get the same effect with an explicit
            # '0.0.0.0', we deny both the empty string and None as values.
            raise ValueError("Host values of '' or None are not allowed. "
                             "Use '0.0.0.0' (IPv4) or '::' (IPv6) instead "
                             "to listen on all active interfaces.")
        self._bind_addr = value
    bind_addr = property(_get_bind_addr, _set_bind_addr,
        doc="""The interface on which to listen for connections.
        
        For TCP sockets, a (host, port) tuple. Host values may be any IPv4
        or IPv6 address, or any valid hostname. The string 'localhost' is a
        synonym for '127.0.0.1' (or '::1', if your hosts file prefers IPv6).
        The string '0.0.0.0' is a special IPv4 entry meaning "any active
        interface" (INADDR_ANY), and '::' is the similar IN6ADDR_ANY for
        IPv6. The empty string or None are not allowed.
        
        For UNIX sockets, supply the filename as a string.""")
    
    def start(self):
        """Run the server forever."""
        # We don't have to trap KeyboardInterrupt or SystemExit here,
        # because cherrpy.server already does so, calling self.stop() for us.
        # If you're using this server with another framework, you should
        # trap those exceptions in whatever code block calls start().
        self._interrupt = None
        
        # Select the appropriate socket
        if isinstance(self.bind_addr, basestring):
            # AF_UNIX socket
            
            # So we can reuse the socket...
            try: os.unlink(self.bind_addr)
            except: pass
            
            # So everyone can access the socket...
            try: os.chmod(self.bind_addr, 0777)
            except: pass
            
            info = [(socket.AF_UNIX, socket.SOCK_STREAM, 0, "", self.bind_addr)]
        else:
            # AF_INET or AF_INET6 socket
            # Get the correct address family for our host (allows IPv6 addresses)
            host, port = self.bind_addr
            try:
                info = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                          socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
            except socket.gaierror:
                # Probably a DNS issue. Assume IPv4.
                info = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", self.bind_addr)]
        
        self.socket = None
        msg = "No socket could be created"
        for res in info:
            af, socktype, proto, canonname, sa = res
            try:
                self.bind(af, socktype, proto)
            except socket.error, msg:
                if self.socket:
                    self.socket.close()
                self.socket = None
                continue
            break
        if not self.socket:
            raise socket.error, msg
        
        # Timeout so KeyboardInterrupt can be caught on Win32
        self.socket.settimeout(1)
        self.socket.listen(self.request_queue_size)
        
        # Create worker threads
        self.requests.start()
        
        self.ready = True
        while self.ready:
            self.tick()
            if self.interrupt:
                while self.interrupt is True:
                    # Wait for self.stop() to complete. See _set_interrupt.
                    time.sleep(0.1)
                if self.interrupt:
                    raise self.interrupt
    
    def bind(self, family, type, proto=0):
        """Create (or recreate) the actual socket object."""
        self.socket = socket.socket(family, type, proto)
        prevent_socket_inheritance(self.socket)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.nodelay:
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if self.ssl_certificate and self.ssl_private_key:
            if SSL is None:
                raise ImportError("You must install pyOpenSSL to use HTTPS.")
            
            # See http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/442473
            ctx = SSL.Context(SSL.SSLv23_METHOD)
            ctx.use_privatekey_file(self.ssl_private_key)
            ctx.use_certificate_file(self.ssl_certificate)
            self.socket = SSLConnection(ctx, self.socket)
            self.populate_ssl_environ()
            
            # If listening on the IPV6 any address ('::' = IN6ADDR_ANY),
            # activate dual-stack. See http://www.cherrypy.org/ticket/871.
            if (not isinstance(self.bind_addr, basestring)
                and self.bind_addr[0] == '::' and family == socket.AF_INET6):
                try:
                    self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                except (AttributeError, socket.error):
                    # Apparently, the socket option is not available in
                    # this machine's TCP stack
                    pass
        
        self.socket.bind(self.bind_addr)
    
    def tick(self):
        """Accept a new connection and put it on the Queue."""
        try:
            s, addr = self.socket.accept()
            prevent_socket_inheritance(s)
            if not self.ready:
                return
            if hasattr(s, 'settimeout'):
                s.settimeout(self.timeout)
            
            environ = self.environ.copy()
            # SERVER_SOFTWARE is common for IIS. It's also helpful for
            # us to pass a default value for the "Server" response header.
            if environ.get("SERVER_SOFTWARE") is None:
                environ["SERVER_SOFTWARE"] = "%s WSGI Server" % self.version
            # set a non-standard environ entry so the WSGI app can know what
            # the *real* server protocol is (and what features to support).
            # See http://www.faqs.org/rfcs/rfc2145.html.
            environ["ACTUAL_SERVER_PROTOCOL"] = self.protocol
            environ["SERVER_NAME"] = self.server_name
            
            if isinstance(self.bind_addr, basestring):
                # AF_UNIX. This isn't really allowed by WSGI, which doesn't
                # address unix domain sockets. But it's better than nothing.
                environ["SERVER_PORT"] = ""
            else:
                environ["SERVER_PORT"] = str(self.bind_addr[1])
                # optional values
                # Until we do DNS lookups, omit REMOTE_HOST
                environ["REMOTE_ADDR"] = addr[0]
                environ["REMOTE_PORT"] = str(addr[1])
            
            conn = self.ConnectionClass(s, self.wsgi_app, environ)
            self.requests.put(conn)
        except socket.timeout:
            # The only reason for the timeout in start() is so we can
            # notice keyboard interrupts on Win32, which don't interrupt
            # accept() by default
            return
        except socket.error, x:
            if x.args[0] in socket_error_eintr:
                # I *think* this is right. EINTR should occur when a signal
                # is received during the accept() call; all docs say retry
                # the call, and I *think* I'm reading it right that Python
                # will then go ahead and poll for and handle the signal
                # elsewhere. See http://www.cherrypy.org/ticket/707.
                return
            if x.args[0] in socket_errors_nonblocking:
                # Just try again. See http://www.cherrypy.org/ticket/479.
                return
            if x.args[0] in socket_errors_to_ignore:
                # Our socket was closed.
                # See http://www.cherrypy.org/ticket/686.
                return
            raise
    
    def _get_interrupt(self):
        return self._interrupt
    def _set_interrupt(self, interrupt):
        self._interrupt = True
        self.stop()
        self._interrupt = interrupt
    interrupt = property(_get_interrupt, _set_interrupt,
                         doc="Set this to an Exception instance to "
                             "interrupt the server.")
    
    def stop(self):
        """Gracefully shutdown a server that is serving forever."""
        self.ready = False
        
        sock = getattr(self, "socket", None)
        if sock:
            if not isinstance(self.bind_addr, basestring):
                # Touch our own socket to make accept() return immediately.
                try:
                    host, port = sock.getsockname()[:2]
                except socket.error, x:
                    if x.args[0] not in socket_errors_to_ignore:
                        raise
                else:
                    # Note that we're explicitly NOT using AI_PASSIVE,
                    # here, because we want an actual IP to touch.
                    # localhost won't work if we've bound to a public IP,
                    # but it will if we bound to '0.0.0.0' (INADDR_ANY).
                    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                                  socket.SOCK_STREAM):
                        af, socktype, proto, canonname, sa = res
                        s = None
                        try:
                            s = socket.socket(af, socktype, proto)
                            # See http://groups.google.com/group/cherrypy-users/
                            #        browse_frm/thread/bbfe5eb39c904fe0
                            s.settimeout(1.0)
                            s.connect((host, port))
                            s.close()
                        except socket.error:
                            if s:
                                s.close()
            if hasattr(sock, "close"):
                sock.close()
            self.socket = None
        
        self.requests.stop(self.shutdown_timeout)
    
    def populate_ssl_environ(self):
        """Create WSGI environ entries to be merged into each request."""
        cert = open(self.ssl_certificate, 'rb').read()
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
        ssl_environ = {
            "wsgi.url_scheme": "https",
            "HTTPS": "on",
            # pyOpenSSL doesn't provide access to any of these AFAICT
##            'SSL_PROTOCOL': 'SSLv2',
##            SSL_CIPHER 	string 	The cipher specification name
##            SSL_VERSION_INTERFACE 	string 	The mod_ssl program version
##            SSL_VERSION_LIBRARY 	string 	The OpenSSL program version
            }
        
        # Server certificate attributes
        ssl_environ.update({
            'SSL_SERVER_M_VERSION': cert.get_version(),
            'SSL_SERVER_M_SERIAL': cert.get_serial_number(),
##            'SSL_SERVER_V_START': Validity of server's certificate (start time),
##            'SSL_SERVER_V_END': Validity of server's certificate (end time),
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
        
        self.environ.update(ssl_environ)

