#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, zlib, json, base64, os
from functools import partial
from urllib import urlencode
from httplib import OK, NOT_FOUND

from calibre.srv.tests.base import LibraryBaseTest


def make_request(conn, url, headers={}, prefix='/ajax', username=None, password=None):
    if username and password:
        headers[b'Authorization'] = b'Basic ' + base64.standard_b64encode((username + ':' + password).encode('utf-8'))
    conn.request('GET', prefix + url, headers=headers)
    r = conn.getresponse()
    data = r.read()
    if r.status == httplib.OK and data and data[0] in b'{[':
        data = json.loads(data)
    return r, data


class ContentTest(LibraryBaseTest):

    def test_ajax_book(self):  # {{{
        'Test /ajax/book'
        with self.create_server() as server:
            db = server.handler.router.ctx.library_broker.get(None)
            conn = server.connect()
            request = partial(make_request, conn, prefix='/ajax/book')

            r, data = request('/x')
            self.ae(r.status, httplib.NOT_FOUND)

            r, onedata = request('/1')
            self.ae(r.status, httplib.OK)
            self.ae(request('/1/' + db.server_library_id)[1], onedata)
            self.ae(request('/%s?id_is_uuid=true' % db.field_for('uuid', 1))[1], onedata)

            r, data = request('s')
            self.ae(set(data.iterkeys()), set(map(str, db.all_book_ids())))
            r, zdata = request('s', headers={'Accept-Encoding':'gzip'})
            self.ae(r.getheader('Content-Encoding'), 'gzip')
            self.ae(json.loads(zlib.decompress(zdata, 16+zlib.MAX_WBITS)), data)
            r, data = request('s?ids=1,2')
            self.ae(set(data.iterkeys()), {'1', '2'})

    # }}}

    def test_ajax_categories(self):  # {{{
        'Test /ajax/categories and /ajax/search'
        with self.create_server() as server:
            db = server.handler.router.ctx.library_broker.get(None)
            db.set_pref('virtual_libraries', {'1':'title:"=Title One"'})
            conn = server.connect()
            request = partial(make_request, conn)

            r, data = request('/categories')
            self.ae(r.status, httplib.OK)
            r, xdata = request('/categories/' + db.server_library_id)
            self.ae(r.status, httplib.OK)
            self.ae(data, xdata)
            names = {x['name']:x['url'] for x in data}
            for q in ('Newest', 'All books', 'Tags', 'Series', 'Authors', 'Enum', 'Composite Tags'):
                self.assertIn(q, names)
            r, data = request(names['Tags'], prefix='')
            self.ae(r.status, httplib.OK)
            names = {x['name']:x['url'] for x in data['items']}
            self.ae(set(names), set('Tag One,Tag Two,News'.split(',')))
            r, data = request(names['Tag One'], prefix='')
            self.ae(r.status, httplib.OK)
            self.ae(set(data['book_ids']), {1, 2})
            r, data = request('/search?' + urlencode({'query': 'tags:"=Tag One"'}))
            self.ae(r.status, httplib.OK)
            self.ae(set(data['book_ids']), {1, 2})
            r, data = request('/search?' + urlencode({'query': 'tags:"=Tag One"', 'vl':'1'}))
            self.ae(set(data['book_ids']), {2})
    # }}}

    def test_srv_restrictions(self):
        ' Test that virtual lib. + search restriction works on all end points'
        with self.create_server(auth=True, auth_mode='basic') as server:
            db = server.handler.router.ctx.library_broker.get(None)
            db.set_pref('virtual_libraries', {'1':'id:1', '12':'id:1 or id:2'})
            db.set_field('tags', {1: ['present'], 3: ['missing']})
            server.handler.ctx.user_manager.add_user('12', 'test', restriction={
                'library_restrictions':{os.path.basename(db.backend.library_path): 'id:1 or id:2'}})
            conn = server.connect()
            url_for = server.handler.router.url_for

            def r(path, status=OK):
                r, data = make_request(conn, path, username='12', password='test', prefix='')
                self.assertEqual(status, r.status)
                return data
            ok = r
            nf = partial(r, status=NOT_FOUND)

            ok(url_for('/ajax/book', book_id=1))
            nf(url_for('/ajax/book', book_id=3))
            data = ok(url_for('/ajax/books'))
            self.assertIsNone(data['3'])
            for i in '12':
                self.assertIsNotNone(data[i])
            self.assertEqual(set(r('/ajax/search')['book_ids']), {1,2})
            self.assertEqual(set(r('/ajax/search?query=id:2')['book_ids']), {2})
            self.assertEqual(set(r('/ajax/search?vl=1')['book_ids']), {1})

            nf(url_for('/book-manifest', book_id=3, fmt='x'))
            nf(url_for('/book-file', book_id=3, fmt='x', size=1, mtime=1, name='x'))
