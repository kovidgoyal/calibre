#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap
from io import BytesIO

from calibre.srv.tests.base import BaseTest

def headers(raw):
    return BytesIO(textwrap.dedent(raw).encode('utf-8'))

class TestHTTP(BaseTest):

    def test_header_parsing(self):
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

