#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

# Imports {{{


import copy
import json
import os
import signal
import sys
from collections import namedtuple
from functools import lru_cache
from html5_parser import parse
from io import BytesIO
from itertools import count, repeat
from qt.core import (
    QApplication, QByteArray, QMarginsF, QObject, QPageLayout, Qt, QTimer, QUrl,
    pyqtSignal, sip
)
from qt.webengine import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
    QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler
)

from calibre import detect_ncpus, human_readable, prepare_string_for_xml
from calibre.constants import (
    FAKE_HOST, FAKE_PROTOCOL, __version__, ismacos, iswindows
)
from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
from calibre.ebooks.oeb.base import XHTML, XPath
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.pdf.image_writer import (
    Image, PDFMetadata, draw_image_page, get_page_layout
)
from calibre.ebooks.pdf.render.serialize import PDFStream
from calibre.gui2 import setup_unix_signals
from calibre.srv.render_book import check_for_maths
from calibre.utils.fonts.sfnt.container import Sfnt, UnsupportedFont
from calibre.utils.fonts.sfnt.errors import NoGlyphs
from calibre.utils.fonts.sfnt.merge import merge_truetype_fonts_for_pdf
from calibre.utils.fonts.sfnt.subset import pdf_subset
from calibre.utils.logging import default_log
from calibre.utils.monotonic import monotonic
from calibre.utils.podofo import (
    dedup_type3_fonts, get_podofo, remove_unused_fonts, set_metadata_implementation
)
from calibre.utils.short_uuid import uuid4
from calibre.utils.webengine import secure_webengine, send_reply
from polyglot.builtins import as_bytes, iteritems
from polyglot.urllib import urlparse

OK, KILL_SIGNAL = range(0, 2)
HANG_TIME = 60  # seconds
# }}}


# Utils {{{
def data_as_pdf_doc(data):
    podofo = get_podofo()
    ans = podofo.PDFDoc()
    ans.load(data)
    return ans


def preprint_js():
    ans = getattr(preprint_js, 'ans', None)
    if ans is None:
        ans = preprint_js.ans = P('pdf-preprint.js', data=True).decode('utf-8').replace('HYPHEN_CHAR', 'true' if ismacos else 'false', 1)
    return ans


def last_tag(root):
    return tuple(root.iterchildren('*'))[-1]


def create_skeleton(container):
    spine_name = tuple(container.spine_names)[-1][0]
    root = container.parsed(spine_name)
    root = copy.deepcopy(root)
    body = last_tag(root)
    body.text = body.tail = None
    del body[:]
    name = container.add_file(spine_name, b'', modify_name_if_needed=True)
    container.replace(name, root)
    return name


def local_name(x):
    return x.split('}', 1)[-1].lower()


def fix_fullscreen_images(container):

    def is_svg_fs_markup(names, svg):
        if svg is not None:
            if len(names) == 2 or len(names) == 3:
                if names[-1] == 'image' and names[-2] == 'svg':
                    if len(names) == 2 or names[0] == 'div':
                        if svg.get('width') == '100%' and svg.get('height') == '100%':
                            return True
        return False

    for file_name, is_linear in container.spine_names:
        root = container.parsed(file_name)
        root_kids = tuple(root.iterchildren('*'))
        if not root_kids:
            continue
        body = root_kids[-1]
        child_tags = []
        for child in body.iterchildren('*'):
            tag = local_name(child.tag)
            if tag in ('script', 'style'):
                continue
            child_tags.append(tag)
            if len(child_tags) > 1:
                break
        if len(child_tags) == 1 and child_tags[0] in ('div', 'svg'):
            names = []
            svg = None
            for elem in body.iterdescendants('*'):
                name = local_name(elem.tag)
                if name != 'style' and name != 'script':
                    names.append(name)
                    if name == 'svg':
                        svg = elem
            if is_svg_fs_markup(names, svg):
                svg.set('width', '100vw')
                svg.set('height', '100vh')
                container.dirty(file_name)
# }}}


# Renderer {{{
class Container(ContainerBase):

    tweak_mode = True
    is_dir = True

    def __init__(self, opf_path, log, root_dir=None):
        ContainerBase.__init__(self, root_dir or os.path.dirname(opf_path), opf_path, log)


class UrlSchemeHandler(QWebEngineUrlSchemeHandler):

    def __init__(self, container, parent=None):
        QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.allowed_hosts = (FAKE_HOST,)
        self.container = container

    def requestStarted(self, rq):
        if bytes(rq.requestMethod()) != b'GET':
            return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestDenied)
        url = rq.requestUrl()
        host = url.host()
        if host not in self.allowed_hosts or url.scheme() != FAKE_PROTOCOL:
            return self.fail_request(rq)
        path = url.path()
        if path.startswith('/book/'):
            name = path[len('/book/'):]
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
                    rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                    return
                data = as_bytes(data)
                mime_type = {
                    # Prevent warning in console about mimetype of fonts
                    'application/vnd.ms-opentype':'application/x-font-ttf',
                    'application/x-font-truetype':'application/x-font-ttf',
                    'application/font-sfnt': 'application/x-font-ttf',
                }.get(mime_type, mime_type)
                send_reply(rq, mime_type, data)
            except Exception:
                import traceback
                traceback.print_exc()
                return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestFailed)
        elif path.startswith('/mathjax/'):
            try:
                ignore, ignore, base, rest = path.split('/', 3)
            except ValueError:
                print(f'Could not find file {path} in mathjax', file=sys.stderr)
                rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
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
                send_reply(rq, mime_type, data)
            except FileNotFoundError:
                print(f'Could not find file {path} in mathjax', file=sys.stderr)
                rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            except Exception:
                import traceback
                traceback.print_exc()
                return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestFailed)
        else:
            return self.fail_request(rq)

    def fail_request(self, rq, fail_code=None):
        if fail_code is None:
            fail_code = QWebEngineUrlRequestJob.Error.UrlNotFound
        rq.fail(fail_code)
        print(f"Blocking FAKE_PROTOCOL request: {rq.requestUrl().toString()} with code: {fail_code}", file=sys.stderr)

# }}}


class Renderer(QWebEnginePage):

    work_done = pyqtSignal(object, object)

    def __init__(self, opts, parent, log):
        QWebEnginePage.__init__(self, parent.profile, parent)
        secure_webengine(self)
        self.working = False
        self.log = log
        self.load_complete = False
        self.settle_time = 0
        self.wait_for_title = None
        s = self.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, int(opts.pdf_default_font_size))
        s.setFontSize(QWebEngineSettings.FontSize.DefaultFixedFontSize, int(opts.pdf_mono_font_size))
        s.setFontSize(QWebEngineSettings.FontSize.MinimumLogicalFontSize, 8)
        s.setFontSize(QWebEngineSettings.FontSize.MinimumFontSize, 8)
        std = {
            'serif': opts.pdf_serif_family,
            'sans' : opts.pdf_sans_family,
            'mono' : opts.pdf_mono_family
        }.get(opts.pdf_standard_font, opts.pdf_serif_family)
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
        self.load_started_at = 0
        t.setTimerType(Qt.TimerType.VeryCoarseTimer)
        t.setInterval(HANG_TIME * 1000)
        t.setSingleShot(True)
        t.timeout.connect(self.on_load_hang)

    def load_started(self):
        self.load_started_at = monotonic()
        self.load_complete = False
        self.load_hang_check_timer.start()

    def load_progress(self, amt):
        self.load_hang_check_timer.start()

    def on_load_hang(self):
        self.log(self.log_prefix, f'Loading not complete after {int(monotonic() - self.load_started_at)} seconds, aborting.')
        self.load_finished(False)

    def title_changed(self, title):
        if self.wait_for_title and title == self.wait_for_title and self.load_complete:
            QTimer.singleShot(self.settle_time, self.print_to_pdf)

    @property
    def log_prefix(self):
        return os.path.basename(self.url().toLocalFile()) + ':'

    def load_finished(self, ok):
        self.load_complete = True
        self.load_hang_check_timer.stop()
        if not ok:
            self.working = False
            self.work_done.emit(self, f'Load of {self.url().toString()} failed')
            return
        if self.wait_for_title and self.title() != self.wait_for_title:
            self.log(self.log_prefix, 'Load finished, waiting for title to change to:', self.wait_for_title)
            return
        QTimer.singleShot(int(1000 * self.settle_time), self.print_to_pdf)

    def javaScriptConsoleMessage(self, level, message, linenum, source_id):
        try:
            self.log(f'{source_id}:{linenum}:{message}')
        except Exception:
            pass

    def print_to_pdf(self):
        self.runJavaScript(preprint_js(), self.start_print)

    def start_print(self, *a):
        self.printToPdf(self.printing_done, self.page_layout)

    def printing_done(self, pdf_data):
        self.working = False
        if not sip.isdeleted(self):
            self.work_done.emit(self, bytes(pdf_data))

    def convert_html_file(self, path, page_layout, settle_time=0, wait_for_title=None):
        self.working = True
        self.load_complete = False
        self.wait_for_title = wait_for_title

        self.settle_time = settle_time
        self.page_layout = page_layout
        url = QUrl(f'{FAKE_PROTOCOL}://{FAKE_HOST}/')
        url.setPath(path)
        self.setUrl(url)


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    def interceptRequest(self, request_info):
        method = bytes(request_info.requestMethod())
        if method not in (b'GET', b'HEAD'):
            self.log.warn(f'Blocking URL request with method: {method}')
            request_info.block(True)
            return
        qurl = request_info.requestUrl()
        if qurl.scheme() not in (FAKE_PROTOCOL,):
            self.log.warn(f'Blocking URL request {qurl.toString()} as it is not for a resource in the book')
            request_info.block(True)
            return


class RenderManager(QObject):

    def __init__(self, opts, log, container):
        QObject.__init__(self)
        self.interceptor = RequestInterceptor(self)
        self.has_maths = {}
        self.interceptor.log = self.log = log
        ans = QWebEngineProfile(QApplication.instance())
        self.url_handler = UrlSchemeHandler(container, parent=ans)
        ans.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), self.url_handler)
        ua = 'calibre-pdf-output ' + __version__
        ans.setHttpUserAgent(ua)
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        ans.setUrlRequestInterceptor(self.interceptor)
        self.profile = ans

        self.opts = opts
        self.workers = []
        self.max_workers = detect_ncpus()
        if iswindows:
            self.original_signal_handlers = {}
        else:
            self.original_signal_handlers = setup_unix_signals(self)

    def create_worker(self):
        worker = Renderer(self.opts, self, self.log)
        worker.work_done.connect(self.work_done)
        self.workers.append(worker)

    def signal_received(self, read_fd):
        try:
            os.read(read_fd, 1024)
        except OSError:
            return
        QApplication.instance().exit(KILL_SIGNAL)

    def block_signal_handlers(self):
        for sig in self.original_signal_handlers:
            signal.signal(sig, lambda x, y: None)

    def restore_signal_handlers(self):
        for sig, handler in self.original_signal_handlers.items():
            signal.signal(sig, handler)

    def run_loop(self):
        self.block_signal_handlers()
        try:
            return QApplication.exec()
        finally:
            self.restore_signal_handlers()

    def convert_html_files(self, jobs, settle_time=0, wait_for_title=None, has_maths=None):
        self.has_maths = has_maths or {}
        while len(self.workers) < min(len(jobs), self.max_workers):
            self.create_worker()
        self.pending = list(jobs)
        self.results = {}
        self.settle_time = settle_time
        self.wait_for_title = wait_for_title
        QTimer.singleShot(0, self.assign_work)
        ret = self.run_loop()
        self.has_maths = {}
        if ret == KILL_SIGNAL:
            raise SystemExit('Kill signal received')
        if ret != OK:
            raise SystemExit('Unknown error occurred')
        return self.results

    def evaljs(self, js):
        if not self.workers:
            self.create_worker()
        w = self.workers[0]
        self.evaljs_result = None
        w.runJavaScript(js, self.evaljs_callback)
        QApplication.exec()
        return self.evaljs_result

    def evaljs_callback(self, result):
        self.evaljs_result = result
        QApplication.instance().exit(0)

    def assign_work(self):
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

    def work_done(self, worker, result):
        self.results[worker.result_key] = result
        if self.pending:
            self.assign_work()
        else:
            for w in self.workers:
                if w.working:
                    return
            QApplication.instance().exit(OK)


def resolve_margins(margins, page_layout):
    old_margins = page_layout.marginsPoints()

    def m(which):
        ans = getattr(margins, which, None)
        if ans is None:
            ans = getattr(old_margins, which)()
        return ans
    return Margins(*map(m, 'left top right bottom'.split()))


def job_for_name(container, name, margins, page_layout):
    index_file = '/book/' + name
    if margins:
        page_layout = QPageLayout(page_layout)
        page_layout.setUnits(QPageLayout.Unit.Point)
        new_margins = QMarginsF(*resolve_margins(margins, page_layout))
        page_layout.setMargins(new_margins)
    return index_file, page_layout, name
# }}}


# Metadata {{{
def update_metadata(pdf_doc, pdf_metadata):
    if pdf_metadata.mi:
        xmp_packet = metadata_to_xmp_packet(pdf_metadata.mi)
        set_metadata_implementation(
            pdf_doc, pdf_metadata.title, pdf_metadata.mi.authors,
            pdf_metadata.mi.book_producer, pdf_metadata.mi.tags, xmp_packet)


def add_cover(pdf_doc, cover_data, page_layout, opts):
    buf = BytesIO()
    page_size = page_layout.fullRectPoints().size()
    img = Image(cover_data)
    writer = PDFStream(buf, (page_size.width(), page_size.height()), compress=True)
    writer.apply_fill(color=(1, 1, 1))
    draw_image_page(writer, img, preserve_aspect_ratio=opts.preserve_cover_aspect_ratio)
    writer.end()
    cover_pdf_doc = data_as_pdf_doc(buf.getvalue())
    pdf_doc.insert_existing_page(cover_pdf_doc)
# }}}


# Margin groups {{{

Margins = namedtuple('Margins', 'left top right bottom')
MarginFile = namedtuple('MarginFile', 'name margins')


def dict_to_margins(val, d=None):
    return Margins(val.get('left', d), val.get('top', d), val.get('right', d), val.get('bottom', d))


def create_margin_files(container):
    for name, is_linear in container.spine_names:
        root = container.parsed(name)
        margins = root.get('data-calibre-pdf-output-page-margins')
        if margins:
            margins = dict_to_margins(json.loads(margins))
        yield MarginFile(name, margins)
# }}}


# Link handling  {{{
def add_anchors_markup(root, uuid, anchors):
    body = last_tag(root)
    div = body.makeelement(
        XHTML('div'), id=uuid,
        style='display:block !important; page-break-before: always !important; break-before: always !important; white-space: pre-wrap !important'
    )
    div.text = '\n\n'
    body.append(div)
    c = count()

    def a(anchor):
        num = next(c)
        a = div.makeelement(
            XHTML('a'), href='#' + anchor,
            style='min-width: 10px !important; min-height: 10px !important;'
            ' border: solid 1px rgba(0, 0, 0, 0) !important; text-decoration: none !important'
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


def add_all_links(container, margin_files):
    uuid = uuid4()
    name_anchor_map = {}
    for name, is_linear in container.spine_names:
        root = container.parsed(name)
        name_anchor_map[name] = frozenset(root.xpath('//*/@id'))
    for margin_file in margin_files:
        name = margin_file.name
        anchors = name_anchor_map.get(name, set())
        add_anchors_markup(container.parsed(name), uuid, anchors)
        container.dirty(name)
    return uuid


def make_anchors_unique(container, log):
    mapping = {}
    count = 0
    base = None
    spine_names = set()

    def replacer(url):
        if replacer.file_type not in ('text', 'ncx'):
            return url
        if not url:
            return url
        if '#' not in url:
            url += '#'
        if url.startswith('#'):
            href, frag = base, url[1:]
            name = base
        else:
            href, frag = url.partition('#')[::2]
            name = container.href_to_name(href, base)
        if not name:
            return url.rstrip('#')
        if not frag and name in spine_names:
            replacer.replaced = True
            return 'https://calibre-pdf-anchor.n#' + name
        key = name, frag
        new_frag = mapping.get(key)
        if new_frag is None:
            if name in spine_names:
                log.warn(f'Link anchor: {name}#{frag} not found, linking to top of file instead')
                replacer.replaced = True
                return 'https://calibre-pdf-anchor.n#' + name
            return url.rstrip('#')
        replacer.replaced = True
        return 'https://calibre-pdf-anchor.a#' + new_frag
        if url.startswith('#'):
            return '#' + new_frag
        return href + '#' + new_frag

    name_anchor_map = {}
    for spine_name, is_linear in container.spine_names:
        spine_names.add(spine_name)
        root = container.parsed(spine_name)
        for elem in root.xpath('//*[@id]'):
            count += 1
            key = spine_name, elem.get('id')
            if key not in mapping:
                new_id = mapping[key] = f'a{count}'
                elem.set('id', new_id)
        body = last_tag(root)
        if not body.get('id'):
            count += 1
            body.set('id', f'a{count}')
        name_anchor_map[spine_name] = body.get('id')

    for name in container.mime_map:
        base = name
        replacer.replaced = False
        container.replace_links(name, replacer)
    return name_anchor_map


class AnchorLocation:

    __slots__ = ('pagenum', 'left', 'top', 'zoom')

    def __init__(self, pagenum=1, left=0, top=0, zoom=0):
        self.pagenum, self.left, self.top, self.zoom = pagenum, left, top, zoom

    def __repr__(self):
        return 'AnchorLocation(pagenum={}, left={}, top={}, zoom={})'.format(*self.as_tuple)

    @property
    def as_tuple(self):
        return self.pagenum, self.left, self.top, self.zoom


def get_anchor_locations(name, pdf_doc, first_page_num, toc_uuid, log):
    ans = {}
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
    for anchor, loc in iteritems(anchors):
        loc = list(loc)
        loc[0] += first_page_num - 1
        ans[anchor] = AnchorLocation(*loc)
    return ans


def fix_links(pdf_doc, anchor_locations, name_anchor_map, mark_links, log):
    pc = pdf_doc.page_count()

    def replace_link(url):
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

    def __init__(self, pdf_doc):
        self.pdf_doc = pdf_doc
        self.root_item = None

    def create(self, title, pagenum, as_child, left, top, zoom):
        if self.root_item is None:
            self.root_item = self.pdf_doc.create_outline(title, pagenum, left, top, zoom)
        else:
            self.root_item = self.root_item.create(title, pagenum, False, left, top, zoom)
        return self.root_item


def annotate_toc(toc, anchor_locations, name_anchor_map, log):
    for child in toc.iterdescendants():
        frag = child.frag
        try:
            if '.' in frag:
                loc = anchor_locations[name_anchor_map[frag]]
            else:
                loc = anchor_locations[frag]
        except Exception:
            log.warn(f'Could not find anchor location for ToC entry: {child.title} with href: {frag}')
            loc = AnchorLocation(1, 0, 0, 0)
        child.pdf_loc = loc


def add_toc(pdf_parent, toc_parent, log, pdf_doc):
    for child in toc_parent:
        title, loc = child.title, child.pdf_loc
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


def get_page_number_display_map(render_manager, opts, num_pages, log):
    num_pages *= 2
    default_map = {n:n for n in range(1, num_pages + 1)}
    if opts.pdf_page_number_map:
        js = '''
        function map_num(n) { return eval(MAP_EXPRESSION); }
        var ans = {};
        for (var i=1; i <= NUM_PAGES; i++) ans[i] = map_num(i);
        JSON.stringify(ans);
        '''.replace('MAP_EXPRESSION', json.dumps(opts.pdf_page_number_map), 1).replace(
                'NUM_PAGES', str(num_pages), 1)
        result = render_manager.evaljs(js)
        try:
            result = json.loads(result)
            if not isinstance(result, dict):
                raise ValueError('Not a dict')
        except Exception:
            log.warn(f'Could not do page number mapping, got unexpected result: {repr(result)}')
        else:
            default_map = {int(k): int(v) for k, v in iteritems(result)}
    return default_map


def add_pagenum_toc(root, toc, opts, page_number_display_map):
    body = last_tag(root)
    indents = []
    for i in range(1, 7):
        indents.extend((i, 1.4*i))

    css = '''
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
    ''' % tuple(indents) + (opts.extra_css or '')
    style = body.makeelement(XHTML('style'), type='text/css')
    style.text = css
    body.append(style)
    body.set('class', 'calibre-pdf-toc')

    def E(tag, cls=None, text=None, tail=None, parent=None, **attrs):
        ans = body.makeelement(XHTML(tag), **attrs)
        ans.text, ans.tail = text, tail
        if cls is not None:
            ans.set('class', cls)
        if parent is not None:
            parent.append(ans)
        return ans

    E('h2', text=(opts.toc_title or _('Table of Contents')), parent=body)
    table = E('table', parent=body)
    for level, node in toc.iterdescendants(level=0):
        tr = E('tr', cls='level-%d' % level, parent=table)
        E('td', text=node.title or _('Unknown'), parent=tr)
        num = node.pdf_loc.pagenum
        num = page_number_display_map.get(num, num)
        E('td', text=f'{num}', parent=tr)

# }}}


# Fonts {{{


def all_glyph_ids_in_w_arrays(arrays, as_set=False):
    ans = set()
    for w in arrays:
        i = 0
        while i + 1 < len(w):
            elem = w[i]
            next_elem = w[i+1]
            if isinstance(next_elem, list):
                ans |= set(range(elem, elem + len(next_elem)))
                i += 2
            else:
                ans |= set(range(elem, next_elem + 1))
                i += 3
    return ans if as_set else sorted(ans)


def fonts_are_identical(fonts):
    sentinel = object()
    for key in ('ToUnicode', 'Data', 'W', 'W2'):
        prev_val = sentinel
        for f in fonts:
            val = f[key]
            if prev_val is not sentinel and prev_val != val:
                return False
            prev_val = val
    return True


def merge_font_files(fonts, log):
    # As of Qt 5.15.1 Chromium has switched to harfbuzz and dropped sfntly. It
    # now produces font descriptors whose W arrays dont match the glyph width
    # information from the hhea table, in contravention of the PDF spec. So
    # we can no longer merge font descriptors, all we can do is merge the
    # actual sfnt data streams into a single stream and subset it to contain
    # only the glyphs from all W arrays.
    # choose the largest font as the base font

    fonts.sort(key=lambda f: len(f['Data'] or b''), reverse=True)
    descendant_fonts = [f for f in fonts if f['Subtype'] != 'Type0']
    total_size = sum(len(f['Data']) for f in descendant_fonts)
    merged_sfnt = merge_truetype_fonts_for_pdf(tuple(f['sfnt'] for f in descendant_fonts), log)
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


def merge_fonts(pdf_doc, log):
    all_fonts = pdf_doc.list_fonts(True)
    base_font_map = {}

    def mergeable(fonts):
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
    for name, fonts in iteritems(base_font_map):
        if mergeable(fonts):
            font_data, references = merge_font_files(fonts, log)
            pdf_doc.merge_fonts(font_data, references)


def test_merge_fonts():
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


def add_header_footer(manager, opts, pdf_doc, container, page_number_display_map, page_layout, page_margins_map, pdf_metadata, report_progress, toc=None):
    header_template, footer_template = opts.pdf_header_template, opts.pdf_footer_template
    if not footer_template and opts.pdf_page_numbers:
        footer_template = PAGE_NUMBER_TEMPLATE
    if not header_template and not footer_template:
        return
    report_progress(0.8, _('Adding headers and footers'))
    name = create_skeleton(container)
    root = container.parsed(name)
    reset_css = 'margin: 0; padding: 0; border-width: 0; background-color: unset;'
    root.set('style', reset_css)
    body = last_tag(root)
    body.attrib.pop('id', None)
    body.set('style', reset_css)
    job = job_for_name(container, name, Margins(0, 0, 0, 0), page_layout)

    def m(tag_name, text=None, style=None, **attrs):
        ans = root.makeelement(XHTML(tag_name), **attrs)
        if text is not None:
            ans.text = text
        if style is not None:
            style = '; '.join(f'{k}: {v}' for k, v in iteritems(style))
            ans.set('style', style)
        return ans

    justify = 'flex-end'
    if header_template:
        justify = 'space-between' if footer_template else 'flex-start'

    def create_toc_stack(iterator):
        ans = []
        for level, child in iterator:
            pdf_loc = getattr(child, 'pdf_loc', None)
            if pdf_loc is not None and pdf_loc.pagenum > 0:
                ans.append((level, pdf_loc.pagenum, child.title))
        return ans

    def stack_to_map(stack):
        ans = []
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

    def page_counts_map(iterator):
        pagenums = []
        for level, child in iterator:
            pdf_loc = getattr(child, 'pdf_loc', None)
            if pdf_loc is not None and pdf_loc.pagenum > 0:
                pagenums.append(pdf_loc.pagenum)
        stack = []
        for i, pagenum in enumerate(pagenums):
            next_page_num = pagenums[i + 1] if i + 1 < len(pagenums) else (pdf_doc.page_count() + 1)
            stack.append((pagenum, next_page_num - pagenum))
        totals = []
        section_nums = []
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

        def tc():
            for x in toc:
                yield 0, x

        toplevel_toc_map = stack_to_map(create_toc_stack(tc()))
        toplevel_pagenum_map, toplevel_pages_map = page_counts_map(tc())

    def create_container(page_num, margins):
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

    def format_template(template, page_num, height):
        template = template.replace('_TOP_LEVEL_SECTION_PAGES_', str(toplevel_pagenum_map[page_num - 1]))
        template = template.replace('_TOP_LEVEL_SECTION_PAGENUM_', str(toplevel_pages_map[page_num - 1]))
        template = template.replace('_TOTAL_PAGES_', str(pages_in_doc))
        template = template.replace('_PAGENUM_', str(page_number_display_map[page_num]))
        template = template.replace('_TITLE_', prepare_string_for_xml(pdf_metadata.title, True))
        template = template.replace('_AUTHOR_', prepare_string_for_xml(pdf_metadata.author, True))
        template = template.replace('_TOP_LEVEL_SECTION_', prepare_string_for_xml(toplevel_toc_map[page_num - 1]))
        template = template.replace('_SECTION_', prepare_string_for_xml(page_toc_map[page_num - 1]))
        troot = parse(template, namespace_elements=True)
        ans = last_tag(troot)[0]
        style = ans.get('style') or ''
        style = (
            'margin: 0; padding: 0; height: {height}pt; border-width: 0;'
            'display: flex; align-items: center; overflow: hidden; background-color: unset;').format(height=height) + style
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
            div.append(format_template(header_template, page_num, margins.top))
        if footer_template:
            div.append(format_template(footer_template, page_num, margins.bottom))

    container.commit()
    # print(open(job[0]).read())
    results = manager.convert_html_files([job], settle_time=1)
    data = results[name]
    if not isinstance(data, bytes):
        raise SystemExit(data)
    # open('/t/impose.pdf', 'wb').write(data)
    doc = data_as_pdf_doc(data)
    first_page_num = pdf_doc.page_count()
    num_pages = doc.page_count()
    if first_page_num != num_pages:
        raise ValueError('The number of header/footers pages ({}) != number of document pages ({})'.format(
            num_pages, first_page_num))
    pdf_doc.append(doc)
    pdf_doc.impose(1, first_page_num + 1, num_pages)
    report_progress(0.9, _('Headers and footers added'))

# }}}


# Maths {{{

@lru_cache(maxsize=2)
def mathjax_dir():
    return P('mathjax', allow_user_override=False)


def add_maths_script(container):
    has_maths = {}
    for name, is_linear in container.spine_names:
        root = container.parsed(name)
        has_maths[name] = hm = check_for_maths(root)
        if not hm:
            continue
        script = root.makeelement(XHTML('script'), type="text/javascript", src=f'{FAKE_PROTOCOL}://{FAKE_HOST}/mathjax/loader/pdf-mathjax-loader.js')
        script.set('async', 'async')
        script.set('data-mathjax-path', f'{FAKE_PROTOCOL}://{FAKE_HOST}/mathjax/data/')
        last_tag(root).append(script)
    return has_maths
# }}}


def fix_markup(container):
    xp = XPath('//h:canvas')
    for file_name, is_linear in container.spine_names:
        root = container.parsed(file_name)
        for canvas in xp(root):
            # Canvas causes rendering issues, see https://bugs.launchpad.net/bugs/1859040
            # for an example.
            canvas.tag = XHTML('div')


def convert(opf_path, opts, metadata=None, output_path=None, log=default_log, cover_data=None, report_progress=lambda x, y: None):
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
    anchor_locations = {}
    jobs = []
    for margin_file in margin_files:
        jobs.append(job_for_name(container, margin_file.name, margin_file.margins, page_layout))
    results = manager.convert_html_files(jobs, settle_time=1, has_maths=has_maths)
    num_pages = 0
    page_margins_map = []
    for margin_file in margin_files:
        name = margin_file.name
        data = results[name]
        if not isinstance(data, bytes):
            raise SystemExit(data)
        doc = data_as_pdf_doc(data)
        anchor_locations.update(get_anchor_locations(name, doc, num_pages + 1, links_page_uuid, log))
        doc_pages = doc.page_count()
        page_margins_map.extend(repeat(resolve_margins(margin_file.margins, page_layout), doc_pages))
        num_pages += doc_pages

        if pdf_doc is None:
            pdf_doc = doc
        else:
            pdf_doc.append(doc)

    page_number_display_map = get_page_number_display_map(manager, opts, num_pages, log)

    if has_toc:
        annotate_toc(toc, anchor_locations, name_anchor_map, log)
        if opts.pdf_add_toc:
            tocname = create_skeleton(container)
            root = container.parsed(tocname)
            add_pagenum_toc(root, toc, opts, page_number_display_map)
            container.commit()
            jobs = [job_for_name(container, tocname, None, page_layout)]
            results = manager.convert_html_files(jobs, settle_time=1)
            tocdoc = data_as_pdf_doc(results[tocname])
            page_margins_map.extend(repeat(resolve_margins(None, page_layout), tocdoc.page_count()))
            pdf_doc.append(tocdoc)

    report_progress(0.7, _('Rendered all HTML as PDF'))

    fix_links(pdf_doc, anchor_locations, name_anchor_map, opts.pdf_mark_links, log)
    if toc and len(toc):
        add_toc(PDFOutlineRoot(pdf_doc), toc, log, pdf_doc)
    report_progress(0.75, _('Added links to PDF content'))

    pdf_metadata = PDFMetadata(metadata)
    add_header_footer(
        manager, opts, pdf_doc, container,
        page_number_display_map, page_layout, page_margins_map,
        pdf_metadata, report_progress, toc if has_toc else None)

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
        for i in range(1, pdf_doc.page_count()):
            margins = page_margins_map[i]
            mult = -1 if i % 2 else 1
            val = opts.pdf_odd_even_offset
            if abs(val) < min(margins.left, margins.right):
                box = list(pdf_doc.get_page_box("CropBox", i))
                box[0] += val * mult
                pdf_doc.set_page_box("CropBox", i, *box)

    if cover_data:
        add_cover(pdf_doc, cover_data, page_layout, opts)

    if metadata is not None:
        update_metadata(pdf_doc, pdf_metadata)
    report_progress(1, _('Updated metadata in PDF'))

    if opts.uncompressed_pdf:
        pdf_doc.uncompress()

    pdf_data = pdf_doc.write()
    if output_path is None:
        return pdf_data
    with open(output_path, 'wb') as f:
        f.write(pdf_data)
