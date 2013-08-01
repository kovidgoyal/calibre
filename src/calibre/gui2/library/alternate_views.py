#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import itertools, operator
from time import time
from collections import OrderedDict
from threading import Lock, Event, Thread
from Queue import Queue
from functools import wraps

from PyQt4.Qt import (
    QListView, QSize, QStyledItemDelegate, QModelIndex, Qt, QImage, pyqtSignal,
    QPalette, QColor, QItemSelection)

from calibre import fit_image

def sync(func):
    @wraps(func)
    def ans(self, *args, **kwargs):
        if self.break_link or self.current_view is self.main_view:
            return
        with self:
            return func(self, *args, **kwargs)
    return ans

class AlternateViews(object):

    def __init__(self, main_view):
        self.views = {None:main_view}
        self.stack_positions = {None:0}
        self.current_view = self.main_view = main_view
        self.stack = None
        self.break_link = False
        self.main_connected = False

    def set_stack(self, stack):
        self.stack = stack
        self.stack.addWidget(self.main_view)

    def add_view(self, key, view):
        self.views[key] = view
        self.stack_positions[key] = self.stack.count()
        self.stack.addWidget(view)
        self.stack.setCurrentIndex(0)
        view.setModel(self.main_view._model)
        view.selectionModel().currentChanged.connect(self.slave_current_changed)
        view.selectionModel().selectionChanged.connect(self.slave_selection_changed)

    def show_view(self, key=None):
        view = self.views[key]
        if view is self.current_view:
            return
        self.stack.setCurrentIndex(self.stack_positions[key])
        self.current_view = view
        if view is not self.main_view:
            self.main_current_changed(self.main_view.currentIndex())
            self.main_selection_changed()
            view.shown()
            if not self.main_connected:
                self.main_connected = True
                self.main_view.selectionModel().currentChanged.connect(self.main_current_changed)
                self.main_view.selectionModel().selectionChanged.connect(self.main_selection_changed)
            view.setFocus(Qt.OtherFocusReason)

    def set_database(self, db, stage=0):
        for view in self.views.itervalues():
            if view is not self.main_view:
                view.set_database(db, stage=stage)

    def __enter__(self):
        self.break_link = True

    def __exit__(self, *args):
        self.break_link = False

    @sync
    def slave_current_changed(self, current, *args):
        self.main_view.set_current_row(current.row(), for_sync=True)

    @sync
    def slave_selection_changed(self, *args):
        rows = {r.row() for r in self.current_view.selectionModel().selectedIndexes()}
        self.main_view.select_rows(rows, using_ids=False, change_current=False, scroll=False)

    @sync
    def main_current_changed(self, current, *args):
        self.current_view.set_current_row(current.row())

    @sync
    def main_selection_changed(self, *args):
        rows = {r.row() for r in self.main_view.selectionModel().selectedIndexes()}
        self.current_view.select_rows(rows)


class CoverCache(dict):

    def __init__(self, limit=200):
        self.items = OrderedDict()
        self.lock = Lock()
        self.limit = limit

    def invalidate(self, book_id):
        with self.lock:
            self.items.pop(book_id, None)

    def __call__(self, key):
        with self.lock:
            ans = self.items.pop(key, False)
            if ans is not False:
                self.items[key] = ans
                if len(self.items) > self.limit:
                    del self.items[next(self.items.iterkeys())]

        return ans

    def set(self, key, val):
        with self.lock:
            self.items[key] = val
            if len(self.items) > self.limit:
                del self.items[next(self.items.iterkeys())]

    def clear(self):
        with self.lock:
            self.items.clear()

    def __hash__(self):
        return id(self)

class CoverDelegate(QStyledItemDelegate):

    def __init__(self, parent, width, height):
        super(CoverDelegate, self).__init__(parent)
        self.cover_size = QSize(width, height)
        self.item_size = self.cover_size + QSize(8, 8)
        self.spacing = max(10, min(50, int(0.1 * width)))
        self.cover_cache = CoverCache()
        self.render_queue = Queue()

    def sizeHint(self, option, index):
        return self.item_size

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, QModelIndex())  # draw the hover and selection highlights
        db = index.model().db
        try:
            book_id = db.id(index.row())
        except (ValueError, IndexError, KeyError):
            return
        db = db.new_api
        cdata = self.cover_cache(book_id)
        painter.save()
        try:
            rect = option.rect
            rect.adjust(4, 4, -4, -4)
            if cdata is None or cdata is False:
                title = db.field_for('title', book_id, default_value='')
                painter.drawText(rect, Qt.AlignCenter|Qt.TextWordWrap, title)
                if cdata is False:
                    self.render_queue.put(book_id)
            else:
                dx = max(0, int((rect.width() - cdata.width())/2.0))
                dy = max(0, rect.height() - cdata.height())
                rect.adjust(dx, dy, -dx, 0)
                painter.drawImage(rect, cdata)
        finally:
            painter.restore()

def join_with_timeout(q, timeout=2):
    q.all_tasks_done.acquire()
    try:
        endtime = time() + timeout
        while q.unfinished_tasks:
            remaining = endtime - time()
            if remaining <= 0.0:
                raise RuntimeError('Waiting for queue to clear timed out')
            q.all_tasks_done.wait(remaining)
    finally:
        q.all_tasks_done.release()

class GridView(QListView):

    update_item = pyqtSignal(object)

    def __init__(self, parent):
        QListView.__init__(self, parent)
        pal = QPalette(self.palette())
        r = g = b = 0x50
        pal.setColor(pal.Base, QColor(r, g, b))
        pal.setColor(pal.Text, QColor(Qt.white if (r + g + b)/3.0 < 128 else Qt.black))
        self.setPalette(pal)
        self.setUniformItemSizes(True)
        self.setWrapping(True)
        self.setFlow(self.LeftToRight)
        self.setLayoutMode(self.Batched)
        self.setResizeMode(self.Adjust)
        self.setSelectionMode(self.ExtendedSelection)
        self.delegate = CoverDelegate(self, 135, 180)
        self.setItemDelegate(self.delegate)
        self.setSpacing(self.delegate.spacing)
        self.ignore_render_requests = Event()
        self.render_thread = None
        self.update_item.connect(self.re_render, type=Qt.QueuedConnection)

    def shown(self):
        if self.render_thread is None:
            self.render_thread = Thread(target=self.render_covers)
            self.render_thread.daemon = True
            self.render_thread.start()

    def render_covers(self):
        q = self.delegate.render_queue
        while True:
            book_id = q.get()
            try:
                if book_id is None:
                    return
                if self.ignore_render_requests.is_set():
                    continue
                try:
                    self.render_cover(book_id)
                except:
                    import traceback
                    traceback.print_exc()
            finally:
                q.task_done()

    def render_cover(self, book_id):
        cdata = self.model().db.new_api.cover(book_id)
        if self.ignore_render_requests.is_set():
            return
        if cdata is not None:
            p = QImage()
            p.loadFromData(cdata)
            cdata = None
            if not p.isNull():
                width, height = p.width(), p.height()
                scaled, nwidth, nheight = fit_image(width, height, self.delegate.cover_size.width(), self.delegate.cover_size.height())
                if scaled:
                    if self.ignore_render_requests.is_set():
                        return
                    p = p.scaled(nwidth, nheight, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                cdata = p
        self.delegate.cover_cache.set(book_id, cdata)
        self.update_item.emit(book_id)

    def re_render(self, book_id):
        m = self.model()
        try:
            index = m.db.row(book_id)
        except (IndexError, ValueError, KeyError):
            return
        self.update(m.index(index, 0))

    def shutdown(self):
        self.ignore_render_requests.set()
        self.delegate.render_queue.put(None)

    def set_database(self, newdb, stage=0):
        if stage == 0:
            self.ignore_render_requests.set()
            try:
                self.model().db.new_api.remove_cover_cache(self.delegate.cover_cache)
            except AttributeError:
                pass  # db is None
            newdb.new_api.add_cover_cache(self.delegate.cover_cache)
            try:
                # Use a timeout so that if, for some reason, the render thread
                # gets stuck, we dont deadlock, future covers wont get
                # rendered, but this is better than a deadlock
                join_with_timeout(self.delegate.render_queue)
            except RuntimeError:
                print ('Cover rendering thread is stuck!')
            finally:
                self.ignore_render_requests.clear()
        else:
            self.delegate.cover_cache.clear()

    def select_rows(self, rows):
        sel = QItemSelection()
        sm = self.selectionModel()
        m = self.model()
        # Create a range based selector for each set of contiguous rows
        # as supplying selectors for each individual row causes very poor
        # performance if a large number of rows has to be selected.
        for k, g in itertools.groupby(enumerate(rows), lambda (i,x):i-x):
            group = list(map(operator.itemgetter(1), g))
            sel.merge(QItemSelection(m.index(min(group), 0), m.index(max(group), 0)), sm.Select)
        sm.select(sel, sm.ClearAndSelect)

    def set_current_row(self, row):
        sm = self.selectionModel()
        sm.setCurrentIndex(self.model().index(row, 0), sm.NoUpdate)

