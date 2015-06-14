#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, zlib
from io import BytesIO

from calibre.ebooks.metadata.epub import get_metadata
from calibre.ebooks.metadata.opf2 import OPF
from calibre.srv.tests.base import LibraryBaseTest
from calibre.utils.magick.draw import identify_data

class ContentTest(LibraryBaseTest):

    def test_static(self):  # {{{
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
    # }}}

    def test_get(self):  # {{{
        'Test /get'
        with self.create_server() as server:
            db = server.handler.router.ctx.get_library()
            conn = server.connect()

            def get(what, book_id, library_id=None):
                conn.request('GET', '/get/%s/%s' % (what, book_id) + (('/' + library_id) if library_id else ''))
                r = conn.getresponse()
                return r, r.read()

            # Test various invalid parameters
            def bad(*args):
                r, data = get(*args)
                self.ae(r.status, httplib.NOT_FOUND)
            bad('xxx', 1)
            bad('fmt1', 10)
            bad('fmt1', 1, 'zzzz')
            bad('fmt1', 'xx')

            # Test simple fetching of format without metadata update
            r, data = get('fmt1', 1, db.server_library_id)
            self.ae(data, db.format(1, 'fmt1'))
            self.assertIsNotNone(r.getheader('Content-Disposition'))
            self.ae(r.getheader('Used-Cache'), 'no')
            r, data = get('fmt1', 1)
            self.ae(data, db.format(1, 'fmt1'))
            self.ae(r.getheader('Used-Cache'), 'yes')

            # Test fetching of format with metadata update
            raw = P('quick_start/eng.epub', data=True)
            r, data = get('epub', 1)
            self.ae(r.status, httplib.OK)
            etag = r.getheader('ETag')
            self.assertIsNotNone(etag)
            self.ae(r.getheader('Used-Cache'), 'no')
            self.assertTrue(data.startswith(b'PK'))
            self.assertGreaterEqual(len(data), len(raw))
            db.set_field('title', {1:'changed'})
            r, data = get('epub', 1)
            self.assertNotEqual(r.getheader('ETag'), etag)
            etag = r.getheader('ETag')
            self.ae(r.getheader('Used-Cache'), 'no')
            mi = get_metadata(BytesIO(data), extract_cover=False)
            self.ae(mi.title, 'changed')
            r, data = get('epub', 1)
            self.ae(r.getheader('Used-Cache'), 'yes')

            # Test plugboards
            import calibre.library.save_to_disk as c
            orig, c.DEBUG = c.DEBUG, False
            try:
                db.set_pref('plugboards', {u'epub': {u'content_server': [[u'changed, {title}', u'title']]}})
                # this is needed as the cache is not invalidated for plugboard changes
                db.set_field('title', {1:'again'})
                r, data = get('epub', 1)
                self.assertNotEqual(r.getheader('ETag'), etag)
                etag = r.getheader('ETag')
                self.ae(r.getheader('Used-Cache'), 'no')
                mi = get_metadata(BytesIO(data), extract_cover=False)
                self.ae(mi.title, 'changed, again')
            finally:
                c.DEBUG = orig

            # Test the serving of covers
            r, data = get('cover', 1)
            self.ae(r.status, httplib.OK)
            self.ae(data, db.cover(1))
            self.ae(r.getheader('Used-Cache'), 'no')
            self.ae(r.getheader('Content-Type'), 'image/jpeg')
            r, data = get('cover', 1)
            self.ae(r.status, httplib.OK)
            self.ae(data, db.cover(1))
            self.ae(r.getheader('Used-Cache'), 'yes')
            r, data = get('cover', 3)
            self.ae(r.status, httplib.NOT_FOUND)
            r, data = get('thumb', 1)
            self.ae(r.status, httplib.OK)
            self.ae(identify_data(data), (60, 60, 'jpeg'))
            self.ae(r.getheader('Used-Cache'), 'no')
            r, data = get('thumb', 1)
            self.ae(r.status, httplib.OK)
            self.ae(r.getheader('Used-Cache'), 'yes')
            r, data = get('thumb_100x100', 1)
            self.ae(r.status, httplib.OK)
            self.ae(identify_data(data), (100, 100, 'jpeg'))
            self.ae(r.getheader('Used-Cache'), 'no')
            r, data = get('thumb_100x100', 1)
            self.ae(r.status, httplib.OK)
            self.ae(r.getheader('Used-Cache'), 'yes')
            db.set_cover({1:I('lt.png', data=True)})
            r, data = get('thumb_100x100', 1)
            self.ae(r.status, httplib.OK)
            self.ae(identify_data(data), (100, 100, 'jpeg'))
            self.ae(r.getheader('Used-Cache'), 'no')

            # Test serving of metadata as opf
            r, data = get('opf', 1)
            self.ae(r.status, httplib.OK)
            self.ae(r.getheader('Content-Type'), 'application/oebps-package+xml; charset=UTF-8')
            self.assertIsNotNone(r.getheader('Last-Modified'))
            opf = OPF(BytesIO(data), populate_spine=False, try_to_guess_cover=False)
            self.ae(db.field_for('title', 1), opf.title)
            self.ae(db.field_for('authors', 1), tuple(opf.authors))
            conn.request('GET', '/get/opf/1', headers={'Accept-Encoding':'gzip'})
            r = conn.getresponse()
            self.ae(r.status, httplib.OK), self.ae(r.getheader('Content-Encoding'), 'gzip')
            raw = r.read()
            self.ae(zlib.decompress(raw, 16+zlib.MAX_WBITS), data)

    # }}}
