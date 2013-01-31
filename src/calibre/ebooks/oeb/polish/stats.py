#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

from PyQt4.Qt import (QWebPage, pyqtProperty, QString, QEventLoop, QWebView,
                      Qt, QSize, QTimer)

from calibre.ebooks.oeb.display.webview import load_html
from calibre.gui2 import must_use_qt

class Page(QWebPage):

    def __init__(self, log):
        self.log = log
        QWebPage.__init__(self)

    def javaScriptConsoleMessage(self, msg, lineno, msgid):
        self.log(u'JS:', unicode(msg))

    def javaScriptAlert(self, frame, msg):
        self.log(unicode(msg))

    def shouldInterruptJavaScript(self):
        return False

    def _pass_json_value_getter(self):
        val = json.dumps(self.bridge_value)
        return QString(val)

    def _pass_json_value_setter(self, value):
        self.bridge_value = json.loads(unicode(value))

    _pass_json_value = pyqtProperty(QString, fget=_pass_json_value_getter,
            fset=_pass_json_value_setter)

class StatsCollector(object):

    def __init__(self, container):
        self.container = container
        self.log = self.logger = container.log
        must_use_qt()

        self.loop = QEventLoop()
        self.view = QWebView()
        self.page = Page(self.log)
        self.view.setPage(self.page)
        self.page.setViewportSize(QSize(1200, 1600))

        self.view.loadFinished.connect(self.collect,
                type=Qt.QueuedConnection)

        self.render_queue = list(container.spine_items)
        self.font_stats = {}

        QTimer.singleShot(0, self.render_book)

        if self.loop.exec_() == 1:
            raise Exception('Failed to gather statistics from book, see log for details')

    def render_book(self):
        try:
            if not self.render_queue:
                self.loop.exit()
            else:
                self.render_next()
        except:
            self.logger.exception('Rendering failed')
            self.loop.exit(1)

    def render_next(self):
        item = unicode(self.render_queue.pop(0))
        self.current_item = item
        load_html(item, self.view)

    def collect(self, ok):
        if not ok:
            self.log.error('Failed to render document: %s'%self.container.relpath(self.current_item))
            self.loop.exit(1)
            return
        try:
            self.collect_font_stats()
        except:
            self.log.exception('Failed to collect font stats from: %s'%self.container.relpath(self.current_item))
            self.loop.exit(1)
            return

        self.render_book()

    def collect_font_stats(self):
        pass


