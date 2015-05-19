#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap, httplib
from io import BytesIO

from calibre.srv.tests.base import BaseTest, TestServer

def headers(raw):
    return BytesIO(textwrap.dedent(raw).encode('utf-8'))

class TestHTTP(BaseTest):

    def test_header_parsing(self):  # {{{
        'Test parsing of HTTP headers'
        from calibre.srv.http import read_headers

        def test(name, raw, **kwargs):
            hdict = read_headers(headers(raw).readline)
            self.assertSetEqual(set(hdict.items()), {(k.replace('_', '-').title(), v) for k, v in kwargs.iteritems()}, name + ' failed')

        test('Continuation line parsing',
            '''\
             a: one\r
             b: two\r
              2\r
             \t3\r
             c:three\r
             \r\n''', a='one', b='two 2 3', c='three')

        test('Non-ascii headers parsing',
             '''\
             a:mūs\r
             \r\n''', a='mūs'.encode('utf-8'))

        with self.assertRaises(ValueError):
            read_headers(headers('Connection:mūs\r\n').readline)
            read_headers(headers('Connection\r\n').readline)
            read_headers(headers('Connection:a\r\n').readline)
            read_headers(headers('Connection:a\n').readline)
            read_headers(headers(' Connection:a\n').readline)
    # }}}

    def test_accept_encoding(self):  # {{{
        'Test parsing of Accept-Encoding'
        from calibre.srv.http import acceptable_encoding
        def test(name, val, ans, allowed={'gzip'}):
            self.ae(acceptable_encoding(val, allowed), ans, name + ' failed')
        test('Empty field', '', None)
        test('Simple', 'gzip', 'gzip')
        test('Case insensitive', 'GZIp', 'gzip')
        test('Multiple', 'gzip, identity', 'gzip')
        test('Priority', '1;q=0.5, 2;q=0.75, 3;q=1.0', '3', {'1', '2', '3'})
        # }}}

    def test_http_basic(self):  # {{{
        'Test basic HTTP protocol conformance'
        from calibre.srv.errors import HTTP404
        body = 'Requested resource not found'
        def handler(conn):
            raise HTTP404(body)
        with TestServer(handler) as server:
            # Test 404
            conn = server.connect()
            conn.request('HEAD', '/moose')
            r = conn.getresponse()
            self.ae(r.status, httplib.NOT_FOUND)
            self.assertIsNotNone(r.getheader('Date', None))
            self.ae(r.getheader('Content-Length'), str(len(body)))
            self.ae(r.getheader('Content-Type'), 'text/plain; charset=UTF-8')
            self.ae(len(r.getheaders()), 3)
            self.ae(r.read(), '')
            conn.request('GET', '/moose')
            r = conn.getresponse()
            self.ae(r.status, httplib.NOT_FOUND)
            self.ae(r.read(), 'Requested resource not found')

            server.change_handler(lambda conn:conn.path[1])
            # Test simple GET
            conn.request('GET', '/test')
            self.ae(conn.getresponse().read(), 'test')

            # Test pipelining
            responses = []
            for i in xrange(10):
                conn._HTTPConnection__state = httplib._CS_IDLE
                conn.request('GET', '/%d'%i)
                responses.append(conn.response_class(conn.sock, strict=conn.strict, method=conn._method))
            for i in xrange(10):
                r = responses[i]
                r.begin()
                self.ae(r.read(), ('%d' % i).encode('ascii'))
            conn._HTTPConnection__state = httplib._CS_IDLE

    # }}}
