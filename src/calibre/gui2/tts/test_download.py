#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, calibre contributors

import hashlib
import os
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

if TYPE_CHECKING:
    from qt.core import QObject


DATA = b'voice model data' * 1024


class DownloadServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        self.stopped = Event()
        super().__init__(('127.0.0.1', 0), DownloadHandler)


class DownloadHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        stopped = cast('DownloadServer', self.server).stopped
        if self.path == '/no-headers':
            stopped.wait(10)
            return
        if self.path == '/not-modified':
            self.send_response(304)
            self.end_headers()
            return
        if self.path == '/error':
            self.send_error(503)
            return
        self.send_response(200)
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
                    if stopped.wait(0.1):
                        break
            else:
                self.wfile.write(DATA)
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
        def setTransferTimeout(self, timeout: int = 30_000) -> None:
            # Exercise real network timeouts without waiting a minute per test.
            super().setTransferTimeout(min(timeout, 1000))

    class DownloadTests(unittest.TestCase):
        def setUp(self) -> None:
            self.directory = tempfile.TemporaryDirectory()
            self.addCleanup(self.directory.cleanup)
            self.errors: list[str] = []
            self.server = DownloadServer()
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.dialog: download.DownloadResources | None = None

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

        def run_download(self, *paths: str, sha256: str | None = None, cancel: bool = False) -> download.DownloadResources:
            self.close_dialog()
            resources = {f'http://127.0.0.1:{self.server.server_port}/{path}': (os.path.join(self.directory.name, path), path) for path in paths}
            hashes = {url: sha256 or hashlib.sha256(DATA).hexdigest() for url in resources}

            def error_dialog(parent: QObject, title: str, message: str, det_msg: str, show: bool) -> None:
                self.errors.append(det_msg)

            with patch.object(download, 'QNetworkAccessManager', NetworkAccessManager), patch.object(download, 'error_dialog', error_dialog):
                self.dialog = dialog = download.DownloadResources('test', 'test', resources, hashes=hashes)
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
                watchdog.start(5000)
                loop.exec()
                watchdog.stop()
                timed_out = not completed
                if timed_out:
                    dialog.reject()
                self.assertFalse(timed_out, 'Download never completed or failed')
                self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected if cancel or self.errors else QDialog.DialogCode.Accepted)
                if cancel:
                    self.assertTrue(bytes_before_cancel)
                    self.assertGreater(bytes_before_cancel[0], 0)
                else:
                    self.assertFalse(dialog.todo)
                return dialog

        def assert_failed(self, dialog: download.DownloadResources, *failed_paths: str) -> None:
            self.assertTrue(self.errors)
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

        def test_slow_active_download(self) -> None:
            dialog = self.run_download('slow')
            self.assertFalse(self.errors)
            self.assertEqual(dialog.bars[0].pb.text(), _('Download finished'))
            with open(os.path.join(self.directory.name, 'slow'), 'rb') as stream:
                self.assertEqual(stream.read(), DATA)

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
            output = process.communicate(timeout=60)[0]
            self.assertEqual(process.returncode, 0, output.decode('utf-8', 'replace'))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(10)


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestDownload)
