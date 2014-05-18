#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json

from PyQt4.Qt import (QWidget, QTimer)

from calibre.constants import iswindows
from calibre.gui2.tweak_book import editors, actions, current_container

class LiveCSS(QWidget):

    def __init__(self, preview, parent=None):
        QWidget.__init__(self, parent)
        self.preview = preview
        preview.refreshed.connect(self.update_data)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.setSingleShot(True)

    def clear(self):
        pass  # TODO: Implement this

    def show_data(self, editor_name, sourceline, tags):
        if sourceline is None:
            self.clear()
        else:
            data = self.read_data(sourceline, tags)
            if data is None:
                self.clear()
                return

    def read_data(self, sourceline, tags):
        mf = self.preview.view.page().mainFrame()
        tags = [x.lower() for x in tags]
        result = unicode(mf.evaluateJavaScript(
            'window.calibre_preview_integration.live_css(%s, %s)' % (
                json.dumps(sourceline), json.dumps(tags))).toString())
        result = json.loads(result)
        if result is not None:
            for node in result['nodes']:
                for item in node['css']:
                    href = item['href']
                    if hasattr(href, 'startswith') and href.startswith('file://'):
                        href = href[len('file://'):]
                        if iswindows and href.startswith('/'):
                            href = href[1:]
                        if href:
                            item['href'] = current_container().abspath_to_name(href, root=self.preview.current_root)
        return result

    @property
    def current_name(self):
        return self.preview.current_name

    @property
    def is_visible(self):
        return self.isVisible()

    def showEvent(self, ev):
        self.update_timer.start()
        actions['auto-reload-preview'].setEnabled(True)
        return QWidget.showEvent(self, ev)

    def sync_to_editor(self, name):
        self.start_update_timer()

    def update_data(self):
        if not self.is_visible:
            return
        editor_name = self.current_name
        ed = editors.get(editor_name, None)
        if self.update_timer.isActive() or (ed is None and editor_name is not None):
            return QTimer.singleShot(100, self.update_data)
        if ed is not None:
            sourceline, tags = ed.current_tag()
            self.show_data(editor_name, sourceline, tags)

    def start_update_timer(self):
        if self.is_visible:
            self.update_timer.start(1000)

    def stop_update_timer(self):
        self.update_timer.stop()

