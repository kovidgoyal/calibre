#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
from http.client import NOT_FOUND, OK
from urllib.parse import quote

from calibre.srv.tests.base import LibraryBaseTest

OPDS2 = 'application/opds+json'


class OPDSTest(LibraryBaseTest):
    def test_accept_header(self) -> None:
        from calibre.srv.opds import accepts_opds2
        from calibre.srv.utils import MultiDict

        class RequestData:
            def __init__(self, *accept) -> None:
                self.inheaders = MultiDict()
                for x in accept:
                    self.inheaders['Accept'] = x

        for accept, expected in {
            (): False,
            ('application/atom+xml',): False,
            ('*/*',): False,
            (OPDS2,): True,
            ('application/OPDS+JSON',): True,
            ('application/opds+json; charset=utf-8',): True,
            ('application/atom+xml;q=0.9, application/opds+json',): True,
            ('application/atom+xml;q=0.5', 'application/opds+json'): True,
            ('application/opds+json, */*;q=0.8',): True,
            # The client prefers OPDS 1, or has no preference
            ('application/atom+xml', 'application/opds+json;q=0.5'): False,
            ('application/atom+xml;profile=opds-catalog;q=1.0, application/opds+json;q=0.1',): False,
            ('application/atom+xml, application/opds+json',): False,
            ('application/opds+json;q=0',): False,
            ('application/opds+json;q=0.0, application/atom+xml',): False,
            ('application/opds-publication+json',): False,
            # Invalid quality values
            ('application/opds+json;q=abc',): False,
            ('application/opds+json;q=nan',): False,
            ('application/opds+json;q=2',): False,
        }.items():
            self.ae(accepts_opds2(RequestData(*accept)), expected, f'Accept: {accept}')

    def test_opds2(self) -> None:
        from calibre.db.cache import Cache
        from calibre.db.legacy import create_backend

        # Title One gets a format that can be downloaded and loses its cover,
        # Unknown has no formats at all, so it is left out of OPDS 2.0 feeds
        db = Cache(create_backend(self.library_path))
        db.init()
        with open(P('quick_start/eng.epub'), 'rb') as src:
            db.add_format(2, 'EPUB', src, run_hooks=False)
        db.set_cover({2: None})
        db.close()

        with self.create_server(max_opds_items=1, max_opds_ungrouped_items=1) as server:
            conn = server.connect()

            def request(url, accept=OPDS2):
                conn.request('GET', url, headers={'Accept': accept} if accept else {})
                r = conn.getresponse()
                data = r.read()
                return r, data

            def feed(url):
                r, data = request(url)
                self.ae(r.status, OK, f'{url}: {data!r}')
                self.ae(r.getheader('Content-Type'), OPDS2)
                self.ae(r.getheader('Vary'), 'Accept')
                ans = json.loads(data)
                links = {x['rel']: x for x in ans['links']}
                self.assertTrue(links['start']['href'].startswith('/opds?library_id='))
                self.assertTrue(links['search']['templated'])
                self.ae(links['self']['type'], OPDS2)
                self.assertTrue(ans['metadata']['title'])
                return ans, links

            # OPDS 1 is still served by default and to clients asking for it
            for accept in (None, 'application/atom+xml'):
                r, data = request('/opds', accept)
                self.ae(r.status, OK)
                self.assertTrue(r.getheader('Content-Type').startswith('application/atom+xml'))
                self.ae(r.getheader('Vary'), 'Accept')
                self.assertIn(b'<feed', data)

            top, links = feed('/opds')
            self.ae(links['self']['href'], links['start']['href'])
            nav = {x['title']: x['href'] for x in top['navigation']}
            self.assertIn('By Newest', nav)
            self.assertIn('By Title', nav)
            self.assertIn('By Authors', nav)
            self.ae(len([x for x in nav if x.startswith('Library: ')]), 1)

            # All books, one per page
            books, links = feed(nav['By Title'])
            self.ae(len(books['publications']), 1)
            self.assertNotIn('previous', links)
            pub = books['publications'][0]
            self.ae(pub['metadata']['title'], 'Title One')
            self.ae(pub['metadata']['author'], ['Author One'])
            self.assertTrue(pub['metadata']['identifier'].startswith('urn:uuid:'))
            self.ae(pub['metadata']['subject'], ['Tag One', 'Tag Two'])
            self.assertIn('Tag One', pub['metadata']['description'])
            self.ae(pub['metadata']['language'], ['en'])
            self.assertNotIn('images', pub)

            # Following the pagination links stays in OPDS 2.0
            page2, links2 = feed(links['next']['href'])
            pub = page2['publications'][0]
            self.ae(pub['metadata']['title'], 'Title Two')
            self.ae(pub['metadata']['language'], ['de'])
            self.ae(pub['metadata']['belongsTo'], {'series': {'name': 'A Series One', 'position': 2.0}})
            self.ae(len(pub['images']), 2)
            self.ae(links2['previous']['href'], links['first']['href'] + '&offset=0')
            # Unknown has no formats, so Title Two is the last page
            self.assertNotIn('next', links2)
            acquisitions = {x['type']: x['href'] for x in pub['links'] if x['rel'] == 'http://opds-spec.org/acquisition'}
            self.ae(set(acquisitions), {'application/epub+zip'})
            r, data = request(acquisitions['application/epub+zip'], None)
            self.ae(r.status, OK)
            self.assertTrue(data.startswith(b'PK'))
            last, _ = feed(links['last']['href'])
            self.ae([x['metadata']['title'] for x in last['publications']], ['Title Two'])

            # Authors are grouped by first letter, as there are more than max_opds_ungrouped_items
            groups, _ = feed(nav['By Authors'])
            group = groups['navigation'][0]
            self.assertGreater(group['properties']['numberOfItems'], 0)
            authors, _ = feed(group['href'])
            author = authors['navigation'][0]
            self.assertGreater(author['properties']['numberOfItems'], 0)
            by_author, _ = feed(author['href'])
            self.assertIn(author['title'], by_author['publications'][0]['metadata']['author'])

            # Search, using the URL template
            results, _ = feed(links['search']['href'].replace('{query}', quote('title:"=Title One"')))
            self.ae([x['metadata']['title'] for x in results['publications']], ['Title One'])
            r, _ = request('/opds/search/' + quote('title:"=No such title"'))
            self.ae(r.status, NOT_FOUND)
            # Books without formats are only in OPDS 1 feeds
            url = '/opds/search/' + quote('title:"=Unknown"')
            r, _ = request(url)
            self.ae(r.status, NOT_FOUND)
            r, data = request(url, None)
            self.ae(r.status, OK)
            self.assertIn(b'Unknown', data)
