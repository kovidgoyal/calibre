#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

# Imports {{{
import copy
import json
import os
import signal
import sys
from functools import lru_cache
from itertools import count, repeat
from typing import TYPE_CHECKING, NamedTuple, NotRequired, TypedDict, cast
from urllib.parse import urlparse

from html5_parser import parse
from lxml import etree
from qt.core import QApplication, QByteArray, QMarginsF, QObject, QPageLayout, Qt, QTimer, QUrl, pyqtSignal, sip
from qt.webengine import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
)

from calibre import detect_ncpus, human_readable, prepare_string_for_xml
from calibre.constants import FAKE_HOST, FAKE_PROTOCOL, __appname__, __version__, ismacos, iswindows
from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
from calibre.ebooks.oeb.base import XHTML, XPath, rewrite_idrefs
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.pdf.image_writer import PDFMetadata, get_page_layout
from calibre.gui2 import qapplication_or_fail, setup_unix_signals
from calibre.srv.render_book import check_for_maths
from calibre.utils.fonts.sfnt.container import Sfnt, UnsupportedFont
from calibre.utils.fonts.sfnt.errors import NoGlyphs
from calibre.utils.fonts.sfnt.merge import merge_truetype_fonts_for_pdf
from calibre.utils.fonts.sfnt.subset import pdf_subset
from calibre.utils.localization import _
from calibre.utils.logging import Log, default_log
from calibre.utils.monotonic import monotonic
from calibre.utils.podofo import add_image_page, dedup_type3_fonts, get_podofo, remove_unused_fonts, set_metadata_implementation
from calibre.utils.resources import get_path as P
from calibre.utils.short_uuid import uuid4
from calibre.utils.webengine import secure_webengine, send_reply, setup_profile
from polyglot.builtins import as_bytes

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
    from optparse import Values

    from lxml.etree import _Element

    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.oeb.polish.toc import TOC
    from calibre_extensions.podofo import PDFDoc, PDFOutlineItem

    type Job = tuple[str, QPageLayout, str]
    type ProgressReporter = Callable[[float, str], object]
    type WArray = list[int | float | list[int | float]]

# }}}

OK, KILL_SIGNAL = range(2)
HANG_TIME = 60  # seconds
PRINT_HANG_TIME = 600  # seconds


# Utils {{{
def data_as_pdf_doc(data: bytes) -> PDFDoc:
    podofo = get_podofo()
    ans = podofo.PDFDoc()
    ans.load(data)
    return ans


_preprint_js_cache: str | None = None


def preprint_js() -> str:
    global _preprint_js_cache
    if _preprint_js_cache is None:
        _preprint_js_cache = P('pdf-preprint.js', data=True).decode('utf-8').replace('HYPHEN_CHAR', 'true' if ismacos else 'false', 1)
    return _preprint_js_cache


def parsed_html(container: ContainerBase, name: str) -> _Element:
    ans = container.parsed(name)
    assert isinstance(ans, etree._Element)  # only called for spine items and the skeleton, which are (X)HTML
    return ans


def last_tag(root: _Element) -> _Element:
    return tuple(root.iterchildren('*'))[-1]


def create_skeleton(container: ContainerBase) -> str:
    spine_name = tuple(container.spine_names)[-1][0]
    root = parsed_html(container, spine_name)
    root = copy.deepcopy(root)
    body = None
    for child in tuple(root.iterchildren('*')):
        if body is None:
            if child.tag == XHTML('body') or child.tag == 'body':
                body = child
        else:
            root.remove(child)
    if body is None:
        body = last_tag(root)
    body.text = body.tail = None
    del body[:]
    name = container.add_file(spine_name, b'', modify_name_if_needed=True)
    container.replace(name, root)
    return name


def local_name(x: str) -> str:
    return x.split('}', 1)[-1].lower()


def fix_fullscreen_images(container: ContainerBase) -> None:

    def is_svg_fs_markup(names: list[str], svg: _Element | None) -> bool:
        if svg is not None:
            if len(names) == 2 or len(names) == 3:
                if names[-1] == 'image' and names[-2] == 'svg':
                    if len(names) == 2 or names[0] == 'div':
                        if svg.get('width') == '100%' and svg.get('height') == '100%':
                            return True
        return False

    for file_name, is_linear in container.spine_names:
        root = parsed_html(container, file_name)
        root_kids = tuple(root.iterchildren('*'))
        if not root_kids:
            continue
        body = root_kids[-1]
        child_tags = []
        for child in body.iterchildren('*'):
            ctag = child.tag
            assert isinstance(ctag, str)  # iterchildren('*') yields only elements
            tag = local_name(ctag)
            if tag in ('script', 'style'):
                continue
            child_tags.append(tag)
            if len(child_tags) > 1:
                break
        if len(child_tags) == 1 and child_tags[0] in ('div', 'svg'):
            names = []
            svg = None
            for elem in body.iterdescendants('*'):
                etag = elem.tag
                assert isinstance(etag, str)  # iterdescendants('*') yields only elements
                name = local_name(etag)
                if name not in {'style', 'script'}:
                    names.append(name)
                    if name == 'svg':
                        svg = elem
            if is_svg_fs_markup(names, svg):
                assert svg is not None
                svg.set('width', '100vw')
                svg.set('height', '100vh')
                container.dirty(file_name)


# }}}


# Renderer {{{
class Container(ContainerBase):
    tweak_mode = True
    is_dir = True

    def __init__(self, opf_path: str, log: Log, root_dir: str | None = None) -> None:
        ContainerBase.__init__(self, root_dir or os.path.dirname(opf_path), opf_path, log)


class UrlSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, container: ContainerBase, parent: QObject | None = None) -> None:
        QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.allowed_hosts = (FAKE_HOST,)
        self.container = container

    def requestStarted(self, a0: QWebEngineUrlRequestJob | None) -> None:
        assert a0 is not None  # Qt always passes a job
        if bytes(a0.requestMethod()) != b'GET':
            return self.fail_request(a0, QWebEngineUrlRequestJob.Error.RequestDenied)
        url = a0.requestUrl()
        host = url.host()
        if host not in self.allowed_hosts or url.scheme() != FAKE_PROTOCOL:
            return self.fail_request(a0)
        path = url.path()
        if path.startswith('/book/'):
            name = path[len('/book/') :]
            try:
                mime_type = self.container.mime_map.get(name) or guess_type(name)
                try:
                    with self.container.open(name) as f:
                        q = os.path.abspath(f.name)
                        if not q.startswith(self.container.root):
                            raise FileNotFoundError('Attempt to leave sandbox')
                        data = f.read()
                except FileNotFoundError:
                    print(f'Could not find file {name} in book', file=sys.stderr)
                    a0.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                    return
                data = as_bytes(data)
                mime_type = {
                    # Prevent warning in console about mimetype of fonts
                    'application/vnd.ms-opentype': 'application/x-font-ttf',
                    'application/x-font-truetype': 'application/x-font-ttf',
                    'application/font-sfnt': 'application/x-font-ttf',
                }.get(mime_type, mime_type)
                send_reply(a0, mime_type, data)
            except Exception:
                import traceback

                traceback.print_exc()
                return self.fail_request(a0, QWebEngineUrlRequestJob.Error.RequestFailed)
        elif path.startswith('/mathjax/'):
            try:
                _ign, _ign, base, rest = path.split('/', 3)
            except ValueError:
                print(f'Could not find file {path} in mathjax', file=sys.stderr)
                a0.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            try:
                mime_type = guess_type(rest)
                if base == 'loader' and '/' not in rest and '\\' not in rest:
                    data = P(rest, allow_user_override=False, data=True)
                elif base == 'data':
                    q = os.path.abspath(os.path.join(mathjax_dir(), rest))
                    if not q.startswith(mathjax_dir()):
                        raise FileNotFoundError('')
                    with open(q, 'rb') as f:
                        data = f.read()
                else:
                    raise FileNotFoundError('')
                send_reply(a0, mime_type, data)
            except FileNotFoundError:
                print(f'Could not find file {path} in mathjax', file=sys.stderr)
                a0.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            except Exception:
                import traceback

                traceback.print_exc()
                return self.fail_request(a0, QWebEngineUrlRequestJob.Error.RequestFailed)
        else:
            return self.fail_request(a0)

    def fail_request(self, rq: QWebEngineUrlRequestJob, fail_code: QWebEngineUrlRequestJob.Error | None = None) -> None:
        if fail_code is None:
            fail_code = QWebEngineUrlRequestJob.Error.UrlNotFound
        rq.fail(fail_code)
        print(f'Blocking FAKE_PROTOCOL request: {rq.requestUrl().toString()} with code: {fail_code}', file=sys.stderr)


# }}}


class Renderer(QWebEnginePage):
    work_done = pyqtSignal(object, object)
    result_key: str  # set by RenderManager.assign_work()

    def __init__(self, opts: Values, parent: RenderManager, log: Log) -> None:
        QWebEnginePage.__init__(self, parent.profile, parent)
        secure_webengine(self)
        self.working = False
        self.log = log
        self.load_complete = False
        self.settle_time = 0
        self.wait_for_title: str | None = None
        s = self.settings()
        assert s is not None
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, int(opts.pdf_default_font_size))
        s.setFontSize(QWebEngineSettings.FontSize.DefaultFixedFontSize, int(opts.pdf_mono_font_size))
        s.setFontSize(QWebEngineSettings.FontSize.MinimumLogicalFontSize, 8)
        s.setFontSize(QWebEngineSettings.FontSize.MinimumFontSize, 8)
        std = {'serif': opts.pdf_serif_family, 'sans': opts.pdf_sans_family, 'mono': opts.pdf_mono_family}.get(opts.pdf_standard_font, opts.pdf_serif_family)
        if std:
            s.setFontFamily(QWebEngineSettings.FontFamily.StandardFont, std)
        if opts.pdf_serif_family:
            s.setFontFamily(QWebEngineSettings.FontFamily.SerifFont, opts.pdf_serif_family)
        if opts.pdf_sans_family:
            s.setFontFamily(QWebEngineSettings.FontFamily.SansSerifFont, opts.pdf_sans_family)
        if opts.pdf_mono_family:
            s.setFontFamily(QWebEngineSettings.FontFamily.FixedFont, opts.pdf_mono_family)

        self.titleChanged.connect(self.title_changed)
        self.loadStarted.connect(self.load_started)
        self.loadProgress.connect(self.load_progress)
        self.loadFinished.connect(self.load_finished)
        self.load_hang_check_timer = t = QTimer(self)
        self.load_started_at = 0.0
        t.setTimerType(Qt.TimerType.VeryCoarseTimer)
        t.setInterval(HANG_TIME * 1000)
        t.setSingleShot(True)
        t.timeout.connect(self.on_load_hang)
        self.print_hang_check_timer = t = QTimer(self)
        t.setTimerType(Qt.TimerType.VeryCoarseTimer)
        t.setInterval(PRINT_HANG_TIME * 1000)
        t.setSingleShot(True)
        t.timeout.connect(self.on_print_hang)
        self.renderProcessTerminated.connect(self.render_process_terminated)

    def fail(self, msg: str) -> None:
        self.load_hang_check_timer.stop()
        self.print_hang_check_timer.stop()
        if self.working:
            self.working = False
            self.work_done.emit(self, msg)

    def render_process_terminated(self, status: QWebEnginePage.RenderProcessTerminationStatus, exit_code: int) -> None:
        if self.working:
            self.fail(
                f'Rendering of {self.url().toString()} failed as the render process terminated abnormally'
                f' with status: {status.name} and exit code: {exit_code}.'
                ' This can be caused by bugs in the rendering engine triggered by some fonts, for example color emoji fonts.'
            )

    def on_print_hang(self) -> None:
        self.fail(
            f'Rendering of {self.url().toString()} not complete after {int(monotonic() - self.job_started_at)} seconds, aborting.'
            ' This can be caused by bugs in the rendering engine triggered by some fonts, for example color emoji fonts.'
        )

    def load_started(self) -> None:
        self.load_started_at = monotonic()
        self.load_complete = False
        self.load_hang_check_timer.start()

    def load_progress(self, amt: int) -> None:
        self.load_hang_check_timer.start()

    def on_load_hang(self) -> None:
        self.log(self.log_prefix, f'Loading not complete after {int(monotonic() - self.load_started_at)} seconds, aborting.')
        self.load_finished(False)

    def title_changed(self, title: str) -> None:
        if self.wait_for_title and title == self.wait_for_title and self.load_complete:
            QTimer.singleShot(self.settle_time, self.print_to_pdf)

    @property
    def log_prefix(self) -> str:
        return os.path.basename(self.url().toLocalFile()) + ':'

    def load_finished(self, ok: bool) -> None:
        self.load_complete = True
        self.load_hang_check_timer.stop()
        if not self.working:
            return
        if not ok:
            self.fail(f'Load of {self.url().toString()} failed')
            return
        self.print_hang_check_timer.start()
        if self.wait_for_title and self.title() != self.wait_for_title:
            self.log(self.log_prefix, 'Load finished, waiting for title to change to:', self.wait_for_title)
            return
        QTimer.singleShot(int(1000 * self.settle_time), self.print_to_pdf)

    def javaScriptConsoleMessage(self, level: QWebEnginePage.JavaScriptConsoleMessageLevel, message: str | None, lineNumber: int, sourceID: str | None) -> None:
        try:
            self.log(f'{sourceID}:{lineNumber}:{message}')
        except Exception:
            pass

    def print_to_pdf(self) -> None:
        self.runJavaScript(preprint_js(), self.start_print)

    def start_print(self, *a: object) -> None:
        self.printToPdf(self.printing_done, self.page_layout)

    def printing_done(self, pdf_data: QByteArray | bytes | bytearray | memoryview) -> None:
        if sip.isdeleted(self):
            return
        self.print_hang_check_timer.stop()
        if not self.working:
            return  # job already failed because of a timeout or render process crash
        data = bytes(pdf_data)
        if not data:
            self.fail(f'Rendering of {self.url().toString()} failed, no PDF data was produced')
            return
        self.working = False
        self.work_done.emit(self, data)

    def convert_html_file(self, path: str, page_layout: QPageLayout, settle_time: int = 0, wait_for_title: str | None = None) -> None:
        self.working = True
        self.load_complete = False
        self.wait_for_title = wait_for_title

        self.settle_time = settle_time
        self.page_layout = page_layout
        url = QUrl(f'{FAKE_PROTOCOL}://{FAKE_HOST}/')
        url.setPath(path)
        self.setUrl(url)
        self.job_started_at = monotonic()


class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    log: Log

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        method = bytes(info.requestMethod())
        if method not in (b'GET', b'HEAD'):
            self.log.warn(f'Blocking URL request with method: {method}')
            info.block(True)
            return
        qurl = info.requestUrl()
        if qurl.scheme() != FAKE_PROTOCOL:
            self.log.warn(f'Blocking URL request {qurl.toString()} as it is not for a resource in the book')
            info.block(True)
            return


class RenderManager(QObject):
    def __init__(self, opts: Values, log: Log, container: ContainerBase) -> None:
        QObject.__init__(self)
        self.interceptor = RequestInterceptor(self)
        self.has_maths: dict[str, bool] = {}
        self.interceptor.log = self.log = log
        ans = QWebEngineProfile(QApplication.instance())
        setup_profile(ans)
        self.url_handler = UrlSchemeHandler(container, parent=ans)
        ans.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), self.url_handler)
        ua = 'calibre-pdf-output ' + __version__
        ans.setHttpUserAgent(ua)
        s = ans.settings()
        assert s is not None
        s.setDefaultTextEncoding('utf-8')
        ans.setUrlRequestInterceptor(self.interceptor)
        self.profile = ans

        self.opts = opts
        self.workers: list[Renderer] = []
        self.max_workers = detect_ncpus()
        if iswindows:
            self.original_signal_handlers = {}
        else:
            self.original_signal_handlers = setup_unix_signals(self)

    def create_worker(self) -> None:
        worker = Renderer(self.opts, self, self.log)
        worker.work_done.connect(self.work_done)
        self.workers.append(worker)

    def signal_received(self, read_fd: int) -> None:
        try:
            os.read(read_fd, 1024)
        except OSError:
            return
        qapplication_or_fail().exit(KILL_SIGNAL)

    def block_signal_handlers(self) -> None:
        for sig in self.original_signal_handlers:
            signal.signal(sig, lambda x, y: None)

    def restore_signal_handlers(self) -> None:
        for sig, handler in self.original_signal_handlers.items():
            signal.signal(sig, handler)

    def run_loop(self) -> int:
        self.block_signal_handlers()
        try:
            return QApplication.exec()
        finally:
            self.restore_signal_handlers()

    def convert_html_files(
        self, jobs: Sequence[Job], settle_time: int = 0, wait_for_title: str | None = None, has_maths: dict[str, bool] | None = None
    ) -> dict[str, bytes | str]:
        self.has_maths = has_maths or {}
        self.render_count = 0
        self.total_count = len(jobs)
        while len(self.workers) < min(len(jobs), self.max_workers):
            self.create_worker()
        self.pending = list(jobs)
        self.log(f'Rendering {len(self.pending)} HTML files')
        self.results: dict[str, bytes | str] = {}
        self.failure: str | None = None
        self.settle_time = settle_time
        self.wait_for_title = wait_for_title
        QTimer.singleShot(0, self.assign_work)
        ret = self.run_loop()
        self.has_maths = {}
        if ret == KILL_SIGNAL:
            raise SystemExit('Kill signal received')
        if ret != OK:
            raise SystemExit('Unknown error occurred')
        if self.failure is not None:
            raise SystemExit(self.failure)
        return self.results

    def evaljs(self, js: str) -> object:
        if not self.workers:
            self.create_worker()
        w = self.workers[0]
        self.evaljs_result: object = None
        w.runJavaScript(js, self.evaljs_callback)
        QApplication.exec()
        return self.evaljs_result

    def evaljs_callback(self, result: object) -> None:
        self.evaljs_result = result
        qapplication_or_fail().exit(0)

    def assign_work(self) -> None:
        free_workers = [w for w in self.workers if not w.working]
        while free_workers and self.pending:
            html_file, page_layout, result_key = self.pending.pop()
            w = free_workers.pop()
            w.result_key = result_key
            wait_for_title = self.wait_for_title
            settle_time = self.settle_time
            if self.has_maths.get(result_key):
                wait_for_title = 'mathjax-load-complete'
                settle_time *= 2
            w.convert_html_file(html_file, page_layout, settle_time=settle_time, wait_for_title=wait_for_title)

    def work_done(self, worker: Renderer, result: bytes | str) -> None:
        self.results[worker.result_key] = result
        if isinstance(result, str):
            # No point rendering the remaining files as the conversion has failed
            self.failure = result
            self.pending = []
            qapplication_or_fail().exit(OK)
            return
        for w in self.workers:
            if not w.working and w.job_started_at > 0:
                time_taken = monotonic() - w.job_started_at
                self.render_count += 1
                self.log.debug(f'Rendered: {worker.result_key} in {time_taken:.1f} seconds ({self.render_count}/{self.total_count})')
                w.job_started_at = 0
        if self.pending:
            self.assign_work()
        else:
            for w in self.workers:
                if w.working:
                    return
            qapplication_or_fail().exit(OK)


def resolve_margins(margins: Margins | None, page_layout: QPageLayout) -> ResolvedMargins:
    old_margins = page_layout.marginsPoints()

    def m(which: str) -> float:
        ans = getattr(margins, which, None)
        if ans is None:
            ans = getattr(old_margins, which)()
        return ans

    return ResolvedMargins(*map(m, 'left top right bottom'.split()))


def job_for_name(container: ContainerBase, name: str, margins: Margins | None, page_layout: QPageLayout) -> Job:
    index_file = '/book/' + name
    if margins:
        page_layout = QPageLayout(page_layout)
        page_layout.setUnits(QPageLayout.Unit.Point)
        new_margins = QMarginsF(*resolve_margins(margins, page_layout))
        page_layout.setMargins(new_margins)
    return index_file, page_layout, name


# }}}


# Metadata {{{
def update_metadata(pdf_doc: PDFDoc, pdf_metadata: PDFMetadata) -> None:
    if pdf_metadata.mi:
        xmp_packet = metadata_to_xmp_packet(pdf_metadata.mi)
        set_metadata_implementation(
            pdf_doc,
            pdf_metadata.title,
            pdf_metadata.mi.authors,
            pdf_metadata.mi.book_producer,
            pdf_metadata.mi.tags,
            xmp_packet,
        )


def add_cover(pdf_doc: PDFDoc, cover_data: bytes, page_layout: QPageLayout, opts: Values) -> None:
    r = page_layout.fullRect(QPageLayout.Unit.Point)
    add_image_page(
        pdf_doc,
        cover_data,
        page_size=(r.left(), r.top(), r.width(), r.height()),
        preserve_aspect_ratio=opts.preserve_cover_aspect_ratio,
    )


# }}}

# Margin groups {{{


class Margins(NamedTuple):
    left: float | None
    top: float | None
    right: float | None
    bottom: float | None


class ResolvedMargins(NamedTuple):
    left: float
    top: float
    right: float
    bottom: float


class MarginFile(NamedTuple):
    name: str
    margins: Margins | None


def dict_to_margins(val: Mapping[str, float], d: float | None = None) -> Margins:
    return Margins(val.get('left', d), val.get('top', d), val.get('right', d), val.get('bottom', d))


def create_margin_files(container: ContainerBase) -> Iterator[MarginFile]:
    for name, is_linear in container.spine_names:
        root = parsed_html(container, name)
        raw_margins = root.get('data-calibre-pdf-output-page-margins')
        margins = dict_to_margins(json.loads(raw_margins)) if raw_margins else None
        yield MarginFile(name, margins)


# }}}


# Link handling {{{
def add_anchors_markup(root: _Element, uuid: str, anchors: Iterable[str]) -> None:
    body = last_tag(root)
    # A separate column spanning element is used to force the page break, as
    # when body is multi-column a page break on a non-spanning element only
    # causes a column break, so the anchors end up in a column alongside
    # content, which is then lost when the anchors page is deleted.
    # See https://bugs.launchpad.net/calibre/+bug/2142731
    # The anchors themselves must not be inside the spanner as some versions
    # of Chromium report the location of the spanner and its descendants as
    # being on the first page, causing the anchors page to not be deleted.
    # See https://bugs.launchpad.net/calibre/+bug/2170285
    breaker = body.makeelement(
        XHTML('div'),
        style='display:block !important; page-break-before: always !important; break-before: always !important; column-span: all !important;'
        ' height: 0 !important; margin: 0 !important; padding: 0 !important; border-width: 0 !important',
    )
    body.append(breaker)
    div = body.makeelement(
        XHTML('div'),
        id=uuid,
        style='display:block !important; white-space: pre-wrap !important',
    )
    div.text = '\n\n'
    body.append(div)
    c = count()

    def a(anchor: str) -> None:
        num = next(c)
        a = div.makeelement(
            XHTML('a'),
            href='#' + anchor,
            style='min-width: 10px !important; min-height: 10px !important; border: solid 1px rgba(0, 0, 0, 0) !important; text-decoration: none !important',
        )
        a.text = a.tail = ' '
        if num % 8 == 0:
            # prevent too many anchors on a line as it causes chromium to
            # rescale the viewport
            a.tail = '\n'
        div.append(a)

    for anchor in anchors:
        a(anchor)
    a(uuid)


def add_all_links(container: ContainerBase, margin_files: Iterable[MarginFile]) -> str:
    uuid = uuid4()
    name_anchor_map: dict[str, frozenset[str]] = {}
    for name, is_linear in container.spine_names:
        root = parsed_html(container, name)
        name_anchor_map[name] = frozenset(root.xpath('//*/@id'))
    for margin_file in margin_files:
        name = margin_file.name
        anchors = name_anchor_map.get(name, set())
        add_anchors_markup(parsed_html(container, name), uuid, anchors)
        container.dirty(name)
    return uuid


class _AnchorReplacer:
    file_type: str
    replaced: bool

    def __init__(self, container: ContainerBase, mapping: dict[tuple[str, str], str], spine_names: set[str], log: Log) -> None:
        self.container = container
        self.mapping = mapping
        self.spine_names = spine_names
        self.log = log
        self.file_type = ''
        self.replaced = False
        self.base = ''

    def __call__(self, url: str) -> str:
        if self.file_type not in ('text', 'ncx'):
            return url
        if not url:
            return url
        if '#' not in url:
            url += '#'
        if url.startswith('#'):
            href, frag = self.base, url[1:]
            name: str | None = self.base
        else:
            href, frag = url.partition('#')[::2]
            name = self.container.href_to_name(href, self.base)
        if not name:
            return url.rstrip('#')
        if not frag and name in self.spine_names:
            self.replaced = True
            return 'https://calibre-pdf-anchor.n#' + name
        key = name, frag
        new_frag = self.mapping.get(key)
        if new_frag is None:
            if name in self.spine_names:
                self.log.warn(f'Link anchor: {name}#{frag} not found, linking to top of file instead')
                self.replaced = True
                return 'https://calibre-pdf-anchor.n#' + name
            return url.rstrip('#')
        self.replaced = True
        return 'https://calibre-pdf-anchor.a#' + new_frag


def make_anchors_unique(container: ContainerBase, log: Log) -> dict[str, str]:
    mapping: dict[tuple[str, str], str] = {}
    count = 0
    spine_names: set[str] = set()
    replacer = _AnchorReplacer(container, mapping, spine_names, log)

    name_anchor_map: dict[str, str] = {}
    for spine_name, is_linear in container.spine_names:
        spine_names.add(spine_name)
        root = parsed_html(container, spine_name)
        for elem in root.xpath('//*[@id]'):
            count += 1
            key = spine_name, elem.get('id')
            if key not in mapping:
                new_id = mapping[key] = f'a{count}'
                elem.set('id', new_id)
        rewrite_idrefs(root, lambda eid: mapping.get((spine_name, eid), eid))  # ruff: ignore[function-uses-loop-variable]
        body = last_tag(root)
        body_id = body.get('id')
        if not body_id:
            count += 1
            body_id = f'a{count}'
            body.set('id', body_id)
        name_anchor_map[spine_name] = body_id

    for name in container.mime_map:
        replacer.base = name
        replacer.replaced = False
        container.replace_links(name, replacer)
    return name_anchor_map


class AnchorLocation:
    __slots__ = ('left', 'pagenum', 'top', 'zoom')

    def __init__(self, pagenum: int = 1, left: float = 0, top: float = 0, zoom: float = 0) -> None:
        self.pagenum, self.left, self.top, self.zoom = pagenum, left, top, zoom

    def __repr__(self) -> str:
        return 'AnchorLocation(pagenum={}, left={}, top={}, zoom={})'.format(*self.as_tuple)

    @property
    def as_tuple(self) -> tuple[int, float, float, float]:
        return self.pagenum, self.left, self.top, self.zoom


def get_anchor_locations(name: str, pdf_doc: PDFDoc, first_page_num: int, toc_uuid: str, log: Log, top_margin: float = 0) -> dict[str, AnchorLocation]:
    ans: dict[str, AnchorLocation] = {}
    anchors = pdf_doc.extract_anchors()
    try:
        toc_pagenum = anchors.pop(toc_uuid)[0]
    except KeyError:
        toc_pagenum = None
    if toc_pagenum is None:
        log.warn(f'Failed to find ToC anchor in {name}')
        toc_pagenum = 0
    if toc_pagenum > 1:
        pdf_doc.delete_pages(toc_pagenum, pdf_doc.page_count() - toc_pagenum + 1)
    for anchor, (pagenum, left, top, zoom) in anchors.items():
        pagenum += first_page_num - 1
        # Chromium generates XYZ destination coordinates relative to the content
        # area (ignoring top margin), so the top value is top_margin pts too large.
        if top_margin:
            top -= top_margin
        ans[anchor] = AnchorLocation(pagenum, left, top, zoom)
    return ans


def fix_links(pdf_doc: PDFDoc, anchor_locations: dict[str, AnchorLocation], name_anchor_map: dict[str, str], mark_links: bool, log: Log) -> None:
    pc = pdf_doc.page_count()

    def replace_link(url: str) -> tuple[int, float, float, float] | None:
        purl = urlparse(url)
        if purl.scheme != 'https' or purl.netloc not in ('calibre-pdf-anchor.a', 'calibre-pdf-anchor.n'):
            return
        loc = None
        if purl.netloc == 'calibre-pdf-anchor.a':
            loc = anchor_locations.get(purl.fragment)
            if loc is None:
                log.warn(f'Anchor location for link to {purl.fragment} not found')
        else:
            loc = anchor_locations.get(name_anchor_map.get(purl.fragment))
            if loc is None:
                log.warn(f'Anchor location for link to {purl.fragment} not found')
        if loc is None:
            return None
        if loc.pagenum > pc:
            log.warn(f'Anchor location for link to {purl.fragment} is past the end of the document, moving it to last page')
            loc.pagenum = pc
        return loc.as_tuple

    pdf_doc.alter_links(replace_link, mark_links)


# }}}


# Outline creation {{{
class PDFOutlineRoot:
    def __init__(self, pdf_doc: PDFDoc) -> None:
        self.pdf_doc = pdf_doc
        self.root_item: PDFOutlineItem | None = None

    def create(self, title: str, pagenum: int, as_child: bool, left: float, top: float, zoom: float) -> PDFOutlineItem:
        if self.root_item is None:
            self.root_item = self.pdf_doc.create_outline(title, pagenum, left, top, zoom)
        else:
            self.root_item = self.root_item.create(title, pagenum, False, left, top, zoom)
        return self.root_item


def annotate_toc(toc: TOC, anchor_locations: dict[str, AnchorLocation], name_anchor_map: dict[str, str], log: Log) -> None:
    for child in toc.iterdescendants():
        frag = child.frag
        try:
            if frag is None:
                raise KeyError(frag)
            if '.' in frag:
                loc = anchor_locations[name_anchor_map[frag]]
            else:
                loc = anchor_locations[frag]
        except Exception:
            log.warn(f'Could not find anchor location for ToC entry: {child.title} with href: {frag}')
            loc = AnchorLocation(1, 0, 0, 0)
        # pdf_loc is a dynamic attribute used only by PDF output
        child.pdf_loc = loc  # ty: ignore[unresolved-attribute]


def add_toc(pdf_parent: PDFOutlineRoot | PDFOutlineItem, toc_parent: TOC, log: Log, pdf_doc: PDFDoc) -> None:
    for child in toc_parent:
        title, loc = child.title or '', child.pdf_loc  # ty: ignore[unresolved-attribute] set in annotate_toc()
        try:
            pdf_child = pdf_parent.create(title, loc.pagenum, True, loc.left, loc.top, loc.zoom)
        except ValueError:
            if loc.pagenum > 1:
                log.warn(f'TOC node: {title} at page: {loc.pagenum} is beyond end of file, moving it to last page')
                pdf_child = pdf_parent.create(title, pdf_doc.page_count(), True, loc.left, loc.top, loc.zoom)
            else:
                log.warn(f'Ignoring TOC node: {title} at page: {loc.pagenum}')
                continue
        if len(child):
            add_toc(pdf_child, child, log, pdf_doc)


def get_page_number_display_map(render_manager: RenderManager, opts: Values, num_pages: int, log: Log) -> dict[int, int]:
    num_pages *= 2
    default_map = {n: n for n in range(1, num_pages + 1)}
    if opts.pdf_page_number_map:
        js = '''
        function map_num(n) { return eval(MAP_EXPRESSION); }
        var ans = {};
        for (var i=1; i <= NUM_PAGES; i++) ans[i] = map_num(i);
        JSON.stringify(ans);
        '''.replace('MAP_EXPRESSION', json.dumps(opts.pdf_page_number_map), 1).replace('NUM_PAGES', str(num_pages), 1)
        result = render_manager.evaljs(js)
        try:
            # JSON.stringify() returns a str, anything else causes json.loads() to raise, handled below
            result = json.loads(cast('str', result))
            if not isinstance(result, dict):
                raise TypeError('Not a dict')
        except Exception:
            log.warn(f'Could not do page number mapping, got unexpected result: {result!r}')
        else:
            default_map = {int(k): int(v) for k, v in result.items()}
    return default_map


def add_pagenum_toc(root: _Element, toc: TOC, opts: Values, page_number_display_map: dict[int, int]) -> None:
    body = last_tag(root)
    indents: list[float] = []
    for i in range(1, 7):
        indents.extend((i, 1.4 * i))

    css = (
        '''
    .calibre-pdf-toc table { width: 100%% }

    .calibre-pdf-toc table tr td:last-of-type { text-align: right }

    .calibre-pdf-toc .level-0 {
        font-size: larger;
    }

    .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
    .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
    .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
    .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
    .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
    .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
    '''  # ruff: ignore[printf-string-formatting]
        % tuple(indents)
        + (opts.extra_css or '')
    )
    style = body.makeelement(XHTML('style'), type='text/css')
    style.text = css
    body.append(style)
    body.set('class', 'calibre-pdf-toc')

    def E(tag: str, cls: str | None = None, text: str | None = None, tail: str | None = None, parent: _Element | None = None, **attrs: str) -> _Element:
        ans = body.makeelement(XHTML(tag), attrib=attrs)
        ans.text, ans.tail = text, tail
        if cls is not None:
            ans.set('class', cls)
        if parent is not None:
            parent.append(ans)
        return ans

    E('h2', text=(opts.toc_title or _('Table of Contents')), parent=body)
    table = E('table', parent=body)
    for level, node in toc.iterdescendants(level=0):
        tr = E('tr', cls=f'level-{level}', parent=table)
        E('td', text=node.title or _('Unknown'), parent=tr)
        num = node.pdf_loc.pagenum  # ty: ignore[unresolved-attribute] set in annotate_toc()
        num = page_number_display_map.get(num, num)
        E('td', text=f'{num}', parent=tr)


# }}}

# Fonts {{{


class PDFFont(TypedDict):
    # The dicts returned by PDFDoc.list_fonts(), see podofo/fonts.cpp
    BaseFont: str
    Subtype: str
    Reference: tuple[int, int]
    Data: bytes | None
    DescendantFont: tuple[int, int] | None
    StreamRef: tuple[int, int] | None
    Encoding: str | None
    ToUnicode: bytes | None
    W: WArray | None
    W2: WArray | None
    CIDToGIDMap: bytes | None
    sfnt: NotRequired[Sfnt]  # added by merge_fonts()


def all_glyph_ids_in_w_arrays(arrays: Iterable[WArray], as_set: bool = False) -> set[int] | list[int]:
    ans: set[int] = set()
    for w in arrays:
        i = 0
        while i + 1 < len(w):
            elem = cast('int', w[i])  # CIDs in W arrays are integers
            next_elem = w[i + 1]
            if isinstance(next_elem, list):
                ans |= set(range(elem, elem + len(next_elem)))
                i += 2
            else:
                ans |= set(range(elem, cast('int', next_elem) + 1))
                i += 3
    return ans if as_set else sorted(ans)


def fonts_are_identical(fonts: Iterable[PDFFont]) -> bool:
    sentinel = object()
    for key in ('ToUnicode', 'Data', 'W', 'W2'):
        prev_val = sentinel
        for f in fonts:
            val = f[key]
            if prev_val is not sentinel and prev_val != val:
                return False
            prev_val = val
    return True


def merge_font_files(fonts: list[PDFFont], log: Log) -> tuple[bytes, tuple[tuple[int, int], ...]]:
    # As of Qt 5.15.1 Chromium has switched to harfbuzz and dropped sfntly. It
    # now produces font descriptors whose W arrays don't match the glyph width
    # information from the hhea table, in contravention of the PDF spec. So
    # we can no longer merge font descriptors, all we can do is merge the
    # actual sfnt data streams into a single stream and subset it to contain
    # only the glyphs from all W arrays.
    # choose the largest font as the base font

    fonts.sort(key=lambda f: len(f['Data'] or b''), reverse=True)
    descendant_fonts = [f for f in fonts if f['Subtype'] != 'Type0']
    total_size = sum(len(f['Data'] or b'') for f in descendant_fonts)  # mergeable() ensures Data is not empty
    merged_sfnt = merge_truetype_fonts_for_pdf(tuple(f['sfnt'] for f in descendant_fonts), log)
    if False:
        # As of Qt 6.7.2 webengine produces W arrays that do not contain all
        # used glyph ids, so we cannot subset. Can be tested by
        # echo 'this is a test boulder sentence' > test.txt; ebook-convert test.txt .pdf
        w_arrays = tuple(filter(None, (f['W'] for f in descendant_fonts)))
        glyph_ids = all_glyph_ids_in_w_arrays(w_arrays, as_set=True)
        h_arrays = tuple(filter(None, (f['W2'] for f in descendant_fonts)))
        glyph_ids |= all_glyph_ids_in_w_arrays(h_arrays, as_set=True)
        try:
            pdf_subset(merged_sfnt, glyph_ids)
        except NoGlyphs:
            log.warn(f'Subsetting of {fonts[0]["BaseFont"]} failed with no glyphs found, ignoring')
    font_data = merged_sfnt()[0]
    log(f'Merged {len(fonts)} instances of {fonts[0]["BaseFont"]} reducing size from {human_readable(total_size)} to {human_readable(len(font_data))}')
    return font_data, tuple(f['Reference'] for f in descendant_fonts)


def merge_fonts(pdf_doc: PDFDoc, log: Log) -> None:
    # the stub for list_fonts() is imprecise, see list_fonts() in podofo/fonts.cpp
    all_fonts = cast('list[PDFFont]', pdf_doc.list_fonts(True))
    base_font_map: dict[str, list[PDFFont]] = {}

    def mergeable(fonts: list[PDFFont]) -> bool:
        has_type0 = False
        for font in fonts:
            if font['Subtype'] == 'Type0':
                has_type0 = True
                if not font['Encoding'] or not font['Encoding'].startswith('Identity-'):
                    return False
            else:
                if not font['Data']:
                    return False
                try:
                    sfnt = Sfnt(font['Data'])
                except UnsupportedFont:
                    return False
                font['sfnt'] = sfnt
                if b'glyf' not in sfnt:
                    return False
        return has_type0

    for f in all_fonts:
        base_font_map.setdefault(f['BaseFont'], []).append(f)
    for name, fonts in base_font_map.items():
        if mergeable(fonts):
            font_data, references = merge_font_files(fonts, log)
            pdf_doc.merge_fonts(font_data, references)


def test_merge_fonts() -> None:
    path = sys.argv[-1]
    podofo = get_podofo()
    pdf_doc = podofo.PDFDoc()
    pdf_doc.open(path)
    from calibre.utils.logging import default_log

    merge_fonts(pdf_doc, default_log)
    out = path.rpartition('.')[0] + '-merged.pdf'
    pdf_doc.save(out)
    print('Merged PDF written to', out)


# }}}

# Header/footer {{{

PAGE_NUMBER_TEMPLATE = '<footer><div style="margin: auto">_PAGENUM_</div></footer>'


def add_header_footer(
    manager: RenderManager,
    opts: Values,
    pdf_doc: PDFDoc,
    container: ContainerBase,
    page_number_display_map: dict[int, int],
    page_layout: QPageLayout,
    page_margins_map: Sequence[ResolvedMargins],
    pdf_metadata: PDFMetadata,
    report_progress: ProgressReporter,
    toc: TOC | None,
    log: Log,
) -> None:
    header_template, footer_template = opts.pdf_header_template, opts.pdf_footer_template
    if not footer_template and opts.pdf_page_numbers:
        footer_template = PAGE_NUMBER_TEMPLATE
    if not header_template and not footer_template:
        return
    report_progress(0.8, _('Adding headers and footers'))
    name = create_skeleton(container)
    root = parsed_html(container, name)
    reset_css = 'margin: 0; padding: 0; border-width: 0; background-color: unset; column-count: unset; column-width: unset;'
    root.set('style', reset_css)
    body = last_tag(root)
    body.attrib.pop('id', None)
    body.set('style', reset_css)
    job = job_for_name(container, name, Margins(0, 0, 0, 0), page_layout)
    page_layout = job[1]

    def m(tag_name: str, text: str | None = None, style: dict[str, str] | None = None, **attrs: str) -> _Element:
        ans = root.makeelement(XHTML(tag_name), attrib=attrs)
        if text is not None:
            ans.text = text
        if style is not None:
            style_str = '; '.join(f'{k}: {v}' for k, v in style.items())
            ans.set('style', style_str)
        return ans

    justify = 'flex-end'
    if header_template:
        justify = 'space-between' if footer_template else 'flex-start'

    def create_toc_stack(iterator: Iterable[tuple[int, TOC]]) -> list[tuple[int, int, str | None]]:
        ans: list[tuple[int, int, str | None]] = []
        for level, child in iterator:
            pdf_loc = getattr(child, 'pdf_loc', None)
            if pdf_loc is not None and pdf_loc.pagenum > 0:
                ans.append((level, pdf_loc.pagenum, child.title))
        return ans

    def stack_to_map(stack: Sequence[tuple[int, int, str | None]]) -> list[str | None]:
        ans: list[str | None] = []
        stack_pos = 0
        current, page_for_current, level_for_current = '', -1, -1
        stack_len = len(stack)
        for page in range(1, pdf_doc.page_count() + 1):
            while stack_pos < stack_len:
                level, pagenum, title = stack[stack_pos]
                if pagenum != page:
                    break
                if pagenum != page_for_current or level > level_for_current:
                    page_for_current = pagenum
                    level_for_current = level
                    current = title
                stack_pos += 1
            ans.append(current)
        return ans

    def page_counts_map(iterator: Iterable[tuple[int, TOC]]) -> tuple[list[int], list[int]]:
        pagenums: list[int] = []
        for level, child in iterator:
            pdf_loc = getattr(child, 'pdf_loc', None)
            if pdf_loc is not None and pdf_loc.pagenum > 0:
                pagenums.append(pdf_loc.pagenum)
        stack: list[tuple[int, int]] = []
        for i, pagenum in enumerate(pagenums):
            next_page_num = pagenums[i + 1] if i + 1 < len(pagenums) else (pdf_doc.page_count() + 1)
            stack.append((pagenum, next_page_num - pagenum))
        totals: list[int] = []
        section_nums: list[int] = []
        stack_len = len(stack)
        stack_pos = 0
        current, page_for_current, counter = 0, -1, 0
        for page in range(1, pdf_doc.page_count() + 1):
            while stack_pos < stack_len:
                pagenum, pages = stack[stack_pos]
                if pagenum != page:
                    break
                if pagenum != page_for_current:
                    current = pages
                    page_for_current = pagenum
                    counter = 0
                stack_pos += 1
            counter += 1
            totals.append(current)
            section_nums.append(counter)
        return totals, section_nums

    if toc is None:
        page_toc_map = stack_to_map(())
        toplevel_toc_map = stack_to_map(())
        toplevel_pagenum_map, toplevel_pages_map = page_counts_map(())
    else:
        page_toc_map = stack_to_map(create_toc_stack(toc.iterdescendants(level=0)))

        def tc() -> Iterator[tuple[int, TOC]]:
            for x in toc:
                yield 0, x

        toplevel_toc_map = stack_to_map(create_toc_stack(tc()))
        toplevel_pagenum_map, toplevel_pages_map = page_counts_map(tc())

    dpi = 96  # don't know how to query Qt for this, seems to be the same on all platforms

    def pt_to_px(pt: float) -> int:
        return int(pt * dpi / 72)

    def create_container(page_num: int, margins: ResolvedMargins) -> _Element:
        style = {
            'page-break-inside': 'avoid',
            'page-break-after': 'always',
            'display': 'flex',
            'flex-direction': 'column',
            'height': '100vh',
            'justify-content': justify,
            'margin-left': f'{margins.left}pt',
            'margin-right': f'{margins.right}pt',
            'margin-top': '0',
            'margin-bottom': '0',
            'padding': '0',
            'border-width': '0',
            'overflow': 'hidden',
            'background-color': 'unset',
        }
        ans = m('div', style=style, id=f'p{page_num}')
        return ans

    def format_template(template: str, page_num: int, height: float, margins: ResolvedMargins) -> _Element:
        div_width_px = pt_to_px(page_layout.paintRectPoints().width() - margins.left - margins.right)
        template = template.replace('_TOP_LEVEL_SECTION_PAGES_', str(toplevel_pagenum_map[page_num - 1]))
        template = template.replace('_TOP_LEVEL_SECTION_PAGENUM_', str(toplevel_pages_map[page_num - 1]))
        template = template.replace('_TOTAL_PAGES_', str(pages_in_doc))
        template = template.replace('_PAGENUM_', str(page_number_display_map[page_num]))
        template = template.replace('_TITLE_', prepare_string_for_xml(pdf_metadata.title, True))
        template = template.replace('_AUTHOR_', prepare_string_for_xml(pdf_metadata.author, True))
        template = template.replace('_TOP_LEVEL_SECTION_', prepare_string_for_xml(cast('str', toplevel_toc_map[page_num - 1])))
        template = template.replace('_SECTION_', prepare_string_for_xml(cast('str', page_toc_map[page_num - 1])))
        template = template.replace('_WIDTH_PIXELS_', str(div_width_px))
        template = template.replace('_HEIGHT_PIXELS_', str(pt_to_px(height)))
        troot = parse(template, namespace_elements=True)
        ans = last_tag(troot)[0]
        style = ans.get('style') or ''
        style = (
            f'margin: 0; padding: 0; height: {height}pt; border-width: 0;display: flex; align-items: center; overflow: hidden; background-color: unset;'
        ) + style
        ans.set('style', style)
        for child in ans.xpath('descendant-or-self::*[@class]'):
            cls = frozenset(child.get('class').split())
            q = 'even-page' if page_num % 2 else 'odd-page'
            if q in cls or q.replace('-', '_') in cls:
                style = child.get('style') or ''
                child.set('style', style + '; display: none')
        return ans

    pages_in_doc = pdf_doc.page_count()

    for page_num in range(1, pages_in_doc + 1):
        margins = page_margins_map[page_num - 1]
        div = create_container(page_num, margins)
        body.append(div)
        if header_template:
            div.append(format_template(header_template, page_num, margins.top, margins))
        if footer_template:
            div.append(format_template(footer_template, page_num, margins.bottom, margins))

    container.commit()
    # print(container.raw_data(name))
    results = manager.convert_html_files([job], settle_time=1)
    data = results[name]
    if not isinstance(data, bytes):
        raise SystemExit(data)
    # open('/t/impose.pdf', 'wb').write(data)
    doc = data_as_pdf_doc(data)
    first_page_num = pdf_doc.page_count()
    num_pages = doc.page_count()
    if first_page_num != num_pages:
        raise ValueError(f'The number of header/footers pages ({num_pages}) < number of document pages ({first_page_num})')
    pdf_doc.append(doc)
    pdf_doc.impose(1, first_page_num + 1, num_pages)
    report_progress(0.9, _('Headers and footers added'))


# }}}

# Maths {{{


@lru_cache(maxsize=2)
def mathjax_dir() -> str:
    return P('mathjax', allow_user_override=False)


def add_maths_script(container: ContainerBase) -> dict[str, bool]:
    has_maths: dict[str, bool] = {}
    for name, is_linear in container.spine_names:
        root = parsed_html(container, name)
        has_maths[name] = hm = check_for_maths(root)
        if not hm:
            continue
        script = root.makeelement(
            XHTML('script'),
            type='text/javascript',
            src=f'{FAKE_PROTOCOL}://{FAKE_HOST}/mathjax/loader/pdf-mathjax-loader.js',
        )
        script.set('async', 'async')
        script.set('data-mathjax-path', f'{FAKE_PROTOCOL}://{FAKE_HOST}/mathjax/data/')
        last_tag(root).append(script)
    return has_maths


# }}}


def fix_markup(container: ContainerBase) -> None:
    xp = XPath('//h:canvas')
    for file_name, is_linear in container.spine_names:
        root = parsed_html(container, file_name)
        for canvas in xp(root):
            # Canvas causes rendering issues, see https://bugs.launchpad.net/bugs/1859040
            # for an example.
            canvas.tag = XHTML('div')


def convert(
    opf_path: str,
    opts: Values,
    metadata: Metadata | None = None,
    output_path: str | None = None,
    log: Log = default_log,
    cover_data: bytes | None = None,
    report_progress: ProgressReporter = lambda x, y: None,
) -> bytes | None:
    container = Container(opf_path, log)
    fix_markup(container)
    report_progress(0.05, _('Parsed all content for markup transformation'))
    if opts.pdf_hyphenate:
        from calibre.ebooks.oeb.polish.hyphenation import add_soft_hyphens

        add_soft_hyphens(container)
    has_maths = add_maths_script(container)
    fix_fullscreen_images(container)

    name_anchor_map = make_anchors_unique(container, log)
    margin_files = tuple(create_margin_files(container))
    toc = get_toc(container, verify_destinations=False)
    has_toc = toc and len(toc)
    links_page_uuid = add_all_links(container, margin_files)
    container.commit()
    report_progress(0.1, _('Completed markup transformation'))

    manager = RenderManager(opts, log, container)
    page_layout = get_page_layout(opts)
    pdf_doc = None
    anchor_locations: dict[str, AnchorLocation] = {}
    jobs: list[Job] = []
    for margin_file in margin_files:
        jobs.append(job_for_name(container, margin_file.name, margin_file.margins, page_layout))
    results = manager.convert_html_files(jobs, settle_time=1, has_maths=has_maths)
    num_pages = 0
    page_margins_map: list[ResolvedMargins] = []
    all_docs: list[PDFDoc] = []
    for i, margin_file in enumerate(margin_files):
        name = margin_file.name
        data = results[name]
        if not isinstance(data, bytes):
            raise SystemExit(data)
        doc = data_as_pdf_doc(data)
        effective_margins = resolve_margins(margin_file.margins, page_layout)
        anchor_locations.update(get_anchor_locations(name, doc, num_pages + 1, links_page_uuid, log, effective_margins.top))
        doc_pages = doc.page_count()
        page_margins_map.extend(repeat(effective_margins, doc_pages))
        num_pages += doc_pages
        all_docs.append(doc)

    pdf_doc = all_docs[0]
    pdf_doc.append(*all_docs[1:])

    page_number_display_map = get_page_number_display_map(manager, opts, num_pages, log)

    if has_toc:
        annotate_toc(toc, anchor_locations, name_anchor_map, log)
        if opts.pdf_add_toc:
            tocname = create_skeleton(container)
            root = parsed_html(container, tocname)
            add_pagenum_toc(root, toc, opts, page_number_display_map)
            container.commit()
            jobs = [job_for_name(container, tocname, None, page_layout)]
            results = manager.convert_html_files(jobs, settle_time=1)
            data = results[tocname]
            if not isinstance(data, bytes):
                raise SystemExit(data)
            tocdoc = data_as_pdf_doc(data)
            page_margins_map.extend(repeat(resolve_margins(None, page_layout), tocdoc.page_count()))
            pdf_doc.append(tocdoc)

    report_progress(0.7, _('Rendered all HTML as PDF'))

    fix_links(pdf_doc, anchor_locations, name_anchor_map, opts.pdf_mark_links, log)
    if toc and len(toc):
        add_toc(PDFOutlineRoot(pdf_doc), toc, log, pdf_doc)
    report_progress(0.75, _('Added links to PDF content'))

    pdf_metadata = PDFMetadata(metadata)
    add_header_footer(
        manager,
        opts,
        pdf_doc,
        container,
        page_number_display_map,
        page_layout,
        page_margins_map,
        pdf_metadata,
        report_progress,
        toc if has_toc else None,
        log,
    )

    num_removed = remove_unused_fonts(pdf_doc)
    if num_removed:
        log('Removed', num_removed, 'unused fonts')

    merge_fonts(pdf_doc, log)
    num_removed = dedup_type3_fonts(pdf_doc)
    if num_removed:
        log('Removed', num_removed, 'duplicated Type3 glyphs')

    num_removed = pdf_doc.dedup_images()
    if num_removed:
        log('Removed', num_removed, 'duplicate images')

    if opts.pdf_odd_even_offset:
        for page_num in range(1, pdf_doc.page_count() + 1):
            margins = page_margins_map[page_num - 1]
            mult = -1 if page_num % 2 else 1
            val = opts.pdf_odd_even_offset
            if abs(val) < min(margins.left, margins.right):
                box = list(pdf_doc.get_page_box('CropBox', page_num))
                box[0] += val * mult
                pdf_doc.set_page_box('CropBox', page_num, *box)

    if cover_data:
        add_cover(pdf_doc, cover_data, page_layout, opts)

    if metadata is not None:
        update_metadata(pdf_doc, pdf_metadata)
    pdf_doc.creator = pdf_doc.producer = __appname__ + ' ' + __version__
    report_progress(1, _('Updated metadata in PDF'))

    if opts.uncompressed_pdf:
        pdf_doc.uncompress()

    pdf_data = pdf_doc.write()
    if output_path is None:
        return pdf_data
    with open(output_path, 'wb') as f:
        f.write(pdf_data)
