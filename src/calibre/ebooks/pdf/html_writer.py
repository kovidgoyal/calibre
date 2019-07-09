#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from io import BytesIO

from PyQt5.Qt import QApplication, QTimer, QUrl
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calibre.constants import iswindows
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.split import merge_html
from calibre.ebooks.pdf.image_writer import (
    Image, PDFMetadata, draw_image_page, get_page_layout, update_metadata
)
from calibre.ebooks.pdf.render.serialize import PDFStream
from calibre.gui2 import setup_unix_signals
from calibre.gui2.webengine import secure_webengine
from calibre.utils.logging import default_log
from calibre.utils.podofo import get_podofo
from polyglot.builtins import range

OK, LOAD_FAILED, KILL_SIGNAL = range(0, 3)


class Container(ContainerBase):

    tweak_mode = True
    is_dir = True

    def __init__(self, opf_path, log, root_dir=None):
        ContainerBase.__init__(self, root_dir or os.path.dirname(opf_path), opf_path, log)


class Renderer(QWebEnginePage):

    def __init__(self, opts):
        QWebEnginePage.__init__(self)
        secure_webengine(self)
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
        if not iswindows:
            setup_unix_signals(self)

    def load_finished(self, ok):
        if not ok:
            QApplication.instance().exit(LOAD_FAILED)
            return
        QTimer.singleShot(int(1000 * self.settle_time), self.print_to_pdf)

    def signal_received(self, read_fd):
        try:
            os.read(read_fd, 1024)
        except EnvironmentError:
            return
        QApplication.instance().exit(KILL_SIGNAL)

    def print_to_pdf(self):
        self.printToPdf(self.printing_done, self.page_layout)

    def printing_done(self, pdf_data):
        self.pdf_data = pdf_data
        QApplication.instance().exit(OK)

    def convert_html_file(self, path, page_layout, settle_time=0):
        self.settle_time = settle_time
        self.page_layout = page_layout
        self.pdf_data = None
        self.setUrl(QUrl.fromLocalFile(path))
        ret = QApplication.exec_()
        if ret == LOAD_FAILED:
            raise SystemExit('Failed to load {}'.format(path))
        if ret == KILL_SIGNAL:
            raise SystemExit('Kill signal received')
        if ret != OK:
            raise SystemExit('Unknown error occurred')
        return self.pdf_data


def add_cover(pdf_doc, cover_data, page_layout, opts):
    buf = BytesIO()
    page_size = page_layout.fullRectPoints().size()
    img = Image(cover_data)
    writer = PDFStream(buf, (page_size.width(), page_size.height()), compress=True)
    writer.apply_fill(color=(1, 1, 1))
    draw_image_page(writer, img, preserve_aspect_ratio=opts.preserve_cover_aspect_ratio)
    writer.end()
    cover_pdf = buf.getvalue()
    podofo = get_podofo()
    cover_pdf_doc = podofo.PDFDoc()
    cover_pdf_doc.load(cover_pdf)
    pdf_doc.insert_existing_page(cover_pdf_doc)


def convert(opf_path, opts, metadata=None, output_path=None, log=default_log, cover_data=None):
    container = Container(opf_path, log)
    spine_names = [name for name, is_linear in container.spine_names]
    master = spine_names[0]
    if len(spine_names) > 1:
        merge_html(container, spine_names, master, insert_page_breaks=True)

    container.commit()
    index_file = container.name_to_abspath(master)

    renderer = Renderer(opts)
    page_layout = get_page_layout(opts)
    pdf_data = renderer.convert_html_file(index_file, page_layout, settle_time=1)
    podofo = get_podofo()
    pdf_doc = podofo.PDFDoc()
    pdf_doc.load(pdf_data)

    if cover_data:
        add_cover(pdf_doc, cover_data, page_layout, opts)

    if metadata is not None:
        update_metadata(pdf_doc, PDFMetadata(metadata))

    pdf_data = pdf_doc.write()
    if output_path is None:
        return pdf_data
    with open(output_path, 'wb') as f:
        f.write(pdf_data)
