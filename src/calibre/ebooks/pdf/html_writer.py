#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import signal
from collections import namedtuple
from io import BytesIO

from PyQt5.Qt import (
    QApplication, QMarginsF, QObject, QPageLayout, QTimer, QUrl, pyqtSignal
)
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calibre import detect_ncpus
from calibre.constants import iswindows
from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
from calibre.ebooks.oeb.base import XHTML
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.split import merge_html
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.ebooks.pdf.image_writer import (
    Image, PDFMetadata, draw_image_page, get_page_layout
)
from calibre.ebooks.pdf.render.serialize import PDFStream
from calibre.gui2 import setup_unix_signals
from calibre.gui2.webengine import secure_webengine
from calibre.utils.logging import default_log
from calibre.utils.podofo import get_podofo, set_metadata_implementation
from calibre.utils.short_uuid import uuid4
from polyglot.builtins import iteritems, range
from polyglot.urllib import urlparse

OK, KILL_SIGNAL = range(0, 2)


class Container(ContainerBase):

    tweak_mode = True
    is_dir = True

    def __init__(self, opf_path, log, root_dir=None):
        ContainerBase.__init__(self, root_dir or os.path.dirname(opf_path), opf_path, log)


class Renderer(QWebEnginePage):

    work_done = pyqtSignal(object, object)

    def __init__(self, opts, parent):
        QWebEnginePage.__init__(self, parent)
        secure_webengine(self)
        self.working = False
        self.settle_time = 0
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

        self.loadFinished.connect(self.load_finished)

    def load_finished(self, ok):
        if not ok:
            self.working = False
            self.work_done.emit(self, 'Load of {} failed'.format(self.url().toString()))
            return
        QTimer.singleShot(int(1000 * self.settle_time), self.print_to_pdf)

    def print_to_pdf(self):
        self.printToPdf(self.printing_done, self.page_layout)

    def printing_done(self, pdf_data):
        self.working = False
        self.work_done.emit(self, bytes(pdf_data))

    def convert_html_file(self, path, page_layout, settle_time=0):
        self.working = True
        self.settle_time = settle_time
        self.page_layout = page_layout
        self.setUrl(QUrl.fromLocalFile(path))


class RenderManager(QObject):

    def __init__(self, opts):
        QObject.__init__(self)
        self.opts = opts
        self.workers = []
        self.max_workers = detect_ncpus()
        if not iswindows:
            self.original_signal_handlers = setup_unix_signals(self)

    def create_worker(self):
        worker = Renderer(self.opts, self)
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

    def convert_html_files(self, jobs, settle_time=0):
        while len(self.workers) < min(len(jobs), self.max_workers):
            self.create_worker()
        self.pending = list(jobs)
        self.results = {}
        self.settle_time = settle_time
        QTimer.singleShot(0, self.assign_work)
        ret = self.run_loop()
        if ret == KILL_SIGNAL:
            raise SystemExit('Kill signal received')
        if ret != OK:
            raise SystemExit('Unknown error occurred')
        return self.results

    def assign_work(self):
        free_workers = [w for w in self.workers if not w.working]
        while free_workers and self.pending:
            html_file, page_layout, result_key = self.pending.pop()
            w = free_workers.pop()
            w.result_key = result_key
            w.convert_html_file(html_file, page_layout, settle_time=self.settle_time)

    def work_done(self, worker, result):
        self.results[worker.result_key] = result
        if self.pending:
            self.assign_work()
        else:
            for w in self.workers:
                if w.working:
                    return
            QApplication.instance().exit(OK)


def update_metadata(pdf_doc, pdf_metadata):
    if pdf_metadata.mi:
        xmp_packet = metadata_to_xmp_packet(pdf_metadata.mi)
        set_metadata_implementation(
            pdf_doc, pdf_metadata.title, pdf_metadata.mi.authors,
            pdf_metadata.mi.book_producer, pdf_metadata.mi.tags, xmp_packet)


def data_as_pdf_doc(data):
    podofo = get_podofo()
    ans = podofo.PDFDoc()
    ans.load(data)
    return ans


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


def create_margin_groups(container):

    def merge_group(group):
        if len(group) > 1:
            group_margins = group[0][1]
            names = [name for (name, margins) in group]
            merge_html(container, names, names[0], insert_page_breaks=True)
            group = [(names[0], group_margins)]
        return group

    groups = []
    current_group = []
    for name, is_linear in container.spine_names:
        root = container.parsed(name)
        margins = root.get('data-calibre-pdf-output-page-margins')
        if margins:
            margins = json.loads(margins)
        if current_group:
            prev_margins = current_group[-1][1]
            if prev_margins != margins:
                groups.append(merge_group(current_group))
                current_group = []
        current_group.append((name, margins))
    if current_group:
        groups.append(merge_group(current_group))
    return groups


def job_for_name(container, name, margins, page_layout):
    index_file = container.name_to_abspath(name)
    if margins:
        page_layout = QPageLayout(page_layout)
        page_layout.setUnits(QPageLayout.Point)
        old_margins = page_layout.marginsPoints()
        new_margins = QMarginsF(
            margins.get('left', old_margins.left()),
            margins.get('top', old_margins.top()),
            margins.get('right', old_margins.right()),
            margins.get('bottom', old_margins.bottom()))
        page_layout.setMargins(new_margins)
    return index_file, page_layout, name


def add_anchors_markup(root, uuid, anchors):
    body = root[-1]
    div = body.makeelement(XHTML('div'), id=uuid, style='page-break-before: always')
    body.append(div)
    for i, anchor in enumerate(anchors):
        div.append(div.makeelement(XHTML('a'), href='#' + anchor))
        div[-1].text = '{}'.format(i)
        div[-1].tail = ' '
    div.append(div.makeelement(XHTML('a'), href='#' + uuid))
    div[-1].text = 'top'
    div[-1].tail = ' '


def add_all_links(container, margin_groups):
    uuid = uuid4()
    name_anchor_map = {}
    for name, is_linear in container.spine_names:
        root = container.parsed(name)
        name_anchor_map[name] = frozenset(root.xpath('//*/@id'))
    for group in margin_groups:
        name = group[0][0]
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
            return url
        if not frag and name in spine_names:
            replacer.replaced = True
            return 'https://calibre-pdf-anchor.n#' + name
        key = name, frag
        new_frag = mapping.get(key)
        if new_frag is None:
            return url
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


AnchorLocation = namedtuple('AnchorLocation', 'pagenum left top zoom')


def get_anchor_locations(pdf_doc, first_page_num, toc_uuid):
    ans = {}
    anchors = pdf_doc.extract_anchors()
    toc_pagenum = anchors.pop(toc_uuid)[0]
    for r in range(pdf_doc.page_count(), toc_pagenum - 1, -1):
        pdf_doc.delete_page(r - 1)
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
        return loc

    pdf_doc.alter_links(replace_link, mark_links)


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


def add_toc(pdf_parent, toc_parent, anchor_locations, name_anchor_map):
    for child in toc_parent:
        title, frag = child.title, child.frag
        try:
            if '.' in frag:
                loc = anchor_locations[name_anchor_map[frag]]
            else:
                loc = anchor_locations[frag]
        except Exception:
            loc = AnchorLocation(1, 0, 0, 0)
        pdf_child = pdf_parent.create(title, loc.pagenum, True, loc.left, loc.top, loc.zoom)
        if len(child):
            add_toc(pdf_child, child, anchor_locations, name_anchor_map)


def convert(opf_path, opts, metadata=None, output_path=None, log=default_log, cover_data=None):
    container = Container(opf_path, log)
    margin_groups = create_margin_groups(container)
    name_anchor_map = make_anchors_unique(container)
    toc = get_toc(container, verify_destinations=False)
    links_page_uuid = add_all_links(container, margin_groups)
    container.commit()

    manager = RenderManager(opts)
    page_layout = get_page_layout(opts)
    pdf_doc = None
    anchor_locations = {}
    jobs = []
    for group in margin_groups:
        name, margins = group[0]
        jobs.append(job_for_name(container, name, margins, page_layout))
    results = manager.convert_html_files(jobs, settle_time=1)
    num_pages = 0
    for group in margin_groups:
        name, margins = group[0]
        data = results[name]
        if not isinstance(data, bytes):
            raise SystemExit(data)
        doc = data_as_pdf_doc(data)
        anchor_locations.update(get_anchor_locations(doc, num_pages + 1, links_page_uuid))
        num_pages += doc.page_count()

        if pdf_doc is None:
            pdf_doc = doc
        else:
            pdf_doc.append(doc)

    fix_links(pdf_doc, anchor_locations, name_anchor_map, opts.pdf_mark_links, log)
    if toc and len(toc):
        add_toc(PDFOutlineRoot(pdf_doc), toc, anchor_locations, name_anchor_map)

    if cover_data:
        add_cover(pdf_doc, cover_data, page_layout, opts)

    if metadata is not None:
        update_metadata(pdf_doc, PDFMetadata(metadata))

    # TODO: Remove unused fonts
    # TODO: Remove duplicate fonts
    # TODO: Subset and embed fonts before rendering PDF

    pdf_data = pdf_doc.write()
    if output_path is None:
        return pdf_data
    with open(output_path, 'wb') as f:
        f.write(pdf_data)
