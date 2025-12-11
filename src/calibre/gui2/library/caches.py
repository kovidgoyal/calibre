#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys
import weakref
from collections import OrderedDict
from queue import LifoQueue
from threading import Event, Lock, Thread, current_thread

from qt.core import QBuffer, QByteArray, QImage, QImageWriter, QIODevice, QObject, QPixmap, Qt, pyqtSignal

from calibre.db.utils import ThumbnailCache as TC
from calibre.utils import join_with_timeout
from calibre.utils.img import resize_to_fit


class ThumbnailCache(TC):

    def __init__(self, max_size=1024, thumbnail_size=(100, 100), name='gui-thumbnail-cache', version=0):
        TC.__init__(self, name=name, min_disk_cache=100, max_size=max_size,
                    thumbnail_size=thumbnail_size, version=version)

    def set_database(self, db):
        TC.set_group_id(self, db.library_id)


class CoverCache(dict):
    '''
    This is a RAM cache to speed up rendering of covers by storing them as
    QPixmaps. It is possible that it is called from multiple threads, thus the
    locking and staging. For example, it can be called by the db layer when a
    book is removed either by the GUI or the content server.
    '''

    def __init__(self, limit=100):
        self.items = OrderedDict()
        self.lock = Lock()
        self.limit = limit
        self.pixmap_staging = []
        self.gui_thread = current_thread()

    def clear_staging(self):
        ' Must be called in the GUI thread '
        self.pixmap_staging = []

    def invalidate(self, book_ids):
        with self.lock:
            for book_id in book_ids:
                self._pop(book_id)

    def make_most_recent(self, book_id: int) -> None:
        self.items.move_to_end(book_id)

    def _pop(self, book_id):
        val = self.items.pop(book_id, None)
        if isinstance(val, QPixmap) and current_thread() is not self.gui_thread:
            self.pixmap_staging.append(val)

    def __getitem__(self, book_id):
        ' Must be called in the GUI thread '
        with self.lock:
            self.clear_staging()
            ans = self.items.get(book_id, False)
            if ans is not False:
                if isinstance(ans, QImage):
                    # Convert to QPixmap, since rendering QPixmap is much
                    # faster
                    ans = QPixmap.fromImage(ans)
                self.make_most_recent(book_id)
        return ans

    def set(self, key, val):
        with self.lock:
            self.items[key] = val
            self.make_most_recent(key)
            if len(self.items) > self.limit:
                val = self.items.popitem(last=False)
                if isinstance(val, QPixmap) and current_thread() is not self.gui_thread:
                    self.pixmap_staging.append(val)

    def clear(self):
        with self.lock:
            if current_thread() is not self.gui_thread:
                pixmaps = (x for x in self.items.values() if isinstance(x, QPixmap))
                self.pixmap_staging.extend(pixmaps)
            self.items.clear()

    def __hash__(self):
        return id(self)

    def set_limit(self, limit):
        with self.lock:
            self.limit = limit
            is_non_gui_thread = current_thread() is not self.gui_thread
            while len(self.items) > self.limit:
                val = self.items.popitem(last=False)
                if is_non_gui_thread and isinstance(val, QPixmap):
                    self.pixmap_staging.append(val)


class Thumbnailer:

    thumbnail_class = QImage
    pixmap_class = QPixmap
    CACHE_FORMAT = 'PPM'

    def __init__(self):
        self.image_format_for_pixmap = QPixmap(1,1).toImage().format()

    def make_thumbnail(self, cover_as_bytes: bytes, width: int, height: int) -> tuple[QImage, bytes]:
        if not cover_as_bytes:
            return self.thumbnail_class(), b''
        cover: QImage = self.thumbnail_class()
        if not cover.loadFromData(cover_as_bytes):
            return cover, b''
        cover, _ = resize_to_fit(cover, width, height)
        serialized = self.serialize(cover)
        if cover.format() != self.image_format_for_pixmap:
            cover.convertTo(self.image_format_for_pixmap)
        return cover, serialized

    def serialize_img(self, x: QImage, buf: QBuffer) -> bool:
        w = QImageWriter(buf, self.CACHE_FORMAT.encode())
        if not w.write(x):
            print('Failed to serialize cover thumbnail to PPM format with error:', w.errorString(), file=sys.stderr)
            return False
        return True

    def serialize(self, x: QImage) -> bytes:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        if not self.serialize_img(x, buf):
            return b''
        return ba.data()

    def unserialize_img(self, data: memoryview) -> QImage:
        ans = self.thumbnail_class()
        ans.loadFromData(data)
        return ans

    def unserialize(self, thumbnail_as_bytes: bytes) -> QImage:
        return self.unserialize_img(memoryview(thumbnail_as_bytes))

    def as_pixmap(self, img: QImage) -> QPixmap:
        return self.pixmap_class() if img.isNull() else self.pixmap_class.fromImage(img)


class ThumbnailRenderer(QObject):

    _cover_rendered = pyqtSignal(str, int, object)  # book_id, QImage
    rendered = pyqtSignal(int, object)

    def __init__(self, disk_cache: ThumbnailCache, ram_cache: CoverCache, thumbnailer: Thumbnailer, parent: QObject):
        super().__init__(parent)
        self.dbref = lambda: None
        self.thumbnailer = thumbnailer
        self.disk_cache, self.ram_cache = disk_cache, ram_cache
        self.render_thread = None
        self.ignore_render_requests = Event()
        self.render_queue = LifoQueue()
        self.current_library_id = ''
        self._cover_rendered.connect(self.on_cover_rendered, type=Qt.ConnectionType.QueuedConnection)

    def on_cover_rendered(self, library_id: str, book_id: int, img: QImage) -> None:
        pmap = self.thumbnailer.as_pixmap(img)
        self.ram_cache.set(book_id, pmap)
        if library_id == self.current_library_id:
            self.rendered.emit(book_id, pmap)

    def ensure_render_thread(self) -> None:
        if self.render_thread is None:
            self.render_thread = Thread(target=self.fetch_covers, name='ThumbnailRenderer', daemon=True)
            self.render_thread.start()

    def shutdown(self) -> None:
        self.ignore_render_requests.set()
        self.render_queue.put((None, None))
        self.disk_cache.shutdown()
        self.render_thread = None

    def fetch_covers(self):
        q = self.render_queue
        ignore_render_requests = self.ignore_render_requests
        while True:
            library_id, book_id = q.get()
            try:
                if book_id is None:
                    break
                if ignore_render_requests.is_set() or library_id != self.current_library_id:
                    continue
                thumb = None
                try:
                    # Fetch the cover from the cache or file system
                    thumb = self.fetch_cover_from_cache(book_id)
                except Exception:
                    import traceback
                    traceback.print_exc()
                # Store newly rendered thumbnail in RAM cache
                try:
                    self._cover_rendered.emit(library_id, book_id, thumb)
                except Exception:
                    break  # Underlying C++ object deleted
            finally:
                q.task_done()

    def fetch_cover_from_cache(self, book_id: int) -> QImage | None:
        '''
        This method fetches the cover from the cache if it exists, otherwise renders
        the cover as a thumbnail, stores it in the cache and returns the rendered QImage.
        If the book has no cover or loading the cover fails, returns None.
        '''
        if not (db := self.dbref()) or self.ignore_render_requests.is_set():
            return None
        tc = self.thumbnail_cache
        thumbnail_as_bytes, timestamp = tc[book_id]  # None, None if not cached.
        thumbnail: QImage = QImage()
        if timestamp is None or thumbnail_as_bytes is None:
            # Cover not in cache. Try to read the cover from the library.
            has_cover, cover_as_bytes, timestamp = db.new_api.cover_or_cache(book_id, 0)
            if has_cover:
                thumbnail, thumbnail_as_bytes = self.make_thumbnail(cover_as_bytes)
                tc.insert(book_id, timestamp, thumbnail_as_bytes)
        else:
            # A cover is in the cache. Check whether it is up to date.
            has_cover, cover_as_bytes, timestamp = db.new_api.cover_or_cache(book_id, timestamp)
            if has_cover:
                if cover_as_bytes is None:
                    # The cached cover is up-to-date.
                    if thumbnail_as_bytes:
                        thumbnail = self.unserialize_thumbnail(book_id, thumbnail_as_bytes)
                        if thumbnail.isNull():
                            print(f'Could not load image from thumbnail data for book: {book_id}, regenerating thumbnail', file=sys.stderr)
                            tc.invalidate((book_id,))
                            return self.fetch_cover_from_cache(book_id)
                else:
                    thumbnail, thumbnail_as_bytes = self.make_thumbnail(cover_as_bytes)
                    tc.insert(book_id, timestamp, thumbnail_as_bytes)
            else:
                # We found a cached cover for a book without a cover. This can
                # happen in older version of calibre that can reuse book_ids
                # between libraries and books in one library have covers where
                # they don't in another library. This version doesn't have the
                # problem because the cache UUID is set when the database
                # changes instead of when the cache thread is created.
                tc.invalidate((book_id,))
        return thumbnail

    def make_thumbnail(self, cover_as_bytes: bytes) -> tuple[QImage, bytes]:
        tc = self.disk_cache
        return self.thumbnailer.make_thumbnail(cover_as_bytes, *tc.thumbnail_size)

    def unserialize_thumbnail(self, book_id: int,  thumbnail_as_bytes: bytes) -> QImage:
        ans = self.thumbnailer.unserialize(thumbnail_as_bytes)
        if ans.isNull():
            print(f'Could not load image from thumbnail data for book: {book_id}', file=sys.stderr)
        return ans

    def set_database(self, db):
        self.ignore_render_requests.set()
        self.current_library_id = db.new_api.library_id
        try:
            olddb = self.dbref()
            if olddb is not None:
                olddb.remove_cover_cache(self.disk_cache)
                olddb.remove_cover_cache(self.ram_cache)
            if db is None:
                self.dbref = lambda: None
            else:
                self.dbref = weakref.ref(db.new_api)
                db.new_api.add_cover_cache(self.disk_cache)
                db.new_api.add_cover_cache(self.ram_cache)
            try:
                # Use a timeout so that if, for some reason, the render thread
                # gets stuck, we don't deadlock, future covers won't get
                # rendered, but this is better than a deadlock
                join_with_timeout(self.render_queue)
            except RuntimeError:
                print('Cover rendering thread is stuck!', file=sys.stderr)
        finally:
            self.ignore_render_requests.clear()
            if db is not None:
                self.disk_cache.set_database(db)
            self.ram_cache.clear()

    def request_render(self, book_id: int) -> None:
        self.render_queue.put((self.current_library_id, book_id))


class CombinedCoverCache(QObject):

    rendered = pyqtSignal(int, object)

    def __init__(
        self, max_size=1024, thumbnail_size=(100, 100), name='gui-thumbnail-cache', version=0, ram_limit=100,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.renderer = ThumbnailRenderer(
            ThumbnailCache(max_size=max_size, thumbnail_size=thumbnail_size, name=name, version=version),
            CoverCache(limit=ram_limit), self
        )
        self.renderer.rendered.connect(self.rendered)

    def set_database(self, db):
        self.renderer.set_database(db)

    def thumbnail_as_pixmap(self, book_id: int) -> tuple[QPixmap, bool]:
        ans = self.renderer.ram_cache[book_id]
        if isinstance(ans, QPixmap):
            return ans, True
        self.renderer.request_render(book_id)
        return QPixmap(), False
