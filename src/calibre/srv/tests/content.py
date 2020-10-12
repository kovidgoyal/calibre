#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import zlib, json, time, os
from io import BytesIO

from calibre.ebooks.metadata.epub import get_metadata
from calibre.ebooks.metadata.opf2 import OPF
from calibre.srv.tests.base import LibraryBaseTest
from calibre.utils.imghdr import identify
from calibre.utils.shared_file import share_open
from polyglot import http_client
from polyglot.binary import from_hex_unicode


def setUpModule():
    # Needed for cover generation
    from calibre.gui2 import ensure_app, load_builtin_fonts
    ensure_app(), load_builtin_fonts()


class ContentTest(LibraryBaseTest):

    def test_static(self):  # {{{
        'Test serving of static content'
        with self.create_server() as server:
            conn = server.connect()

            def missing(url, body=b''):
                conn.request('GET', url)
                r = conn.getresponse()
                self.ae(r.status, http_client.NOT_FOUND)
                self.ae(r.read(), body)

            for prefix in ('static', 'icon'):
                missing('/%s/missing.xxx' % prefix)
                missing('/%s/../out.html' % prefix, b'Naughty, naughty!')
                missing('/%s/C:/out.html' % prefix, b'Naughty, naughty!')

            def test_response(r):
                self.assertIn('max-age=', r.getheader('Cache-Control'))
                self.assertIn('public', r.getheader('Cache-Control'))
                self.assertIsNotNone(r.getheader('Expires'))
                self.assertIsNotNone(r.getheader('ETag'))
                self.assertIsNotNone(r.getheader('Content-Type'))

            def test(src, url, sz=None):
                raw = P(src, data=True)
                conn.request('GET', url)
                r = conn.getresponse()
                self.ae(r.status, http_client.OK)
                data = r.read()
                if sz is None:
                    self.ae(data, raw)
                else:
                    self.ae(sz, identify(data)[1])
                test_response(r)
                conn.request('GET', url, headers={'If-None-Match':r.getheader('ETag')})
                r = conn.getresponse()
                self.ae(r.status, http_client.NOT_MODIFIED)
                self.ae(b'', r.read())

            test('content-server/empty.html', '/static/empty.html')
            test('images/lt.png', '/favicon.png')
            test('images/lt.png', '/icon/lt.png?sz=full')
            test('images/lt.png', '/icon/lt.png', sz=48)
            test('images/lt.png', '/icon/lt.png?sz=16', sz=16)
    # }}}

    def test_get(self):  # {{{
        'Test /get'
        with self.create_server() as server:
            db = server.handler.router.ctx.library_broker.get(None)
            conn = server.connect()

            def get(what, book_id, library_id=None, q=''):
                q = ('?' + q) if q else q
                conn.request('GET', '/get/%s/%s' % (what, book_id) + (('/' + library_id) if library_id else '') + q)
                r = conn.getresponse()
                return r, r.read()

            # Test various invalid parameters
            def bad(*args):
                r, data = get(*args)
                self.ae(r.status, http_client.NOT_FOUND)
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
            self.ae(r.status, http_client.OK)
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
            def change_cover(count, book_id=2):
                cpath = db.format_abspath(book_id, '__COVER_INTERNAL__')
                db.set_cover({2:I('lt.png', data=True)})
                t = time.time() + 1 + count
                # Ensure mtime changes, needed on OS X where HFS+ has a 1s
                # mtime resolution
                os.utime(cpath, (t, t))

            r, data = get('cover', 1)
            self.ae(r.status, http_client.OK)
            self.ae(data, db.cover(1))
            self.ae(r.getheader('Used-Cache'), 'no')
            self.ae(r.getheader('Content-Type'), 'image/jpeg')
            r, data = get('cover', 1)
            self.ae(r.status, http_client.OK)
            self.ae(data, db.cover(1))
            self.ae(r.getheader('Used-Cache'), 'yes')
            r, data = get('cover', 3)
            self.ae(r.status, http_client.OK)  # Auto generated cover
            r, data = get('thumb', 1)
            self.ae(r.status, http_client.OK)
            self.ae(identify(data), ('jpeg', 60, 60))
            self.ae(r.getheader('Used-Cache'), 'no')
            r, data = get('thumb', 1)
            self.ae(r.status, http_client.OK)
            self.ae(r.getheader('Used-Cache'), 'yes')
            r, data = get('thumb', 1, q='sz=100')
            self.ae(r.status, http_client.OK)
            self.ae(identify(data), ('jpeg', 100, 100))
            self.ae(r.getheader('Used-Cache'), 'no')
            r, data = get('thumb', 1, q='sz=100x100')
            self.ae(r.status, http_client.OK)
            self.ae(r.getheader('Used-Cache'), 'yes')
            change_cover(1, 1)
            r, data = get('thumb', 1, q='sz=100')
            self.ae(r.status, http_client.OK)
            self.ae(identify(data), ('jpeg', 100, 100))
            self.ae(r.getheader('Used-Cache'), 'no')

            # Test file sharing in cache
            r, data = get('cover', 2)
            self.ae(r.status, http_client.OK)
            self.ae(data, db.cover(2))
            self.ae(r.getheader('Used-Cache'), 'no')
            path = from_hex_unicode(r.getheader('Tempfile'))
            f, fdata = share_open(path, 'rb'), data
            # Now force an update
            change_cover(1)
            r, data = get('cover', 2)
            self.ae(r.status, http_client.OK)
            self.ae(data, db.cover(2))
            self.ae(r.getheader('Used-Cache'), 'no')
            path = from_hex_unicode(r.getheader('Tempfile'))
            f2, f2data = share_open(path, 'rb'), data
            # Do it again
            change_cover(2)
            r, data = get('cover', 2)
            self.ae(r.status, http_client.OK)
            self.ae(data, db.cover(2))
            self.ae(r.getheader('Used-Cache'), 'no')
            self.ae(f.read(), fdata)
            self.ae(f2.read(), f2data)

            # Test serving of metadata as opf
            r, data = get('opf', 1)
            self.ae(r.status, http_client.OK)
            self.ae(r.getheader('Content-Type'), 'application/oebps-package+xml; charset=UTF-8')
            self.assertIsNotNone(r.getheader('Last-Modified'))
            opf = OPF(BytesIO(data), populate_spine=False, try_to_guess_cover=False)
            self.ae(db.field_for('title', 1), opf.title)
            self.ae(db.field_for('authors', 1), tuple(opf.authors))
            conn.request('GET', '/get/opf/1', headers={'Accept-Encoding':'gzip'})
            r = conn.getresponse()
            self.ae(r.status, http_client.OK), self.ae(r.getheader('Content-Encoding'), 'gzip')
            raw = r.read()
            self.ae(zlib.decompress(raw, 16+zlib.MAX_WBITS), data)

            # Test serving metadata as json
            r, data = get('json', 1)
            self.ae(r.status, http_client.OK)
            self.ae(db.field_for('title', 1), json.loads(data)['title'])
            conn.request('GET', '/get/json/1', headers={'Accept-Encoding':'gzip'})
            r = conn.getresponse()
            self.ae(r.status, http_client.OK), self.ae(r.getheader('Content-Encoding'), 'gzip')
            raw = r.read()
            self.ae(zlib.decompress(raw, 16+zlib.MAX_WBITS), data)

    # }}}

    def test_char_count(self):  # {{{
        from calibre.srv.render_book import get_length
        from calibre.ebooks.oeb.parse_utils import html5_parse

        root = html5_parse('<p>a b\nc\td\re')
        self.ae(get_length(root), 5)
        root = html5_parse('<script>xyz</script>a<iMg>b')
        self.ae(get_length(root), 1002)
        root = html5_parse('<p><!-- abc -->m')
        self.ae(get_length(root), 1)
    # }}}

    def test_html_as_json(self):  # {{{
        from calibre.srv.render_book import html_as_json
        from calibre.ebooks.oeb.parse_utils import html5_parse

        def t(html, body_children, nsmap=('http://www.w3.org/1999/xhtml',)):
            root = html5_parse(html)
            raw = html_as_json(root)
            # print(raw.decode('utf-8'))
            data = json.loads(raw)
            self.ae(data['version'], 1)
            self.ae(tuple(data['ns_map']), nsmap)
            bc = data['tree']['c'][1]['c']
            self.ae(bc, body_children)

        t('<p>a<!--c-->t</p>l', [{"n":"p","x":"a","l":"l","c":[{"s":"c","x":"c","l":"t"}]}])
        t('<p class="foo" id="bar">a', [{"n":"p","x":"a","a":[['class','foo'],['id','bar']]}])
        t(
            '<svg xlink:href="h"></svg>', [{'n': 'svg', 's': 1, 'a': [['href', 'h', 2]]}],
            ('http://www.w3.org/1999/xhtml', 'http://www.w3.org/2000/svg', 'http://www.w3.org/1999/xlink')
        )
        text = '🐈\n\t\\mūs"'
        t("<p id='{}'>Peña".format(text), [{"n":"p","x":"Peña","a":[['id',text]]}])
        text = 'a' * (127 * 1024)
        t('<p>{0}<p>{0}'.format(text), [{"n":"p","x":text}, {'n':'p','x':text}])
    # }}}
