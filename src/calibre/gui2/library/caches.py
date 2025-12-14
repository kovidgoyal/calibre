#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import sys
import tempfile
import weakref
from collections import OrderedDict
from collections.abc import Iterable, Iterator, MutableMapping
from functools import partial
from queue import Empty, Queue
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import TypeVar

from qt.core import QBuffer, QByteArray, QColor, QImage, QImageReader, QImageWriter, QIODevice, QObject, QPixmap, Qt, pyqtSignal

from calibre.db.utils import ThumbnailCache as TC
from calibre.utils import join_with_timeout
from calibre.utils.img import resize_to_fit


class ThumbnailCache(TC):

    def __init__(self, max_size=1024, thumbnail_size=(100, 100), name='gui-thumbnail-cache', version=0, location=None):
        TC.__init__(self, name=name, min_disk_cache=100, max_size=max_size,
                    thumbnail_size=thumbnail_size, version=version, location=location)

    def set_database(self, db):
        TC.set_group_id(self, db.library_id)


T = TypeVar('T')


class RAMCache(MutableMapping[int, T]):
    '''
    This is a RAM cache to speed up rendering of covers by storing them as
    QPixmaps. It is possible that it is called from multiple threads, thus the
    locking and staging. For example, it can be called by the db layer when a
    book is removed either by the GUI or the content server.
    '''

    def __init__(self, limit=100):
        self.items = OrderedDict[int, T]()
        self.lock = Lock()
        self.limit = limit
        self.pixmap_staging: list[T] = []
        self.gui_thread = current_thread()

    def invalidate(self, book_ids: Iterable[int]) -> None:
        with self.lock:
            needs_staging = current_thread() is not self.gui_thread
            for book_id in book_ids:
                v = self.items.pop(book_id, None)
                if v is not None and needs_staging:
                    self.pixmap_staging.append(v)

    def _make_most_recent(self, book_id: int) -> None:
        self.items.move_to_end(book_id)

    def __delitem__(self, book_id: int) -> None:
        with self.lock:
            val = self.items.pop(book_id, None)
            if val is not None and current_thread() is not self.gui_thread:
                self.pixmap_staging.append(val)

    def __getitem__(self, book_id: int) -> None | T:
        with self.lock:
            if current_thread() is self.gui_thread:
                self.pixmap_staging = []
            ans = self.items.get(book_id, self)
            if ans is self:
                ans = None
            else:
                self._make_most_recent(book_id)
        return ans

    def __setitem__(self, key: int, val: T) -> None:
        with self.lock:
            self.items[key] = val
            self._make_most_recent(key)
            if len(self.items) > self.limit:
                val = self.items.popitem(last=False)
                if isinstance(val, QPixmap) and current_thread() is not self.gui_thread:
                    self.pixmap_staging.append(val)

    def __iter__(self) -> Iterator[int]:
        with self.lock:
            items = tuple(self.items)
        return iter(items)

    def __len__(self) -> int:
        with self.lock:
            return len(self.items)

    def clear(self) -> None:
        with self.lock:
            if current_thread() is not self.gui_thread:
                pixmaps = (x for x in self.items.values() if x is not None)
                self.pixmap_staging.extend(pixmaps)
            else:
                self.pixmap_staging = []
            self.items.clear()

    def set_limit(self, limit):
        with self.lock:
            self.limit = limit
            needs_staging = current_thread() is not self.gui_thread
            while len(self.items) > self.limit:
                val = self.items.popitem(last=False)
                if needs_staging and val is not None:
                    self.pixmap_staging.append(val)


class Thumbnailer:

    thumbnail_class: type[QImage] = QImage
    pixmap_class: type[QPixmap] = QPixmap
    CACHE_FORMAT = 'PPM'

    def __init__(self):
        self.image_format_for_pixmap = self.pixmap_class(1,1).toImage().format()

    def make_thumbnail(self, cover_as_bytes: bytes, width: int, height: int) -> tuple[QImage, bytes]:
        if not cover_as_bytes:
            return self.thumbnail_class(), b''
        cover: QImage = self.thumbnail_class()
        if not cover.loadFromData(cover_as_bytes):
            return cover, b''
        cover = self.resize_to_fit(cover, width, height)
        serialized = self.serialize(cover)
        if cover.format() != self.image_format_for_pixmap:
            cover.convertTo(self.image_format_for_pixmap)
        return cover, serialized

    def resize_to_fit(self, cover: QImage, width: int, height: int) -> QImage:
        _, cover = resize_to_fit(cover, width, height)
        return cover

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
        buf.close()
        return ba.data()

    def unserialize_img(self, buf: memoryview) -> QImage:
        ans = self.thumbnail_class()
        ans.loadFromData(buf)
        return ans

    def unserialize(self, thumbnail_as_bytes: bytes) -> QImage:
        return self.unserialize_img(memoryview(thumbnail_as_bytes))

    def as_pixmap(self, img: QImage) -> QPixmap:
        return self.pixmap_class.fromImage(img)


class ThumbnailRenderer(QObject):

    _cover_rendered = pyqtSignal(str, int, int, int, object)  # library_id, book_id, width, height, QImage
    rendered = pyqtSignal(int, object)  # book_id, QPixmap

    def emit_cover_rendered(self, library_id: str, book_id: int, width: int, height: int, thumb: QImage) -> None:
        self._cover_rendered.emit(library_id, book_id, width, height, thumb)

    def emit_rendered(self, book_id: int, thumb: QPixmap) -> None:
        self.rendered.emit(book_id, thumb)

    def __init__(self, disk_cache: ThumbnailCache, ram_cache: RAMCache, thumbnailer: Thumbnailer, parent: QObject):
        super().__init__(parent)
        self.dbref = lambda: None
        self.thumbnailer = thumbnailer
        self.disk_cache, self.ram_cache = disk_cache, ram_cache
        self.render_thread = None
        self.ignore_render_requests = Event()
        self.render_queue = Queue()
        self.current_library_id = ''
        self._cover_rendered.connect(self.on_cover_rendered, type=Qt.ConnectionType.QueuedConnection)

    def on_cover_rendered(self, library_id: str, book_id: int, width: int, height: int, img: QImage) -> None:
        if library_id != self.current_library_id or (width, height) != self.disk_cache.thumbnail_size or self.ignore_render_requests.is_set():
            return
        pmap = self.thumbnailer.as_pixmap(img)
        self.ram_cache[book_id] = pmap
        self.emit_rendered(book_id, pmap)

    def ensure_render_thread(self) -> None:
        if self.render_thread is None:
            self.render_thread = Thread(target=self.fetch_covers, name='ThumbnailRenderer', daemon=True)
            self.render_thread.start()

    def shutdown(self) -> None:
        self.ignore_render_requests.set()
        self.render_queue.put((None, None, None, None))
        self.disk_cache.shutdown()
        self.render_thread = None
    __del__ = shutdown

    def fetch_covers(self):
        q = self.render_queue
        ignore_render_requests = self.ignore_render_requests
        while True:
            library_id, book_id, width, height = q.get()
            try:
                if book_id is None:
                    break
                if ignore_render_requests.is_set() or library_id != self.current_library_id:
                    continue
                try:
                    # Fetch the cover from the cache or library
                    thumb = self.fetch_cover_from_cache(book_id, width, height)
                except Exception:
                    import traceback
                    traceback.print_exc()
                    thumb = QImage()
                try:
                    self.emit_cover_rendered(library_id, book_id, width, height, thumb)
                except Exception:  # Underlying C++ object deleted
                    import traceback
                    traceback.print_exc()
                    break
            finally:
                q.task_done()

    def fetch_cover_from_cache(self, book_id: int, width: int, height: int) -> QImage:
        '''
        This method fetches the thumbnail from the cache if it exists, otherwise renders
        the cover as a thumbnail, stores it in the cache and returns the rendered QImage.
        If the book has no cover or loading the cover fails, returns null QImage.
        '''
        if not (db := self.dbref()) or self.ignore_render_requests.is_set():
            return None
        tc = self.disk_cache
        thumbnail_as_bytes, timestamp = tc[book_id]  # None, None if not cached.
        thumbnail: QImage = QImage()
        if timestamp is None or thumbnail_as_bytes is None:
            # Cover not in cache. Try to read the cover from the library.
            has_cover, cover_as_bytes, timestamp = db.cover_or_cache(book_id, 0)
            if has_cover:
                thumbnail, thumbnail_as_bytes = self.make_thumbnail(cover_as_bytes, width, height)
                tc.insert(book_id, timestamp, thumbnail_as_bytes)
        else:
            # A cover is in the cache. Check whether it is up to date.
            has_cover, cover_as_bytes, timestamp = db.cover_or_cache(book_id, timestamp)
            if has_cover:
                if cover_as_bytes is None:
                    # The cached cover is up-to-date.
                    if thumbnail_as_bytes:
                        thumbnail = self.unserialize_thumbnail(book_id, thumbnail_as_bytes)
                        if thumbnail.isNull():
                            tc.invalidate((book_id,))
                            return self.fetch_cover_from_cache(book_id, width, height)
                else:
                    thumbnail, thumbnail_as_bytes = self.make_thumbnail(cover_as_bytes, width, height)
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

    def make_thumbnail(self, cover_as_bytes: bytes, width: int, height: int) -> tuple[QImage, bytes]:
        return self.thumbnailer.make_thumbnail(cover_as_bytes, width, height)

    def unserialize_thumbnail(self, book_id: int, thumbnail_as_bytes: bytes) -> QImage:
        ans = self.thumbnailer.unserialize(thumbnail_as_bytes)
        if ans.isNull():
            print(f'Could not load image from thumbnail data for book: {book_id}', file=sys.stderr)
        return ans

    def join_with_timeout(self, timeout: float = 2) -> None:
        try:
            # Use a timeout so that if, for some reason, the render thread
            # gets stuck, we don't deadlock, future covers won't get
            # rendered, but this is better than a deadlock
            join_with_timeout(self.render_queue, timeout)
        except RuntimeError:
            print('Cover rendering thread is stuck!', file=sys.stderr)

    def invalidate(self, book_ids: Iterable[int]) -> None:
        if not isinstance(book_ids, (tuple, set, frozenset, list, dict)):
            book_ids = tuple(book_ids)
        self.ram_cache.invalidate(book_ids)
        self.disk_cache.invalidate(book_ids)

    def set_database(self, db):
        self.current_library_id = db.new_api.library_id
        self.ignore_render_requests.set()
        try:
            olddb = self.dbref()
            if olddb is not None:
                olddb.remove_cover_cache(self)
            if db is None:
                self.dbref = lambda: None
            else:
                self.dbref = weakref.ref(db.new_api)
                db.new_api.add_cover_cache(self)
        finally:
            self.ignore_render_requests.clear()
            self.join_with_timeout()
            if db is not None:
                self.disk_cache.set_database(db)
            self.ram_cache.clear()

    def request_render(self, book_id: int) -> None:
        self.ensure_render_thread()
        width, height = self.disk_cache.thumbnail_size
        self.render_queue.put((self.current_library_id, book_id, width, height))

    def set_thumbnail_size(self, width: int, height: int) -> None:
        if (width, height) == self.disk_cache.thumbnail_size:
            return
        self.ignore_render_requests.set()
        try:
            self.disk_cache.set_thumbnail_size(width, height)
            self.ram_cache.clear()
            if self.render_thread is not None:
                self.join_with_timeout()
        finally:
            self.ignore_render_requests.clear()

    def cached_or_none(self, book_id: int) -> QPixmap | None:
        ans = self.ram_cache[book_id]
        if ans is not None:
            return ans
        if not (db := self.dbref()):
            return None
        thumbnail_as_bytes, cached_timestamp = self.disk_cache[book_id]
        if cached_timestamp is None:  # not in cache
            self.request_render(book_id)
            return None
        cover_timestamp = db.cover_timestamp(book_id)
        ans: QPixmap | None = None
        if cover_timestamp is None:  # no cover
            self.disk_cache.invalidate((book_id,))
            ans = self.thumbnailer.pixmap_class()
        elif cover_timestamp > cached_timestamp:  # stale cached cover
            self.disk_cache.invalidate((book_id,))
            self.request_render(book_id)
        else:
            img = self.unserialize_thumbnail(book_id, thumbnail_as_bytes)
            if img.isNull():  # failed to unserialize, re-render
                self.disk_cache.invalidate((book_id,))
                self.request_render(book_id)
            else:
                ans = self.thumbnailer.as_pixmap(img)
        if ans is not None:
            self.ram_cache[book_id] = ans
        return ans

    def set_disk_cache_max_size(self, size_in_mb: float) -> None:
        self.disk_cache.set_size(size_in_mb)

    def set_ram_limit(self, num_entries: int) -> None:
        self.ram_cache.set_limit(num_entries)


class CoverThumbnailCache(QObject):

    rendered = pyqtSignal(int, object)

    def __init__(
        self, max_size=1024, thumbnail_size=(100, 100), name='gui-thumbnail-cache', version=0, ram_limit=100,
        thumbnailer: Thumbnailer | None = None, parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.renderer = ThumbnailRenderer(
            ThumbnailCache(max_size=max_size, thumbnail_size=thumbnail_size, name=name, version=version),
            RAMCache(limit=ram_limit), thumbnailer or Thumbnailer(), self
        )
        self.renderer.rendered.connect(self.rendered)

    def set_database(self, db):
        self.renderer.set_database(db)

    def set_thumbnail_size(self, width: int, height: int) -> None:
        self.renderer.set_thumbnail_size(width, height)

    def set_disk_cache_max_size(self, size_in_mb: float) -> None:
        self.renderer.set_disk_cache_max_size(size_in_mb)

    def set_ram_limit(self, num_entries: int) -> None:
        self.renderer.set_ram_limit(num_entries)

    def shutdown(self) -> None:
        self.renderer.shutdown()

    @property
    def thumbnail_size(self) -> tuple[int, int]:
        return self.renderer.disk_cache.thumbnail_size

    def thumbnail_as_pixmap(self, book_id: int) -> QPixmap | None:
        '''
        Return the thumbnail from the cache if available otherwise return None and request it be rendered.
        The rendered signal will be emitted when it is rendered.
        If the pixmap is null, then it means either the book has no cover or there was some error
        rendering the cover as a thumbnail.
        '''
        return self.renderer.cached_or_none(book_id)


# Testing {{{
class ThumbnailerForTest(Thumbnailer):
    pixmap_class = QImage
    def __init__(self):
        self.image_format_for_pixmap = QImage.Format.Format_ARGB32_Premultiplied
    def as_pixmap(self, img):
        return QImage(img)


class ThumbnailRendererForTest(ThumbnailRenderer):
    def __init__(self, tdir):
        super().__init__(ThumbnailCache(thumbnail_size=(5, 5), location=tdir), RAMCache(), ThumbnailerForTest(), None)
        self.signal_queue = Queue()
        self.rendered_items = []

    def emit_cover_rendered(self, *a) -> None:
        self.signal_queue.put(partial(self.on_cover_rendered, *a))

    def emit_rendered(self, *a) -> None:
        self.rendered_items.append(a)

    def pump_signals(self, block=False, timeout=None):
        count = 0
        while True:
            try:
                self.signal_queue.get(block, timeout)()
                count += 1
                block = False
            except Empty:
                break
        return count


def run_test(self, t: ThumbnailRendererForTest):
    from calibre.db.constants import COVER_FILE_NAME
    legacy = self.init_legacy(self.cloned_library)
    db = legacy.new_api
    cimg = QImage(t.disk_cache.thumbnail_size[0]*2, t.disk_cache.thumbnail_size[1]*2, QImage.Format.Format_RGB32)
    cimg.fill(Qt.GlobalColor.red)
    db.set_cover({1: cimg})
    cimg.fill(Qt.GlobalColor.green)
    db.set_cover({2: cimg})
    cimg.fill(Qt.GlobalColor.blue)
    self.assertIsNone(db.cover_timestamp(3))
    db.set_cover({3: cimg})
    self.assertIsNotNone(db.cover_timestamp(3))
    ae = self.assertEqual

    def set_database(legacy):
        t.pump_signals()
        before = len(t.rendered_items)
        t.set_database(legacy)
        t.pump_signals()
        ae(before, len(t.rendered_items))

    def wait_for_render(timeout=2):
        if not t.rendered_items:
            limit = monotonic() + timeout
            while (now := monotonic()) < limit:
                if t.pump_signals(True, limit - now):
                    return
            raise AssertionError('Timed out waiting for render')

    def ac(book_id, col, n=0):
        wait_for_render()
        q, i = t.rendered_items[n]
        del t.rendered_items[n]
        ae(book_id, q)

        if i.isNull():
            raise AssertionError('image unexpectedly null')
        ae((i.size().width(), i.size().height()), t.disk_cache.thumbnail_size)
        actual = i.pixelColor(0, 0)
        expected = QColor(col)
        self.assertLess(max(
            abs(expected.red()-actual.red()), abs(expected.green()-actual.green()), abs(expected.blue()-actual.blue())),
                        4, f'{expected.name()} != {actual.name()}')

    t.set_database(legacy)
    self.assertIsNone(t.cached_or_none(1))
    ac(1, Qt.GlobalColor.red)
    self.assertIsNotNone(t.cached_or_none(1))
    self.assertFalse(t.ram_cache.pixmap_staging)
    t.ram_cache.clear()
    self.assertIsNotNone(t.cached_or_none(1))
    for q in (2, 3):
        self.assertIsNone(t.cached_or_none(q))
    ac(2, Qt.GlobalColor.green)
    ac(3, Qt.GlobalColor.blue)
    cimg.fill(Qt.GlobalColor.yellow)
    db.set_cover({3: cimg})
    self.assertIsNone(t.cached_or_none(3))
    ac(3, Qt.GlobalColor.yellow)
    db.set_cover({3: cimg})
    path = os.path.join(db.backend.library_path, db._get_book_path(3), COVER_FILE_NAME)
    with open(path, 'w') as f:
        f.write('not a valid image')
    self.assertIsNone(t.cached_or_none(3))
    wait_for_render()
    _, q = t.rendered_items[0]
    del t.rendered_items[0]
    self.assertTrue(q.isNull())
    db.set_cover({3: cimg})
    os.remove(path)
    self.assertIsNone(t.cached_or_none(3))
    wait_for_render()
    _, q = t.rendered_items[0]
    del t.rendered_items[0]
    self.assertTrue(q.isNull())
    cimg.fill(Qt.GlobalColor.blue)
    db.set_cover({3: cimg})
    t.set_thumbnail_size(6, 6)
    ae(0, len(t.ram_cache))
    self.assertIsNone(t.cached_or_none(1))
    ac(1, Qt.GlobalColor.red)
    legacy2 = self.init_legacy(self.clone_library(legacy.library_path))
    db = legacy2.new_api
    db.backend.library_id = 'legacy2'
    self.assertNotEqual(legacy.library_id, legacy2.library_id)
    t.set_database(legacy2)
    ae(0, len(t.ram_cache))
    self.assertIsNone(t.cached_or_none(1))
    ac(1, Qt.GlobalColor.red)

    from calibre.gui2.library.bookshelf_view import ThumbnailerWithDominantColor
    class T(ThumbnailerWithDominantColor):
        def __init__(self):
            self.image_format_for_pixmap = QImage.Format.Format_ARGB32_Premultiplied
    th = T()
    data = ThumbnailerForTest().serialize(cimg)
    i, data = th.make_thumbnail(data, *t.disk_cache.thumbnail_size)
    q = th.unserialize(data)
    ae(i.dominant_color.name(), q.dominant_color.name())


def test_cover_cache(self):
    with tempfile.TemporaryDirectory() as tdir:
        t = ThumbnailRendererForTest(tdir)
        try:
            run_test(self, t)
        finally:
            t.shutdown()
            t.join_with_timeout()
# }}}
