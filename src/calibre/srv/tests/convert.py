#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import os
from contextlib import closing
from http.client import OK
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

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
                        job = JobStatus(1, book_id, jobdir, db.server_library_id, '', {'output_fmt': 'TXT'})
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
