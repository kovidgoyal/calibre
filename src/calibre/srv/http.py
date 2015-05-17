#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, socket, re
from urllib import unquote
from urlparse import parse_qs
from functools import partial

from calibre import as_unicode
from calibre.srv.errors import MaxSizeExceeded, NonHTTPConnRequest

HTTP1  = 'HTTP/1.0'
HTTP11 = 'HTTP/1.1'
protocol_map = {(1, 0):HTTP1, (1, 1):HTTP11}
quoted_slash = re.compile(br'%2[fF]')

def parse_request_uri(uri):  # {{{
    """Parse a Request-URI into (scheme, authority, path).

    Note that Request-URI's must be one of::

        Request-URI    = "*" | absoluteURI | abs_path | authority

    Therefore, a Request-URI which starts with a double forward-slash
    cannot be a "net_path"::

        net_path      = "//" authority [ abs_path ]

    Instead, it must be interpreted as an "abs_path" with an empty first
    path segment::

        abs_path      = "/"  path_segments
        path_segments = segment *( "/" segment )
        segment       = *pchar *( ";" param )
        param         = *pchar
    """
    if uri == b'*':
        return None, None, uri

    i = uri.find(b'://')
    if i > 0 and b'?' not in uri[:i]:
        # An absoluteURI.
        # If there's a scheme (and it must be http or https), then:
        # http_URL = "http:" "//" host [ ":" port ] [ abs_path [ "?" query
        # ]]
        scheme, remainder = uri[:i].lower(), uri[i + 3:]
        authority, path = remainder.split(b'/', 1)
        path = b'/' + path
        return scheme, authority, path

    if uri.startswith(b'/'):
        # An abs_path.
        return None, None, uri
    else:
        # An authority.
        return None, uri, None
# }}}

comma_separated_headers = {
    b'Accept', b'Accept-Charset', b'Accept-Encoding',
    b'Accept-Language', b'Accept-Ranges', b'Allow', b'Cache-Control',
    b'Connection', b'Content-Encoding', b'Content-Language', b'Expect',
    b'If-Match', b'If-None-Match', b'Pragma', b'Proxy-Authenticate', b'TE',
    b'Trailer', b'Transfer-Encoding', b'Upgrade', b'Vary', b'Via', b'Warning',
    b'WWW-Authenticate'
}

decoded_headers = {
    'Transfer-Encoding', 'Connection', 'Keep-Alive', 'Expect',
}

def read_headers(readline, max_line_size, hdict=None):  # {{{
    """
    Read headers from the given stream into the given header dict.

    If hdict is None, a new header dict is created. Returns the populated
    header dict.

    Headers which are repeated are folded together using a comma if their
    specification so dictates.

    This function raises ValueError when the read bytes violate the HTTP spec.
    You should probably return "400 Bad Request" if this happens.
    """
    if hdict is None:
        hdict = {}

    while True:
        line = readline()
        if not line:
            # No more data--illegal end of headers
            raise ValueError("Illegal end of headers.")

        if line == b'\r\n':
            # Normal end of headers
            break
        if not line.endswith(b'\r\n'):
            raise ValueError("HTTP requires CRLF terminators")

        if line[0] in (b' ', b'\t'):
            # It's a continuation line.
            v = line.strip()
        else:
            try:
                k, v = line.split(b':', 1)
            except ValueError:
                raise ValueError("Illegal header line.")
            k = k.strip().title()
            v = v.strip()
            hname = k.decode('ascii')

        if k in comma_separated_headers:
            existing = hdict.get(hname)
            if existing:
                v = b", ".join((existing, v))
        try:
            v = v.decode('ascii')
        except UnicodeDecodeError:
            if hname in decoded_headers:
                raise
        hdict[hname] = v

    return hdict
# }}}

def http_communicate(conn):
    ' Represents interaction with a http client over a single, persistent connection '
    request_seen = False
    try:
        while True:
            # (re)set req to None so that if something goes wrong in
            # the HTTPPair constructor, the error doesn't
            # get written to the previous request.
            req = None
            req = conn.server_loop.http_handler(conn)

            # This order of operations should guarantee correct pipelining.
            req.parse_request()
            if not req.ready:
                # Something went wrong in the parsing (and the server has
                # probably already made a simple_response). Return and
                # let the conn close.
                return

            request_seen = True
            req.respond()
            if req.close_connection:
                return
    except socket.timeout:
        # Don't error if we're between requests; only error
        # if 1) no request has been started at all, or 2) we're
        # in the middle of a request. This allows persistent
        # connections for HTTP/1.1
        if (not request_seen) or (req and req.started_request):
            # Don't bother writing the 408 if the response
            # has already started being written.
            if req and not req.sent_headers:
                req.simple_response(httplib.REQUEST_TIMEOUT, "Request Timeout")
    except NonHTTPConnRequest:
        raise
    except Exception:
        conn.server_loop.log.exception()
        if req and not req.sent_headers:
            req.simple_response(httplib.INTERNAL_SERVER_ERROR, "Internal Server Error")


class HTTPPair(object):

    ''' Represents a HTTP request/response pair '''

    def __init__(self, conn):
        self.conn = conn
        self.server_loop = conn.server_loop
        self.max_header_line_size = self.server_loop.max_header_line_size
        self.scheme = 'http' if self.server_loop.ssl_context is None else 'https'
        self.inheaders = {}
        self.outheaders = []

        """When True, the request has been parsed and is ready to begin generating
        the response. When False, signals the calling Connection that the response
        should not be generated and the connection should close, immediately after
        parsing the request."""
        self.ready = False

        """Signals the calling Connection that the request should close. This does
        not imply an error! The client and/or server may each request that the
        connection be closed, after the response."""
        self.close_connection = False

        self.started_request = False
        self.reponse_protocol = HTTP1

        self.status = b''
        self.sent_headers = False

    def parse_request(self):
        """Parse the next HTTP request start-line and message-headers."""
        try:
            if not self.read_request_line():
                return
        except MaxSizeExceeded:
            self.simple_response(
                httplib.REQUEST_URI_TOO_LONG, "Request-URI Too Long",
                "The Request-URI sent with the request exceeds the maximum allowed bytes.")
            return

        try:
            if not self.read_request_headers():
                return
        except MaxSizeExceeded:
            self.simple_response(
                httplib.REQUEST_ENTITY_TOO_LARGE, "Request Entity Too Large",
                "The headers sent with the request exceed the maximum allowed bytes.")
            return

        self.ready = True

    def read_request_line(self):
        request_line = self.conn.socket_file.readline(maxsize=self.max_header_line_size)

        # Set started_request to True so http_communicate() knows to send 408
        # from here on out.
        self.started_request = True
        if not request_line:
            return False

        if request_line == b'\r\n':
            # RFC 2616 sec 4.1: "...if the server is reading the protocol
            # stream at the beginning of a message and receives a CRLF
            # first, it should ignore the CRLF."
            # But only ignore one leading line! else we enable a DoS.
            request_line = self.conn.socket_file.readline(maxsize=self.max_header_line_size)
            if not request_line:
                return False

        if not request_line.endswith(b'\r\n'):
            self.simple_response(
                httplib.BAD_REQUEST, 'Bad Request', "HTTP requires CRLF terminators")
            return False

        try:
            method, uri, req_protocol = request_line.strip().split(b' ', 2)
            rp = int(req_protocol[5]), int(req_protocol[7])
            self.method = method.decode('ascii')
        except (ValueError, IndexError):
            self.simple_response(httplib.BAD_REQUEST, "Bad Request", "Malformed Request-Line")
            return False

        try:
            self.request_protocol = protocol_map[rp]
        except KeyError:
            self.simple_response(httplib.HTTP_VERSION_NOT_SUPPORTED, "HTTP Version Not Supported")
            return False

        scheme, authority, path = parse_request_uri(uri)
        if b'#' in path:
            self.simple_response(httplib.BAD_REQUEST, "Bad Request", "Illegal #fragment in Request-URI.")
            return False

        if scheme:
            try:
                self.scheme = scheme.decode('ascii')
            except ValueError:
                self.simple_response(httplib.BAD_REQUEST, "Bad Request", 'Un-decodeable scheme')
                return False

        qs = b''
        if b'?' in path:
            path, qs = path.split(b'?', 1)
            try:
                self.qs = {k.decode('utf-8'):tuple(x.decode('utf-8') for x in v) for k, v in parse_qs(qs, keep_blank_values=True).iteritems()}
            except Exception:
                self.simple_response(httplib.BAD_REQUEST, "Bad Request", "Malformed Request-Line",
                                     'Unparseable query string')
                return False

        try:
            path = '%2F'.join(unquote(x).decode('utf-8') for x in quoted_slash.split(path))
        except ValueError as e:
            self.simple_response(httplib.BAD_REQUEST, "Bad Request", as_unicode(e))
            return False
        self.path = tuple(x.replace('%2F', '/') for x in path.split('/'))

        self.response_protocol = protocol_map[min((1, 1), rp)]

        return True

    def read_request_headers(self):
        # then all the http headers
        try:
            read_headers(partial(self.conn.socket_file.readline, maxsize=self.max_header_line_size), self.inheaders)
            content_length = int(self.inheaders.get('Content-Length', 0))
        except ValueError as e:
            self.simple_response(httplib.BAD_REQUEST, "Bad Request", as_unicode(e))
            return False

        if content_length > self.server_loop.max_request_body_size:
            self.simple_response(
                httplib.REQUEST_ENTITY_TOO_LARGE, "Request Entity Too Large",
                "The entity sent with the request exceeds the maximum "
                "allowed bytes (%d)." % self.server_loop.max_request_body_size)
            return False

        # Persistent connection support
        if self.response_protocol is HTTP11:
            # Both server and client are HTTP/1.1
            if self.inheaders.get("Connection", "") == "close":
                self.close_connection = True
        else:
            # Either the server or client (or both) are HTTP/1.0
            if self.inheaders.get("Connection", "") != "Keep-Alive":
                self.close_connection = True

        # Transfer-Encoding support
        te = ()
        if self.response_protocol is HTTP11:
            rte = self.inheaders.get("Transfer-Encoding")
            if rte:
                te = [x.strip().lower() for x in rte.split(",") if x.strip()]
        self.chunked_read = False
        if te:
            for enc in te:
                if enc == "chunked":
                    self.chunked_read = True
                else:
                    # Note that, even if we see "chunked", we must reject
                    # if there is an extension we don't recognize.
                    self.simple_response(httplib.NOT_IMPLEMENTED, "Not Implemented", "Unknown transfer encoding: %s" % enc)
                    self.close_connection = True
                    return False

        if self.inheaders.get("Expect", '').lower() == "100-continue":
            # Don't use simple_response here, because it emits headers
            # we don't want.
            msg = HTTP11 + " 100 Continue\r\n\r\n"
            self.flushed_write(msg.encode('ascii'))
        return True

    def simple_response(self, status_code, status_text, msg=""):
        abort = status_code in (httplib.REQUEST_ENTITY_TOO_LARGE, httplib.REQUEST_URI_TOO_LONG)
        if abort:
            self.close_connection = True
            if self.reponse_protocol is HTTP1:
                # HTTP/1.0 has no 413/414 codes
                status_code, status_text = 400, 'Bad Request'

        msg = msg.encode('utf-8')
        buf = [
            '%s %d %s' % (self.reponse_protocol, status_code, status_text),
            "Content-Length: %s" % len(msg),
            "Content-Type: text/plain; charset=UTF-8"
        ]
        if abort and self.reponse_protocol is HTTP11:
            buf.append("Connection: close")
        buf.append('')
        buf = [(x + '\r\n').encode('ascii') for x in buf]
        buf.append(msg)
        self.flushed_write(b''.join(buf))

    def flushed_write(self, data):
        self.conn.socket_file.write(data)
        self.conn.socket_file.flush()
