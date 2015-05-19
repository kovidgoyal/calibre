#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, socket, re, os
from io import BytesIO
import repr as reprlib
from urllib import unquote
from functools import partial
from operator import itemgetter

from calibre import as_unicode
from calibre.constants import __version__
from calibre.srv.errors import (
    MaxSizeExceeded, NonHTTPConnRequest, HTTP404, IfNoneMatch)
from calibre.srv.respond import finalize_output, generate_static_output
from calibre.srv.utils import MultiDict, http_date

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
    'Accept', 'Accept-Charset', 'Accept-Encoding',
    'Accept-Language', 'Accept-Ranges', 'Allow', 'Cache-Control',
    'Connection', 'Content-Encoding', 'Content-Language', 'Expect',
    'If-Match', 'If-None-Match', 'Pragma', 'Proxy-Authenticate', 'TE',
    'Trailer', 'Transfer-Encoding', 'Upgrade', 'Vary', 'Via', 'Warning',
    'WWW-Authenticate'
}

decoded_headers = {
    'Transfer-Encoding', 'Connection', 'Keep-Alive', 'Expect',
} | comma_separated_headers

def read_headers(readline):  # {{{
    """
    Read headers from the given stream into the given header dict.

    If hdict is None, a new header dict is created. Returns the populated
    header dict.

    Headers which are repeated are folded together using a comma if their
    specification so dictates.

    This function raises ValueError when the read bytes violate the HTTP spec.
    You should probably return "400 Bad Request" if this happens.
    """
    hdict = MultiDict()

    def safe_decode(hname, value):
        try:
            return value.decode('ascii')
        except UnicodeDecodeError:
            if hname in decoded_headers:
                raise
        return value

    current_key = current_value = None

    def commit():
        if current_key:
            key = current_key.decode('ascii')
            val = safe_decode(key, current_value)
            if key in comma_separated_headers:
                existing = hdict.pop(key)
                if existing is not None:
                    val = existing + ', ' + val
            hdict[key] = val

    while True:
        line = readline()
        if not line:
            # No more data--illegal end of headers
            raise ValueError("Illegal end of headers.")

        if line == b'\r\n':
            # Normal end of headers
            commit()
            break
        if not line.endswith(b'\r\n'):
            raise ValueError("HTTP requires CRLF terminators")

        if line[0] in b' \t':
            # It's a continuation line.
            if current_key is None or current_value is None:
                raise ValueError('Orphaned continuation line')
            current_value += b' ' + line.strip()
        else:
            commit()
            current_key = current_value = None
            k, v = line.split(b':', 1)
            current_key = k.strip().title()
            current_value = v.strip()

    return hdict
# }}}

def http_communicate(conn):
    ' Represents interaction with a http client over a single, persistent connection '
    request_seen = False
    try:
        while True:
            # (re)set pair to None so that if something goes wrong in
            # the HTTPPair constructor, the error doesn't
            # get written to the previous request.
            pair = None
            pair = conn.server_loop.http_handler(conn)

            # This order of operations should guarantee correct pipelining.
            pair.parse_request()
            if not pair.ready:
                # Something went wrong in the parsing (and the server has
                # probably already made a simple_response). Return and
                # let the conn close.
                return

            request_seen = True
            pair.respond()
            if pair.close_connection:
                return
    except socket.timeout:
        # Don't error if we're between requests; only error
        # if 1) no request has been started at all, or 2) we're
        # in the middle of a request. This allows persistent
        # connections for HTTP/1.1
        if (not request_seen) or (pair and pair.started_request):
            # Don't bother writing the 408 if the response
            # has already started being written.
            if pair and not pair.sent_headers:
                pair.simple_response(httplib.REQUEST_TIMEOUT)
    except NonHTTPConnRequest:
        raise
    except socket.error:
        # This socket is broken. Log the error and close connection
        conn.server_loop.log.exception(
            'Communication failed while processing request:', pair.repr_for_log() if getattr(pair, 'started_request', False) else 'None')
    except Exception:
        conn.server_loop.log.exception('Error serving request:', pair.repr_for_log() if getattr(pair, 'started_request', False) else 'None')
        if pair and not pair.sent_headers:
            pair.simple_response(httplib.INTERNAL_SERVER_ERROR)

class FixedSizeReader(object):

    def __init__(self, socket_file, content_length):
        self.socket_file, self.remaining = socket_file, content_length

    def read(self, size=-1):
        if size < 0:
            size = self.remaining
        size = min(self.remaining, size)
        if size < 1:
            return b''
        data = self.socket_file.read(size)
        self.remaining -= len(data)
        return data


class ChunkedReader(object):

    def __init__(self, socket_file, maxsize):
        self.socket_file, self.maxsize = socket_file, maxsize
        self.rbuf = BytesIO()
        self.bytes_read = 0
        self.finished = False

    def check_size(self):
        if self.bytes_read > self.maxsize:
            raise MaxSizeExceeded('Request entity too large', self.bytes_read, self.maxsize)

    def read_chunk(self):
        if self.finished:
            return
        line = self.socket_file.readline()
        self.bytes_read += len(line)
        self.check_size()
        chunk_size = line.strip().split(b';', 1)[0]
        try:
            chunk_size = int(line, 16) + 2
        except Exception:
            raise ValueError('%s is not a valid chunk size' % reprlib.repr(chunk_size))
        if chunk_size + self.bytes_read > self.maxsize:
            raise MaxSizeExceeded('Request entity too large', self.bytes_read + chunk_size, self.maxsize)
        chunk = self.socket_file.read(chunk_size)
        if len(chunk) < chunk_size:
            raise ValueError('Bad chunked encoding, chunk truncated: %d < %s' % (len(chunk), chunk_size))
        if not chunk.endswith(b'\r\n'):
            raise ValueError('Bad chunked encoding: %r != CRLF' % chunk[:-2])
        self.rbuf.seek(0, os.SEEK_END)
        self.bytes_read += chunk_size
        if chunk_size == 2:
            self.finished = True
        else:
            self.rbuf.write(chunk[:-2])

    def read(self, size=-1):
        if size < 0:
            # Read all data
            while not self.finished:
                self.read_chunk()
            self.rbuf.seek(0)
            rv = self.rbuf.read()
            if rv:
                self.rbuf.truncate(0)
            return rv
        if size == 0:
            return b''
        while self.rbuf.tell() < size and not self.finished:
            self.read_chunk()
        data = self.rbuf.getvalue()
        self.rbuf.truncate(0)
        if size < len(data):
            self.rbuf.write(data[size:])
            return data[:size]
        return data


class HTTPPair(object):

    ''' Represents a HTTP request/response pair '''

    def __init__(self, handle_request, conn):
        self.conn = conn
        self.server_loop = conn.server_loop
        self.max_header_line_size = self.server_loop.opts.max_header_line_size * 1024
        self.max_request_body_size = self.server_loop.opts.max_request_body_size * 1024 * 1024
        self.scheme = 'http' if self.server_loop.ssl_context is None else 'https'
        self.inheaders = MultiDict()
        self.outheaders = MultiDict()
        self.handle_request = handle_request
        self.request_line = None
        self.path = ()
        self.qs = MultiDict()
        self.method = None

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

        self.status_code = None
        self.sent_headers = False

        self.request_content_length = 0
        self.chunked_read = False

    def parse_request(self):
        """Parse the next HTTP request start-line and message-headers."""
        try:
            if not self.read_request_line():
                return
        except MaxSizeExceeded:
            self.simple_response(
                httplib.REQUEST_URI_TOO_LONG,
                "The Request-URI sent with the request exceeds the maximum allowed bytes.")
            return

        try:
            if not self.read_request_headers():
                return
        except MaxSizeExceeded:
            self.simple_response(
                httplib.REQUEST_ENTITY_TOO_LARGE,
                "The headers sent with the request exceed the maximum allowed bytes.")
            return

        self.ready = True

    def read_request_line(self):
        self.request_line = request_line = self.conn.socket_file.readline(maxsize=self.max_header_line_size)

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
                httplib.BAD_REQUEST, "HTTP requires CRLF terminators")
            return False

        try:
            method, uri, req_protocol = request_line.strip().split(b' ', 2)
            rp = int(req_protocol[5]), int(req_protocol[7])
            self.method = method.decode('ascii')
        except (ValueError, IndexError):
            self.simple_response(httplib.BAD_REQUEST, "Malformed Request-Line")
            return False

        try:
            self.request_protocol = protocol_map[rp]
        except KeyError:
            self.simple_response(httplib.HTTP_VERSION_NOT_SUPPORTED)
            return False

        scheme, authority, path = parse_request_uri(uri)
        if b'#' in path:
            self.simple_response(httplib.BAD_REQUEST, "Illegal #fragment in Request-URI.")
            return False

        if scheme:
            try:
                self.scheme = scheme.decode('ascii')
            except ValueError:
                self.simple_response(httplib.BAD_REQUEST, 'Un-decodeable scheme')
                return False

        qs = b''
        if b'?' in path:
            path, qs = path.split(b'?', 1)
            try:
                self.qs = MultiDict.create_from_query_string(qs)
            except Exception:
                self.simple_response(httplib.BAD_REQUEST, "Malformed Request-Line",
                                     'Unparseable query string')
                return False

        try:
            path = '%2F'.join(unquote(x).decode('utf-8') for x in quoted_slash.split(path))
        except ValueError as e:
            self.simple_response(httplib.BAD_REQUEST, as_unicode(e))
            return False
        self.path = tuple(x.replace('%2F', '/') for x in path.split('/'))

        self.response_protocol = protocol_map[min((1, 1), rp)]

        return True

    def read_request_headers(self):
        # then all the http headers
        try:
            self.inheaders = read_headers(partial(self.conn.socket_file.readline, maxsize=self.max_header_line_size))
            self.request_content_length = int(self.inheaders.get('Content-Length', 0))
        except ValueError as e:
            self.simple_response(httplib.BAD_REQUEST, as_unicode(e))
            return False

        if self.request_content_length > self.max_request_body_size:
            self.simple_response(
                httplib.REQUEST_ENTITY_TOO_LARGE,
                "The entity sent with the request exceeds the maximum "
                "allowed bytes (%d)." % self.max_request_body_size)
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
                    self.simple_response(httplib.NOT_IMPLEMENTED, "Unknown transfer encoding: %r" % enc)
                    self.close_connection = True
                    return False

        if self.inheaders.get("Expect", '').lower() == "100-continue":
            # Don't use simple_response here, because it emits headers
            # we don't want.
            msg = HTTP11 + " 100 Continue\r\n\r\n"
            self.flushed_write(msg.encode('ascii'))
        return True

    def simple_response(self, status_code, msg="", read_remaining_input=False):
        abort = status_code in (httplib.REQUEST_ENTITY_TOO_LARGE, httplib.REQUEST_URI_TOO_LONG)
        if abort:
            self.close_connection = True
            if self.reponse_protocol is HTTP1:
                # HTTP/1.0 has no 413/414 codes
                status_code = httplib.BAD_REQUEST

        msg = msg.encode('utf-8')
        buf = [
            '%s %d %s' % (self.reponse_protocol, status_code, httplib.responses[status_code]),
            "Content-Length: %s" % len(msg),
            "Content-Type: text/plain; charset=UTF-8",
            "Date: " + http_date(),
        ]
        if abort and self.reponse_protocol is HTTP11:
            buf.append("Connection: close")
        buf.append('')
        buf = [(x + '\r\n').encode('ascii') for x in buf]
        if self.method != 'HEAD':
            buf.append(msg)
        if read_remaining_input:
            self.input_reader.read()
        self.flushed_write(b''.join(buf))

    def send_not_modified(self, etag=None):
        buf = [
            '%s %d %s' % (self.reponse_protocol, httplib.NOT_MODIFIED, httplib.responses[httplib.NOT_MODIFIED]),
            "Content-Length: 0",
            "Date: " + http_date(),
        ]
        if etag is not None:
            buf.append('ETag: ' + etag)
        for header in ('Expires', 'Cache-Control', 'Vary'):
            val = self.outheaders.get(header)
            if val:
                buf.append(header + ': ' + val)
        buf.append('')
        buf = [(x + '\r\n').encode('ascii') for x in buf]
        self.flushed_write(b''.join(buf))

    def flushed_write(self, data):
        self.conn.socket_file.write(data)
        self.conn.socket_file.flush()

    def repr_for_log(self):
        return 'HTTPPair: %r\nPath:%r\nQuery:\n%s\nIn Headers:\n%s\nOut Headers:\n%s' % (
            self.request_line, self.path, self.qs.pretty('\t'), self.inheaders.pretty('\t'), self.outheaders.pretty('\t')
        )

    def generate_static_output(self, name, generator):
        return generate_static_output(self.server_loop.gso_cache, self.server_loop.gso_lock, name, generator)

    def respond(self):
        if self.chunked_read:
            self.input_reader = ChunkedReader(self.conn.socket_file, self.max_request_body_size)
        else:
            self.input_reader = FixedSizeReader(self.conn.socket_file, self.request_content_length)

        try:
            output = self.handle_request(self)
        except HTTP404 as e:
            self.simple_response(httplib.NOT_FOUND, e.message, read_remaining_input=True)
            return
        # Read and discard any remaining body from the HTTP request
        self.input_reader.read()
        if self.status_code is None:
            self.status_code = httplib.OK

        try:
            self.status_code, output = finalize_output(output, self.inheaders, self.outheaders, self.status_code, self.response_protocol is HTTP1, self.method)
        except IfNoneMatch as e:
            if self.method in ('GET', 'HEAD'):
                self.send_not_modified(e.etag)
            else:
                self.simple_response(httplib.PRECONDITION_FAILED)
            return

        self.send_headers()

        if self.method != 'HEAD':
            output.commit(self.conn.socket_file)
        self.conn.socket_file.flush()

    def send_headers(self):
        self.sent_headers = True
        self.outheaders.set('Date', http_date(), replace_all=True)
        self.outheaders.set('Server', 'calibre %s' % __version__, replace_all=True)
        if 'Connection' not in self.outheaders:
            if self.reponse_protocol is HTTP11:
                if self.close_connection:
                    self.outheaders.set('Connection', 'close')
            else:
                if not self.close_connection:
                    self.outheaders.set('Connection', 'Keep-Alive')

        buf = [HTTP11 + (' %d ' % self.status_code) + httplib.responses[self.status_code]]
        for header, value in sorted(self.outheaders.iteritems(), key=itemgetter(0)):
            buf.append('%s: %s' % (header, value))
        buf.append('')
        self.flushed_write(b''.join((x + '\r\n').encode('ascii') for x in buf))


def create_http_handler(handle_request):
    return partial(HTTPPair, handle_request)
