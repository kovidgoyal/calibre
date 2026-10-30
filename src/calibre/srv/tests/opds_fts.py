#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
from base64 import standard_b64encode
from http.client import BAD_REQUEST, NOT_FOUND, OK, PRECONDITION_REQUIRED, UNAUTHORIZED, UNPROCESSABLE_ENTITY
from io import BytesIO
from time import monotonic
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from lxml import etree

from calibre.srv.opds import OPDS2_MIME
from calibre.srv.tests.base import LibraryBaseTest

NS = {'a': 'http://www.w3.org/2005/Atom'}


class OPDSFullTextTest(LibraryBaseTest):
    def request(self, conn, url, accept=OPDS2_MIME, user=None):
        headers = {'Accept': accept}
        if user:
            headers['Authorization'] = 'Basic ' + standard_b64encode(f'{user}:test'.encode()).decode()
        conn.request('GET', url, headers=headers)
        response = conn.getresponse()
        return response, response.read()

    def index(self, db):
        # Exercise the real FTS database with deterministic extracted text,
        # without starting background format-extraction workers.
        db.enable_fts(start_pool=False)
        for book_id, fmt, text in (
            (1, 'TXT', 'A distant nebula contains stellar dust.'),
            (1, 'MD', 'A distant nebula contains stellar dust.'),
            (2, 'TXT', 'A nebula hides the secretword.'),
        ):
            db.add_format(book_id, fmt, BytesIO(text.encode()), run_hooks=False)
            db.commit_fts_result(book_id, fmt, len(text), 'fixture', text, '', monotonic())
        db.add_format(3, 'TXT', BytesIO(b'A book waiting to index: pendingterm'), run_hooks=False)

    def search_links(self, raw, accept):
        if accept == OPDS2_MIME:
            return [x for x in json.loads(raw)['links'] if x.get('rel') == 'search']
        return [dict(x.attrib) for x in etree.fromstring(raw).xpath('a:link[@rel="search"]', namespaces=NS)]

    def test_opds_full_text(self):
        with self.create_server(max_opds_items=1, url_prefix='/calibre') as server:
            db = server.handler.ctx.library_broker.get(None)
            self.index(db)
            conn = server.connect()
            for accept, variable in ((OPDS2_MIME, '{query}'), ('application/atom+xml', '{searchTerms}')):
                with self.subTest(accept=accept):
                    response, raw = self.request(conn, '/calibre/opds', accept)
                    self.ae(response.status, OK)
                    links = self.search_links(raw, accept)
                    self.ae(len(links), 2)
                    self.assertNotIn('full_text', links[0]['href'])
                    self.ae(links[1]['title'], 'Search book contents')
                    self.assertIn('library_id', parse_qs(urlsplit(links[1]['href']).query))
                    url = links[1]['href'].replace(variable, quote('nebula', safe=''))
                    response, raw = self.request(conn, url, accept)
                    self.ae(response.status, OK, raw)
                    self.ae(response.getheader('Vary'), 'Accept')
                    if accept == OPDS2_MIME:
                        result = json.loads(raw)
                        self.ae([p['metadata']['title'] for p in result['publications']], ['Title One'])
                        pagination = {x['rel']: x['href'] for x in result['links'] if x.get('rel') != 'search'}
                        acquisition = next(x['href'] for x in result['publications'][0]['links'] if x['type'] == 'text/plain')
                        self.ae(self.request(conn, acquisition, accept)[1], b'A nebula hides the secretword.')
                    else:
                        root = etree.fromstring(raw)
                        self.ae(root.xpath('a:entry/a:title/text()', namespaces=NS), ['Title One'])
                        pagination = {x.get('rel'): x.get('href') for x in root.xpath('a:link', namespaces=NS) if x.get('rel') != 'search'}
                    for rel in ('self', 'next', 'last', 'first') if accept == OPDS2_MIME else ('next', 'last', 'first'):
                        self.ae(parse_qs(urlsplit(pagination[rel]).query)['full_text'], ['y'])
                    response, raw = self.request(conn, pagination['next'], accept)
                    self.ae(response.status, OK)
                    if accept == OPDS2_MIME:
                        page = json.loads(raw)
                        self.ae([p['metadata']['title'] for p in page['publications']], ['Title Two'])
                        self.assertFalse(any(x.get('rel') == 'next' for x in page['links']))
                    else:
                        root = etree.fromstring(raw)
                        self.ae(root.xpath('a:entry/a:title/text()', namespaces=NS), ['Title Two'])
                        self.assertFalse(root.xpath('a:link[@rel="next"]', namespaces=NS))
                    # The normal metadata search still has its old semantics.
                    self.ae(self.request(conn, links[0]['href'].replace(variable, 'nebula'), accept)[0].status, NOT_FOUND)
                    metadata_url = links[0]['href'].replace(variable, quote('title:"=Title One"', safe=''))
                    self.ae(self.request(conn, metadata_url, accept)[0].status, OK)
                    phrase_url = links[1]['href'].replace(variable, quote('"stellar dust"', safe=''))
                    self.ae(self.request(conn, phrase_url, accept)[0].status, OK)

    def test_opds_full_text_errors(self):
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            conn = server.connect()
            for accept in (OPDS2_MIME, 'application/atom+xml'):
                self.ae(len(self.search_links(self.request(conn, '/opds', accept)[1], accept)), 1)
                self.ae(self.request(conn, '/opds/search/nebula?full_text=y', accept)[0].status, PRECONDITION_REQUIRED)
            self.index(db)
            for path, status in (
                ('/opds/search?full_text=y', BAD_REQUEST),
                ('/opds/search/%20?full_text=y', BAD_REQUEST),
                ('/opds/search/%22unterminated?full_text=y', UNPROCESSABLE_ENTITY),
                ('/opds/search/notindexed?full_text=y', NOT_FOUND),
                ('/opds/search/pendingterm?full_text=y', NOT_FOUND),
                ('/opds/search/nebula?full_text=invalid', BAD_REQUEST),
                ('/opds/search/nebula?full_text=y&offset=invalid', NOT_FOUND),
                ('/opds/search/nebula?full_text=y&library_id=missing', NOT_FOUND),
            ):
                for accept in (OPDS2_MIME, 'application/atom+xml'):
                    self.ae(self.request(conn, path, accept)[0].status, status, path)
            db.enable_fts(False)
            self.ae(len(self.search_links(self.request(conn, '/opds')[1], OPDS2_MIME)), 1)

    def test_opds_full_text_permissions(self):
        other_path = self.mkdtemp()
        self.create_db(other_path)
        with self.create_server(libraries=(self.library_path, other_path), auth=True, auth_mode='basic', max_opds_items=1) as server:
            ctx = server.handler.ctx
            db = ctx.library_broker.get(None)
            self.index(db)
            other_id = next(key for key, name in ctx.library_broker.library_map.items() if name == os.path.basename(other_path))
            ctx.user_manager.add_user('owner', 'test')
            ctx.user_manager.add_user('reader', 'test', readonly=True)
            ctx.user_manager.add_user('limited', 'test', restriction={'library_restrictions': {os.path.basename(self.library_path): 'id:1'}})
            ctx.user_manager.add_user('empty', 'test', restriction={'library_restrictions': {os.path.basename(self.library_path): 'id:999'}})
            ctx.user_manager.add_user('one-library', 'test', restriction={'allowed_library_names': [os.path.basename(self.library_path)]})
            conn = server.connect()
            for accept in (OPDS2_MIME, 'application/atom+xml'):
                self.ae(self.request(conn, '/opds/search/nebula?full_text=y', accept)[0].status, UNAUTHORIZED)
                self.ae(self.request(conn, '/opds/search/secretword?full_text=y', accept, 'owner')[0].status, OK)
                self.ae(self.request(conn, '/opds/search/secretword?full_text=y', accept, 'reader')[0].status, OK)
                self.ae(self.request(conn, '/opds/search/secretword?full_text=y', accept, 'limited')[0].status, NOT_FOUND)
                self.ae(self.request(conn, '/opds/search/nebula?full_text=y', accept, 'empty')[0].status, NOT_FOUND)
                response, raw = self.request(conn, '/opds/search/nebula?full_text=y', accept, 'limited')
                self.ae(response.status, OK)
                self.assertNotIn(b'Title One', raw)
                if accept == OPDS2_MIME:
                    result = json.loads(raw)
                    self.ae([p['metadata']['title'] for p in result['publications']], ['Title Two'])
                    self.assertFalse(any(x.get('rel') == 'next' for x in result['links']))
                query = '?' + urlencode({'full_text': 'y', 'library_id': other_id})
                self.ae(self.request(conn, '/opds/search/nebula' + query, accept, 'owner')[0].status, PRECONDITION_REQUIRED)
                self.ae(self.request(conn, '/opds/search/nebula' + query, accept, 'one-library')[0].status, NOT_FOUND)
