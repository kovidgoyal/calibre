#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
from contextlib import closing
from datetime import datetime
from http.client import BAD_REQUEST, FORBIDDEN, NOT_FOUND, OK
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from calibre.ebooks.metadata.book.base import Metadata
from calibre.srv.metadata_download import (
    MAX_DOWNLOADS_PER_USER,
    DownloadJob,
    IdentifyCaches,
    download_covers,
    download_jobs,
    download_metadata,
    finished_too_soon,
    identify_caches,
    job_done,
    leftover_covers_dirs,
    starting_downloads,
)
from calibre.srv.tests.ajax import make_request
from calibre.srv.tests.base import LibraryBaseTest
from calibre.utils.date import UNDEFINED_DATE, local_tz
from calibre.utils.monotonic import monotonic
from calibre.utils.resources import get_image_path as I
from polyglot.binary import as_base64_bytes

if TYPE_CHECKING:
    from http.client import HTTPConnection, HTTPResponse
    from queue import Queue

    from calibre.srv.tests.ajax import ResponseData


def start(conn: HTTPConnection, book_id: int, username: str, data: object, library_id: str = '') -> tuple[HTTPResponse, ResponseData]:
    url = f'/metadata-download/start/{book_id}' + (f'/{library_id}' if library_id else '')
    return make_request(conn, url, prefix='', username=username, password='pw', method='POST', data=json.dumps(data).encode())


def make_request_headers(username: str) -> dict[str, bytes]:
    return {'Authorization': b'Basic ' + as_base64_bytes(username + ':pw')}


def status(conn: HTTPConnection, job_id: int, username: str, query: str = '', library_id: str = '') -> tuple[HTTPResponse, ResponseData]:
    url = f'/metadata-download/status/{job_id}' + (f'/{library_id}' if library_id else '') + query
    return make_request(conn, url, prefix='', username=username, password='pw', method='POST')


class MetadataDownloadTest(LibraryBaseTest):
    def test_metadata_download_start(self) -> None:
        "Only users that can change the metadata of the book can download metadata for it"
        with self.create_server(auth=True, auth_mode='basic') as server:
            ctx = server.handler.router.ctx
            db = ctx.library_broker.get(None)
            lname = os.path.basename(db.backend.library_path)
            ctx.user_manager.add_user('rw', 'pw')
            ctx.user_manager.add_user('ro', 'pw', readonly=True)
            ctx.user_manager.add_user('restricted', 'pw', restriction={'library_restrictions': {lname: 'id:1'}})
            jobs_manager = Mock()
            jobs_manager.start_job.side_effect = range(100, 200)
            server.handler.set_jobs_manager(jobs_manager)
            query = {'title': 'A title', 'authors': ['An author'], 'identifiers': {'isbn': '123'}, 'comments': '<p>xxx</p>'}
            with (
                closing(server.connect()) as conn,
                patch('calibre.ebooks.metadata.sources.update.update_sources') as update_sources,
                patch.dict(download_jobs, clear=True),
            ):
                for username in ('ro', 'restricted'):
                    r, result = start(conn, 1, username, query)
                    self.ae(r.status, FORBIDDEN, username)
                r, result = start(conn, 1000, 'rw', query)
                self.ae(r.status, NOT_FOUND)
                for bad in ([], {'title': 1}, {'authors': 'x'}, {'authors': [1]}, {'identifiers': {'isbn': 1}}, {'comments': []}, {'title': ''}):
                    r, result = start(conn, 1, 'rw', bad)
                    self.ae(r.status, BAD_REQUEST, bad)
                jobs_manager.start_job.assert_not_called()
                update_sources.assert_not_called()

                r, result = start(conn, 1, 'rw', query)
                self.ae(r.status, OK)
                self.ae(result, {'job_id': 100})
                update_sources.assert_called_once_with()
                args = jobs_manager.start_job.call_args[0]
                self.ae(args[1:3], ('calibre.srv.metadata_download', 'download_metadata'))
                self.ae(args[3], ('A title', ['An author'], {'isbn': '123'}, '<p>xxx</p>'))
                dj = download_jobs[100]
                self.ae((dj.username, dj.library_id, dj.book_id, dj.running), ('rw', db.server_library_id, 1, True))

                # A user can only have a few unfinished downloads
                for i in range(MAX_DOWNLOADS_PER_USER - 1):
                    self.ae(start(conn, 1, 'rw', query)[0].status, OK)
                r, result = start(conn, 1, 'rw', query)
                self.ae(r.status, 429)
                self.ae(len(download_jobs), MAX_DOWNLOADS_PER_USER)
                download_jobs[100].running = False
                self.ae(start(conn, 1, 'rw', query)[0].status, OK)

                # Downloads that are being started count towards the limit, so
                # that simultaneous requests cannot exceed it
                download_jobs.clear()

                def start_job(*a: object, **kw: object) -> int:
                    self.ae(starting_downloads['rw'], 1)
                    return 200

                jobs_manager.start_job.side_effect = start_job
                self.ae(start(conn, 1, 'rw', query)[0].status, OK)
                self.assertFalse(starting_downloads)

                # A job that finishes before it is recorded is not lost
                def start_and_finish_job(*a: object, **kw: object) -> int:
                    job_done(Mock(job_id=201, failed=False, was_aborted=False, result={'results': [], 'ignore_fields': [], 'log': '', 'caches': {}}))
                    return 201

                jobs_manager.start_job.side_effect = start_and_finish_job
                self.ae(start(conn, 1, 'rw', query)[0].status, OK)
                self.assertFalse(finished_too_soon)
                self.assertFalse(download_jobs[201].running)
                self.assertTrue(download_jobs[201].ok)

    def test_metadata_download_status(self) -> None:
        "Only the user that started a download, in the library it was started in, can get its results or abort it"
        other_library_path = self.mkdtemp()
        self.create_db(other_library_path)
        with self.create_server(libraries=(self.library_path, other_library_path), auth=True, auth_mode='basic') as server:
            ctx = server.handler.router.ctx
            library_id = ctx.library_broker.get(None).server_library_id
            other_library_id = next(lid for lid in ctx.library_broker.library_map if lid != library_id)
            ctx.user_manager.add_user('owner', 'pw')
            ctx.user_manager.add_user('other', 'pw')
            jobs_manager = Mock()
            server.handler.set_jobs_manager(jobs_manager)
            results = {
                'results': [{'title': 'Downloaded', 'languages': ['eng', 'fra']}],
                'ignore_fields': ['tags'],
                'log': 'the log',
                'caches': {'Source': {'isbn_to_identifier': {}, 'identifier_to_cover': {'1': 'http://x'}}},
            }
            with closing(server.connect()) as conn, patch.dict(download_jobs, clear=True), patch.dict(identify_caches, clear=True):
                download_jobs[7] = dj = DownloadJob(7, 'owner', library_id, 1)
                # Other users and other libraries can neither see nor abort the download
                for username, lid in (('other', ''), ('other', library_id), ('owner', other_library_id)):
                    self.ae(status(conn, 7, username, '?abort=1', lid)[0].status, NOT_FOUND)
                    self.ae(status(conn, 7, username, library_id=lid)[0].status, NOT_FOUND)
                jobs_manager.abort_job.assert_not_called()
                r, result = status(conn, 7, 'owner')
                self.ae((r.status, result), (OK, {'running': True}))

                # The results are returned once, to the owner
                job = Mock(job_id=7, failed=False, was_aborted=False, result=results)
                job_done(job)
                self.ae(status(conn, 7, 'other')[0].status, NOT_FOUND)
                r, result = status(conn, 7, 'owner', library_id=library_id)
                self.ae(r.status, OK)
                self.ae(result['results'], [{'title': 'Downloaded', 'languages': ['English', 'French']}])
                self.ae((result['ok'], result['running'], result['ignore_fields'], result['log']), (True, False, ['tags'], 'the log'))
                # The caches have URLs that the metadata sources download, so
                # they must stay on the server
                self.assertNotIn('caches', result)
                self.ae(identify_caches[7].caches, results['caches'])
                self.ae((identify_caches[7].username, identify_caches[7].library_id), ('owner', library_id))
                self.assertNotIn(7, download_jobs)
                self.ae(status(conn, 7, 'owner')[0].status, NOT_FOUND)

                # Failures are reported with the traceback
                download_jobs[8] = DownloadJob(8, 'owner', library_id, 1)
                job_done(Mock(job_id=8, failed=True, was_aborted=False, traceback='the traceback', result=None))
                r, result = status(conn, 8, 'owner')
                self.ae(result, {'running': False, 'ok': False, 'was_aborted': False, 'traceback': 'the traceback'})

                # Aborting a running download, it is remembered until it
                # finishes, so that it counts towards the limit for the user
                jobs_manager.abort_job.return_value = False
                download_jobs[9] = dj = DownloadJob(9, 'owner', library_id, 1)
                r, result = status(conn, 9, 'owner', '?abort=1')
                self.ae(result, {'running': False, 'ok': False, 'was_aborted': True})
                jobs_manager.abort_job.assert_called_once_with(9)
                self.assertTrue(dj.abort_requested)
                self.assertIn(9, download_jobs)
                self.ae(status(conn, 9, 'owner')[0].status, NOT_FOUND)
                job_done(Mock(job_id=9, failed=True, was_aborted=True, traceback='', result=None))
                self.assertNotIn(9, download_jobs)
                self.assertFalse(finished_too_soon)

                # Aborting a download that is waiting for a worker, it will
                # never run, so is forgotten
                jobs_manager.abort_job.return_value = True
                download_jobs[10] = DownloadJob(10, 'owner', library_id, 1)
                r, result = status(conn, 10, 'owner', '?abort=1')
                self.ae(result, {'running': False, 'ok': False, 'was_aborted': True})
                self.assertNotIn(10, download_jobs)

    def test_metadata_download_abandoned(self) -> None:
        "Downloads whose results are no longer being asked for are aborted"
        with self.create_server(auth=True, auth_mode='basic') as server:
            ctx = server.handler.router.ctx
            library_id = ctx.library_broker.get(None).server_library_id
            ctx.user_manager.add_user('owner', 'pw')
            jobs_manager = Mock()
            jobs_manager.abort_job.return_value = False
            server.handler.set_jobs_manager(jobs_manager)
            with closing(server.connect()) as conn, patch.dict(download_jobs, clear=True):
                download_jobs[1] = running = DownloadJob(1, 'owner', library_id, 1)
                download_jobs[2] = finished = DownloadJob(2, 'owner', library_id, 1)
                download_jobs[3] = DownloadJob(3, 'owner', library_id, 1)
                finished.running = False
                running.last_check_at = finished.last_check_at = running.last_check_at - 1000
                self.ae(status(conn, 3, 'owner')[1], {'running': True})
                jobs_manager.abort_job.assert_called_once_with(1)
                self.assertTrue(running.abort_requested)
                self.ae(sorted(download_jobs), [1, 3])
                # The abort is not repeated
                status(conn, 3, 'owner')
                jobs_manager.abort_job.assert_called_once_with(1)

    def test_metadata_download_worker(self) -> None:
        "Downloaded metadata is converted to what the metadata editor in the browser needs"
        # Results from several sources that are merged by identify() do not
        # have an identify_plugin
        mi = Metadata('Title', ['Author One', 'Author Two'])
        mi.publisher = 'Publisher'
        mi.pubdate = datetime(2001, 2, 3, 23, 30, tzinfo=local_tz)
        mi.series, mi.series_index = 'Series', 2
        mi.rating = 3.6
        mi.tags = ['One', 'Two']
        mi.identifiers = {'isbn': '9780316519182'}
        mi.languages = ['en', 'fr', 'xyzzy']
        mi.comments = '<p>Downloaded comments</p>'
        empty = Metadata('Unknown')
        empty.pubdate = UNDEFINED_DATE
        empty.series = '  '
        plain = Metadata('Plain')
        plain.comments = 'Para one\n\nPara two'
        plain.rating = 4.8
        identify = Mock(return_value=[mi, empty, plain])

        def run(prefs: dict[str, object], current_comments: str = '') -> object:
            with (
                patch('calibre.ebooks.metadata.sources.identify.identify', identify),
                patch('calibre.ebooks.metadata.sources.identify.msprefs', prefs),
                patch('calibre.ebooks.metadata.sources.update.patch_plugins'),
                patch('calibre.scraper.simple.cleanup_overseers', return_value=lambda: None),
            ):
                return download_metadata('Title', ['Author One'], {'isbn': '1'}, current_comments)

        ans = run({'append_comments': False, 'ignore_fields': ['tags', 'identifier:isbn']}, 'current comments')
        self.ae(identify.call_args[1], {'title': 'Title', 'authors': ['Author One'], 'identifiers': {'isbn': '1'}})
        self.ae(ans['ignore_fields'], ['tags'])
        self.ae(
            ans['results'],
            [
                {
                    'title': 'Title',
                    'authors': ['Author One', 'Author Two'],
                    'publisher': 'Publisher',
                    'pubdate': '2001-02-03',
                    'series': 'Series',
                    'series_index': 2.0,
                    'rating': 7,
                    'tags': ['One', 'Two'],
                    'identifiers': {'isbn': '9780316519182'},
                    'languages': ['eng', 'fra'],
                    'comments': '<p>Downloaded comments</p>',
                },
                {},
                {
                    'title': 'Plain',
                    # Truncated, as in the Edit metadata dialog
                    'rating': 9,
                    # Converted to HTML, as in the Edit metadata dialog
                    'comments': '<p class="description">Para one</p>\n<p class="description">Para two</p>',
                },
            ],
        )
        # Downloaded comments are appended to the current comments only when
        # the user has chosen that and there are current comments
        ans = run({'append_comments': True, 'ignore_fields': []}, 'Current comments')
        merged = ans['results'][0]['merged_comments']
        self.assertIn('Current comments', merged)
        self.assertLess(merged.index('Current comments'), merged.index('Downloaded comments'))
        self.assertNotIn('merged_comments', run({'append_comments': True, 'ignore_fields': []}, ' ')['results'][0])

    def test_cover_download(self) -> None:
        "Covers are downloaded for the user that asked, using the caches from that user's metadata download, and served until the user is done"
        from calibre.utils.img import save_cover_data_to

        jpeg = save_cover_data_to(I('lt.png', data=True))
        with self.create_server(auth=True, auth_mode='basic') as server:
            ctx = server.handler.router.ctx
            db = ctx.library_broker.get(None)
            library_id = db.server_library_id
            for username in ('owner', 'other'):
                ctx.user_manager.add_user(username, 'pw')
            ctx.user_manager.add_user('ro', 'pw', readonly=True)
            jobs_manager = Mock()
            jobs_manager.start_job.side_effect = range(300, 400)
            jobs_manager.abort_job.return_value = False
            server.handler.set_jobs_manager(jobs_manager)
            query = {'title': 'A title', 'authors': ['An author'], 'identifiers': {'isbn': '123'}, 'metadata_download_id': 7}

            def cover(conn: HTTPConnection, job_id: int, num: int, username: str) -> tuple[HTTPResponse, bytes]:
                conn.request('GET', f'/metadata-download/cover/{job_id}/{num}', headers=make_request_headers(username))
                r = conn.getresponse()
                return r, r.read()

            with (
                closing(server.connect()) as conn,
                patch('calibre.ebooks.metadata.sources.update.update_sources'),
                patch.dict(download_jobs, clear=True),
                patch.dict(identify_caches, clear=True),
            ):
                caches = {'Source': {'isbn_to_identifier': {}, 'identifier_to_cover': {'123': 'http://x'}}}
                identify_caches[7] = IdentifyCaches('owner', library_id, caches, monotonic())
                identify_caches[8] = IdentifyCaches('other', library_id, caches, monotonic())

                def start_covers(username: str, q: dict[str, object] = query) -> tuple[HTTPResponse, ResponseData]:
                    return make_request(
                        conn, '/metadata-download/start-covers/1', prefix='', username=username, password='pw', method='POST', data=json.dumps(q).encode()
                    )

                self.ae(start_covers('ro')[0].status, FORBIDDEN)
                self.ae(start_covers('owner', {**query, 'metadata_download_id': 'x'})[0].status, BAD_REQUEST)
                # The caches of another user's download are not used
                r, result = start_covers('owner', {**query, 'metadata_download_id': 8})
                self.ae((r.status, result), (OK, {'job_id': 300}))
                args = jobs_manager.start_job.call_args[0]
                self.ae(args[2], 'download_covers')
                title, authors, identifiers, used_caches, covers_dir = args[3]
                self.ae((title, authors, identifiers, used_caches), ('A title', ['An author'], {'isbn': '123'}, {}))
                self.assertTrue(os.path.isdir(covers_dir))
                self.ae(download_jobs[300].covers_dir, covers_dir)
                status(conn, 300, 'owner', '?abort=1')
                # The covers of aborted downloads are removed, once the worker
                # is no longer writing them
                self.assertTrue(os.path.exists(covers_dir))
                job_done(Mock(job_id=300, failed=True, was_aborted=True, traceback='', result=None))
                self.assertFalse(os.path.exists(covers_dir))

                r, result = start_covers('owner')
                job_id = result['job_id']
                title, authors, identifiers, used_caches, covers_dir = jobs_manager.start_job.call_args[0][3]
                self.ae(used_caches, caches)

                # Covers are listed as they are downloaded
                self.ae(status(conn, job_id, 'owner')[1], {'running': True, 'covers': []})
                for num, (width, height) in enumerate(((10, 10), (20, 30))):
                    with open(os.path.join(covers_dir, f'{num}.jpg'), 'wb') as f:
                        f.write(jpeg)
                    with open(os.path.join(covers_dir, f'{num}.json'), 'w') as f:
                        json.dump({'source': f'S{num}', 'width': width, 'height': height}, f)
                # Files that are still being written are ignored
                with open(os.path.join(covers_dir, '2.json.tmp'), 'w') as f:
                    f.write('{')
                r, result = status(conn, job_id, 'owner')
                self.ae([c['num'] for c in result['covers']], [0, 1])
                self.ae(result['covers'][1], {'num': 1, 'source': 'S1', 'width': 20, 'height': 30})

                # Only the user that started the download can get its covers
                r, data = cover(conn, job_id, 0, 'owner')
                self.ae((r.status, r.getheader('Content-Type'), data), (OK, 'image/jpeg', jpeg))
                for num, username in ((0, 'other'), (5, 'owner'), (-1, 'owner')):
                    self.ae(cover(conn, job_id, num, username)[0].status, NOT_FOUND)

                # When finished, the covers are sorted by size and kept
                job_done(Mock(job_id=job_id, failed=False, was_aborted=False, result='cover log'))
                for i in range(2):
                    r, result = status(conn, job_id, 'owner')
                    self.ae((result['running'], result['ok'], result['log']), (False, True, 'cover log'))
                    self.ae([c['num'] for c in result['covers']], [1, 0])
                self.ae(cover(conn, job_id, 1, 'owner')[0].status, OK)
                # Until the browser is done with them
                r, result = status(conn, job_id, 'owner', '?abort=1')
                self.ae(result, {'running': False, 'ok': False, 'was_aborted': True})
                jobs_manager.abort_job.assert_called_once_with(300)
                self.assertNotIn(job_id, download_jobs)
                self.assertFalse(os.path.exists(covers_dir))
                self.ae(cover(conn, job_id, 0, 'owner')[0].status, NOT_FOUND)

                # Abandoned covers are removed
                r, result = start_covers('owner')
                covers_dir = download_jobs[result['job_id']].covers_dir
                job_done(Mock(job_id=result['job_id'], failed=False, was_aborted=False, result=''))
                download_jobs[result['job_id']].last_check_at -= 1000
                identify_caches[7] = identify_caches[7]._replace(created_at=identify_caches[7].created_at - 10000)
                status(conn, 9999, 'owner')
                self.assertNotIn(result['job_id'], download_jobs)
                self.assertFalse(os.path.exists(covers_dir))
                self.assertNotIn(7, identify_caches)

    def test_cover_download_worker(self) -> None:
        "The worker saves the covers that can be set as the cover of a book, as they are downloaded"
        from calibre.utils.img import save_cover_data_to

        jpeg = save_cover_data_to(I('lt.png', data=True))
        png = I('lt.png', data=True)
        good, bad = Mock(), Mock()
        good.name, bad.name = 'Good', 'Bad'

        def run_download(log: object, results: Queue[object], abort: object, **kw: object) -> None:
            self.ae(kw, {'title': 'T', 'authors': ['A'], 'identifiers': {'isbn': '1'}})
            results.put((bad, 60, 60, 'png', png))
            results.put((good, 60, 80, 'jpeg', jpeg))

        caches = {'Source': {'isbn_to_identifier': {}, 'identifier_to_cover': {}}}
        with (
            TemporaryDirectory() as covers_dir,
            patch('calibre.ebooks.metadata.sources.covers.run_download', run_download),
            patch('calibre.ebooks.metadata.sources.base.load_caches') as load_caches,
            patch('calibre.ebooks.metadata.sources.update.patch_plugins'),
            patch('calibre.scraper.simple.cleanup_overseers', return_value=lambda: None),
        ):
            log = download_covers('T', ['A'], {'isbn': '1'}, caches, covers_dir)
            load_caches.assert_called_once_with(caches)
            self.ae(sorted(os.listdir(covers_dir)), ['0.jpg', '0.json'])
            with open(os.path.join(covers_dir, '0.jpg'), 'rb') as f:
                self.ae(f.read(), jpeg)
            with open(os.path.join(covers_dir, '0.json')) as f:
                self.ae(json.load(f), {'source': 'Good', 'width': 60, 'height': 80})
            self.assertIn('Bad', log)

    def test_cover_download_cleanup(self) -> None:
        "The covers of cover downloads are removed when they are aborted before starting, or could not be removed at first"
        with self.create_server(auth=True, auth_mode='basic') as server:
            ctx = server.handler.router.ctx
            library_id = ctx.library_broker.get(None).server_library_id
            ctx.user_manager.add_user('owner', 'pw')
            jobs_manager = Mock()
            server.handler.set_jobs_manager(jobs_manager)
            with closing(server.connect()) as conn, patch.dict(download_jobs, clear=True), TemporaryDirectory() as tdir:
                # Aborted while waiting for a worker, so it never runs
                jobs_manager.abort_job.return_value = True
                covers_dir = os.path.join(tdir, 'waiting')
                os.mkdir(covers_dir)
                download_jobs[1] = DownloadJob(1, 'owner', library_id, 1, covers_dir)
                self.ae(status(conn, 1, 'owner', '?abort=1')[1], {'running': False, 'ok': False, 'was_aborted': True})
                self.assertNotIn(1, download_jobs)
                self.assertFalse(os.path.exists(covers_dir))

                # The worker was still writing when the directory was removed
                covers_dir = os.path.join(tdir, 'leftover')
                os.mkdir(covers_dir)
                dj = download_jobs[2] = DownloadJob(2, 'owner', library_id, 1, covers_dir)
                dj.running = False
                with patch('calibre.srv.metadata_download.shutil.rmtree'):
                    status(conn, 2, 'owner', '?abort=1')
                self.assertTrue(os.path.exists(covers_dir))
                self.assertIn(covers_dir, leftover_covers_dirs)
                status(conn, 3, 'owner')
                self.assertFalse(os.path.exists(covers_dir))
                self.assertNotIn(covers_dir, leftover_covers_dirs)
