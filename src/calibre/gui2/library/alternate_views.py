#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import itertools, operator, os
from types import MethodType
from time import time
from threading import Event, Thread
from Queue import Queue
from functools import wraps, partial
from textwrap import wrap

from PyQt4.Qt import (
    QListView, QSize, QStyledItemDelegate, QModelIndex, Qt, QImage, pyqtSignal,
    QTimer, QPalette, QColor, QItemSelection, QPixmap, QMenu, QApplication,
    QMimeData, QUrl, QDrag, QPoint, QPainter, QRect, pyqtProperty, QEvent,
    QPropertyAnimation, QEasingCurve, pyqtSlot, QHelpEvent, QAbstractItemView,
    QStyleOptionViewItem, QToolTip, QByteArray, QBuffer)

from calibre import fit_image, prints, prepare_string_for_xml
from calibre.ebooks.metadata import fmt_sidx
from calibre.gui2 import gprefs, config
from calibre.gui2.library.caches import CoverCache, ThumbnailCache
from calibre.utils.config import prefs

CM_TO_INCH = 0.393701
CACHE_FORMAT = 'PPM'

def auto_height(widget):
    return max(185, QApplication.instance().desktop().availableGeometry(widget).height() / 5.0)

class EncodeError(ValueError):
    pass

def image_to_data(image):  # {{{
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    if not image.save(buf, CACHE_FORMAT):
        raise EncodeError('Failed to encode thumbnail')
    ret = bytes(ba.data())
    buf.close()
    return ret
# }}}

# Drag 'n Drop {{{
def dragMoveEvent(self, event):
    event.acceptProposedAction()

def event_has_mods(self, event=None):
    mods = event.modifiers() if event is not None else \
            QApplication.keyboardModifiers()
    return mods & Qt.ControlModifier or mods & Qt.ShiftModifier

def mousePressEvent(base_class, self, event):
    ep = event.pos()
    if self.indexAt(ep) in self.selectionModel().selectedIndexes() and \
            event.button() == Qt.LeftButton and not self.event_has_mods():
        self.drag_start_pos = ep
    if hasattr(self, 'handle_mouse_press_event'):
        return self.handle_mouse_press_event(event)
    return base_class.mousePressEvent(self, event)

def drag_icon(self, cover, multiple):
    cover = cover.scaledToHeight(120, Qt.SmoothTransformation)
    if multiple:
        base_width = cover.width()
        base_height = cover.height()
        base = QImage(base_width+21, base_height+21,
                QImage.Format_ARGB32_Premultiplied)
        base.fill(QColor(255, 255, 255, 0).rgba())
        p = QPainter(base)
        rect = QRect(20, 0, base_width, base_height)
        p.fillRect(rect, QColor('white'))
        p.drawRect(rect)
        rect.moveLeft(10)
        rect.moveTop(10)
        p.fillRect(rect, QColor('white'))
        p.drawRect(rect)
        rect.moveLeft(0)
        rect.moveTop(20)
        p.fillRect(rect, QColor('white'))
        p.save()
        p.setCompositionMode(p.CompositionMode_SourceAtop)
        p.drawImage(rect.topLeft(), cover)
        p.restore()
        p.drawRect(rect)
        p.end()
        cover = base
    return QPixmap.fromImage(cover)

def drag_data(self):
    m = self.model()
    db = m.db
    selected = self.get_selected_ids()
    ids = ' '.join(map(str, selected))
    md = QMimeData()
    md.setData('application/calibre+from_library', ids)
    fmt = prefs['output_format']

    def url_for_id(i):
        try:
            ans = db.format_path(i, fmt, index_is_id=True)
        except:
            ans = None
        if ans is None:
            fmts = db.formats(i, index_is_id=True)
            if fmts:
                fmts = fmts.split(',')
            else:
                fmts = []
            for f in fmts:
                try:
                    ans = db.format_path(i, f, index_is_id=True)
                except:
                    ans = None
        if ans is None:
            ans = db.abspath(i, index_is_id=True)
        return QUrl.fromLocalFile(ans)

    md.setUrls([url_for_id(i) for i in selected])
    drag = QDrag(self)
    col = self.selectionModel().currentIndex().column()
    try:
        md.column_name = self.column_map[col]
    except AttributeError:
        md.column_name = 'title'
    drag.setMimeData(md)
    cover = self.drag_icon(m.cover(self.currentIndex().row()),
            len(selected) > 1)
    drag.setHotSpot(QPoint(-15, -15))
    drag.setPixmap(cover)
    return drag

def mouseMoveEvent(base_class, self, event):
    if not self.drag_allowed:
        return
    if self.drag_start_pos is None:
        return base_class.mouseMoveEvent(self, event)

    if self.event_has_mods():
        self.drag_start_pos = None
        return

    if not (event.buttons() & Qt.LeftButton) or \
            (event.pos() - self.drag_start_pos).manhattanLength() \
                    < QApplication.startDragDistance():
        return

    index = self.indexAt(event.pos())
    if not index.isValid():
        return
    drag = self.drag_data()
    drag.exec_(Qt.CopyAction)
    self.drag_start_pos = None

def dragEnterEvent(self, event):
    if int(event.possibleActions() & Qt.CopyAction) + \
        int(event.possibleActions() & Qt.MoveAction) == 0:
        return
    paths = self.paths_from_event(event)

    if paths:
        event.acceptProposedAction()

def dropEvent(self, event):
    paths = self.paths_from_event(event)
    event.setDropAction(Qt.CopyAction)
    event.accept()
    self.files_dropped.emit(paths)

def paths_from_event(self, event):
    '''
    Accept a drop event and return a list of paths that can be read from
    and represent files with extensions.
    '''
    md = event.mimeData()
    if md.hasFormat('text/uri-list') and not \
            md.hasFormat('application/calibre+from_library'):
        urls = [unicode(u.toLocalFile()) for u in md.urls()]
        return [u for u in urls if os.path.splitext(u)[1] and
                os.path.exists(u)]

def setup_dnd_interface(cls_or_self):
    if isinstance(cls_or_self, type):
        cls = cls_or_self
        base_class = cls.__bases__[0]
        fmap = globals()
        for x in (
            'dragMoveEvent', 'event_has_mods', 'mousePressEvent', 'mouseMoveEvent',
            'drag_data', 'drag_icon', 'dragEnterEvent', 'dropEvent', 'paths_from_event'):
            func = fmap[x]
            if x in {'mouseMoveEvent', 'mousePressEvent'}:
                func = partial(func, base_class)
            setattr(cls, x, MethodType(func, None, cls))
        return cls
    else:
        self = cls_or_self
        self.drag_allowed = True
        self.drag_start_pos = None
        self.setDragEnabled(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(self.DragDrop)
# }}}

# Manage slave views {{{
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
        view.files_dropped.connect(self.main_view.files_dropped)

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

    def set_context_menu(self, menu):
        for view in self.views.itervalues():
            if view is not self.main_view:
                view.set_context_menu(menu)
# }}}

# Rendering of covers {{{
class CoverDelegate(QStyledItemDelegate):

    MARGIN = 4

    @pyqtProperty(float)
    def animated_size(self):
        return self._animated_size

    @animated_size.setter
    def animated_size(self, val):
        self._animated_size = val

    def __init__(self, parent):
        super(CoverDelegate, self).__init__(parent)
        self._animated_size = 1.0
        self.animation = QPropertyAnimation(self, 'animated_size', self)
        self.animation.setEasingCurve(QEasingCurve.OutInCirc)
        self.animation.setDuration(500)
        self.set_dimensions()
        self.cover_cache = CoverCache(limit=gprefs['cover_grid_cache_size'])
        self.render_queue = Queue()
        self.animating = None
        self.highlight_color = QColor(Qt.white)

    def set_dimensions(self):
        width = self.original_width = gprefs['cover_grid_width']
        height = self.original_height = gprefs['cover_grid_height']
        self.original_show_title = show_title = gprefs['cover_grid_show_title']

        if height < 0.1:
            height = auto_height(self.parent())
        else:
            height *= self.parent().logicalDpiY() * CM_TO_INCH

        if width < 0.1:
            width = 0.75 * height
        else:
            width *= self.parent().logicalDpiX() * CM_TO_INCH
        self.cover_size = QSize(width, height)
        self.title_height = 0
        if show_title:
            f = self.parent().font()
            sz = f.pixelSize()
            if sz < 5:
                sz = f.pointSize() * self.parent().logicalDpiY() / 72.0
            self.title_height = max(25, sz + 10)
        self.item_size = self.cover_size + QSize(2 * self.MARGIN, (2 * self.MARGIN) + self.title_height)
        self.calculate_spacing()
        self.animation.setStartValue(1.0)
        self.animation.setKeyValueAt(0.5, 0.5)
        self.animation.setEndValue(1.0)

    def calculate_spacing(self):
        spc = self.original_spacing = gprefs['cover_grid_spacing']
        if spc < 0.01:
            self.spacing = max(10, min(50, int(0.1 * self.original_width)))
        else:
            self.spacing = self.parent().logicalDpiX() * CM_TO_INCH * spc

    def sizeHint(self, option, index):
        return self.item_size

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, QModelIndex())  # draw the hover and selection highlights
        m = index.model()
        db = m.db
        try:
            book_id = db.id(index.row())
        except (ValueError, IndexError, KeyError):
            return
        if book_id in m.ids_to_highlight_set:
            painter.save()
            try:
                painter.setPen(self.highlight_color)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.drawRoundedRect(option.rect, 10, 10, Qt.RelativeSize)
            finally:
                painter.restore()
        marked = db.data.get_marked(book_id)
        db = db.new_api
        cdata = self.cover_cache[book_id]
        device_connected = self.parent().gui.device_connected is not None
        on_device = device_connected and db.field_for('ondevice', book_id)
        painter.save()
        right_adjust = 0
        try:
            rect = option.rect
            rect.adjust(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)
            orect = QRect(rect)
            if cdata is None or cdata is False:
                title = db.field_for('title', book_id, default_value='')
                authors = ' & '.join(db.field_for('authors', book_id, default_value=()))
                painter.setRenderHint(QPainter.TextAntialiasing, True)
                painter.drawText(rect, Qt.AlignCenter|Qt.TextWordWrap, '%s\n\n%s' % (title, authors))
                if cdata is False:
                    self.render_queue.put(book_id)
            else:
                if self.title_height != 0:
                    trect = QRect(rect)
                    rect.setBottom(rect.bottom() - self.title_height)
                if self.animating is not None and self.animating.row() == index.row():
                    cdata = cdata.scaled(cdata.size() * self._animated_size)
                dx = max(0, int((rect.width() - cdata.width())/2.0))
                dy = max(0, rect.height() - cdata.height())
                right_adjust = dx
                rect.adjust(dx, dy, -dx, 0)
                painter.drawPixmap(rect, cdata)
                if self.title_height != 0:
                    rect = trect
                    rect.setTop(rect.bottom() - self.title_height + 5)
                    painter.setRenderHint(QPainter.TextAntialiasing, True)
                    title = db.field_for('title', book_id, default_value='')
                    metrics = painter.fontMetrics()
                    painter.drawText(rect, Qt.AlignCenter|Qt.TextSingleLine,
                                     metrics.elidedText(title, Qt.ElideRight, rect.width()))
            if marked:
                try:
                    p = self.marked_emblem
                except AttributeError:
                    p = self.marked_emblem = QPixmap(I('rating.png')).scaled(48, 48, transformMode=Qt.SmoothTransformation)
                drect = QRect(orect)
                drect.setLeft(drect.left() + right_adjust)
                drect.setRight(drect.left() + p.width())
                drect.setBottom(drect.bottom() - self.title_height)
                drect.setTop(drect.bottom() - p.height())
                painter.drawPixmap(drect, p)
            if on_device:
                try:
                    p = self.on_device_emblem
                except AttributeError:
                    p = self.on_device_emblem = QPixmap(I('ok.png')).scaled(48, 48, transformMode=Qt.SmoothTransformation)
                drect = QRect(orect)
                drect.setRight(drect.right() - right_adjust)
                drect.setBottom(drect.bottom() - self.title_height)
                drect.setTop(drect.bottom() - p.height() + 1)
                drect.setLeft(drect.right() - p.width() + 1)
                painter.drawPixmap(drect, p)
        finally:
            painter.restore()

    @pyqtSlot(QHelpEvent, QAbstractItemView, QStyleOptionViewItem, QModelIndex, result=bool)
    def helpEvent(self, event, view, option, index):
        if event is not None and view is not None and event.type() == QEvent.ToolTip:
            try:
                db = index.model().db
            except AttributeError:
                return False
            try:
                book_id = db.id(index.row())
            except (ValueError, IndexError, KeyError):
                return False
            db = db.new_api
            device_connected = self.parent().gui.device_connected
            on_device = device_connected is not None and db.field_for('ondevice', book_id)
            p = prepare_string_for_xml
            title = db.field_for('title', book_id)
            authors = db.field_for('authors', book_id)
            if title and authors:
                title = '<b>%s</b>' % ('<br>'.join(wrap(p(title), 120)))
                authors = '<br>'.join(wrap(p(' & '.join(authors)), 120))
                tt = '%s<br><br>%s' % (title, authors)
                series = db.field_for('series', book_id)
                if series:
                    use_roman_numbers=config['use_roman_numerals_for_series_number']
                    val = _('Book %(sidx)s of <span class="series_name">%(series)s</span>')%dict(
                        sidx=fmt_sidx(db.field_for('series_index', book_id), use_roman=use_roman_numbers),
                        series=p(series))
                    tt += '<br><br>' + val
                if on_device:
                    val = _('This book is on the device in %s') % on_device
                    tt += '<br><br>' + val
                QToolTip.showText(event.globalPos(), tt, view)
                return True
        return False

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
# }}}

# The View {{{
@setup_dnd_interface
class GridView(QListView):

    update_item = pyqtSignal(object)
    files_dropped = pyqtSignal(object)

    def __init__(self, parent):
        QListView.__init__(self, parent)
        setup_dnd_interface(self)
        self.setUniformItemSizes(True)
        self.setWrapping(True)
        self.setFlow(self.LeftToRight)
        # We cannot set layout mode to batched, because that breaks
        # restore_vpos()
        # self.setLayoutMode(self.Batched)
        self.setResizeMode(self.Adjust)
        self.setSelectionMode(self.ExtendedSelection)
        self.setVerticalScrollMode(self.ScrollPerPixel)
        self.delegate = CoverDelegate(self)
        self.delegate.animation.valueChanged.connect(self.animation_value_changed)
        self.delegate.animation.finished.connect(self.animation_done)
        self.setItemDelegate(self.delegate)
        self.setSpacing(self.delegate.spacing)
        self.padding_left = 0
        self.set_color()
        self.ignore_render_requests = Event()
        self.thumbnail_cache = ThumbnailCache(max_size=gprefs['cover_grid_disk_cache_size'],
            thumbnail_size=(self.delegate.cover_size.width(), self.delegate.cover_size.height()))
        self.render_thread = None
        self.update_item.connect(self.re_render, type=Qt.QueuedConnection)
        self.doubleClicked.connect(self.double_clicked)
        self.setCursor(Qt.PointingHandCursor)
        self.gui = parent
        self.context_menu = None
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(200)
        self.update_timer.timeout.connect(self.update_viewport)
        self.update_timer.setSingleShot(True)

    @property
    def first_visible_row(self):
        geom = self.viewport().geometry()
        for y in xrange(geom.top(), (self.spacing()*2) + geom.top(), 5):
            for x in xrange(geom.left(), (self.spacing()*2) + geom.left(), 5):
                ans = self.indexAt(QPoint(x, y)).row()
                if ans > -1:
                    return ans

    @property
    def last_visible_row(self):
        geom = self.viewport().geometry()
        for y in xrange(geom.bottom(), geom.bottom() - 2 * self.spacing(), -5):
            for x in xrange(geom.left(), (self.spacing()*2) + geom.left(), 5):
                ans = self.indexAt(QPoint(x, y)).row()
                if ans > -1:
                    item_width = self.delegate.item_size.width() + 2*self.spacing()
                    return ans + (geom.width() // item_width)

    def update_viewport(self):
        self.ignore_render_requests.clear()
        self.update_timer.stop()
        m = self.model()
        for r in xrange(self.first_visible_row or 0, self.last_visible_row or (m.count() - 1)):
            self.update(m.index(r, 0))

    def double_clicked(self, index):
        d = self.delegate
        if d.animating is None and not config['disable_animations']:
            d.animating = index
            d.animation.start()
        self.gui.iactions['View'].view_triggered(index)

    def animation_value_changed(self, value):
        if self.delegate.animating is not None:
            self.update(self.delegate.animating)

    def animation_done(self):
        if self.delegate.animating is not None:
            idx = self.delegate.animating
            self.delegate.animating = None
            self.update(idx)

    def set_color(self):
        r, g, b = gprefs['cover_grid_color']
        pal = QPalette()
        col = QColor(r, g, b)
        pal.setColor(pal.Base, col)
        dark = (r + g + b)/3.0 < 128
        pal.setColor(pal.Text, QColor(Qt.white if dark else Qt.black))
        self.setPalette(pal)
        self.delegate.highlight_color = pal.color(pal.Text)

    def refresh_settings(self):
        size_changed = (
            gprefs['cover_grid_width'] != self.delegate.original_width or
            gprefs['cover_grid_height'] != self.delegate.original_height
        )
        if (size_changed or gprefs['cover_grid_show_title'] != self.delegate.original_show_title):
            self.delegate.set_dimensions()
            self.setSpacing(self.delegate.spacing)
            if size_changed:
                self.delegate.cover_cache.clear()
        if gprefs['cover_grid_spacing'] != self.delegate.original_spacing:
            self.delegate.calculate_spacing()
            self.setSpacing(self.delegate.spacing)
        self.set_color()
        self.delegate.cover_cache.set_limit(gprefs['cover_grid_cache_size'])
        if size_changed:
            self.thumbnail_cache.set_thumbnail_size(self.delegate.cover_size.width(), self.delegate.cover_size.height())
        cs = gprefs['cover_grid_disk_cache_size']
        if (cs*(1024**2)) != self.thumbnail_cache.max_size:
            self.thumbnail_cache.set_size(cs)

    def shown(self):
        if self.render_thread is None:
            self.thumbnail_cache.set_database(self.gui.current_db)
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
        if self.ignore_render_requests.is_set():
            return
        tcdata, timestamp = self.thumbnail_cache[book_id]
        use_cache = False
        if timestamp is None:
            # Not in cache
            has_cover, cdata, timestamp = self.model().db.new_api.cover_or_cache(book_id, 0)
        else:
            has_cover, cdata, timestamp = self.model().db.new_api.cover_or_cache(book_id, timestamp)
            if has_cover and cdata is None:
                # The cached cover is fresh
                cdata = tcdata
                use_cache = True

        if has_cover:
            p = QImage()
            p.loadFromData(cdata, CACHE_FORMAT if cdata is tcdata else 'JPEG')
            if p.isNull() and cdata is tcdata:
                # Invalid image in cache
                self.thumbnail_cache.invalidate((book_id,))
                self.update_item.emit(book_id)
                return
            cdata = None if p.isNull() else p
            if not use_cache:  # cache is stale
                if cdata is not None:
                    width, height = p.width(), p.height()
                    scaled, nwidth, nheight = fit_image(width, height, self.delegate.cover_size.width(), self.delegate.cover_size.height())
                    if scaled:
                        if self.ignore_render_requests.is_set():
                            return
                        p = p.scaled(nwidth, nheight, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    cdata = p
                # update cache
                if cdata is None:
                    self.thumbnail_cache.invalidate((book_id,))
                else:
                    try:
                        self.thumbnail_cache.insert(book_id, timestamp, image_to_data(cdata))
                    except EncodeError as err:
                        self.thumbnail_cache.invalidate((book_id,))
                        prints(err)
                    except Exception:
                        import traceback
                        traceback.print_exc()
        elif tcdata is not None:
            # Cover was removed, but it exists in cache, remove from cache
            self.thumbnail_cache.invalidate((book_id,))
        self.delegate.cover_cache.set(book_id, cdata)
        self.update_item.emit(book_id)

    def re_render(self, book_id):
        self.delegate.cover_cache.clear_staging()
        m = self.model()
        try:
            index = m.db.row(book_id)
        except (IndexError, ValueError, KeyError):
            return
        self.update(m.index(index, 0))

    def shutdown(self):
        self.ignore_render_requests.set()
        self.delegate.render_queue.put(None)
        self.thumbnail_cache.shutdown()

    def set_database(self, newdb, stage=0):
        if stage == 0:
            self.ignore_render_requests.set()
            try:
                for x in (self.delegate.cover_cache, self.thumbnail_cache):
                    self.model().db.new_api.remove_cover_cache(x)
            except AttributeError:
                pass  # db is None
            for x in (self.delegate.cover_cache, self.thumbnail_cache):
                newdb.new_api.add_cover_cache(x)
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

    def set_context_menu(self, menu):
        self.context_menu = menu

    def contextMenuEvent(self, event):
        if self.context_menu is not None:
            menu = self._temp_menu = QMenu(self)
            sac = self.gui.iactions['Sort By']
            sort_added = tuple(ac for ac in self.context_menu.actions() if ac is sac.qaction)
            if not sort_added:
                menu.addAction(sac.qaction)
            for ac in self.context_menu.actions():
                menu.addAction(ac)
            sac.update_menu()
            menu.popup(event.globalPos())
            event.accept()

    def get_selected_ids(self):
        m = self.model()
        return [m.id(i) for i in self.selectionModel().selectedIndexes()]

    def restore_vpos(self, vpos):
        self.verticalScrollBar().setValue(vpos)

    def restore_hpos(self, hpos):
        pass

    def handle_mouse_press_event(self, ev):
        if QApplication.keyboardModifiers() & Qt.ShiftModifier:
            # Shift-Click in QLitView is broken. It selects extra items in
            # various circumstances, for example, click on some item in the
            # middle of a row then click on an item in the next row, all items
            # in the first row will be selected instead of only items after the
            # middle item.
            index = self.indexAt(ev.pos())
            if not index.isValid():
                return
            ci = self.currentIndex()
            sm = self.selectionModel()
            sm.setCurrentIndex(index, sm.NoUpdate)
            if not ci.isValid():
                return
            if not sm.hasSelection():
                sm.select(index, sm.ClearAndSelect)
                return
            cr = ci.row()
            tgt = index.row()
            top = self.model().index(min(cr, tgt), 0)
            bottom = self.model().index(max(cr, tgt), 0)
            sm.select(QItemSelection(top, bottom), sm.Select)
        else:
            return QListView.mousePressEvent(self, ev)
# }}}
