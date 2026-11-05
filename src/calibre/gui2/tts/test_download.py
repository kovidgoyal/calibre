#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, calibre contributors

import hashlib
import os
import re
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

if TYPE_CHECKING:
    from qt.core import QObject


# Keep this small, the download is served in 1 KiB chunks and many tests
# time out once per chunk. Five chunks is enough to exceed MAX_RETRIES.
DATA = b'voice model data' * 64 * 5


class DownloadServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        self.stopped = Event()
        self.requests: list[tuple[str, str, str]] = []
        super().__init__(('127.0.0.1', 0), DownloadHandler)


class DownloadHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server = cast('DownloadServer', self.server)
        stopped = server.stopped
        server.requests.append((self.path, self.headers.get('Range', ''), self.headers.get('If-Range', '')))
        count = sum(path == self.path for path, _, _ in server.requests)
        if self.path == '/no-headers':
            stopped.wait(10)
            return
        if self.path == '/growing-stall':
            # Each attempt gets further before stalling, without support for resuming
            self.send_response(200)
            self.send_header('Content-Length', str(len(DATA)))
            self.end_headers()
            try:
                self.wfile.write(DATA[: 1024 * count])
                self.wfile.flush()
            except BrokenPipeError, ConnectionResetError:
                return
            stopped.wait(10)
            return
        if self.path in ('/corrupt', '/corrupt-once'):
            data = DATA if self.path == '/corrupt-once' and count > 1 else b'X' + DATA[1:]
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
                self.wfile.flush()
            except BrokenPipeError, ConnectionResetError:
                return
            return
        if self.path == '/not-modified':
            self.send_response(304)
            self.end_headers()
            return
        if self.path == '/error':
            self.send_error(503)
            return
        if self.path == '/not-found':
            self.send_error(404)
            return
        if self.path == '/transient' and count == 1:
            self.send_error(503)
            return
        if self.path.startswith('/range'):
            match = re.fullmatch(r'bytes=(\d+)-(\d*)', self.headers.get('Range', ''))
            ranged = match is not None and not (self.path == '/range-ignore' and count > 1)
            start, end = 0, len(DATA) - 1
            if ranged and match is not None:
                start = int(match[1])
                if match[2]:
                    end = min(int(match[2]), end)
                elif self.path == '/range-capped':
                    # Servers may return less than the requested range
                    end = min(start + 1023, end)
            self.send_response(206 if ranged else 200)
            if self.path != '/range-no-validator':
                self.send_header('ETag', '"model-v2"' if self.path == '/range-changed-validator' and count > 1 else '"model-v1"')
            if ranged:
                header_start = start + 1 if self.path == '/range-wrong-offset' and count > 1 else start
                self.send_header('Content-Range', f'bytes {header_start}-{end}/{len(DATA)}')
            length = end - start + 1
            if self.path == '/range-wrong-length' and ranged:
                length += 1
            self.send_header('Content-Length', str(length))
            self.end_headers()
            try:
                if self.path == '/range-always-stall' and length > 1024:
                    self.wfile.write(DATA[start : start + 1024])
                    self.wfile.flush()
                    stopped.wait(10)
                elif count == 1 and self.path in {
                    '/range-resume',
                    '/range-disconnect',
                    '/range-ignore',
                    '/range-wrong-offset',
                    '/range-unhashed',
                    '/range-no-validator',
                    '/range-changed-validator',
                    '/range-wrong-length',
                    '/range-capped',
                }:
                    self.wfile.write(DATA[start : start + 1024])
                    self.wfile.flush()
                    if self.path != '/range-disconnect':
                        stopped.wait(10)
                else:
                    self.wfile.write(DATA[start : end + 1])
                    self.wfile.flush()
            except BrokenPipeError, ConnectionResetError:
                return
            return
        self.send_response(200)
        if not self.path.startswith('/no-length'):
            self.send_header('Content-Length', str(len(DATA)))
        self.end_headers()
        try:
            if self.path == '/stall':
                self.wfile.write(DATA[:2048])
                self.wfile.flush()
                stopped.wait(10)
            elif self.path == '/slow':
                for start in range(0, len(DATA), 1024):
                    self.wfile.write(DATA[start : start + 1024])
                    self.wfile.flush()
                    if stopped.wait(0.03):
                        break
            else:
                self.wfile.write(DATA)
                self.wfile.flush()
                if self.path == '/no-length-stall':
                    stopped.wait(10)
        except BrokenPipeError, ConnectionResetError:
            # Expected when the client cancels or times out a request.
            return

    def log_message(self, format: str, *args: object) -> None:
        return


def run_download_tests_in_worker() -> None:
    from qt.core import QApplication, QDialog, QEventLoop, QNetworkAccessManager, QNetworkProxy, QTimer, sip

    from calibre.gui2.tts import download
    from calibre.utils.localization import _

    # A QApplication must not be created in the main test runner process.
    app = QApplication([])
    QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))

    class NetworkAccessManager(QNetworkAccessManager):
        MAX_TRANSFER_TIMEOUT_MS = 100

        def setTransferTimeout(self, timeout: int = 30_000) -> None:
            # Exercise real network timeouts without waiting a minute per test.
            super().setTransferTimeout(min(timeout, self.MAX_TRANSFER_TIMEOUT_MS))

    class DownloadTests(unittest.TestCase):
        def setUp(self) -> None:
            self.retry_delay = patch.object(download.ProgressBar, 'RETRY_DELAY_MS', 10)
            self.retry_delay.start()
            self.addCleanup(self.retry_delay.stop)
            # Fewer retries keep the tests that wait for timeouts fast
            self.max_retries = patch.object(download.ProgressBar, 'MAX_RETRIES', 2)
            self.max_retries.start()
            self.addCleanup(self.max_retries.stop)
            self.directory = tempfile.TemporaryDirectory()
            self.addCleanup(self.directory.cleanup)
            self.errors: list[str] = []
            self.server = DownloadServer()
            self.thread = Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
            self.thread.start()
            self.dialog: download.DownloadResources | None = None

        def use_long_transfer_timeout(self) -> None:
            # For tests that must not time out. The short default timeout is
            # too close to the gaps between chunks of /slow on loaded CI
            # machines. This costs nothing as these downloads never stall.
            p = patch.object(NetworkAccessManager, 'MAX_TRANSFER_TIMEOUT_MS', 5000)
            p.start()
            self.addCleanup(p.stop)

        def tearDown(self) -> None:
            self.close_dialog()
            self.server.stopped.set()
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(5)

        def close_dialog(self) -> None:
            if self.dialog is not None:
                self.dialog.reject()
                app.processEvents()
                sip.delete(self.dialog)
                self.dialog = None

        def run_download(
            self,
            *paths: str,
            sha256: str | None = None,
            cancel: bool = False,
            cancel_retry: bool = False,
            verified: bool = True,
            write_error: bool = False,
        ) -> download.DownloadResources:
            self.close_dialog()
            self.errors.clear()
            resources = {f'http://127.0.0.1:{self.server.server_port}/{path}': (os.path.join(self.directory.name, path), path) for path in paths}
            hashes = {url: sha256 or hashlib.sha256(DATA).hexdigest() for url in resources} if verified else {}

            def error_dialog(parent: QObject, title: str, message: str, det_msg: str, show: bool) -> None:
                self.errors.append(det_msg)

            with patch.object(download, 'QNetworkAccessManager', NetworkAccessManager), patch.object(download, 'error_dialog', error_dialog):
                self.dialog = dialog = download.DownloadResources('test', 'test', resources, hashes=hashes)
                if write_error:
                    writer = patch.object(dialog.bars[0].file_obj, 'write', side_effect=OSError('disk full'))
                    writer.start()
                    self.addCleanup(writer.stop)
                loop = QEventLoop()
                completed: list[int] = []

                def finished(result: int) -> None:
                    completed.append(result)
                    loop.quit()

                dialog.finished.connect(finished)
                watchdog = QTimer()
                watchdog.setSingleShot(True)
                watchdog.timeout.connect(loop.quit)
                bytes_before_cancel: list[int] = []

                def cancel_after_data() -> None:
                    bytes_before_cancel.append(dialog.bars[0].file_obj.tell())
                    dialog.reject()

                if cancel:
                    assert dialog.bars[0].reply is not None
                    dialog.bars[0].reply.readyRead.connect(cancel_after_data)
                retry_cancel = QTimer()
                cancelled_retry: list[bool] = []

                def cancel_during_retry() -> None:
                    if dialog.bars[0].retry_timer.isActive():
                        cancelled_retry.append(True)
                        retry_cancel.stop()
                        dialog.reject()

                if cancel_retry:
                    retry_cancel.timeout.connect(cancel_during_retry)
                    retry_cancel.start(1)
                watchdog.start(15000)
                loop.exec()
                watchdog.stop()
                retry_cancel.stop()
                timed_out = not completed
                if timed_out:
                    dialog.reject()
                self.assertFalse(timed_out, 'Download never completed or failed')
                self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected if cancel or cancel_retry or self.errors else QDialog.DialogCode.Accepted)
                if cancel:
                    self.assertTrue(bytes_before_cancel)
                    self.assertGreater(bytes_before_cancel[0], 0)
                elif cancel_retry:
                    self.assertTrue(cancelled_retry)
                else:
                    self.assertFalse(dialog.todo)
                return dialog

        def assert_failed(self, dialog: download.DownloadResources, *failed_paths: str) -> None:
            self.assertEqual(len(self.errors), 1)
            self.assertTrue(dialog.failures)
            for bar in dialog.bars:
                if not failed_paths or bar.qurl.path().lstrip('/') in failed_paths:
                    self.assertEqual(bar.pb.text(), _('Download failed'))

        def test_stalled_downloads(self) -> None:
            for path in ('no-headers', 'stall'):
                with self.subTest(path=path):
                    dialog = self.run_download(path)
                    self.assert_failed(dialog)
                    self.assertEqual(os.listdir(self.directory.name), [])

        def test_multiple_downloads(self) -> None:
            dialog = self.run_download('complete', 'stall')
            self.assert_failed(dialog, 'stall')
            self.assertEqual(os.listdir(self.directory.name), ['complete'])
            with open(os.path.join(self.directory.name, 'complete'), 'rb') as stream:
                self.assertEqual(stream.read(), DATA)

        def test_failed_download(self) -> None:
            dialog = self.run_download('error')
            self.assert_failed(dialog)
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_checksum_failure_preserves_cache(self) -> None:
            path = os.path.join(self.directory.name, 'complete')
            with open(path, 'wb') as stream:
                stream.write(b'existing cache')
            dialog = self.run_download('complete', sha256='0' * 64)
            self.assert_failed(dialog)
            self.assertEqual(os.listdir(self.directory.name), ['complete'])
            with open(path, 'rb') as stream:
                self.assertEqual(stream.read(), b'existing cache')

        def test_not_modified_preserves_cache(self) -> None:
            path = os.path.join(self.directory.name, 'not-modified')
            with open(path, 'wb') as stream:
                stream.write(DATA)
            dialog = self.run_download('not-modified')
            self.assertFalse(self.errors)
            self.assertEqual(dialog.bars[0].pb.text(), _('Download finished'))
            self.assertEqual(os.listdir(self.directory.name), ['not-modified'])
            with open(path, 'rb') as stream:
                self.assertEqual(stream.read(), DATA)

        def test_cancel_cleans_partial_download(self) -> None:
            self.run_download('stall', cancel=True)
            self.assertFalse(self.errors)
            self.assertEqual(os.listdir(self.directory.name), [])

        def assert_downloaded(self, path: str) -> None:
            self.assertFalse(self.errors)
            with open(os.path.join(self.directory.name, path), 'rb') as stream:
                self.assertEqual(stream.read(), DATA)

        def test_uninterrupted_download_uses_single_request(self) -> None:
            self.run_download('range-complete')
            self.assert_downloaded('range-complete')
            self.assertEqual([r for _, r, _ in self.server.requests], [''])

        def test_server_returns_partial_range(self) -> None:
            self.run_download('range-capped')
            self.assert_downloaded('range-capped')
            self.assertEqual([r for _, r, _ in self.server.requests], [''] + [f'bytes={start}-' for start in range(1024, len(DATA), 1024)])

        def test_resume_after_timeout(self) -> None:
            self.run_download('range-resume')
            self.assert_downloaded('range-resume')
            self.assertEqual(self.server.requests[1][1:], ('bytes=1024-', '"model-v1"'))

        def test_resume_after_disconnect(self) -> None:
            self.run_download('range-disconnect')
            self.assert_downloaded('range-disconnect')
            self.assertEqual(self.server.requests[1][1], 'bytes=1024-')

        def test_repeated_interruptions_make_progress(self) -> None:
            self.run_download('range-always-stall')
            self.assert_downloaded('range-always-stall')
            offsets = [int(r.split('=')[1].split('-')[0]) if r else 0 for _, r, _ in self.server.requests]
            self.assertEqual(offsets, list(range(0, len(DATA), 1024)))
            self.assertGreater(len(offsets), download.ProgressBar.MAX_RETRIES)

        def test_server_ignores_resume_range(self) -> None:
            self.run_download('range-ignore')
            self.assert_downloaded('range-ignore')
            self.assertEqual(len(self.server.requests), 2)

        def test_unhashed_resource_resumes_with_validator(self) -> None:
            self.run_download('range-unhashed', verified=False)
            self.assert_downloaded('range-unhashed')
            self.assertEqual(self.server.requests[0][1], '')
            self.assertEqual(self.server.requests[1][1:], ('bytes=1024-', '"model-v1"'))

        def test_unhashed_resource_restarts_without_validator(self) -> None:
            self.run_download('range-no-validator', verified=False)
            self.assert_downloaded('range-no-validator')
            self.assertEqual([r for _, r, _ in self.server.requests], ['', ''])

        def test_wrong_range_preserves_existing_cache(self) -> None:
            path = os.path.join(self.directory.name, 'range-wrong-offset')
            with open(path, 'wb') as stream:
                stream.write(b'existing cache')
            dialog = self.run_download('range-wrong-offset')
            self.assert_failed(dialog)
            self.assertEqual(len(self.server.requests), 2)
            with open(path, 'rb') as stream:
                self.assertEqual(stream.read(), b'existing cache')
            self.assertEqual(os.listdir(self.directory.name), ['range-wrong-offset'])

        def test_inconsistent_range_length(self) -> None:
            dialog = self.run_download('range-wrong-length')
            self.assert_failed(dialog)
            self.assertEqual(len(self.server.requests), 2)
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_retry_transient_http_error(self) -> None:
            self.run_download('transient')
            self.assert_downloaded('transient')
            self.assertEqual(len(self.server.requests), 2)

        def test_retry_limit(self) -> None:
            dialog = self.run_download('error')
            self.assert_failed(dialog)
            self.assertEqual(len(self.server.requests), download.ProgressBar.MAX_RETRIES + 1)

        def test_permanent_http_error_is_not_retried(self) -> None:
            dialog = self.run_download('not-found')
            self.assert_failed(dialog)
            self.assertEqual(len(self.server.requests), 1)

        def test_response_without_content_length(self) -> None:
            self.run_download('no-length')
            self.assert_downloaded('no-length')

        def test_cancel_pending_retry(self) -> None:
            self.run_download('error', cancel_retry=True)
            loop = QEventLoop()
            QTimer.singleShot(150, loop.quit)
            loop.exec()
            self.assertFalse(self.errors)
            self.assertEqual(len(self.server.requests), 1)
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_unhashed_resource_validator_changes(self) -> None:
            dialog = self.run_download('range-changed-validator', verified=False)
            self.assert_failed(dialog)
            self.assertEqual(len(self.server.requests), 2)
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_complete_hash_without_end_of_response(self) -> None:
            self.run_download('no-length-stall')
            self.assert_downloaded('no-length-stall')
            self.assertEqual(len(self.server.requests), 1)

        def test_write_failure_is_reported(self) -> None:
            dialog = self.run_download('complete', write_error=True)
            self.assert_failed(dialog)
            self.assertIn('disk full', self.errors[0])
            self.assertEqual(len(self.server.requests), 1)
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_retry_does_not_interrupt_other_downloads(self) -> None:
            self.use_long_transfer_timeout()
            self.run_download('slow', 'transient')
            self.assert_downloaded('slow')
            self.assert_downloaded('transient')
            self.assertEqual(sum(path == '/slow' for path, _, _ in self.server.requests), 1)

        def test_restart_after_corruption(self) -> None:
            self.run_download('corrupt-once')
            self.assert_downloaded('corrupt-once')
            self.assertEqual(len(self.server.requests), 2)

        def test_persistent_corruption_fails(self) -> None:
            dialog = self.run_download('corrupt')
            self.assert_failed(dialog)
            self.assertIn(_('checksum does not match'), self.errors[0])
            self.assertEqual(len(self.server.requests), 2)
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_not_modified_without_cache(self) -> None:
            dialog = self.run_download('not-modified')
            self.assert_failed(dialog)
            self.assertIn('no previously downloaded copy', self.errors[0])
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_restarting_download_retries_are_bounded(self) -> None:
            dialog = self.run_download('growing-stall', verified=False)
            self.assert_failed(dialog)
            self.assertEqual(len(self.server.requests), download.ProgressBar.MAX_RETRIES + 1)
            self.assertEqual(os.listdir(self.directory.name), [])

        def test_install_failure_preserves_cache(self) -> None:
            path = os.path.join(self.directory.name, 'complete')
            with open(path, 'wb') as stream:
                stream.write(b'existing cache')
            with patch.object(download.os, 'replace', side_effect=PermissionError('cannot replace cache')):
                dialog = self.run_download('complete')
            self.assert_failed(dialog)
            with open(path, 'rb') as stream:
                self.assertEqual(stream.read(), b'existing cache')
            self.assertEqual(os.listdir(self.directory.name), ['complete'])

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DownloadTests))
    if not result.wasSuccessful():
        raise SystemExit(1)


class TestDownload(unittest.TestCase):
    def test_tts_downloads(self) -> None:
        from calibre.utils.ipc.simple_worker import start_pipe_worker

        process = start_pipe_worker(
            'from calibre.gui2.tts.test_download import run_download_tests_in_worker; run_download_tests_in_worker()',
            env={'QT_QPA_PLATFORM': 'offscreen'},
            stderr=subprocess.STDOUT,
        )
        try:
            output = process.communicate(timeout=180)[0]
            self.assertEqual(process.returncode, 0, output.decode('utf-8', 'replace'))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(10)


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestDownload)
