#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
from contextlib import closing
from http.client import BAD_REQUEST, NOT_FOUND, OK
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from calibre.srv.changes import FormatsAdded
from calibre.srv.convert import FORBIDDEN_CLIENT_OPTIONS, JobStatus, conversion_jobs, get_conversion_options, sanitize_conversion_options
from calibre.srv.tests.ajax import make_request
from calibre.srv.tests.base import LibraryBaseTest


class ConvertTest(LibraryBaseTest):
    def test_conversion_status_notification(self):
        "Notify the GUI only when a completed conversion adds a format to the library"
        notify = Mock()
        with self.create_server(auth=True, auth_mode='basic', notify_changes=notify) as server:
            ctx = server.handler.router.ctx
            ctx.user_manager.add_user('testuser', 'testpw')
            db = ctx.library_broker.get(None)
            book_id = 1
            data = b'converted text'
            with closing(server.connect()) as conn:
                for ok in (False, True):
                    notify.reset_mock()
                    with self.subTest(ok=ok), TemporaryDirectory() as tdir:
                        # The endpoint deletes the job directory, so use a sub-directory of tdir
                        jobdir = os.path.join(tdir, 'job')
                        os.mkdir(jobdir)
                        job = JobStatus(1, book_id, jobdir, db.server_library_id, '', {'output_fmt': 'TXT'}, username='testuser')
                        job.running = False
                        job.ok = ok
                        with open(job.output_path, 'wb') as f:
                            f.write(data)
                        with patch.dict(conversion_jobs, {job.job_id: job}):
                            r, result = make_request(
                                conn,
                                f'/conversion/status/{job.job_id}',
                                prefix='',
                                username='testuser',
                                password='testpw',
                                method='POST',
                            )
                            self.ae(r.status, OK)
                            self.ae(result['ok'], ok)
                            if ok:
                                self.ae(db.format(book_id, 'TXT'), data)
                                notify.assert_called_once()
                                library_path, change = notify.call_args.args
                                self.ae(library_path, db.backend.library_path)
                                self.assertIsInstance(change, FormatsAdded)
                                self.ae(change.formats_map, {book_id: ('TXT',)})
                            else:
                                self.assertFalse(db.has_format(book_id, 'TXT'))
                                notify.assert_not_called()

    def test_conversion_output_fmt_validated(self):
        "output_fmt must be the name of an output format, as it is used to build the output path"
        with self.create_server(auth=True, auth_mode='basic') as server:
            server.handler.router.ctx.user_manager.add_user('testuser', 'testpw')
            with closing(server.connect()) as conn:

                def start(data):
                    return make_request(conn, '/conversion/start/1', prefix='', username='testuser', password='testpw', method='POST', data=data)[0]

                for output_fmt in ('/../../../../tmp/x.txt', '../x.epub', 'txt/../../x.epub', 'nosuchformat', 1, 'x' * 100000):
                    r = start(json.dumps({'input_fmt': 'epub', 'output_fmt': output_fmt, 'options': {}}).encode())
                    self.ae(r.status, BAD_REQUEST, f'output_fmt={output_fmt!r:.50}')
                # The error message must not echo back arbitrarily large client input
                r = start(json.dumps({'input_fmt': 'epub', 'output_fmt': 'x' * 100000, 'options': {}}).encode())
                self.assertLess(len(r.reason) + int(r.getheader('Content-Length', 0)), 1000)

    def test_conversion_input_fmt_validated(self):
        "input_fmt must be a format the book has, as it is used to build the source file path"
        with self.create_server(auth=True, auth_mode='basic') as server:
            server.handler.router.ctx.user_manager.add_user('testuser', 'testpw')
            with closing(server.connect()) as conn:
                # book 2 has only FMT1, so EPUB is not a valid input format for it
                for book_id, input_fmt in ((1, '/../../x.epub'), (1, 'epub/../../x'), (1, 'nosuchformat'), (1, 1), (1, None), (2, 'epub')):
                    data = json.dumps({'input_fmt': input_fmt, 'output_fmt': 'txt', 'options': {}}).encode()
                    r, result = make_request(conn, f'/conversion/start/{book_id}', prefix='', username='testuser', password='testpw', method='POST', data=data)
                    self.ae(r.status, BAD_REQUEST, f'book_id={book_id} input_fmt={input_fmt!r}')
                # A valid request, with formats in any case, is accepted
                jobs_manager = Mock()
                jobs_manager.start_job.return_value = 3
                server.handler.set_jobs_manager(jobs_manager)
                with patch.dict(conversion_jobs):
                    data = json.dumps({'input_fmt': 'epub', 'output_fmt': 'TXT', 'options': {}}).encode()
                    r, result = make_request(conn, '/conversion/start/1', prefix='', username='testuser', password='testpw', method='POST', data=data)
                    self.ae(r.status, OK)
                    self.ae(json.loads(result), 3)
                    job = conversion_jobs.pop(3)
                    self.ae(job.conversion_data['input_fmt'], 'EPUB')
                    self.assertTrue(job.output_path.endswith('output.txt'))
                    job.cleanup()

    def test_conversion_start_malformed_request(self):
        "A malformed conversion request must be rejected with a client error, not a server error"
        with self.create_server(auth=True, auth_mode='basic') as server:
            server.handler.router.ctx.user_manager.add_user('testuser', 'testpw')
            with closing(server.connect()) as conn:
                for data in (b'not json', b'[]', b'"epub"', b'null', b'{"input_fmt": "epub", "output_fmt": "txt", "options": []}'):
                    r, result = make_request(conn, '/conversion/start/1', prefix='', username='testuser', password='testpw', method='POST', data=data)
                    self.ae(r.status, BAD_REQUEST, f'data={data!r}')

    def test_conversion_status_only_for_job_owner(self):
        "Only the user that started a conversion job can query, abort or complete it"
        with self.create_server(auth=True, auth_mode='basic') as server:
            ctx = server.handler.router.ctx
            db = ctx.library_broker.get(None)
            lname = os.path.basename(db.backend.library_path)
            ctx.user_manager.add_user('owner', 'pw', restriction={'library_restrictions': {lname: 'id:1'}})
            ctx.user_manager.add_user('other', 'pw', restriction={'library_restrictions': {lname: 'id:2'}})
            jobs_manager = Mock()
            server.handler.set_jobs_manager(jobs_manager)
            book_id = 1
            data = b'converted text'

            def status(conn, job_id, username, query=''):
                return make_request(conn, f'/conversion/status/{job_id}{query}', prefix='', username=username, password='pw', method='POST')

            with closing(server.connect()) as conn, TemporaryDirectory() as tdir:
                jobdir = os.path.join(tdir, 'job')
                os.mkdir(jobdir)
                job = JobStatus(7, book_id, jobdir, db.server_library_id, '', {'output_fmt': 'TXT'}, username='owner')
                with open(job.output_path, 'wb') as f:
                    f.write(data)
                with patch.dict(conversion_jobs, {job.job_id: job}):
                    # Another user can neither abort a running job nor see its status
                    r, result = status(conn, job.job_id, 'other', '?abort_job=1')
                    self.ae(r.status, NOT_FOUND)
                    jobs_manager.abort_job.assert_not_called()
                    # Another user cannot complete the job, and the job is not consumed
                    job.running = False
                    r, result = status(conn, job.job_id, 'other')
                    self.ae(r.status, NOT_FOUND)
                    self.assertIn(job.job_id, conversion_jobs)
                    self.assertFalse(db.has_format(book_id, 'TXT'))
                    # The owner can complete the job
                    r, result = status(conn, job.job_id, 'owner')
                    self.ae(r.status, OK)
                    self.ae(db.format(book_id, 'TXT'), data)
                    self.assertNotIn(job.job_id, conversion_jobs)

    def test_conversion_status_only_in_job_library(self):
        "A conversion job can only be queried, aborted or completed in the library it was started in"
        other_library_path = self.mkdtemp()
        self.create_db(other_library_path)
        with self.create_server(libraries=(self.library_path, other_library_path), auth=True, auth_mode='basic') as server:
            ctx = server.handler.router.ctx
            ctx.user_manager.add_user('owner', 'pw')
            library_map = ctx.library_broker.library_map
            other_library_id = next(library_id for library_id, name in library_map.items() if name == os.path.basename(other_library_path))
            other_db = ctx.library_broker.get(other_library_id)
            default_db = ctx.library_broker.get(None)
            jobs_manager = Mock()
            server.handler.set_jobs_manager(jobs_manager)
            book_id = 1
            data = b'converted text'

            def status(conn, job_id, query):
                return make_request(conn, f'/conversion/status/{job_id}?{urlencode(query)}', prefix='', username='owner', password='pw', method='POST')

            with closing(server.connect()) as conn, TemporaryDirectory() as tdir:
                jobdir = os.path.join(tdir, 'job')
                os.mkdir(jobdir)
                job = JobStatus(7, book_id, jobdir, other_library_id, '', {'output_fmt': 'TXT'}, username='owner')
                with open(job.output_path, 'wb') as f:
                    f.write(data)
                with patch.dict(conversion_jobs, {job.job_id: job}):
                    # The same user, but in another library, can neither abort a running job nor see its status
                    r, result = status(conn, job.job_id, {'abort_job': '1'})
                    self.ae(r.status, NOT_FOUND)
                    jobs_manager.abort_job.assert_not_called()
                    # The job cannot be completed into the wrong library, and is not consumed
                    job.running = False
                    r, result = status(conn, job.job_id, {})
                    self.ae(r.status, NOT_FOUND)
                    self.assertIn(job.job_id, conversion_jobs)
                    self.assertFalse(default_db.has_format(book_id, 'TXT'))
                    self.assertFalse(other_db.has_format(book_id, 'TXT'))
                    # In the job's own library it can be completed
                    r, result = status(conn, job.job_id, {'library_id': other_library_id})
                    self.ae(r.status, OK)
                    self.ae(other_db.format(book_id, 'TXT'), data)
                    self.assertFalse(default_db.has_format(book_id, 'TXT'))
                    self.assertNotIn(job.job_id, conversion_jobs)

    def test_sanitize_conversion_options(self):
        "Client supplied conversion options must be restricted to the advertised, safe set"
        with self.create_server() as server:
            ctx = server.handler.router.ctx
            db = ctx.library_broker.get(None)
            book_id = 1  # has an EPUB format in the test library

            # A genuinely advertised option should survive so we know the
            # allowlist is not simply dropping everything.
            allowed = set(get_conversion_options('epub', 'epub', book_id, db)['options'])
            self.assertTrue(allowed, 'expected the server to advertise at least one conversion option')
            good = min(allowed)

            client_options = {
                good: 'somevalue',
                # dangerous path/URL/guard options a remote client must never set
                'cover': '/etc/passwd',
                'read_metadata_from_opf': '/etc/passwd',
                'debug_pipeline': '/tmp/attacker',
                'allow_local_files_outside_root': True,
                # not advertised by the API at all
                'this_option_does_not_exist': 'x',
            }
            sanitized = sanitize_conversion_options(ctx, db, 'epub', 'epub', book_id, client_options)

            self.assertIn(good, sanitized)
            self.assertEqual(sanitized[good], 'somevalue')
            for name in FORBIDDEN_CLIENT_OPTIONS:
                self.assertNotIn(name, sanitized, f'forbidden option {name!r} was not dropped')
            self.assertNotIn('this_option_does_not_exist', sanitized)
