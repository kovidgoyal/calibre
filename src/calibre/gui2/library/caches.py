#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Lock, current_thread
from collections import OrderedDict

from PyQt4.Qt import QImage, QPixmap

class CoverCache(dict):

    ' This is a RAM cache to speed up rendering of covers by storing them as QPixmaps '

    def __init__(self, limit=200):
        self.items = OrderedDict()
        self.lock = Lock()
        self.limit = limit
        self.pixmap_staging = []
        self.gui_thread = current_thread()

    def clear_staging(self):
        ' Must be called in the GUI thread '
        self.pixmap_staging = []

    def invalidate(self, book_id):
        with self.lock:
            self._pop(book_id)

    def _pop(self, book_id):
        val = self.items.pop(book_id, None)
        if type(val) is QPixmap and current_thread() is not self.gui_thread:
            self.pixmap_staging.append(val)

    def __getitem__(self, key):
        ' Must be called in the GUI thread '
        with self.lock:
            self.clear_staging()
            ans = self.items.pop(key, False)  # pop() so that item is moved to the top
            if ans is not False:
                if type(ans) is QImage:
                    # Convert to QPixmap, since rendering QPixmap is much
                    # faster
                    ans = QPixmap.fromImage(ans)
                self.items[key] = ans

        return ans

    def set(self, key, val):
        with self.lock:
            self._pop(key)  # pop() so that item is moved to the top
            self.items[key] = val
            if len(self.items) > self.limit:
                del self.items[next(self.items.iterkeys())]

    def clear(self):
        with self.lock:
            if current_thread() is not self.gui_thread:
                pixmaps = (x for x in self.items.itervalues() if type(x) is QPixmap)
                self.pixmap_staging.extend(pixmaps)
            self.items.clear()

    def __hash__(self):
        return id(self)

    def set_limit(self, limit):
        with self.lock:
            self.limit = limit
            if len(self.items) > self.limit:
                extra = len(self.items) - self.limit
                remove = tuple(self.iterkeys())[:extra]
                for k in remove:
                    self._pop(k)

