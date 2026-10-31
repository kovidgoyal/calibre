#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
import time
from base64 import standard_b64encode
from http.client import NOT_FOUND, NOT_MODIFIED, OK, UNAUTHORIZED
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from zipfile import ZipFile

from calibre.db.tests.base import IMG
from calibre.srv.comic import DIVINA_PROFILE, comic_is_right_to_left, comic_pages, convertible_types, page_types, readable_types
from calibre.srv.opds import DIVINA_MIME, OPDS2_MIME
from calibre.srv.tests.base import LibraryBaseTest
from calibre.utils.avif_test import NOT_AN_IMAGE, STILL_AVIF
from calibre.utils.imghdr import identify
from calibre.utils.jxl_test import STILL_JXL
from calibre.utils.resources import get_image_path as I
from calibre.utils.zipfile import ZipFile as ComicZipFile


def cbz(pages):
    buf = BytesIO()
    with ZipFile(buf, 'w') as archive:
        for name, data in pages:
            archive.writestr(name, data)
    return buf.getvalue()


def replace_cbz(db, book_id, data) -> None:
    # The download cache only recopies a format whose mtime is newer than its
    # cached copy, which a replacement made in the same filesystem timestamp
    # tick would not be, so move the mtime of the replacement forward.
    db.add_format(book_id, 'CBZ', BytesIO(data), run_hooks=False)
    path = db.format_abspath(book_id, 'CBZ')
    mtime = max(os.path.getmtime(path), time.time()) + 2
    os.utime(path, (mtime, mtime))


class ComicTest(LibraryBaseTest):
    def test_comic_reading_direction(self) -> None:
        rtl = b'<ComicInfo><Manga>YesAndRightToLeft</Manga></ComicInfo>'
        no = b'<ComicInfo><Manga>No</Manga></ComicInfo>'

        def is_rtl(*entries, pages=(('1.jpg', IMG),)):
            with ComicZipFile(BytesIO(cbz([*pages, *entries]))) as archive:
                return comic_is_right_to_left(archive, comic_pages(archive))

        for filename, data, expected in (
            ('ComicInfo.xml', rtl, True),
            ('COMICINFO.XML', rtl, True),
            ('ComicInfo.xml', b'<ComicInfo><Manga> YesAndRightToLeft </Manga></ComicInfo>', True),
            ('ComicInfo.xml', b'<ComicInfo><Manga>yesandrighttoleft</Manga></ComicInfo>', True),
            ('ComicInfo.xml', b'<ComicInfo xmlns="urn:x"><Manga>YesAndRightToLeft</Manga></ComicInfo>', True),
            ('ComicInfo.xml', b'<ComicInfo><!-- c --><Manga>YesAndRightToLeft</Manga></ComicInfo>', True),
            ('folder/ComicInfo.xml', rtl, False),
            ('__MACOSX/ComicInfo.xml', rtl, False),
            ('ComicInfo.xml', b'<ComicInfo><Manga>Yes</Manga></ComicInfo>', False),
            ('ComicInfo.xml', no, False),
            ('ComicInfo.xml', b'<ComicInfo><Manga>Unknown</Manga></ComicInfo>', False),
            ('ComicInfo.xml', b'<ComicInfo/>', False),
            ('ComicInfo.xml', b'<Other><Manga>YesAndRightToLeft</Manga></Other>', False),
            ('ComicInfo.xml', b'<ComicInfo><Manga>YesAndRightToLeft</Manga>', False),
            ('ComicInfo.xml', b'not XML', False),
        ):
            with self.subTest(filename=filename, data=data):
                self.ae(is_rtl((filename, data)), expected)
        # Archives created by zipping a folder have ComicInfo.xml next to the pages
        title = (('Title/1.jpg', IMG), ('Title/2.jpg', IMG))
        self.assertTrue(is_rtl(('Title/ComicInfo.xml', rtl), pages=title))
        self.assertTrue(is_rtl(('ComicInfo.xml', rtl), pages=title))
        self.assertFalse(is_rtl(('Other/ComicInfo.xml', rtl), pages=title))
        self.assertTrue(is_rtl(('ComicInfo.xml', no), ('Title/ComicInfo.xml', rtl), pages=title))
        self.assertTrue(is_rtl(('Title/ComicInfo.xml', b'not XML'), ('ComicInfo.xml', rtl), pages=title))
        # Exactly cased names win and broken copies do not hide valid ones,
        # whatever their order in the archive
        for entries in ((('comicinfo.xml', no), ('ComicInfo.xml', rtl)), (('ComicInfo.xml', rtl), ('comicinfo.xml', no))):
            self.assertTrue(is_rtl(*entries))
        self.assertTrue(is_rtl(('ComicInfo.xml', b'not XML'), ('COMICINFO.XML', rtl)))
        with ComicZipFile(BytesIO(cbz([('ComicInfo.xml', rtl)]))) as archive:
            with patch('calibre.srv.comic.MAX_COMICINFO_SIZE', len(rtl)):
                self.assertTrue(comic_is_right_to_left(archive, []))
            with patch('calibre.srv.comic.MAX_COMICINFO_SIZE', len(rtl) - 1):
                self.assertFalse(comic_is_right_to_left(archive, []))
        # Resolving external entities must not read local files into metadata.
        path = os.path.join(self.mkdtemp(), 'direction.txt')
        with open(path, 'w') as f:
            f.write('YesAndRightToLeft')
        xml = f'<!DOCTYPE ComicInfo [<!ENTITY direction SYSTEM "{Path(path).as_uri()}">]><ComicInfo><Manga>&direction;</Manga></ComicInfo>'.encode()
        self.assertFalse(is_rtl(('ComicInfo.xml', xml)))
        encrypted = bytearray(cbz([('ComicInfo.xml', rtl)]))
        encrypted[6] |= 1
        encrypted[encrypted.index(b'PK\x01\x02') + 8] |= 1
        with ComicZipFile(BytesIO(encrypted)) as archive:
            self.assertFalse(comic_is_right_to_left(archive, []))

    def test_comic_manga_manifest(self) -> None:
        png = I('lt.png', data=True)
        pages = [('2.png', png), ('1.jpg', IMG)]
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            conn = server.connect()
            # Use a separate book for each case, rather than replacing the
            # format, so the test does not depend on the download cache
            # noticing a newer mtime.
            cases = (
                (1, [('ComicInfo.xml', b'<ComicInfo><Manga>YesAndRightToLeft</Manga></ComicInfo>')], 'rtl'),
                (2, [], None),
                (3, [('ComicInfo.xml', b'not XML')], None),
            )
            for book_id, metadata, expected in cases:
                db.add_format(book_id, 'CBZ', BytesIO(cbz([*pages, *metadata])), run_hooks=False)
            for book_id, metadata, expected in cases:
                with self.subTest(metadata=metadata):
                    _, manifest = self.manifest(conn, f'/comic-manifest/{book_id}')
                    self.ae(manifest['metadata'].get('readingProgression'), expected)
                    self.ae(manifest['metadata']['numberOfPages'], 2)
                    self.ae([x['type'] for x in manifest['readingOrder']], ['image/jpeg', 'image/png'])
                    for resource, data in zip(manifest['readingOrder'], (IMG, png)):
                        response, raw = self.request(conn, resource['href'])
                        self.ae(response.status, OK)
                        self.ae(raw, data)

    def request(self, conn, url, *, user=None, accept=None, headers=None, method='GET'):
        headers = dict(headers or {})
        if user:
            headers['Authorization'] = 'Basic ' + standard_b64encode(f'{user}:test'.encode()).decode()
        if accept:
            headers['Accept'] = accept
        conn.request(method, url, headers=headers)
        response = conn.getresponse()
        return response, response.read()

    def manifest(self, conn, url='/comic-manifest/1', **kwargs):
        response, raw = self.request(conn, url, **kwargs)
        self.ae(response.status, OK, raw)
        self.ae(response.getheader('Content-Type'), DIVINA_MIME)
        return response, json.loads(raw)

    def test_comic_page_order(self) -> None:
        pages = [('z/10.jpg', IMG), ('z/2.png', b'png'), ('z/1.JPG', IMG), ('__MACOSX/z/._0.jpg', IMG), ('notes.txt', b'text')]
        with ZipFile(BytesIO(cbz(pages))) as archive:
            self.ae(comic_pages(archive), ['z/1.JPG', 'z/2.png', 'z/10.jpg'])
        # As in Comic Input, use basenames when pages have different depths.
        with ZipFile(BytesIO(cbz([('a/z/1.jpg', IMG), ('b/2.jpg', IMG)]))) as archive:
            self.ae(comic_pages(archive), ['a/z/1.jpg', 'b/2.jpg'])

    def test_comic_manifest_and_pages(self) -> None:
        png = I('lt.png', data=True)
        data = cbz([('本/page10.png', png), ('本/page2.jpg', IMG), ('本/page1.png', png), ('notes.txt', b'text')])
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            db.add_format(1, 'CBZ', BytesIO(data), run_hooks=False)
            conn = server.connect()
            response, manifest = self.manifest(conn)
            self.ae(manifest['metadata']['conformsTo'], DIVINA_PROFILE)
            self.ae(manifest['metadata']['numberOfPages'], 3)
            self.ae(manifest['metadata']['title'], db.field_for('title', 1))
            self.ae(manifest['metadata']['author'], list(db.field_for('authors', 1)))
            self.assertIn('private', response.getheader('Cache-Control'))
            self.ae([x['type'] for x in manifest['readingOrder']], ['image/png', 'image/jpeg', 'image/png'])
            for resource, expected in zip(manifest['readingOrder'], (png, IMG, png)):
                response, raw = self.request(conn, resource['href'])
                self.ae(response.status, OK, raw)
                self.ae(response.getheader('Content-Type'), resource['type'])
                self.ae(raw, expected)
                response, raw = self.request(conn, resource['href'], method='HEAD')
                self.ae(response.status, OK)
                self.ae(raw, b'')
                self.ae(int(response.getheader('Content-Length')), len(expected))

    def test_comic_feed_is_lazy(self) -> None:
        data = cbz([('1.jpg', IMG), ('ComicInfo.xml', b'<ComicInfo><Manga>YesAndRightToLeft</Manga></ComicInfo>')])
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            db.add_format(1, 'CBZ', BytesIO(data), run_hooks=False)
            db.add_format(2, 'CBR', BytesIO(b'not opened'), run_hooks=False)
            conn = server.connect()
            url = server.handler.router.url_for('/opds/search', query='id:1 or id:2')
            with patch('calibre.srv.comic.open_comic', side_effect=AssertionError('feed opened an archive')):
                response, raw = self.request(conn, url, accept=OPDS2_MIME)
            self.ae(response.status, OK, raw)
            feed = json.loads(raw)
            comic = next(p for p in feed['publications'] if any(x['type'] == DIVINA_MIME for x in p['links']))
            # Page count and reading direction need the archive, so they are
            # only in the manifest
            self.assertNotIn('numberOfPages', comic['metadata'])
            self.assertNotIn('readingProgression', comic['metadata'])
            self.ae(sum(x['type'] == DIVINA_MIME for p in feed['publications'] for x in p['links']), 1)
            link = next(x for x in comic['links'] if x['type'] == DIVINA_MIME)
            self.ae(link['rel'], 'http://opds-spec.org/acquisition')
            self.manifest(conn, link['href'])
            archive_link = next(x for x in comic['links'] if '/get/cbz/' in x['href'])
            response, raw = self.request(conn, archive_link['href'])
            self.ae(response.status, OK)
            self.ae(raw, data)
            response, raw = self.request(conn, url, accept='application/atom+xml')
            self.ae(response.status, OK)
            self.assertNotIn(DIVINA_MIME.encode(), raw)

    def test_comic_image_alternates(self) -> None:
        pages = [('1.png', I('lt.png', data=True)), ('2.avif', STILL_AVIF), ('3.jxl', STILL_JXL)]
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            db.add_format(1, 'CBZ', BytesIO(cbz(pages)), run_hooks=False)
            conn = server.connect()
            _, manifest = self.manifest(conn)
            for resource, (name, expected) in zip(manifest['readingOrder'], pages):
                native, types = page_types(name)
                links = [resource, *resource.get('alternate', ())]
                self.ae(tuple(x['type'] for x in links), types)
                native_link = next(x for x in links if x['type'] == native)
                response, raw = self.request(conn, native_link['href'])
                self.ae((response.status, response.getheader('Content-Type'), raw), (OK, native, expected))
                for link in links:
                    if link is native_link:
                        continue
                    response, raw = self.request(conn, link['href'])
                    self.ae((response.status, response.getheader('Content-Type')), (OK, link['type']))
                    fmt, width, height = identify(raw)
                    self.ae('image/' + fmt, link['type'])
                    self.ae((width, height), identify(expected)[1:])
            self.assertIn('image/jpeg', convertible_types())
            # A source format can still be served intact when its decoder is
            # unavailable. Never advertise conversions the server cannot do.
            with patch('calibre.srv.comic.readable_types', return_value=frozenset()):
                self.ae(page_types('1.jxl'), ('image/jxl', ('image/jxl',)))
            self.assertIn('image/avif', readable_types())

    def test_comic_cache_and_replacement(self) -> None:
        png = I('lt.png', data=True)
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            db.add_format(1, 'CBZ', BytesIO(cbz([('1.png', png), ('2.jpg', IMG)])), run_hooks=False)
            conn = server.connect()
            manifest_response, manifest = self.manifest(conn)
            response, raw = self.request(conn, '/comic-manifest/1', headers={'If-None-Match': manifest_response.getheader('ETag')})
            self.ae((response.status, raw), (NOT_MODIFIED, b''))
            page = manifest['readingOrder'][0]
            alternate = next(x for x in page['alternate'] if x['type'] == 'image/jpeg')
            response, raw = self.request(conn, alternate['href'])
            etag = response.getheader('ETag')
            self.ae(response.status, OK)
            self.ae(identify(raw)[0], 'jpeg')
            with patch('calibre.srv.comic.image_to_data', side_effect=AssertionError('cached request transcoded')):
                response, raw = self.request(conn, alternate['href'], headers={'If-None-Match': etag})
            self.ae((response.status, raw), (NOT_MODIFIED, b''))
            replace_cbz(db, 1, cbz([('1.jpg', IMG)]))
            replacement_response, replacement = self.manifest(conn)
            self.assertNotEqual(replacement_response.getheader('ETag'), manifest_response.getheader('ETag'))
            self.ae(replacement['metadata']['numberOfPages'], 1)
            response, _ = self.request(conn, page['href'])
            self.ae(response.status, NOT_FOUND)
            response, raw = self.request(conn, replacement['readingOrder'][0]['href'])
            self.ae((response.status, raw), (OK, IMG))
            self.assertNotEqual(response.getheader('ETag'), etag)
            db.remove_formats({1: ('CBZ',)})
            self.ae(self.request(conn, '/comic-manifest/1')[0].status, NOT_FOUND)
            self.ae(self.request(conn, replacement['readingOrder'][0]['href'])[0].status, NOT_FOUND)

    def test_comic_revision_survives_restart(self) -> None:
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            db.add_format(1, 'CBZ', BytesIO(cbz([('1.jpg', IMG)])), run_hooks=False)
            _, manifest = self.manifest(server.connect())
        # The download cache is recreated by a new server, page URLs must not
        # depend on it
        with self.create_server() as server:
            response, raw = self.request(server.connect(), manifest['readingOrder'][0]['href'])
            self.ae((response.status, raw), (OK, IMG))
            self.assertIn('immutable', response.getheader('Cache-Control'))
            response, raw = self.request(server.connect(), '/comic-page/1/0')
            self.ae(response.status, OK)
            self.assertNotIn('immutable', response.getheader('Cache-Control'))

    def test_comic_unconvertible_pages(self) -> None:
        self.ae(page_types('1.gif'), ('image/gif', ('image/gif',)))
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            db.add_format(1, 'CBZ', BytesIO(cbz([('1.png', NOT_AN_IMAGE), ('2.jpg', IMG)])), run_hooks=False)
            conn = server.connect()
            _, manifest = self.manifest(conn)
            jpeg = next(x for x in manifest['readingOrder'][0]['alternate'] if x['type'] == 'image/jpeg')
            self.ae(self.request(conn, jpeg['href'])[0].status, NOT_FOUND)
            with patch('calibre.srv.comic.MAX_PAGE_SIZE', len(IMG) - 1):
                self.ae(self.request(conn, manifest['readingOrder'][1]['href'])[0].status, NOT_FOUND)
            with patch('calibre.srv.comic.MAX_PAGE_SIZE', len(IMG)):
                self.ae(self.request(conn, manifest['readingOrder'][1]['href'])[0].status, OK)

    def test_comic_misnamed_images(self) -> None:
        png = I('lt.png', data=True)
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            db.add_format(1, 'CBZ', BytesIO(cbz([('1.jpg', png), ('2.png', b'not an image')])), run_hooks=False)
            conn = server.connect()
            _, manifest = self.manifest(conn)
            response, raw = self.request(conn, manifest['readingOrder'][0]['href'])
            self.ae((response.status, response.getheader('Content-Type')), (OK, 'image/jpeg'))
            self.ae(identify(raw), ('jpeg', *identify(png)[1:]))
            self.ae(self.request(conn, manifest['readingOrder'][1]['href'])[0].status, NOT_FOUND)

    def test_comic_invalid_requests(self) -> None:
        with self.create_server() as server:
            db = server.handler.ctx.library_broker.get(None)
            conn = server.connect()
            for path in ('/comic-manifest/1', '/comic-manifest/99999', '/comic-page/1/0', '/comic-page/99999/0'):
                self.ae(self.request(conn, path)[0].status, NOT_FOUND, path)
            db.add_format(1, 'CBZ', BytesIO(b'not a zip archive'), run_hooks=False)
            self.ae(self.request(conn, '/comic-manifest/1')[0].status, NOT_FOUND)
            replace_cbz(db, 1, cbz([('notes.txt', b'not a page')]))
            self.ae(self.request(conn, '/comic-manifest/1')[0].status, NOT_FOUND)
            replace_cbz(db, 1, cbz([('1.jpg', IMG)]))
            for path in ('/comic-page/1/-1', '/comic-page/1/1', '/comic-page/1/x', '/comic-page/1/0?type=image/svg+xml'):
                self.ae(self.request(conn, path)[0].status, NOT_FOUND, path)
            # A bad library id must not silently select the default library.
            for path in ('/comic-manifest/1', '/comic-page/1/0'):
                self.ae(self.request(conn, path + '?library_id=missing')[0].status, NOT_FOUND)
            encrypted = bytearray(cbz([('1.jpg', IMG)]))
            encrypted[6] |= 1  # The encryption flag in the local file header
            encrypted[encrypted.index(b'PK\x01\x02') + 8] |= 1  # And in the central directory
            replace_cbz(db, 1, bytes(encrypted))
            self.ae(self.request(conn, '/comic-page/1/0')[0].status, NOT_FOUND)

    def test_comic_permissions_and_libraries(self) -> None:
        other_path = self.mkdtemp()
        self.create_db(other_path)
        with self.create_server(libraries=(self.library_path, other_path), auth=True, auth_mode='basic', url_prefix='/calibre') as server:
            ctx = server.handler.ctx
            first = ctx.library_broker.get(None)
            other_id = next(key for key, name in ctx.library_broker.library_map.items() if name == os.path.basename(other_path))
            other = ctx.library_broker.get(other_id)
            first.add_format(1, 'CBZ', BytesIO(cbz([('1.jpg', IMG)])), run_hooks=False)
            other.add_format(1, 'CBZ', BytesIO(cbz([('1.png', I('lt.png', data=True))])), run_hooks=False)
            ctx.user_manager.add_user('owner', 'test')
            ctx.user_manager.add_user('limited', 'test', restriction={'library_restrictions': {os.path.basename(self.library_path): 'id:2'}})
            ctx.user_manager.add_user('one-library', 'test', restriction={'allowed_library_names': [os.path.basename(self.library_path)]})
            conn = server.connect()
            base = '/calibre/comic-manifest/1'
            self.ae(self.request(conn, base)[0].status, UNAUTHORIZED)
            _, manifest = self.manifest(conn, base, user='owner')
            href = manifest['readingOrder'][0]['href']
            self.assertTrue(href.startswith('/calibre/comic-page/1/0?'))
            self.ae(parse_qs(urlsplit(href).query)['library_id'], [first.server_library_id])
            for url in (base, href):
                self.ae(self.request(conn, url, user='limited')[0].status, NOT_FOUND)
            feed_url = server.handler.router.url_for('/opds/search', query='id:1')
            self.ae(self.request(conn, feed_url, user='limited', accept=OPDS2_MIME)[0].status, NOT_FOUND)
            _, other_manifest = self.manifest(conn, base + '?' + urlencode({'library_id': other_id}), user='owner')
            other_href = other_manifest['readingOrder'][0]['href']
            self.assertNotEqual(other_href, href)
            response, raw = self.request(conn, other_href, user='owner')
            self.ae((response.status, raw), (OK, I('lt.png', data=True)))
            for url in (base + '?' + urlencode({'library_id': other_id}), other_href):
                self.ae(self.request(conn, url, user='one-library')[0].status, NOT_FOUND)
