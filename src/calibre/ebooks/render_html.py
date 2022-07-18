#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os
import sys
from qt.core import (
    QApplication, QByteArray, QMarginsF, QPageLayout, QPageSize, Qt, QTimer, QUrl
)
from qt.webengine import (
    QWebEnginePage, QWebEngineProfile, QWebEngineScript,
    QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler
)

from calibre.constants import FAKE_HOST, FAKE_PROTOCOL
from calibre.ebooks.metadata.pdf import page_images
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.gui2 import must_use_qt
from calibre.gui_launch import setup_qt_logging
from calibre.utils.filenames import atomic_rename
from calibre.utils.logging import default_log
from calibre.utils.monotonic import monotonic
from calibre.utils.webengine import (
    secure_webengine, send_reply, setup_fake_protocol, setup_profile
)

LOAD_TIMEOUT = 20
PRINT_TIMEOUT = 10


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    def interceptRequest(self, request_info):
        method = bytes(request_info.requestMethod())
        if method not in (b'GET', b'HEAD'):
            default_log.warn(f'Blocking URL request with method: {method}')
            request_info.block(True)
            return
        qurl = request_info.requestUrl()
        if qurl.scheme() not in (FAKE_PROTOCOL,):
            default_log.warn(f'Blocking URL request {qurl.toString()} as it is not for a resource related to the HTML file being rendered')
            request_info.block(True)
            return


class UrlSchemeHandler(QWebEngineUrlSchemeHandler):

    def __init__(self, root, parent=None):
        self.root = root
        super().__init__(parent)
        self.allowed_hosts = (FAKE_HOST,)

    def requestStarted(self, rq):
        if bytes(rq.requestMethod()) != b'GET':
            return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestDenied)
        url = rq.requestUrl()
        host = url.host()
        if host not in self.allowed_hosts or url.scheme() != FAKE_PROTOCOL:
            return self.fail_request(rq)
        path = url.path()
        rp = path[1:]
        if not rp:
            return self.fail_request(rq, QWebEngineUrlRequestJob.Error.UrlNotFound)
        resolved_path = os.path.abspath(os.path.join(self.root, rp.replace('/', os.sep)))
        if not resolved_path.startswith(self.root):
            return self.fail_request(rq, QWebEngineUrlRequestJob.Error.UrlNotFound)

        try:
            with open(resolved_path, 'rb') as f:
                data = f.read()
        except OSError as err:
            default_log(f'Failed to read file: {rp} with error: {err}')
            return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestFailed)

        send_reply(rq, guess_type(os.path.basename(resolved_path)), data)

    def fail_request(self, rq, fail_code=None):
        if fail_code is None:
            fail_code = QWebEngineUrlRequestJob.Error.UrlNotFound
        rq.fail(fail_code)
        print(f"Blocking FAKE_PROTOCOL request: {rq.requestUrl().toString()} with code: {fail_code}", file=sys.stderr)


class Render(QWebEnginePage):

    def __init__(self, profile):
        QWebEnginePage.__init__(self, profile, QApplication.instance())
        secure_webengine(self)
        self.printing_started = False
        self.loadFinished.connect(self.load_finished, type=Qt.ConnectionType.QueuedConnection)
        self.pdfPrintingFinished.connect(self.print_finished)
        self.hang_timer = t = QTimer(self)
        t.setInterval(500)
        t.timeout.connect(self.hang_check)

    def break_cycles(self):
        self.hang_timer.timeout.disconnect()
        self.pdfPrintingFinished.disconnect()
        self.setParent(None)

    def load_finished(self, ok):
        if ok:
            self.runJavaScript('''
            var ans = {};
            var meta = document.querySelector('meta[name=calibre-html-render-data]');
            if (meta) {
                try {
                    ans = JSON.parse(meta.content);
                    console.log(ans);
                } catch {}
            }
            ans;
            ''', QWebEngineScript.ScriptWorldId.ApplicationWorld, self.start_print)
        else:
            self.hang_timer.stop()
            QApplication.instance().exit(1)

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        pass

    def start_load(self, path_to_html, root):
        url = QUrl(f'{FAKE_PROTOCOL}://{FAKE_HOST}')
        url.setPath('/' + os.path.relpath(path_to_html, root).replace(os.sep, '/'))
        self.setUrl(url)
        self.start_time = monotonic()
        self.hang_timer.start()

    def hang_check(self):
        if self.printing_started:
            if monotonic() - self.start_time > PRINT_TIMEOUT:
                self.hang_timer.stop()
                QApplication.instance().exit(4)
        else:
            if monotonic() - self.start_time > LOAD_TIMEOUT:
                self.hang_timer.stop()
                QApplication.instance().exit(3)

    def start_print(self, data):
        margins = QMarginsF(0, 0, 0, 0)
        page_size = QPageSize(QPageSize.PageSizeId.A4)
        if isinstance(data, dict):
            try:
                if 'margins' in data:
                    margins = QMarginsF(*data['margins'])
                if 'size' in data:
                    sz = data['size']
                    if type(getattr(QPageSize, sz, None)) is type(QPageSize.PageSizeId.A4):  # noqa
                        page_size = QPageSize(getattr(QPageSize, sz))
                    else:
                        from calibre.ebooks.pdf.image_writer import (
                            parse_pdf_page_size
                        )
                        ps = parse_pdf_page_size(sz, data.get('unit', 'inch'))
                        if ps is not None:
                            page_size = ps
            except Exception:
                pass
        page_layout = QPageLayout(page_size, QPageLayout.Orientation.Portrait, margins)
        self.printToPdf('rendered.pdf', page_layout)
        self.printing_started = True
        self.start_time = monotonic()

    def print_finished(self, path, ok):
        QApplication.instance().exit(0 if ok else 2)
        self.hang_timer.stop()


def main(path_to_html, tdir, image_format='jpeg', root=''):
    if image_format not in ('jpeg', 'png'):
        raise ValueError('Image format must be either jpeg or png')
    must_use_qt()
    setup_qt_logging()
    setup_fake_protocol()
    profile = setup_profile(QWebEngineProfile(QApplication.instance()))
    path_to_html = os.path.abspath(path_to_html)
    url_handler = UrlSchemeHandler(root or os.path.dirname(path_to_html), parent=profile)
    interceptor = RequestInterceptor(profile)
    profile.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), url_handler)
    profile.setUrlRequestInterceptor(interceptor)

    os.chdir(tdir)
    renderer = Render(profile)
    renderer.start_load(path_to_html, url_handler.root)
    ret = QApplication.instance().exec()
    renderer.break_cycles()
    del renderer
    if ret == 0:
        page_images('rendered.pdf', image_format=image_format)
        ext = {'jpeg': 'jpg'}.get(image_format, image_format)
        atomic_rename('page-images-1.' + ext, 'rendered.' + image_format)
    return ret == 0


if __name__ == '__main__':
    if not main(sys.argv[-1], '.'):
        raise SystemExit('Failed to render HTML')
