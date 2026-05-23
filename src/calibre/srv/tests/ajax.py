#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import json
import os
from base64 import standard_b64encode
from compression import zlib
from functools import partial
from http.client import FORBIDDEN, NOT_FOUND, OK
from io import BytesIO
from urllib.parse import quote, urlencode

from calibre.ebooks.metadata.meta import get_metadata
from calibre.srv.tests.base import LibraryBaseTest
from calibre.utils.localization import _
from polyglot.binary import as_base64_bytes


def make_request(conn, url, headers={}, prefix='/ajax', username=None, password=None, method='GET', data=None):
    if username and password:
        headers[b'Authorization'] = b'Basic ' + as_base64_bytes(username + ':' + password)
    conn.request(method, prefix + url, headers=headers, body=data)
    r = conn.getresponse()
    data = r.read()
    if r.status == OK and data and data[0] in b'{[':
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
            self.ae(r.status, NOT_FOUND)

            r, onedata = request('/1')
            self.ae(r.status, OK)
            self.ae(request('/1/' + db.server_library_id)[1], onedata)
            self.ae(request('/{}?id_is_uuid=true'.format(db.field_for('uuid', 1)))[1], onedata)

            r, data = request('s')
            self.ae(set(data), set(map(str, db.all_book_ids())))
            r, zdata = request('s', headers={'Accept-Encoding':'gzip'})
            self.ae(r.getheader('Content-Encoding'), 'gzip')
            self.ae(json.loads(zlib.decompress(zdata, 16+zlib.MAX_WBITS)), data)
            r, data = request('s?ids=1,2')
            self.ae(set(data), {'1', '2'})

    # }}}

    def test_move_duplicate_to_library(self):  # {{{
        'Test that ignored duplicates are not removed when moving to another library'
        target_library_path = self.mkdtemp()
        self.create_db(target_library_path)
        with self.create_server(libraries=(self.library_path, target_library_path), auth=True, auth_mode='basic') as server:
            server.handler.ctx.user_manager.add_user('12', 'test')
            ctx = server.handler.router.ctx
            library_map = ctx.library_broker.library_map
            target_library_id = next(
                library_id for library_id, name in library_map.items()
                if name == os.path.basename(target_library_path))
            source_db = ctx.library_broker.get(None)
            target_db = ctx.library_broker.get(target_library_id)
            target_book_ids = target_db.all_book_ids()
            self.assertTrue(source_db.has_id(1))
            conn = server.connect()
            r, data = make_request(
                conn, f'/cdb/copy-to-library/{target_library_id}/{source_db.server_library_id}',
                username='12', password='test',
                prefix='', method='POST', headers={'Content-Type': 'application/json'}, data=json.dumps({
                    'book_ids': [1], 'move': True, 'duplicate_action': 'ignore', 'automerge_action': 'overwrite',
                }).encode('utf-8'))
            self.ae(r.status, OK)
            self.assertTrue(data['1']['ok'])
            self.ae(data['1']['payload']['action'], 'duplicate')
            self.assertIsNone(data['1']['payload']['new_book_id'])
            self.assertTrue(source_db.has_id(1))
            self.ae(target_db.all_book_ids(), target_book_ids)

    # }}}

    def test_data_file_paths_are_confined_to_book_dir(self):  # {{{
        with self.create_server(auth=True, auth_mode='basic') as server:
            server.handler.ctx.user_manager.add_user('12', 'test')
            db = server.handler.router.ctx.library_broker.get(None)
            bookdir = os.path.dirname(db.format_abspath(1, 'FMT1'))
            sibling = bookdir + ' sibling'
            os.makedirs(sibling)
            victim = os.path.join(sibling, 'victim')
            with open(victim, 'wb') as f:
                f.write(b'outside')

            conn = server.connect()
            url_for = server.handler.router.url_for
            bad_name = '../../' + os.path.basename(sibling) + '/victim'
            r, data = make_request(
                conn, url_for('/data-files/upload', book_id=1), prefix='', method='POST',
                username='12', password='test',
                headers={'Content-Type': 'application/json'}, data=json.dumps([{
                    'name': bad_name,
                    'data_url': 'data:application/octet-stream;base64,' + standard_b64encode(b'bad').decode('ascii'),
                }]).encode('utf-8'))
            self.ae(r.status, OK)
            with open(victim, 'rb') as f:
                self.ae(f.read(), b'outside')
            self.assertNotIn('data/' + bad_name, data['data_files'])

            r, data = make_request(
                conn, url_for('/data-files/remove', book_id=1), prefix='', method='POST',
                username='12', password='test',
                headers={'Content-Type': 'application/json'}, data=json.dumps(['data/' + bad_name]).encode('utf-8'))
            self.ae(r.status, OK)
            with open(victim, 'rb') as f:
                self.ae(f.read(), b'outside')

    # }}}

    def test_ajax_categories(self):  # {{{
        'Test /ajax/categories and /ajax/search'
        with self.create_server() as server:
            db = server.handler.router.ctx.library_broker.get(None)
            db.set_pref('virtual_libraries', {'1':'title:"=Title One"'})
            conn = server.connect()
            request = partial(make_request, conn)

            r, data = request('/categories')
            self.ae(r.status, OK)
            r, xdata = request('/categories/' + db.server_library_id)
            self.ae(r.status, OK)
            self.ae(data, xdata)
            names = {x['name']:x['url'] for x in data}
            for q in (_('Newest'), _('All books'), _('Tags'), _('Authors'), _('Enum'), _('Composite Tags')):
                self.assertIn(q, names)
            r, data = request(names[_('Tags')], prefix='')
            self.ae(r.status, OK)
            names = {x['name']:x['url'] for x in data['items']}
            self.ae(set(names), set('Tag One,Tag Two,News'.split(',')))
            r, data = request(names['Tag One'], prefix='')
            self.ae(r.status, OK)
            self.ae(set(data['book_ids']), {1, 2})
            r, data = request('/search?' + urlencode({'query': 'tags:"=Tag One"'}))
            self.ae(r.status, OK)
            self.ae(set(data['book_ids']), {1, 2})
            r, data = request('/search?' + urlencode({'query': 'tags:"=Tag One"', 'vl':'1'}))
            self.ae(set(data['book_ids']), {2})
            r, data = request('/search?' + urlencode({'query': 'template:"{tags}#@#:t:=Tag One"'}))
            self.ae(r.status, 400)
    # }}}

    def test_srv_restrictions(self):  # {{{
        ' Test that virtual lib. + search restriction works on all end points'
        with self.create_server(auth=True, auth_mode='basic') as server:
            db = server.handler.router.ctx.library_broker.get(None)
            db.set_pref('virtual_libraries', {'1':'id:1', '12':'id:1 or id:2'})
            db.set_field('tags', {1: ['present'], 3: ['missing']})
            db.add_extra_files(1, {'data/visible.txt': BytesIO(b'visible')})
            db.add_extra_files(3, {'data/hidden.txt': BytesIO(b'hidden')})
            self.assertTrue(db.has_id(3))
            server.handler.ctx.user_manager.add_user('12', 'test', restriction={
                'library_restrictions':{os.path.basename(db.backend.library_path): 'id:1 or id:2'}})
            server.handler.ctx.user_manager.add_user('inv', 'test', restriction={
                'library_restrictions':{os.path.basename(db.backend.library_path): '"1'}})
            conn = server.connect()

            def url_for(path, **kw):
                p, q = path.partition('?')[::2]
                ans = server.handler.router.url_for(p, **kw)
                if q:
                    ans += '?' + q
                return ans

            ae = self.assertEqual

            def r(path, status=OK, method='GET'):
                r, data = make_request(conn, path, username='12', password='test', prefix='', method=method)
                ae(status, r.status)
                if status == NOT_FOUND:
                    p = data.partition(b':')[0]
                    ae(p, b'No book with id')
                return data
            ok = r
            nf = partial(r, status=NOT_FOUND)

            # ajax.py
            ok(url_for('/ajax/book', book_id=1))
            nf(url_for('/ajax/book', book_id=3))
            data = ok(url_for('/ajax/books'))
            self.assertIsNone(data['3'])
            for i in '12':
                self.assertIsNotNone(data[i])
            ae(set(r(url_for('/ajax/search'))['book_ids']), {1,2})
            ae(set(r(url_for('/ajax/search?query=id:2'))['book_ids']), {2})
            ae(set(r(url_for('/ajax/search?vl=1'))['book_ids']), {1})
            data = make_request(conn, '/ajax/search', username='inv', password='test', prefix='', method='GET')[1]
            ae(data['bad_restriction'], _('Invalid syntax. Expected a lookup name or a word'))

            # books.py
            nf(url_for('/book-manifest', book_id=3, fmt='TXT'))
            nf(url_for('/book-file', book_id=3, fmt='TXT', size=1, mtime=1, name='x'))
            data = ok(url_for('/book-get-last-read-position', library_id=db.server_library_id, which='1-TXT_3-TXT'))
            ae(set(data), {'1:TXT'})
            nf(url_for('/book-set-last-read-position', book_id=3, library_id=db.server_library_id, fmt='TXT'), method='POST')

            # cdb.py
            r(url_for('/cdb/cmd', which='list'), status=FORBIDDEN)
            r(url_for('/cdb/add-book', job_id=1, add_duplicates='n', filename='test.epub'), status=FORBIDDEN)
            r(url_for('/cdb/delete-books', book_ids='1'), status=FORBIDDEN)

            # code.py
            def sr(path, **k):
                return set(ok(url_for(path, **k))['search_result']['book_ids'])

            for q in 'books-init init get-books'.split():
                ae(sr('/interface-data/' + q), {1, 2})
            ae(sr('/interface-data/get-books?vl=1'), {1})
            ok(url_for('/interface-data/book-metadata', book_id=1))
            nf(url_for('/interface-data/book-metadata', book_id=3))

            # content.py
            ok(url_for('/get', what='thumb', book_id=1))
            nf(url_for('/get', what='thumb', book_id=3))
            ae(ok(url_for('/data-files/get', book_id=1, relpath='data/visible.txt')), b'visible')
            nf(url_for('/data-files/get', book_id=3, relpath='data/hidden.txt'))
            nf(url_for('/data-files/upload', book_id=3), method='POST')
            nf(url_for('/data-files/remove', book_id=3), method='POST')

            # fts.py
            def fake_fts_search(query, use_stemming=True, return_text=True, process_each_result=None, restrict_to_book_ids=None, **kwargs):
                candidate_ids = {1, 3} if restrict_to_book_ids is None else set(restrict_to_book_ids) & {1, 3}
                for book_id in sorted(candidate_ids):
                    result = {'id': book_id, 'book_id': book_id, 'format': 'TXT', 'text': 'matching text'}
                    yield process_each_result(result) if process_each_result else result

            db.is_fts_enabled = lambda: True
            db.fts_indexing_progress = lambda: (0, 0, None)
            db.fts_search = fake_fts_search
            data = ok('/fts/search?' + urlencode({'query': 'matching'}))
            ae({x['book_id'] for x in data['results']}, {1})
            data = ok('/fts/search?' + urlencode({'query': 'matching', 'restriction': 'tags:missing'}))
            ae({x['book_id'] for x in data['results']}, set())
            data = ok('/fts/snippets/1,3?' + urlencode({'query': 'matching'}))
            ae(set(map(int, data['snippets'])), {1})

            # Not going test legacy and opds as they are too painful
    # }}}

    def test_srv_add_book(self):  # {{{
        with self.create_server(auth=True, auth_mode='basic') as server:
            server.handler.ctx.user_manager.add_user('12', 'test')
            server.handler.ctx.user_manager.add_user('ro', 'test', readonly=True)
            conn = server.connect()

            ae = self.assertEqual

            def a(filename, data=None, status=OK, method='POST', username='12', add_duplicates='n', job_id=1):
                r, data = make_request(conn, '/cdb/add-book/{}/{}/{}'.format(job_id, add_duplicates, quote(filename.encode('utf-8'))),
                                       username=username, password='test', prefix='', method=method, data=data)
                ae(status, r.status)
                return data

            def d(book_ids, username='12', status=OK):
                book_ids = ','.join(map(str, book_ids))
                r, data = make_request(conn, f'/cdb/delete-books/{book_ids}',
                                       username=username, password='test', prefix='', method='POST')
                ae(status, r.status)
                return data

            a('test.epub', None, username='ro', status=FORBIDDEN)
            content = b'content'
            filename = 'test add - XXX.txt'
            data = a(filename, content)
            s = BytesIO(content)
            s.name = filename
            mi = get_metadata(s, stream_type='txt')
            ae(data, {'title': mi.title, 'book_id': data['book_id'], 'authors': mi.authors, 'languages': mi.languages, 'id': '1', 'filename': filename})
            r, q = make_request(conn, '/get/txt/{}'.format(data['book_id']), username='12', password='test', prefix='')
            ae(r.status, OK)
            ae(q, content)
            d((1,), username='ro', status=FORBIDDEN)
            d((1, data['book_id']))
    # }}}
