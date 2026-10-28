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


class OPDSPageStreamingTest(LibraryBaseTest):
    def test_comic_pages(self):
        from calibre.srv.comic_pages import NotAcceptable, acceptable_types, page_for_client, page_names, read_page, writable_types
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

        # Clients that do not list image formats get JPEG
        for header in (None, '', '*/*', 'image/*', 'text/html, */*;q=0.8'):
            self.assertEqual(acceptable_types(header), {'image/jpeg': 1.0}, header)
        self.assertEqual(acceptable_types('text/html'), {})
        self.assertEqual(
            acceptable_types('image/avif, image/jxl;q=0.9, image/jpeg;q=0.5, image/png;q=0'), {'image/avif': 1.0, 'image/jxl': 0.9, 'image/jpeg': 0.5}
        )
        self.assertEqual(acceptable_types('image/webp, image/*;q=0.1')['image/png'], 0.1)

        # Pages in an acceptable format that need no resizing are returned unchanged
        self.assertIs(page_for_client(jpeg)[0], jpeg)
        self.assertIs(page_for_client(jpeg, 1000)[0], jpeg)
        self.assertIs(page_for_client(png, 0, 'image/avif, image/png')[0], png)
        data, mt = page_for_client(png)
        self.assertEqual((mt, identify(data)), ('image/jpeg', ('jpeg', 400, 600)))
        data, mt = page_for_client(jpeg, 400)
        self.assertEqual((mt, identify(data)), ('image/jpeg', ('jpeg', 400, 600)))
        # Other pages are converted to the acceptable format the client prefers
        data, mt = page_for_client(jpeg, 400, 'image/png;q=0.8, image/jpeg;q=0.5')
        self.assertEqual((mt, identify(data)), ('image/png', ('png', 400, 600)))
        if 'image/jxl' in writable_types():
            data, mt = page_for_client(png, 0, 'image/jxl, image/jpeg;q=0.5')
            self.assertEqual((mt, identify(data)[0]), ('image/jxl', 'jxl'))
        # AVIF images can be sent but not created
        with self.assertRaises(NotAcceptable):
            page_for_client(jpeg, 0, 'image/avif')

        from calibre.utils.seven_zip import open_archive

        path7z = os.path.join(tdir, 'comic.cb7')
        with open_archive(path7z, 'w') as ar:
            for name, data in pages[:3]:
                ar.writestr(data, name)
        self.assertEqual(page_names(path7z), ('c/page1.jpg', 'c/page2.png', 'c/page10.jpg'))
        self.assertEqual(read_page(path7z, 'c/page2.png'), png)

    def test_opds_pse(self):
        from lxml import etree

        from calibre.srv.opds import PSE_NS
        from calibre.utils.imghdr import identify

        jpeg = make_image(800, 1200)
        with self.create_server(auth=True, auth_mode='basic') as server:
            db = server.handler.router.ctx.library_broker.get(None)
            db.add_format(2, 'CBZ', BytesIO(make_cbz([('2.jpg', jpeg), ('1.jpg', make_image(100, 100, 'PNG'))])), run_hooks=False)
            um = server.handler.ctx.user_manager
            um.add_user('alice', 'secret')
            um.add_user('bob', 'secret', restriction={'library_restrictions': {os.path.basename(self.library_path): 'title:"=Title Two"'}})
            conn = server.connect()

            def request(path, user='alice', accept=None):
                from base64 import standard_b64encode

                auth = standard_b64encode(f'{user}:secret'.encode()).decode()
                headers = {'Authorization': 'Basic ' + auth}
                if accept is not None:
                    headers['Accept'] = accept
                conn.request('GET', path, headers=headers)
                r = conn.getresponse()
                return r.status, r.getheader('Content-Type'), r.read(), r.headers

            status, ctype, raw = request('/opds/search/' + quote('title:"=Title One"'))[:3]
            self.ae(status, 200)
            root = etree.fromstring(raw)
            links = root.xpath('//atom:link[@rel="http://vaemendis.net/opds-pse/stream"]', namespaces={'atom': 'http://www.w3.org/2005/Atom'})
            self.ae(len(links), 1)
            link = links[0]
            # The number of pages is not in the feed, it is sent with the pages
            self.assertIsNone(link.get(f'{{{PSE_NS}}}count'))
            self.ae(link.get('type'), 'image/jpeg')
            href = link.get('href')
            self.assertIn('{pageNumber}', href)
            self.assertIn('{maxWidth}', href)

            status, ctype, raw, headers = request(href.replace('{pageNumber}', '1').replace('{maxWidth}', '400'))
            self.ae((status, ctype), (200, 'image/jpeg'))
            self.ae(identify(raw), ('jpeg', 400, 600))
            self.ae((headers['PSE-Page-Count'], headers['Vary']), ('2', 'Accept'))
            status, ctype, raw, headers = request(href.replace('{pageNumber}', '0'))
            self.ae((status, ctype, identify(raw)), (200, 'image/jpeg', ('jpeg', 100, 100)))
            # The client can ask for other formats
            status, ctype, raw, headers = request(href.replace('{pageNumber}', '0'), accept='image/avif, image/png;q=0.9')
            self.ae((status, ctype, identify(raw)), (200, 'image/png', ('png', 100, 100)))
            self.ae(request(href.replace('{pageNumber}', '1'), accept='image/avif')[0], 406)
            self.ae(request(href.replace('{pageNumber}', '2'))[0], 404)
            self.ae(request(href.replace('{pageNumber}', 'x'))[0], 404)
            # Books without a comic format and books the user cannot see
            self.ae(request('/opds/pse/1/cbz?page=0')[0], 404)
            self.ae(request(href.replace('{pageNumber}', '0'), user='bob')[0], 404)
