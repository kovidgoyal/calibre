#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import sys
from collections import defaultdict
from hashlib import sha256
from threading import Thread

from PyQt5.Qt import QDockWidget, Qt, QVBoxLayout, QWidget, pyqtSignal

from calibre import prints
from calibre.constants import config_dir
from calibre.gui2 import error_dialog
from calibre.gui2.main_window import MainWindow
from calibre.gui2.viewer.annotations import (
    merge_annotations, parse_annotations, save_annots_to_epub, serialize_annotations
)
from calibre.gui2.viewer.convert_book import prepare_book, update_book
from calibre.gui2.viewer.toc import TOC, TOCSearch, TOCView
from calibre.gui2.viewer.web_view import WebView, set_book_path, vprefs
from calibre.utils.date import utcnow
from calibre.utils.ipc.simple_worker import WorkerError
from calibre.utils.serialize import json_loads
from polyglot.builtins import as_bytes

annotations_dir = os.path.join(config_dir, 'viewer', 'annots')


def path_key(path):
    return sha256(as_bytes(path)).hexdigest()


class EbookViewer(MainWindow):

    msg_from_anotherinstance = pyqtSignal(object)
    book_prepared = pyqtSignal(object, object)
    MAIN_WINDOW_STATE_VERSION = 1

    def __init__(self):
        MainWindow.__init__(self, None)
        try:
            os.makedirs(annotations_dir)
        except EnvironmentError:
            pass
        self.current_book_data = {}
        self.book_prepared.connect(self.load_finished, type=Qt.QueuedConnection)

        def create_dock(title, name, area, areas=Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea):
            ans = QDockWidget(title, self)
            ans.setObjectName(name)
            self.addDockWidget(area, ans)
            ans.setVisible(False)
            return ans

        self.toc_dock = create_dock(_('Table of Contents'), 'toc-dock', Qt.LeftDockWidgetArea)
        self.toc_container = w = QWidget(self)
        w.l = QVBoxLayout(w)
        self.toc = TOCView(w)
        self.toc_search = TOCSearch(self.toc, parent=w)
        w.l.addWidget(self.toc), w.l.addWidget(self.toc_search), w.l.setContentsMargins(0, 0, 0, 0)
        self.toc_dock.setWidget(w)

        self.inspector_dock = create_dock(_('Inspector'), 'inspector', Qt.RightDockWidgetArea)
        self.web_view = WebView(self)
        self.web_view.cfi_changed.connect(self.cfi_changed)
        self.web_view.reload_book.connect(self.reload_book)
        self.web_view.toggle_toc.connect(self.toggle_toc)
        self.setCentralWidget(self.web_view)
        state = vprefs['main_window_state']
        if state:
            self.restoreState(state, self.MAIN_WINDOW_STATE_VERSION)

    def handle_commandline_arg(self, arg):
        if arg:
            if os.path.isfile(arg) and os.access(arg, os.R_OK):
                self.load_ebook(arg)
            else:
                prints('Cannot read from:', arg, file=sys.stderr)

    def another_instance_wants_to_talk(self, msg):
        try:
            path, open_at = msg
        except Exception:
            return
        self.load_ebook(path, open_at=open_at)
        self.raise_()

    def toggle_toc(self):
        if self.toc_dock.isVisible():
            self.toc_dock.setVisible(False)
        else:
            self.toc_dock.setVisible(True)

    def load_ebook(self, pathtoebook, open_at=None, reload_book=False):
        # TODO: Implement open_at
        self.web_view.show_preparing_message()
        self.save_annotations()
        self.current_book_data = {}
        t = Thread(name='LoadBook', target=self._load_ebook_worker, args=(pathtoebook, open_at, reload_book))
        t.daemon = True
        t.start()

    def reload_book(self):
        if self.current_book_data:
            self.load_ebook(self.current_book_data['pathtoebook'], reload_book=True)

    def _load_ebook_worker(self, pathtoebook, open_at, reload_book):
        try:
            ans = prepare_book(pathtoebook, force=reload_book)
        except WorkerError as e:
            self.book_prepared.emit(False, {'exception': e, 'tb': e.orig_tb, 'pathtoebook': pathtoebook})
        except Exception as e:
            import traceback
            self.book_prepared.emit(False, {'exception': e, 'tb': traceback.format_exc(), 'pathtoebook': pathtoebook})
        else:
            self.book_prepared.emit(True, {'base': ans, 'pathtoebook': pathtoebook, 'open_at': open_at})

    def load_finished(self, ok, data):
        if not ok:
            error_dialog(self, _('Loading book failed'), _(
                'Failed to open the book at {0}. Click "Show details" for more info.').format(data['pathtoebook']),
                det_msg=data['tb'], show=True)
            return
        set_book_path(data['base'])
        self.current_book_data = data
        self.current_book_data['annotations_map'] = defaultdict(list)
        self.current_book_data['annotations_path_key'] = path_key(data['pathtoebook']) + '.json'
        self.load_book_data()
        self.web_view.start_book_load(initial_cfi=self.initial_cfi_for_current_book())

    def load_book_data(self):
        self.load_book_annotations()
        path = os.path.join(self.current_book_data['base'], 'calibre-book-manifest.json')
        with open(path, 'rb') as f:
            raw = f.read()
        self.current_book_data['manifest'] = manifest = json.loads(raw)
        toc = manifest.get('toc')
        self.toc_model = TOC(toc)
        self.toc.setModel(self.toc_model)

    def load_book_annotations(self):
        amap = self.current_book_data['annotations_map']
        path = os.path.join(self.current_book_data['base'], 'calibre-book-annotations.json')
        if os.path.exists(path):
            with open(path, 'rb') as f:
                raw = f.read()
            merge_annotations(json_loads(raw), amap)
        path = os.path.join(annotations_dir, self.current_book_data['annotations_path_key'])
        if os.path.exists(path):
            with open(path, 'rb') as f:
                raw = f.read()
            merge_annotations(parse_annotations(raw), amap)

    def initial_cfi_for_current_book(self):
        lrp = self.current_book_data['annotations_map']['last-read']
        if lrp:
            lrp = lrp[0]
            if lrp['pos_type'] == 'epubcfi':
                return lrp['pos']

    def cfi_changed(self, cfi):
        if not self.current_book_data:
            return
        self.current_book_data['annotations_map']['last-read'] = [{
            'pos': cfi, 'pos_type': 'epubcfi', 'timestamp': utcnow()}]

    def save_annotations(self):
        if not self.current_book_data:
            return
        amap = self.current_book_data['annotations_map']
        annots = as_bytes(serialize_annotations(amap))
        with open(os.path.join(annotations_dir, self.current_book_data['annotations_path_key']), 'wb') as f:
            f.write(annots)
        if self.current_book_data.get('pathtoebook', '').lower().endswith('.epub'):
            path = self.current_book_data['pathtoebook']
            if os.access(path, os.W_OK):
                before_stat = os.stat(path)
                save_annots_to_epub(path, annots)
                update_book(path, before_stat, {'calibre-book-annotations.json': annots})

    def save_state(self):
        vprefs['main_window_state'] = bytearray(self.saveState(self.MAIN_WINDOW_STATE_VERSION))

    def closeEvent(self, ev):
        self.save_annotations()
        self.save_state()
        return MainWindow.closeEvent(self, ev)
