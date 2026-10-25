#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
from urllib.parse import quote

from calibre.srv.tests.base import LibraryBaseTest

# This family is bundled with calibre so is always available
FAMILY = 'Liberation Serif'


class FontsTest(LibraryBaseTest):
    def request(self, conn, path):
        conn.request('GET', path)
        r = conn.getresponse()
        return r, r.read()

    def test_reader_fonts(self):
        from calibre.utils.fonts.scanner import font_scanner

        with self.create_server() as server:
            conn = server.connect()
            r, data = self.request(conn, '/reader-fonts')
            self.ae(r.status, 200)
            families = json.loads(data)['families']
            self.assertIn(FAMILY, families)
            self.ae(families, sorted(families, key=lambda x: x.lower()))

            # Family names are matched case insensitively
            r, data = self.request(conn, '/reader-font-faces/' + quote(FAMILY.lower()))
            self.ae(r.status, 200)
            data = json.loads(data)
            self.ae(data['family'], FAMILY)
            faces = data['faces']
            self.ae({(f['font-weight'], f['font-style']) for f in faces}, {('normal', 'normal'), ('bold', 'normal'), ('normal', 'italic'), ('bold', 'italic')})

            fonts = font_scanner.fonts_for_family(FAMILY)
            for face in faces:
                r, data = self.request(conn, f'/reader-font-file/{face["index"]}/' + quote(FAMILY))
                self.ae(r.status, 200)
                self.ae(r.getheader('Content-Type'), 'font/ttf')
                with open(fonts[face['index']]['path'], 'rb') as f:
                    self.ae(data, f.read())
                etag = r.getheader('ETag')
                self.assertTrue(etag)
                conn.request('GET', f'/reader-font-file/{face["index"]}/' + quote(FAMILY), headers={'If-None-Match': etag})
                r = conn.getresponse()
                r.read()
                self.ae(r.status, 304)

            for path in (
                '/reader-font-faces/no-such-family',
                '/reader-font-file/0/no-such-family',
                f'/reader-font-file/{len(fonts)}/' + quote(FAMILY),
                '/reader-font-file/-1/' + quote(FAMILY),
            ):
                with self.subTest(path=path):
                    self.ae(self.request(conn, path)[0].status, 404)

    def test_reader_fonts_auth(self):
        with self.create_server(auth=True, auth_mode='basic') as server:
            conn = server.connect()
            for path in ('/reader-fonts', '/reader-font-faces/' + quote(FAMILY), '/reader-font-file/0/' + quote(FAMILY)):
                with self.subTest(path=path):
                    self.ae(self.request(conn, path)[0].status, 401)
