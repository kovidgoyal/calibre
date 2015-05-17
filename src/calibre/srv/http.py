#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, socket

from calibre.srv.errors import MaxSizeExceeded, NonHTTPConnRequest

HTTP1  = 'HTTP/1.0'
HTTP11 = 'HTTP/1.1'

def http_communicate(conn):
    request_seen = False
    try:
        while True:
            # (re)set req to None so that if something goes wrong in
            # the RequestHandlerClass constructor, the error doesn't
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
        self.scheme = b'http' if self.server_loop.ssl_context is None else b'https'
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
