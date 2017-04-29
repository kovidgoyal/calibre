#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import re, httplib, repr as reprlib
from io import BytesIO, DEFAULT_BUFFER_SIZE
from urllib import unquote

from calibre import as_unicode, force_unicode
from calibre.ptempfile import SpooledTemporaryFile
from calibre.srv.errors import HTTPSimpleResponse
from calibre.srv.loop import Connection, READ, WRITE
from calibre.srv.utils import MultiDict, HTTP1, HTTP11, Accumulator

protocol_map = {(1, 0):HTTP1, (1, 1):HTTP11}
quoted_slash = re.compile(br'%2[fF]')
HTTP_METHODS = {'HEAD', 'GET', 'PUT', 'POST', 'TRACE', 'DELETE', 'OPTIONS'}

# Parse URI {{{


def parse_request_uri(uri):
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
        authority, path = remainder.partition(b'/')[::2]
        path = b'/' + path
        return scheme, authority, path

    if uri.startswith(b'/'):
        # An abs_path.
        return None, None, uri
    else:
        # An authority.
        return None, uri, None


def parse_uri(uri, parse_query=True):
    scheme, authority, path = parse_request_uri(uri)
    if path is None:
        raise HTTPSimpleResponse(httplib.BAD_REQUEST, "No path component")
    if b'#' in path:
        raise HTTPSimpleResponse(httplib.BAD_REQUEST, "Illegal #fragment in Request-URI.")

    if scheme:
        try:
            scheme = scheme.decode('ascii')
        except ValueError:
            raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'Un-decodeable scheme')

    path, qs = path.partition(b'?')[::2]
    if parse_query:
        try:
            query = MultiDict.create_from_query_string(qs)
        except Exception:
            raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'Unparseable query string')
    else:
        query = None

    try:
        path = '%2F'.join(unquote(x).decode('utf-8') for x in quoted_slash.split(path))
    except ValueError as e:
        raise HTTPSimpleResponse(httplib.BAD_REQUEST, as_unicode(e))
    path = tuple(filter(None, (x.replace('%2F', '/') for x in path.split('/'))))

    return scheme, path, query
# }}}


# HTTP Header parsing {{{
comma_separated_headers = {
    'Accept', 'Accept-Charset', 'Accept-Encoding',
    'Accept-Language', 'Accept-Ranges', 'Allow', 'Cache-Control',
    'Connection', 'Content-Encoding', 'Content-Language', 'Expect',
    'If-Match', 'If-None-Match', 'Pragma', 'Proxy-Authenticate', 'TE',
    'Trailer', 'Transfer-Encoding', 'Upgrade', 'Vary', 'Via', 'Warning',
}

decoded_headers = {
    'Transfer-Encoding', 'Keep-Alive', 'Expect', 'WWW-Authenticate', 'Authorization',
    'Sec-WebSocket-Key', 'Sec-WebSocket-Version', 'Sec-WebSocket-Protocol',
} | comma_separated_headers

uppercase_headers = {'WWW', 'TE'}


def normalize_header_name(name):
    parts = [x.capitalize() for x in name.split('-')]
    q = parts[0].upper()
    if q in uppercase_headers:
        parts[0] = q
    if len(parts) == 3 and parts[1] == 'Websocket':
        parts[1] = 'WebSocket'
    return '-'.join(parts)


class HTTPHeaderParser(object):

    '''
    Parse HTTP headers. Use this class by repeatedly calling the created object
    with a single line at a time and checking the finished attribute. Can raise ValueError
    for malformed headers, in which case you should probably return BAD_REQUEST.

    Headers which are repeated are folded together using a comma if their
    specification so dictates.
    '''
    __slots__ = ('hdict', 'lines', 'finished')

    def __init__(self):
        self.hdict = MultiDict()
        self.lines = []
        self.finished = False

    def push(self, *lines):
        for line in lines:
            self(line)

    def __call__(self, line):
        'Process a single line'

        def safe_decode(hname, value):
            try:
                return value.decode('utf-8')
            except UnicodeDecodeError:
                if hname in decoded_headers:
                    raise
            return value

        def commit():
            if not self.lines:
                return
            line = b' '.join(self.lines)
            del self.lines[:]

            k, v = line.partition(b':')[::2]
            key = normalize_header_name(k.strip().decode('ascii'))
            val = safe_decode(key, v.strip())
            if not key or not val:
                raise ValueError('Malformed header line: %s' % reprlib.repr(line))
            if key in comma_separated_headers:
                existing = self.hdict.pop(key)
                if existing is not None:
                    val = existing + ', ' + val
            self.hdict[key] = val

        if self.finished:
            raise ValueError('Header block already terminated')

        if line == b'\r\n':
            # Normal end of headers
            commit()
            self.finished = True
            return

        if line and line[0] in b' \t':
            # It's a continuation line.
            if not self.lines:
                raise ValueError('Orphaned continuation line')
            self.lines.append(line.lstrip())
        else:
            commit()
            self.lines.append(line)


def read_headers(readline):
    p = HTTPHeaderParser()
    while not p.finished:
        p(readline())
    return p.hdict
# }}}


class HTTPRequest(Connection):

    request_handler = None
    static_cache = None
    translator_cache = None

    def __init__(self, *args, **kwargs):
        Connection.__init__(self, *args, **kwargs)
        self.max_header_line_size = int(1024 * self.opts.max_header_line_size)
        self.max_request_body_size = int(1024 * 1024 * self.opts.max_request_body_size)

    def read(self, buf, endpos):
        size = endpos - buf.tell()
        if size > 0:
            data = self.recv(size)
            if data:
                buf.write(data)
                return len(data) >= size
            else:
                return False
        else:
            return True

    def readline(self, buf):
        line = self.read_buffer.readline()
        buf.append(line)
        if buf.total_length > self.max_header_line_size:
            self.simple_response(self.header_line_too_long_error_code)
            return
        if line.endswith(b'\n'):
            line = buf.getvalue()
            if not line.endswith(b'\r\n'):
                self.simple_response(httplib.BAD_REQUEST, 'HTTP requires CRLF line terminators')
                return
            return line
        if not line:
            # read buffer is empty, fill it
            self.fill_read_buffer()

    def connection_ready(self):
        'Become ready to read an HTTP request'
        self.method = self.request_line = None
        self.response_protocol = self.request_protocol = HTTP1
        self.path = self.query = None
        self.close_after_response = False
        self.header_line_too_long_error_code = httplib.REQUEST_URI_TOO_LONG
        self.response_started = False
        self.set_state(READ, self.parse_request_line, Accumulator(), first=True)

    def parse_request_line(self, buf, event, first=False):  # {{{
        line = self.readline(buf)
        if line is None:
            return
        self.request_line = line.rstrip()
        if line == b'\r\n':
            # Ignore a single leading empty line, as per RFC 2616 sec 4.1
            if first:
                return self.set_state(READ, self.parse_request_line, Accumulator())
            return self.simple_response(httplib.BAD_REQUEST, 'Multiple leading empty lines not allowed')

        try:
            method, uri, req_protocol = line.strip().split(b' ', 2)
            rp = int(req_protocol[5]), int(req_protocol[7])
            self.method = method.decode('ascii').upper()
        except Exception:
            return self.simple_response(httplib.BAD_REQUEST, "Malformed Request-Line")

        if self.method not in HTTP_METHODS:
            return self.simple_response(httplib.BAD_REQUEST, "Unknown HTTP method")

        try:
            self.request_protocol = protocol_map[rp]
        except KeyError:
            return self.simple_response(httplib.HTTP_VERSION_NOT_SUPPORTED)
        self.response_protocol = protocol_map[min((1, 1), rp)]
        try:
            self.scheme, self.path, self.query = parse_uri(uri)
        except HTTPSimpleResponse as e:
            return self.simple_response(e.http_code, e.message, close_after_response=False)
        self.header_line_too_long_error_code = httplib.REQUEST_ENTITY_TOO_LARGE
        self.set_state(READ, self.parse_header_line, HTTPHeaderParser(), Accumulator())
    # }}}

    @property
    def state_description(self):
        return 'State: %s Client: %s:%s Request: %s' % (
            getattr(self.handle_event, '__name__', None),
            self.remote_addr, self.remote_port,
            force_unicode(getattr(self, 'request_line', 'WebSocketConnection'), 'utf-8'))

    def parse_header_line(self, parser, buf, event):
        line = self.readline(buf)
        if line is None:
            return
        try:
            parser(line)
        except ValueError:
            self.simple_response(httplib.BAD_REQUEST, 'Failed to parse header line')
            return
        if parser.finished:
            self.finalize_headers(parser.hdict)

    def finalize_headers(self, inheaders):
        request_content_length = int(inheaders.get('Content-Length', 0))
        if request_content_length > self.max_request_body_size:
            return self.simple_response(httplib.REQUEST_ENTITY_TOO_LARGE,
                "The entity sent with the request exceeds the maximum "
                "allowed bytes (%d)." % self.max_request_body_size)
        # Persistent connection support
        if self.response_protocol is HTTP11:
            # Both server and client are HTTP/1.1
            if inheaders.get("Connection", "") == "close":
                self.close_after_response = True
        else:
            # Either the server or client (or both) are HTTP/1.0
            if inheaders.get("Connection", "") != "Keep-Alive":
                self.close_after_response = True

        # Transfer-Encoding support
        te = ()
        if self.response_protocol is HTTP11:
            rte = inheaders.get("Transfer-Encoding")
            if rte:
                te = [x.strip().lower() for x in rte.split(",") if x.strip()]
        chunked_read = False
        if te:
            for enc in te:
                if enc == "chunked":
                    chunked_read = True
                else:
                    # Note that, even if we see "chunked", we must reject
                    # if there is an extension we don't recognize.
                    return self.simple_response(httplib.NOT_IMPLEMENTED, "Unknown transfer encoding: %r" % enc)

        if inheaders.get("Expect", '').lower() == "100-continue":
            buf = BytesIO((HTTP11 + " 100 Continue\r\n\r\n").encode('ascii'))
            return self.set_state(WRITE, self.write_continue, buf, inheaders, request_content_length, chunked_read)

        self.read_request_body(inheaders, request_content_length, chunked_read)

    def write_continue(self, buf, inheaders, request_content_length, chunked_read, event):
        if self.write(buf):
            self.read_request_body(inheaders, request_content_length, chunked_read)

    def read_request_body(self, inheaders, request_content_length, chunked_read):
        buf = SpooledTemporaryFile(prefix='rq-body-', max_size=DEFAULT_BUFFER_SIZE, dir=self.tdir)
        if chunked_read:
            self.set_state(READ, self.read_chunk_length, inheaders, Accumulator(), buf, [0])
        else:
            if request_content_length > 0:
                self.set_state(READ, self.sized_read, inheaders, buf, request_content_length)
            else:
                self.prepare_response(inheaders, BytesIO())

    def sized_read(self, inheaders, buf, request_content_length, event):
        if self.read(buf, request_content_length):
            self.prepare_response(inheaders, buf)

    def read_chunk_length(self, inheaders, line_buf, buf, bytes_read, event):
        line = self.readline(line_buf)
        if line is None:
            return
        bytes_read[0] += len(line)
        try:
            chunk_size = int(line.strip(), 16)
        except Exception:
            return self.simple_response(httplib.BAD_REQUEST, '%s is not a valid chunk size' % reprlib.repr(line.strip()))
        if bytes_read[0] + chunk_size + 2 > self.max_request_body_size:
            return self.simple_response(httplib.REQUEST_ENTITY_TOO_LARGE,
                                        'Chunked request is larger than %d bytes' % self.max_request_body_size)
        if chunk_size == 0:
            self.set_state(READ, self.read_chunk_separator, inheaders, Accumulator(), buf, bytes_read, last=True)
        else:
            self.set_state(READ, self.read_chunk, inheaders, buf, chunk_size, buf.tell() + chunk_size, bytes_read)

    def read_chunk(self, inheaders, buf, chunk_size, end, bytes_read, event):
        if not self.read(buf, end):
            return
        bytes_read[0] += chunk_size
        self.set_state(READ, self.read_chunk_separator, inheaders, Accumulator(), buf, bytes_read)

    def read_chunk_separator(self, inheaders, line_buf, buf, bytes_read, event, last=False):
        line = self.readline(line_buf)
        if line is None:
            return
        if line != b'\r\n':
            return self.simple_response(httplib.BAD_REQUEST, 'Chunk does not have trailing CRLF')
        bytes_read[0] += len(line)
        if bytes_read[0] > self.max_request_body_size:
            return self.simple_response(httplib.REQUEST_ENTITY_TOO_LARGE,
                                        'Chunked request is larger than %d bytes' % self.max_request_body_size)
        if last:
            self.prepare_response(inheaders, buf)
        else:
            self.set_state(READ, self.read_chunk_length, inheaders, Accumulator(), buf, bytes_read)

    def handle_timeout(self):
        if self.response_started:
            return False
        self.simple_response(httplib.REQUEST_TIMEOUT)
        return True

    def write(self, buf, end=None):
        raise NotImplementedError()

    def simple_response(self, status_code, msg='', close_after_response=True):
        raise NotImplementedError()

    def prepare_response(self, inheaders, request_body_file):
        raise NotImplementedError()
