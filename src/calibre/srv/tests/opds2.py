#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import os
from io import BytesIO
from urllib.parse import quote
from zipfile import ZipFile

from calibre.srv.tests.base import LibraryBaseTest


def make_image(width, height, fmt='JPEG'):
    from qt.core import QColor, QImage

    from calibre.utils.img import image_to_data

    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(QColor('red'))
    return image_to_data(img, fmt=fmt)


def make_cbz(pages):
    buf = BytesIO()
    with ZipFile(buf, 'w') as zf:
        for name, data in pages:
            zf.writestr(name, data)
    return buf.getvalue()


class OPDS2Test(LibraryBaseTest):
    def test_comic_pages(self):
        from calibre.srv.comic_pages import convert_page, convertible_types, page_names, page_types, read_page
        from calibre.utils.imghdr import identify

        jpeg, png = make_image(800, 1200), make_image(400, 600, 'PNG')
        pages = [('c/page10.jpg', jpeg), ('c/page2.png', png), ('c/page1.jpg', jpeg), ('c/notes.txt', b'x'), ('__MACOSX/c/._page1.jpg', b'x')]
        tdir = self.mkdtemp()
        # A CBR that is actually a ZIP file, as is common
        path = os.path.join(tdir, 'comic.cbr')
        with open(path, 'wb') as f:
            f.write(make_cbz(pages))
        self.assertEqual(page_names(path), ('c/page1.jpg', 'c/page2.png', 'c/page10.jpg'))
        self.assertEqual(read_page(path, 'c/page10.jpg'), jpeg)

        # Pages are offered in their own format, if widely supported, with
        # alternates in the formats they can be converted to
        converted = convertible_types()
        self.assertIn('image/jpeg', converted)
        native, types = page_types('c/page2.png')
        self.assertEqual((native, types[0]), ('image/png', 'image/png'))
        self.assertEqual(set(types), {'image/png'} | set(converted))
        native, types = page_types('c/page.avif')
        self.assertEqual((native, types[:2]), ('image/avif', ['image/jpeg', 'image/avif']))
        self.assertEqual(identify(convert_page(png, 'image/jpeg')), ('jpeg', 400, 600))

        from calibre.utils.seven_zip import open_archive

        path7z = os.path.join(tdir, 'comic.cb7')
        with open_archive(path7z, 'w') as ar:
            for name, data in pages[:3]:
                ar.writestr(data, name)
        self.assertEqual(page_names(path7z), ('c/page1.jpg', 'c/page2.png', 'c/page10.jpg'))
        self.assertEqual(read_page(path7z, 'c/page2.png'), png)

    def test_opds2(self):
        import json
        from base64 import standard_b64encode

        from calibre.utils.imghdr import identify

        jpeg = make_image(800, 1200)
        with self.create_server(auth=True, auth_mode='basic') as server:
            db = server.handler.router.ctx.library_broker.get(None)
            db.add_format(2, 'CBZ', BytesIO(make_cbz([('2.jpg', jpeg), ('1.png', make_image(100, 100, 'PNG'))])), run_hooks=False)
            um = server.handler.ctx.user_manager
            um.add_user('alice', 'secret')
            um.add_user('bob', 'secret', restriction={'library_restrictions': {os.path.basename(self.library_path): 'title:"=Title Two"'}})
            conn = server.connect()

            def request(path, user='alice'):
                auth = standard_b64encode(f'{user}:secret'.encode()).decode()
                conn.request('GET', path, headers={'Authorization': 'Basic ' + auth})
                r = conn.getresponse()
                return r.status, r.getheader('Content-Type'), r.read()

            def get_json(path, expected_type='application/opds+json', user='alice'):
                status, ctype, raw = request(path, user)
                self.ae((status, ctype), (200, expected_type + '; charset=UTF-8'), raw)
                return json.loads(raw)

            def link(obj, rel=None, type=None):
                return next(x['href'] for x in obj['links'] if (rel is None or x.get('rel') == rel) and (type is None or x.get('type') == type))

            # The start of the catalog links to books sorted in different ways and to categories
            start = get_json('/opds2')
            nav = {x['title']: x['href'] for x in start['groups'][0]['navigation']}
            self.assertIn('Authors', nav)
            search = next(x for x in start['links'] if x['rel'] == 'search')
            self.assertTrue(search['templated'])
            self.assertTrue(search['href'].endswith('{?query}'))

            feed = get_json(nav['Title'])
            self.ae(feed['metadata']['numberOfItems'], len(feed['publications']))
            pubs = {p['metadata']['title']: p for p in feed['publications']}
            self.assertTrue({'Title One', 'Title Two'}.issubset(pubs))
            # Only comics can be read page by page
            for title, pub in pubs.items():
                types = {x['type'] for x in pub['links']}
                self.ae('application/divina+json' in types, title == 'Title One', title)
            pub = pubs['Title One']
            self.ae(get_json(link(pub, 'self'), 'application/opds-publication+json')['metadata']['title'], 'Title One')
            author = pub['metadata']['author'][0]
            author_books = get_json(author['links'][0]['href'])
            self.assertIn('Title One', {p['metadata']['title'] for p in author_books['publications']})
            authors = get_json(nav['Authors'])
            self.assertIn(author['name'], {x['title'] for x in authors['navigation']})

            results = get_json(search['href'].replace('{?query}', '?query=' + quote('title:"=Title Two"')))
            self.ae([p['metadata']['title'] for p in results['publications']], ['Title Two'])

            # The Divina manifest lists the pages, in their own format with alternates
            manifest_url = link(pub, type='application/divina+json')
            manifest = get_json(manifest_url, 'application/divina+json')
            self.ae(manifest['metadata']['conformsTo'], 'https://readium.org/webpub-manifest/profiles/divina')
            self.ae(manifest['metadata']['numberOfPages'], 2)
            pages = manifest['readingOrder']
            self.ae([p['type'] for p in pages], ['image/png', 'image/jpeg'])
            status, ctype, raw = request(pages[0]['href'])
            self.ae((status, ctype, identify(raw)), (200, 'image/png', ('png', 100, 100)))
            jpeg_alternate = next(a for a in pages[0]['alternate'] if a['type'] == 'image/jpeg')
            status, ctype, raw = request(jpeg_alternate['href'])
            self.ae((status, ctype, identify(raw)), (200, 'image/jpeg', ('jpeg', 100, 100)))
            status, ctype, raw = request(pages[1]['href'])
            self.ae((status, raw), (200, jpeg))
            self.ae(request(pages[0]['href'].rsplit('/', 1)[0] + '/2')[0], 404)
            self.ae(request(pages[1]['href'] + '?type=image/avif')[0], 404)

            # Books the user cannot see and unknown books and libraries
            self.ae(request(manifest_url, user='bob')[0], 404)
            self.ae(request(pages[0]['href'], user='bob')[0], 404)
            self.ae(request('/opds2/nosuchlibrary')[0], 404)
            self.ae(request(manifest_url.replace('/cbz', '/epub'))[0], 404)
