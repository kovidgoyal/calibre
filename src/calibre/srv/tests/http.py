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
        with TestServer(handler, timeout=0.1, max_header_line_size=100./1024, max_request_body_size=100./(1024*1024)) as server:
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

            server.change_handler(lambda conn:conn.path[0] + conn.input_reader.read().decode('ascii'))
            conn = server.connect()

            # Test simple GET
            conn.request('GET', '/test/')
            r = conn.getresponse()
            self.ae(r.status, httplib.OK)
            self.ae(r.read(), 'test')

            # Test POST with simple body
            conn.request('POST', '/test', 'body')
            r = conn.getresponse()
            self.ae(r.status, httplib.CREATED)
            self.ae(r.read(), 'testbody')

            # Test POST with chunked transfer encoding
            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'4\r\nbody\r\n0\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.CREATED)
            self.ae(r.read(), 'testbody')

            # Test various incorrect input
            orig_level, server.log.filter_level = server.log.filter_level, server.log.ERROR

            conn.request('GET', '/test' + ('a' * 200))
            r = conn.getresponse()
            self.ae(r.status, httplib.BAD_REQUEST)

            conn = server.connect()
            conn.request('GET', '/test', ('a' * 200))
            r = conn.getresponse()
            self.ae(r.status, httplib.REQUEST_ENTITY_TOO_LARGE)

            conn = server.connect()
            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'x\r\nbody\r\n0\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.BAD_REQUEST)
            self.assertIn(b'not a valid chunk size', r.read())

            conn = server.connect()
            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'3\r\nbody\r\n0\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.BAD_REQUEST)
            self.assertIn(b'!= CRLF', r.read())

            conn = server.connect(timeout=1)
            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'30\r\nbody\r\n0\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.BAD_REQUEST)
            self.assertIn(b'Timed out waiting for chunk', r.read())

            server.log.filter_level = orig_level
            conn = server.connect()
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

            # Test closing
            conn.request('GET', '/close', headers={'Connection':'close'})
            self.ae(server.loop.requests.busy, 1)
            r = conn.getresponse()
            self.ae(r.status, 200), self.ae(r.read(), 'close')
            self.ae(server.loop.requests.busy, 0)
            self.assertIsNone(conn.sock)
            self.ae(server.loop.requests.idle, 10)

    # }}}
