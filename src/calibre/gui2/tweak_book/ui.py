#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import QDockWidget, Qt, QLabel, QIcon, QAction

from calibre.gui2.main_window import MainWindow
from calibre.gui2.tweak_book import current_container
from calibre.gui2.tweak_book.file_list import FileListWidget
from calibre.gui2.tweak_book.job import BlockingJob
from calibre.gui2.tweak_book.boss import Boss
from calibre.gui2.keyboard import Manager as KeyboardManager

class Main(MainWindow):

    APP_NAME = _('Tweak Book')

    def __init__(self, opts):
        MainWindow.__init__(self, opts, disable_automatic_gc=True)
        self.boss = Boss(self)
        self.setWindowTitle(self.APP_NAME)
        self.setWindowIcon(QIcon(I('tweak.png')))
        self.opts = opts
        self.path_to_ebook = None
        self.container = None
        self.current_metadata = None
        self.blocking_job = BlockingJob(self)
        self.keyboard = KeyboardManager(parent=self, config_name='shortcuts/tweak')

        self.create_actions()
        self.create_menubar()
        self.create_docks()

        self.status_bar = self.statusBar()
        self.l = QLabel('Placeholder')

        self.setCentralWidget(self.l)
        self.boss(self)

        self.keyboard.finalize()

    def create_actions(self):
        group = _('Global Actions')

        def reg(icon, text, target, sid, keys, description):
            ac = QAction(QIcon(I(icon)), text, self)
            ac.triggered.connect(target)
            if isinstance(keys, type('')):
                keys = (keys,)
            self.keyboard.register_shortcut(
                sid, unicode(ac.text()), default_keys=keys, description=description, action=ac, group=group)
            self.addAction(ac)
            return ac

        self.action_open_book = reg('document_open.png', _('Open &book'), self.boss.open_book, 'open-book', 'Ctrl+O', _('Open a new book'))

    def create_menubar(self):
        b = self.menuBar()
        f = b.addMenu(_('&File'))
        f.addAction(self.action_open_book)

    def create_docks(self):
        self.file_list_dock = d = QDockWidget(_('&Files Browser'), self)
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.file_list = FileListWidget(d)
        d.setWidget(self.file_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, d)

    def resizeEvent(self, ev):
        self.blocking_job.resize(ev.size())
        return super(Main, self).resizeEvent(ev)

    def update_window_title(self):
        self.setWindowTitle(self.current_metadata.title + ' [%s] - %s' %(current_container().book_type.upper(), self.APP_NAME))
