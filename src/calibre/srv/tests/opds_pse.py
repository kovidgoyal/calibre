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
        from calibre.srv.comic_pages import page_as_jpeg, page_names, read_page
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
        # JPEG pages are returned unchanged, others are converted
        self.assertIs(page_as_jpeg(jpeg), jpeg)
        self.assertEqual(identify(page_as_jpeg(png)), ('jpeg', 400, 600))
        self.assertEqual(identify(page_as_jpeg(jpeg, 400)), ('jpeg', 400, 600))
        self.assertIs(page_as_jpeg(jpeg, 1000), jpeg)

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

            def request(path, user='alice'):
                from base64 import standard_b64encode

                auth = standard_b64encode(f'{user}:secret'.encode()).decode()
                conn.request('GET', path, headers={'Authorization': 'Basic ' + auth})
                r = conn.getresponse()
                return r.status, r.getheader('Content-Type'), r.read()

            status, ctype, raw = request('/opds/search/' + quote('title:"=Title One"'))
            self.ae(status, 200)
            root = etree.fromstring(raw)
            links = root.xpath('//atom:link[@rel="http://vaemendis.net/opds-pse/stream"]', namespaces={'atom': 'http://www.w3.org/2005/Atom'})
            self.ae(len(links), 1)
            link = links[0]
            self.ae(link.get(f'{{{PSE_NS}}}count'), '2')
            self.ae(link.get('type'), 'image/jpeg')
            href = link.get('href')
            self.assertIn('{pageNumber}', href)
            self.assertIn('{maxWidth}', href)

            status, ctype, raw = request(href.replace('{pageNumber}', '1').replace('{maxWidth}', '400'))
            self.ae((status, ctype), (200, 'image/jpeg'))
            self.ae(identify(raw), ('jpeg', 400, 600))
            status, ctype, raw = request(href.replace('{pageNumber}', '0'))
            self.ae((status, identify(raw)), (200, ('jpeg', 100, 100)))
            self.ae(request(href.replace('{pageNumber}', '2'))[0], 404)
            self.ae(request(href.replace('{pageNumber}', 'x'))[0], 404)
            # Books without a comic format and books the user cannot see
            self.ae(request('/opds/pse/1/cbz?page=0')[0], 404)
            self.ae(request(href.replace('{pageNumber}', '0'), user='bob')[0], 404)
