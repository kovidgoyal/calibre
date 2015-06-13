#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib

from calibre.srv.tests.base import LibraryBaseTest

class ContentTest(LibraryBaseTest):

    def test_static(self):
        'Test serving of static content'
        with self.create_server() as server:
            conn = server.connect()

            def missing(url, body=b''):
                conn.request('GET', url)
                r = conn.getresponse()
                self.ae(r.status, httplib.NOT_FOUND)
                self.ae(r.read(), body)

            missing('/static/missing.xxx')
            missing('/static/../out.html', b'Naughty, naughty!')
            missing('/static/C:/out.html', b'Naughty, naughty!')

            def test_response(r):
                self.assertIn(b'max-age=', r.getheader('Cache-Control'))
                self.assertIn(b'public', r.getheader('Cache-Control'))
                self.assertIsNotNone(r.getheader('Expires'))
                self.assertIsNotNone(r.getheader('ETag'))
                self.assertIsNotNone(r.getheader('Content-Type'))

            def test(src, url):
                raw = P(src, data=True)
                conn.request('GET', url)
                r = conn.getresponse()
                self.ae(r.status, httplib.OK)
                self.ae(r.read(), raw)
                test_response(r)
                conn.request('GET', url, headers={'If-None-Match':r.getheader('ETag')})
                r = conn.getresponse()
                self.ae(r.status, httplib.NOT_MODIFIED)
                self.ae(b'', r.read())

            test('content-server/empty.html', '/static/empty.html')
            test('images/lt.png', '/favicon.png')
