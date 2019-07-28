#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

# Imports {{{
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import json
import os
import re
import signal
import sys
from collections import namedtuple
from io import BytesIO
from itertools import repeat
from operator import attrgetter, itemgetter

from PyQt5.Qt import (
    QApplication, QMarginsF, QObject, QPageLayout, QTimer, QUrl, pyqtSignal
)
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile
from html5_parser import parse

from calibre import detect_ncpus, prepare_string_for_xml
from calibre.constants import __version__, iswindows
from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
from calibre.ebooks.oeb.base import XHTML
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.ebooks.pdf.image_writer import (
    Image, PDFMetadata, draw_image_page, get_page_layout
)
from calibre.ebooks.pdf.render.serialize import PDFStream
from calibre.gui2 import setup_unix_signals
from calibre.gui2.webengine import secure_webengine
from calibre.utils.fonts.sfnt.container import Sfnt, UnsupportedFont
from calibre.utils.fonts.sfnt.merge import merge_truetype_fonts_for_pdf
from calibre.utils.logging import default_log
from calibre.utils.podofo import (
    dedup_type3_fonts, get_podofo, remove_unused_fonts, set_metadata_implementation
)
from calibre.utils.short_uuid import uuid4
from polyglot.builtins import as_bytes, filter, iteritems, map, range, unicode_type
from polyglot.urllib import urlparse

OK, KILL_SIGNAL = range(0, 2)
# }}}


# Utils {{{
def data_as_pdf_doc(data):
    podofo = get_podofo()
    ans = podofo.PDFDoc()
    ans.load(data)
    return ans


def create_skeleton(container):
    spine_name = tuple(container.spine_names)[-1][0]
    root = container.parsed(spine_name)
    root = copy.deepcopy(root)
    body = root[-1]
    body.text = body.tail = None
    del body[:]
    name = container.add_file(spine_name, b'', modify_name_if_needed=True)
    container.replace(name, root)
    return name

# }}}


# Renderer {{{
class Container(ContainerBase):

    tweak_mode = True
    is_dir = True

    def __init__(self, opf_path, log, root_dir=None):
        ContainerBase.__init__(self, root_dir or os.path.dirname(opf_path), opf_path, log)


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
        s.setAttribute(s.JavascriptEnabled, True)
        s.setFontSize(s.DefaultFontSize, opts.pdf_default_font_size)
        s.setFontSize(s.DefaultFixedFontSize, opts.pdf_mono_font_size)
        s.setFontSize(s.MinimumLogicalFontSize, 8)
        s.setFontSize(s.MinimumFontSize, 8)
        std = {
            'serif': opts.pdf_serif_family,
            'sans' : opts.pdf_sans_family,
            'mono' : opts.pdf_mono_family
        }.get(opts.pdf_standard_font, opts.pdf_serif_family)
        if std:
            s.setFontFamily(s.StandardFont, std)
        if opts.pdf_serif_family:
            s.setFontFamily(s.SerifFont, opts.pdf_serif_family)
        if opts.pdf_sans_family:
            s.setFontFamily(s.SansSerifFont, opts.pdf_sans_family)
        if opts.pdf_mono_family:
            s.setFontFamily(s.FixedFont, opts.pdf_mono_family)

        self.titleChanged.connect(self.title_changed)
        self.loadStarted.connect(self.load_started)
        self.loadFinished.connect(self.load_finished)

    def load_started(self):
        self.load_complete = False

    def title_changed(self, title):
        if self.wait_for_title and title == self.wait_for_title and self.load_complete:
            QTimer.singleShot(0, self.print_to_pdf)

    def load_finished(self, ok):
        self.load_complete = True
        if not ok:
            self.working = False
            self.work_done.emit(self, 'Load of {} failed'.format(self.url().toString()))
            return
        timeout = self.settle_time
        if self.wait_for_title and self.title() == self.wait_for_title:
            timeout = 0
        QTimer.singleShot(int(1000 * timeout), self.print_to_pdf)

    def javaScriptConsoleMessage(self, level, message, linenum, source_id):
        try:
            self.log('{}:{}:{}'.format(source_id, linenum, message))
        except Exception:
            pass

    def print_to_pdf(self):
        self.printToPdf(self.printing_done, self.page_layout)

    def printing_done(self, pdf_data):
        self.working = False
        self.work_done.emit(self, bytes(pdf_data))

    def convert_html_file(self, path, page_layout, settle_time=0, wait_for_title=None):
        self.working = True
        self.load_complete = False
        self.wait_for_title = wait_for_title
        self.settle_time = settle_time
        self.page_layout = page_layout
        self.setUrl(QUrl.fromLocalFile(path))


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    def interceptRequest(self, request_info):
        method = bytes(request_info.requestMethod())
        if method not in (b'GET', b'HEAD'):
            self.log.warn('Blocking URL request with method: {}'.format(method))
            request_info.block(True)
            return
        qurl = request_info.requestUrl()
        if qurl.scheme() != 'file':
            self.log.warn('Blocking URL request with scheme: {}'.format(qurl.scheme()))
            request_info.block(True)
            return
        path = qurl.toLocalFile()
        path = os.path.normcase(os.path.abspath(path))
        if not path.startswith(self.container_root):
            self.log.warn('Blocking URL request with path: {}'.format(path))
            request_info.block(True)
            return


class RenderManager(QObject):

    def __init__(self, opts, log, container_root):
        QObject.__init__(self)
        self.interceptor = RequestInterceptor(self)
        self.interceptor.log = self.log = log
        self.interceptor.container_root = os.path.normcase(os.path.abspath(container_root))
        ans = QWebEngineProfile(QApplication.instance())
        ua = 'calibre-pdf-output ' + __version__
        ans.setHttpUserAgent(ua)
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        ans.setUrlRequestInterceptor(self.interceptor)
        self.profile = ans

        self.opts = opts
        self.workers = []
        self.max_workers = detect_ncpus()
        if not iswindows:
            self.original_signal_handlers = setup_unix_signals(self)

    def create_worker(self):
        worker = Renderer(self.opts, self, self.log)
        worker.work_done.connect(self.work_done)
        self.workers.append(worker)

    def signal_received(self, read_fd):
        try:
            os.read(read_fd, 1024)
        except EnvironmentError:
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
            return QApplication.exec_()
        finally:
            self.restore_signal_handlers()

    def convert_html_files(self, jobs, settle_time=0, wait_for_title=None):
        while len(self.workers) < min(len(jobs), self.max_workers):
            self.create_worker()
        self.pending = list(jobs)
        self.results = {}
        self.settle_time = settle_time
        self.wait_for_title = wait_for_title
        QTimer.singleShot(0, self.assign_work)
        ret = self.run_loop()
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
        QApplication.exec_()
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
            w.convert_html_file(html_file, page_layout, settle_time=self.settle_time, wait_for_title=self.wait_for_title)

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
    index_file = container.name_to_abspath(name)
    if margins:
        page_layout = QPageLayout(page_layout)
        page_layout.setUnits(QPageLayout.Point)
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
    body = root[-1]
    div = body.makeelement(XHTML('div'), id=uuid, style='page-break-before: always')
    body.append(div)

    def a(anchor):
        div.append(div.makeelement(XHTML('a'), href='#' + anchor))
        div[-1].text = '\xa0'
        div[-1].tail = ' '
    tuple(map(a, anchors))
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


def make_anchors_unique(container):
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
        else:
            href, frag = url.partition('#')[::2]
        if base is None:
            name = href
        else:
            name = container.href_to_name(href, base)
        if not name:
            return url.rstrip('#')
        if not frag and name in spine_names:
            replacer.replaced = True
            return 'https://calibre-pdf-anchor.n#' + name
        key = name, frag
        new_frag = mapping.get(key)
        if new_frag is None:
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
                new_id = mapping[key] = 'a{}'.format(count)
                elem.set('id', new_id)
        body = root[-1]
        if not body.get('id'):
            count += 1
            body.set('id', 'a{}'.format(count))
        name_anchor_map[spine_name] = body.get('id')

    for name in container.mime_map:
        base = name
        replacer.replaced = False
        container.replace_links(name, replacer)
    return name_anchor_map


class AnchorLocation(object):

    __slots__ = ('pagenum', 'left', 'top', 'zoom')

    def __init__(self, pagenum=1, left=0, top=0, zoom=0):
        self.pagenum, self.left, self.top, self.zoom = pagenum, left, top, zoom

    def __repr__(self):
        return 'AnchorLocation(pagenum={}, left={}, top={}, zoom={})'.format(self.as_tuple)

    @property
    def as_tuple(self):
        return self.pagenum, self.left, self.top, self.zoom


def get_anchor_locations(pdf_doc, first_page_num, toc_uuid):
    ans = {}
    anchors = pdf_doc.extract_anchors()
    toc_pagenum = anchors.pop(toc_uuid)[0]
    pdf_doc.delete_pages(toc_pagenum, pdf_doc.page_count() - toc_pagenum + 1)
    for anchor, loc in iteritems(anchors):
        loc = list(loc)
        loc[0] += first_page_num - 1
        ans[anchor] = AnchorLocation(*loc)
    return ans


def fix_links(pdf_doc, anchor_locations, name_anchor_map, mark_links, log):

    def replace_link(url):
        purl = urlparse(url)
        if purl.scheme != 'https' or purl.netloc not in ('calibre-pdf-anchor.a', 'calibre-pdf-anchor.n'):
            return
        loc = None
        if purl.netloc == 'calibre-pdf-anchor.a':
            loc = anchor_locations.get(purl.fragment)
            if loc is None:
                log.warn('Anchor location for link to {} not found'.format(purl.fragment))
        else:
            loc = anchor_locations.get(name_anchor_map.get(purl.fragment))
            if loc is None:
                log.warn('Anchor location for link to {} not found'.format(purl.fragment))
        return None if loc is None else loc.as_tuple

    pdf_doc.alter_links(replace_link, mark_links)
# }}}


# Outline creation {{{
class PDFOutlineRoot(object):

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
            log.warn('Could not find anchor location for ToC entry: {} with href: {}'.format(child.title, frag))
            loc = AnchorLocation(1, 0, 0, 0)
        child.pdf_loc = loc


def add_toc(pdf_parent, toc_parent):
    for child in toc_parent:
        title, loc = child.title, child.pdf_loc
        pdf_child = pdf_parent.create(title, loc.pagenum, True, loc.left, loc.top, loc.zoom)
        if len(child):
            add_toc(pdf_child, child)


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
                'NUM_PAGES', unicode_type(num_pages), 1)
        result = render_manager.evaljs(js)
        try:
            result = json.loads(result)
            if not isinstance(result, dict):
                raise ValueError('Not a dict')
        except Exception:
            log.warn('Could not do page number mapping, got unexpected result: {}'.format(repr(result)))
        else:
            default_map = {int(k): int(v) for k, v in iteritems(result)}
    return default_map


def add_pagenum_toc(root, toc, opts, page_number_display_map):
    body = root[-1]
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
        E('td', text='{}'.format(num), parent=tr)

# }}}


# Fonts {{{


class Range(object):

    __slots__ = ('first', 'last', 'widths', 'sort_order')

    def __init__(self, first, last, widths):
        self.first, self.last, self.widths = first, last, widths
        # Sort by first with larger ranges coming before smaller ones
        self.sort_order = self.first, -self.last

    def __repr__(self):
        return '({}, {}, {})'.format(self.first, self.last, self.widths)

    def merge(self, r):
        if r.last <= self.last:
            return  # is a subset
        if r.first > self.last:
            if r.first == self.last + 1 and self.has_single_width == r.has_single_width:
                if self.has_single_width:
                    if r.widths[0] == self.widths[0]:
                        self.last = r.last
                        return
                else:
                    self.last = r.last
                    delta = self.last - self.first + 1 - len(self.widths)
                    self.widths.extend(r.widths[-delta:])
                    return
            return r
        if self.has_single_width != r.has_single_width:
            # make r disjoint
            delta = self.last + 1 - r.first
            r.first = self.last + 1
            if len(r.widths) > 1:
                del r.widths[:delta]
            return r if r.widths else None
        # subsume r into self
        self.last = r.last
        if not self.has_single_width:
            delta = self.last - self.first + 1 - len(self.widths)
            self.widths.extend(r.widths[-delta:])

    @property
    def as_item(self):
        if self.has_single_width:
            return self.first, self.last, self.widths[0]
        return self.first, self.widths

    @property
    def has_single_width(self):
        return len(self.widths) == 1


def merge_w_arrays(arrays):
    ranges = []
    for w in arrays:
        i = 0
        while i + 1 < len(w):
            elem = w[i]
            next_elem = w[i+1]
            if isinstance(next_elem, list):
                ranges.append(Range(elem, elem + len(next_elem) - 1, next_elem))
                i += 2
            elif i + 2 < len(w):
                ranges.append(Range(elem, next_elem, [w[i+2]]))
                i += 3
            else:
                break
    ranges.sort(key=attrgetter('sort_order'))
    merged_ranges = ranges[:1]
    for r in ranges[1:]:
        prev_range = merged_ranges[-1]
        left_over = prev_range.merge(r)
        if left_over is not None:
            merged_ranges.append(left_over)
    if not merged_ranges:
        return []
    ans = []
    for r in merged_ranges:
        ans.extend(r.as_item)
    return ans


class CMap(object):

    def __init__(self):
        self.start_codespace = sys.maxsize
        self.end_codespace = 0
        self.ranges = set()
        self.chars = set()
        self.header = self.footer = None

    def add_codespace(self, start, end):
        self.start_codespace = min(self.start_codespace, start)
        self.end_codespace = max(self.end_codespace, end)

    def serialize(self):
        chars = sorted(self.chars, key=itemgetter(0))

        def ashex(x):
            ans = '{:04X}'.format(x)
            leftover = len(ans) % 4
            if leftover:
                ans = ('0' * (4 - leftover)) + ans
            return ans

        lines = ['1 begincodespacerange', '<{}> <{}>'.format(*map(ashex, (self.start_codespace, self.end_codespace))), 'endcodespacerange']
        while chars:
            group, chars = chars[:100], chars[100:]
            del chars[:100]
            lines.append('{} beginbfchar'.format(len(group)))
            for g in group:
                lines.append('<{}> <{}>'.format(*map(ashex, g)))
            lines.append('endbfchar')

        ranges = sorted(self.ranges, key=itemgetter(0))
        while ranges:
            group, ranges = ranges[:100], ranges[100:]
            lines.append('{} beginbfrange'.format(len(group)))
            for g in group:
                lines.append('<{}> <{}> <{}>'.format(*map(ashex, g)))
            lines.append('endbfrange')
        return self.header + '\n' + '\n'.join(lines) + '\n' + self.footer


def merge_cmaps(cmaps):
    header, incmap, incodespace, inchar, inrange, footer = 'header cmap codespace char range footer'.split()
    start_pat = re.compile(r'\d+\s+begin(codespacerange|bfrange|bfchar)')
    ans = CMap()
    for cmap in cmaps:
        state = header
        headerlines = []
        footerlines = []
        prefix_ended = False
        for line in cmap.decode('utf-8', 'replace').splitlines():
            line = line.strip()
            if state is header:
                headerlines.append(line)
                if line == 'begincmap':
                    state = incmap
                continue
            if state is incmap:
                if line == 'endcmap':
                    state = footer
                    footerlines.append(line)
                    continue
                m = start_pat.match(line)
                if m is not None:
                    state = incodespace if m.group(1) == 'codespacerange' else (inchar if m.group(1) == 'bfchar' else inrange)
                    prefix_ended = True
                    continue
                if not prefix_ended:
                    headerlines.append(line)
                continue
            if state is incodespace:
                if line == 'endcodespacerange':
                    state = incmap
                else:
                    s, e = line.split()
                    s = int(s[1:-1], 16)
                    e = int(e[1:-1], 16)
                    ans.add_codespace(s, e)
                continue
            if state is inchar:
                if line == 'endbfchar':
                    state = incmap
                else:
                    a, b = line.split()
                    a = int(a[1:-1], 16)
                    b = int(b[1:-1], 16)
                    ans.chars.add((a, b))
                continue
            if state is inrange:
                if line == 'endbfrange':
                    state = incmap
                else:
                    # technically bfrange can contain arrays for th eunicode
                    # value but from looking at SkPDFFont.cpp in chromium, it
                    # does not generate any
                    a, b, u = line.split()
                    a = int(a[1:-1], 16)
                    b = int(b[1:-1], 16)
                    u = int(u[1:-1], 16)
                    ans.ranges.add((a, b, u))
                continue
            if state is footer:
                footerlines.append(line)
        if ans.header is None:
            ans.header = '\n'.join(headerlines)
            ans.footer = '\n'.join(footerlines)
    return ans.serialize()


def fonts_are_identical(fonts):
    for key in ('ToUnicode', 'Data'):
        all_values = {f[key] for f in fonts}
        if len(all_values) > 1:
            return False
    return True


def merge_font(fonts):
    # choose the largest font as the base font
    fonts.sort(key=lambda f: len(f['Data'] or b''), reverse=True)
    base_font = fonts[0]
    t0_font = next(f for f in fonts if f['DescendantFont'] == base_font['Reference'])
    descendant_fonts = [f for f in fonts if f['Subtype'] != 'Type0']
    t0_fonts = [f for f in fonts if f['Subtype'] == 'Type0']
    references_to_drop = tuple(f['Reference'] for f in fonts if f is not base_font and f is not t0_font)
    if fonts_are_identical(descendant_fonts):
        return t0_font, base_font, references_to_drop
    cmaps = list(filter(None, (f['ToUnicode'] for f in t0_fonts)))
    if cmaps:
        t0_font['ToUnicode'] = as_bytes(merge_cmaps(cmaps))
    for key in ('W', 'W2'):
        arrays = tuple(filter(None, (f[key] for f in descendant_fonts)))
        base_font[key] = merge_w_arrays(arrays)
    base_font['sfnt'] = merge_truetype_fonts_for_pdf(*(f['sfnt'] for f in descendant_fonts))
    return t0_font, base_font, references_to_drop


def merge_fonts(pdf_doc):
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
    replacements = {}
    items = []
    for name, fonts in iteritems(base_font_map):
        if mergeable(fonts):
            t0_font, base_font, references_to_drop = merge_font(fonts)
            for ref in references_to_drop:
                replacements[ref] = t0_font['Reference']
            data = base_font['sfnt']()[0]
            items.append((
                base_font['Reference'], t0_font['Reference'], base_font['W'] or [], base_font['W2'] or [],
                data, t0_font['ToUnicode'] or b''))
    pdf_doc.merge_fonts(tuple(items), replacements)


def test_merge_fonts():
    path = sys.argv[-1]
    podofo = get_podofo()
    pdf_doc = podofo.PDFDoc()
    pdf_doc.open(path)
    merge_fonts(pdf_doc)
    out = path.rpartition('.')[0] + '-merged.pdf'
    pdf_doc.save(out)
    print('Merged PDF writted to', out)

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
    body = root[-1]
    body.attrib.pop('id', None)
    body.set('style', 'margin: 0; padding: 0; border-width: 0; background-color: unset')
    job = job_for_name(container, name, Margins(0, 0, 0, 0), page_layout)

    def m(tag_name, text=None, style=None, **attrs):
        ans = root.makeelement(XHTML(tag_name), **attrs)
        if text is not None:
            ans.text = text
        if style is not None:
            style = '; '.join('{}: {}'.format(k, v) for k, v in iteritems(style))
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

    if toc is None:
        page_toc_map = stack_to_map(())
        toplevel_toc_map = stack_to_map(())
    else:
        page_toc_map = stack_to_map(create_toc_stack(toc.iterdescendants(level=0)))

        def tc():
            for x in toc:
                yield 0, x
        toplevel_toc_map = stack_to_map(create_toc_stack(tc()))

    def create_container(page_num, margins):
        style = {
            'page-break-inside': 'avoid',
            'page-break-after': 'always',
            'display': 'flex',
            'flex-direction': 'column',
            'height': '100%',
            'justify-content': justify,
            'margin-left': '{}pt'.format(margins.left),
            'margin-right': '{}pt'.format(margins.right),
            'margin-top': '0',
            'margin-bottom': '0',
            'padding': '0',
            'border-width': '0',
            'overflow': 'hidden',
            'background-color': 'unset',
        }

        ans = m('div', style=style, id='p{}'.format(page_num))
        return ans

    def format_template(template, page_num, height):
        template = template.replace('_PAGENUM_', unicode_type(page_number_display_map[page_num]))
        template = template.replace('_TITLE_', prepare_string_for_xml(pdf_metadata.title, True))
        template = template.replace('_AUTHOR_', prepare_string_for_xml(pdf_metadata.author, True))
        template = template.replace('_TOP_LEVEL_SECTION_', prepare_string_for_xml(toplevel_toc_map[page_num - 1]))
        template = template.replace('_SECTION_', prepare_string_for_xml(page_toc_map[page_num - 1]))
        troot = parse(template, namespace_elements=True)
        ans = troot[-1][0]
        style = ans.get('style') or ''
        style = (
            'margin: 0; padding: 0; height: {height}pt; border-width: 0;'
            'display: flex; align-items: center; overflow: hidden; background-color: unset').format(height=height) + style
        ans.set('style', style)
        for child in ans.xpath('descendant-or-self::*[@class]'):
            cls = frozenset(child.get('class').split())
            q = 'even-page' if page_num % 2 else 'odd-page'
            if q in cls or q.replace('-', '_') in cls:
                style = child.get('style') or ''
                child.set('style', style + '; display: none')
        return ans

    for page_num in range(1, pdf_doc.page_count() + 1):
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


def convert(opf_path, opts, metadata=None, output_path=None, log=default_log, cover_data=None, report_progress=lambda x, y: None):
    container = Container(opf_path, log)
    report_progress(0.05, _('Parsed all content for markup transformation'))
    name_anchor_map = make_anchors_unique(container)
    margin_files = tuple(create_margin_files(container))
    toc = get_toc(container, verify_destinations=False)
    has_toc = toc and len(toc)
    links_page_uuid = add_all_links(container, margin_files)
    container.commit()
    report_progress(0.1, _('Completed markup transformation'))

    manager = RenderManager(opts, log, container.root)
    page_layout = get_page_layout(opts)
    pdf_doc = None
    anchor_locations = {}
    jobs = []
    for margin_file in margin_files:
        jobs.append(job_for_name(container, margin_file.name, margin_file.margins, page_layout))
    results = manager.convert_html_files(jobs, settle_time=1)
    num_pages = 0
    page_margins_map = []
    for margin_file in margin_files:
        name = margin_file.name
        data = results[name]
        if not isinstance(data, bytes):
            raise SystemExit(data)
        doc = data_as_pdf_doc(data)
        anchor_locations.update(get_anchor_locations(doc, num_pages + 1, links_page_uuid))
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
            pdf_doc.append(tocdoc)

    report_progress(0.7, _('Rendered all HTML as PDF'))

    fix_links(pdf_doc, anchor_locations, name_anchor_map, opts.pdf_mark_links, log)
    if toc and len(toc):
        add_toc(PDFOutlineRoot(pdf_doc), toc)
    report_progress(0.75, _('Added links to PDF content'))

    pdf_metadata = PDFMetadata(metadata)
    add_header_footer(
        manager, opts, pdf_doc, container,
        page_number_display_map, page_layout, page_margins_map,
        pdf_metadata, report_progress, toc if has_toc else None)

    merge_fonts(pdf_doc)
    num_removed = dedup_type3_fonts(pdf_doc)
    if num_removed:
        log('Removed', num_removed, 'duplicated Type3 glyphs')

    # TODO: dedup images
    # TODO: Support for mathematics

    num_removed = remove_unused_fonts(pdf_doc)
    if num_removed:
        log('Removed', num_removed, 'unused fonts')

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
