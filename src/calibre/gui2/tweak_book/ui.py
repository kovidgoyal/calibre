#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import shutil, tempfile

from PyQt4.Qt import QDockWidget, Qt, QLabel, QIcon

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.main import SUPPORTED
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.gui2 import error_dialog
from calibre.gui2.main_window import MainWindow
from calibre.gui2.tweak_book import set_current_container, current_container
from calibre.gui2.tweak_book.file_list import FileListWidget
from calibre.gui2.tweak_book.job import BlockingJob
from calibre.gui2.tweak_book.undo import GlobalUndoHistory

def load_book(path_to_ebook, base_tdir):
    tdir = tempfile.mkdtemp(dir=base_tdir)
    return get_container(path_to_ebook, tdir=tdir)

class Main(MainWindow):

    APP_NAME = _('Tweak Book')

    def __init__(self, opts):
        MainWindow.__init__(self, opts, disable_automatic_gc=True)
        self.setWindowTitle(self.APP_NAME)
        self.setWindowIcon(QIcon(I('tweak.png')))
        self.opts = opts
        self.tdir = None
        self.path_to_ebook = None
        self.container = None
        self.global_undo = GlobalUndoHistory()
        self.blocking_job = BlockingJob(self)

        self.file_list_dock = d = QDockWidget(_('&Files Browser'), self)
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.file_list = FileListWidget(d)
        d.setWidget(self.file_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, d)

        self.status_bar = self.statusBar()
        self.l = QLabel('Placeholder')

        self.setCentralWidget(self.l)

    def resizeEvent(self, ev):
        self.blocking_job.resize(ev.size())
        return super(Main, self).resizeEvent(ev)

    def open_book(self, path):
        ext = path.rpartition('.')[-1].upper()
        if ext not in SUPPORTED:
            return error_dialog(self, _('Unsupported format'),
                _('Tweaking is only supported for books in the %s formats.'
                  ' Convert your book to one of these formats first.') % _(' and ').join(sorted(SUPPORTED)),
                show=True)

        # TODO: Handle already open, dirtied book

        if self.tdir:
            shutil.rmtree(self.tdir, ignore_errors=True)
        self.tdir = PersistentTemporaryDirectory()
        self.blocking_job('open_book', _('Opening book, please wait...'), self.book_opened, load_book, path, self.tdir)

    def book_opened(self, job):
        if job.traceback is not None:
            return error_dialog(self, _('Failed to open book'),
                    _('Failed to open book, click Show details for more information.'),
                                det_msg=job.traceback, show=True)
        container = job.result
        set_current_container(container)
        self.current_metadata = container.mi
        self.global_undo.open_book(container)
        self.update_window_title()
        self.file_list.build(container)

    def update_window_title(self):
        self.setWindowTitle(self.current_metadata.title + ' [%s] - %s' %(current_container().book_type.upper(), self.APP_NAME))
