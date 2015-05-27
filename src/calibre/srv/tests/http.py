#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, hashlib, zlib, string, time
from io import BytesIO
from tempfile import NamedTemporaryFile

from calibre import guess_type
from calibre.srv.tests.base import BaseTest, TestServer
from calibre.utils.monotonic import monotonic

class TestHTTP(BaseTest):

    def test_header_parsing(self):  # {{{
        'Test parsing of HTTP headers'
        from calibre.srv.http_request import HTTPHeaderParser

        def test(name, *lines, **kwargs):
            p = HTTPHeaderParser()
            p.push(*lines)
            self.assertTrue(p.finished)
            self.assertSetEqual(set(p.hdict.items()), {(k.replace('_', '-').title(), v) for k, v in kwargs.iteritems()}, name + ' failed')

        test('Continuation line parsing',
             'a: one',
             'b: two',
             ' 2',
             '\t3',
             'c:three',
             '\r\n', a='one', b='two 2 3', c='three')

        test('Non-ascii headers parsing',
             b'a:mūs\r', '\r\n', a='mūs'.encode('utf-8'))

        test('Comma-separated parsing',
             'Accept-Encoding: one',
             'accept-Encoding: two',
             '\r\n', accept_encoding='one, two')

        def parse(line):
            HTTPHeaderParser()(line)

        with self.assertRaises(ValueError):
            parse('Connection:mūs\r\n')
            parse('Connection\r\n')
            parse('Connection:a\r\n')
            parse('Connection:a\n')
            parse(' Connection:a\n')
            parse(':a\n')
    # }}}

    def test_accept_encoding(self):  # {{{
        'Test parsing of Accept-Encoding'
        from calibre.srv.http_response import acceptable_encoding
        def test(name, val, ans, allowed={'gzip'}):
            self.ae(acceptable_encoding(val, allowed), ans, name + ' failed')
        test('Empty field', '', None)
        test('Simple', 'gzip', 'gzip')
        test('Case insensitive', 'GZIp', 'gzip')
        test('Multiple', 'gzip, identity', 'gzip')
        test('Priority', '1;q=0.5, 2;q=0.75, 3;q=1.0', '3', {'1', '2', '3'})
    # }}}

    def test_range_parsing(self):  # {{{
        'Test parsing of Range header'
        from calibre.srv.http_response import get_ranges
        def test(val, *args):
            pval = get_ranges(val, 100)
            if len(args) == 1 and args[0] is None:
                self.assertIsNone(pval, val)
            else:
                self.assertListEqual([tuple(x) for x in pval], list(args), val)
        test('crap', None)
        test('crap=', None)
        test('crap=1', None)
        test('crap=1-2', None)
        test('bytes=a-2')
        test('bytes=0-99', (0, 99, 100))
        test('bytes=0-0,-1', (0, 0, 1), (99, 99, 1))
        test('bytes=-5', (95, 99, 5))
        test('bytes=95-', (95, 99, 5))
        test('bytes=-200', (0, 99, 100))
    # }}}

    def test_http_basic(self):  # {{{
        'Test basic HTTP protocol conformance'
        from calibre.srv.errors import HTTP404
        body = 'Requested resource not found'
        def handler(data):
            raise HTTP404(body)
        def raw_send(conn, raw):
            conn.send(raw)
            conn._HTTPConnection__state = httplib._CS_REQ_SENT
            return conn.getresponse()

        with TestServer(handler, timeout=0.1, max_header_line_size=100./1024, max_request_body_size=100./(1024*1024)) as server:
            conn = server.connect()
            r = raw_send(conn, b'hello\n')
            self.ae(r.status, httplib.BAD_REQUEST)
            self.ae(r.read(), b'HTTP requires CRLF line terminators')

            r = raw_send(conn, b'\r\nGET /index.html HTTP/1.1\r\n\r\n')
            self.ae(r.status, httplib.NOT_FOUND), self.ae(r.read(), b'Requested resource not found')

            r = raw_send(conn, b'\r\n\r\nGET /index.html HTTP/1.1\r\n\r\n')
            self.ae(r.status, httplib.BAD_REQUEST)
            self.ae(r.read(), b'Multiple leading empty lines not allowed')

            r = raw_send(conn, b'hello world\r\n')
            self.ae(r.status, httplib.BAD_REQUEST)
            self.ae(r.read(), b'Malformed Request-Line')

            r = raw_send(conn, b'x' * 200)
            self.ae(r.status, httplib.BAD_REQUEST)
            self.ae(r.read(), b'')

            r = raw_send(conn, b'XXX /index.html HTTP/1.1\r\n\r\n')
            self.ae(r.status, httplib.BAD_REQUEST), self.ae(r.read(), b'Unknown HTTP method')

            # Test 404
            conn.request('HEAD', '/moose')
            r = conn.getresponse()
            self.ae(r.status, httplib.NOT_FOUND)
            self.assertIsNotNone(r.getheader('Date', None))
            self.ae(r.getheader('Content-Length'), str(len(body)))
            self.ae(r.getheader('Content-Type'), 'text/plain; charset=UTF-8')
            self.ae(len(r.getheaders()), 3)
            self.ae(r.read(), '')
            conn.request('GET', '/choose')
            r = conn.getresponse()
            self.ae(r.status, httplib.NOT_FOUND)
            self.ae(r.read(), b'Requested resource not found')

            # Test 500
            orig = server.loop.log.filter_level
            server.loop.log.filter_level = server.loop.log.ERROR + 10
            server.change_handler(lambda data:1/0)
            conn = server.connect()
            conn.request('GET', '/test/')
            r = conn.getresponse()
            self.ae(r.status, httplib.INTERNAL_SERVER_ERROR)
            server.loop.log.filter_level = orig

            server.change_handler(lambda data:data.path[0] + data.read().decode('ascii'))
            conn = server.connect()

            # Test simple GET
            conn.request('GET', '/test/')
            r = conn.getresponse()
            self.ae(r.status, httplib.OK)
            self.ae(r.read(), b'test')

            # Test TRACE
            lines = ['TRACE /xxx HTTP/1.1', 'Test: value', 'Xyz: abc, def', '', '']
            r = raw_send(conn, ('\r\n'.join(lines)).encode('ascii'))
            self.ae(r.status, httplib.OK)
            self.ae(r.read().decode('utf-8'), '\n'.join(lines[:-2]))

            # Test POST with simple body
            conn.request('POST', '/test', 'body')
            r = conn.getresponse()
            self.ae(r.status, httplib.CREATED)
            self.ae(r.read(), b'testbody')

            # Test POST with chunked transfer encoding
            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'4\r\nbody\r\na\r\n1234567890\r\n0\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.CREATED)
            self.ae(r.read(), b'testbody1234567890')

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

            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'4\r\nbody\r\n200\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.REQUEST_ENTITY_TOO_LARGE)
            conn.request('POST', '/test', body='a'*200)
            r = conn.getresponse()
            self.ae(r.status, httplib.REQUEST_ENTITY_TOO_LARGE)

            conn = server.connect()
            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'3\r\nbody\r\n0\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.BAD_REQUEST), self.ae(r.read(), b'Chunk does not have trailing CRLF')

            conn = server.connect(timeout=1)
            conn.request('POST', '/test', headers={'Transfer-Encoding': 'chunked'})
            conn.send(b'30\r\nbody\r\n0\r\n\r\n')
            r = conn.getresponse()
            self.ae(r.status, httplib.REQUEST_TIMEOUT)
            self.assertIn(b'', r.read())

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
            r = conn.getresponse()
            self.ae(server.loop.num_active_connections, 1)
            self.ae(r.status, 200), self.ae(r.read(), 'close')
            server.loop.wakeup()
            num = 10
            while num and server.loop.num_active_connections != 0:
                time.sleep(0.01)
                num -= 1
            self.ae(server.loop.num_active_connections, 0)
            self.assertIsNone(conn.sock)
    # }}}

    def test_http_response(self):  # {{{
        'Test HTTP protocol responses'
        from calibre.srv.http_response import parse_multipart_byterange
        def handler(conn):
            return conn.generate_static_output('test', lambda : ''.join(conn.path))
        with NamedTemporaryFile(suffix='test.epub') as f, open(P('localization/locales.zip'), 'rb') as lf, \
                TestServer(handler, timeout=0.2, compress_min_size=0) as server:
            fdata = string.ascii_letters * 100
            f.write(fdata), f.seek(0)

            # Test ETag
            conn = server.connect()
            conn.request('GET', '/an_etagged_path')
            r = conn.getresponse()
            self.ae(r.status, httplib.OK), self.ae(r.read(), b'an_etagged_path')
            etag = r.getheader('ETag')
            self.ae(etag, '"%s"' % hashlib.sha1('an_etagged_path').hexdigest())
            conn.request('GET', '/an_etagged_path', headers={'If-None-Match':etag})
            r = conn.getresponse()
            self.ae(r.status, httplib.NOT_MODIFIED)
            self.ae(r.read(), b'')

            # Test gzip
            conn.request('GET', '/an_etagged_path', headers={'Accept-Encoding':'gzip'})
            r = conn.getresponse()
            self.ae(r.status, httplib.OK), self.ae(zlib.decompress(r.read(), 16+zlib.MAX_WBITS), b'an_etagged_path')

            # Test getting a filesystem file
            for use_sendfile in (True, False):
                server.change_handler(lambda conn: f)
                server.loop.opts.use_sendfile = use_sendfile
                conn = server.connect()
                conn.request('GET', '/test')
                r = conn.getresponse()
                etag = type('')(r.getheader('ETag'))
                self.assertTrue(etag)
                self.ae(r.getheader('Content-Type'), guess_type(f.name)[0])
                self.ae(type('')(r.getheader('Accept-Ranges')), 'bytes')
                self.ae(int(r.getheader('Content-Length')), len(fdata))
                self.ae(r.status, httplib.OK), self.ae(r.read(), fdata)

                conn.request('GET', '/test', headers={'Range':'bytes=2-25'})
                r = conn.getresponse()
                self.ae(r.status, httplib.PARTIAL_CONTENT)
                self.ae(type('')(r.getheader('Accept-Ranges')), 'bytes')
                self.ae(type('')(r.getheader('Content-Range')), 'bytes 2-25/%d' % len(fdata))
                self.ae(int(r.getheader('Content-Length')), 24)
                self.ae(r.read(), fdata[2:26])

                conn.request('GET', '/test', headers={'Range':'bytes=100000-'})
                r = conn.getresponse()
                self.ae(r.status, httplib.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.ae(type('')(r.getheader('Content-Range')), 'bytes */%d' % len(fdata))

                conn.request('GET', '/test', headers={'Range':'bytes=25-50', 'If-Range':etag})
                r = conn.getresponse()
                self.ae(r.status, httplib.PARTIAL_CONTENT), self.ae(r.read(), fdata[25:51])
                self.ae(int(r.getheader('Content-Length')), 26)

                conn.request('GET', '/test', headers={'Range':'bytes=0-1000000'})
                r = conn.getresponse()
                self.ae(r.status, httplib.PARTIAL_CONTENT), self.ae(r.read(), fdata)

                conn.request('GET', '/test', headers={'Range':'bytes=25-50', 'If-Range':'"nomatch"'})
                r = conn.getresponse()
                self.ae(r.status, httplib.OK), self.ae(r.read(), fdata)
                self.assertFalse(r.getheader('Content-Range'))
                self.ae(int(r.getheader('Content-Length')), len(fdata))

                conn.request('GET', '/test', headers={'Range':'bytes=0-25,26-50'})
                r = conn.getresponse()
                self.ae(r.status, httplib.PARTIAL_CONTENT)
                clen = int(r.getheader('Content-Length'))
                data = r.read()
                self.ae(clen, len(data))
                buf = BytesIO(data)
                self.ae(parse_multipart_byterange(buf, r.getheader('Content-Type')), [(0, fdata[:26]), (26, fdata[26:51])])

                # Test sending of larger file
                start_time = monotonic()
                lf.seek(0)
                data =  lf.read()
                server.change_handler(lambda conn: lf)
                conn = server.connect()
                conn.request('GET', '/test')
                r = conn.getresponse()
                self.ae(r.status, httplib.OK)
                rdata = r.read()
                self.ae(len(data), len(rdata))
                self.ae(hashlib.sha1(data).hexdigest(), hashlib.sha1(rdata).hexdigest())
                self.ae(data, rdata)
                time_taken = monotonic() - start_time
                self.assertLess(time_taken, 1, 'Large file transfer took too long')

    # }}}
