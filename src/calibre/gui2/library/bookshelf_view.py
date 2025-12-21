#!/usr/bin/env python
# License: GPLv3
# Copyright: Andy C <achuongdev@gmail.com>, un_pogaz <un.pogaz@gmail.com>, Kovid Goyal <kovid@kovidgoyal.net>

# TODO:
# implement proper current and selection management with support for mouse and keyboard interaction
# implement marks and ondevice indicators
# improve rendering of spine (optional full cover over spine?)
# improve rendering of shelf and background with options for dark/light
# fix drag and drop
# fix arrow keys home/end for navigation
# fix double clicking
# hover shift change to shift off shelf edge. fix hover transition to next book.
# Remove py_dominant_color after beta release
import bisect
import hashlib
import math
import os
import struct
import weakref
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import suppress
from functools import lru_cache, partial
from operator import attrgetter
from threading import Event, RLock, Thread
from time import time
from typing import NamedTuple

from qt.core import (
    QAbstractScrollArea,
    QApplication,
    QBrush,
    QBuffer,
    QColor,
    QContextMenuEvent,
    QEvent,
    QFont,
    QFontMetrics,
    QImage,
    QItemSelection,
    QItemSelectionModel,
    QLinearGradient,
    QLocale,
    QMenu,
    QModelIndex,
    QObject,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QPoint,
    QPointF,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
    qBlue,
    qGreen,
    qRed,
)

from calibre.db.cache import Cache
from calibre.db.legacy import LibraryDatabase
from calibre.ebooks.metadata import rating_to_stars
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import gprefs, resolve_bookshelf_color
from calibre.gui2.library.alternate_views import setup_dnd_interface
from calibre.gui2.library.caches import CoverThumbnailCache, Thumbnailer
from calibre.gui2.library.models import BooksModel
from calibre.gui2.momentum_scroll import MomentumScrollMixin
from calibre.utils.icu import numeric_sort_key
from calibre.utils.img import resize_to_fit
from calibre.utils.localization import lang_map
from calibre_extensions import imageops

TEMPLATE_ERROR_COLOR = QColor('#9C27B0')
TEMPLATE_ERROR = _('TEMPLATE ERROR')


# Utility functions {{{

def get_reading_statue(book_id, db, mi=None) -> str:
    '''
    Determine reading statue for a book based on
    the last read position (if available)

    Returns: 'unread', 'reading', or 'finished'
    '''
    if not mi:
        mi = db.new_api.get_proxy_metadata(book_id)

    formats = mi.get('formats') or []
    if formats:
        # Check if any format has a last read position
        for fmt in formats:
            positions = db.new_api.get_last_read_positions(book_id, fmt, '_')
            if positions:
                # Has reading progress
                for pos in positions:
                    pos_frac = pos.get('pos_frac', 0)
                    if pos_frac >= 0.95:  # 95% or more = finished
                        return 'finished'
                    elif pos_frac > 0.01:  # More than 1% = reading
                        return 'reading'

    return 'unread'


def normalised_size(size_bytes: int) -> float:
    '''Estimate page count from file size.'''
    # Average ebook: ~1-2KB per page, so estimate pages from size
    if size_bytes and size_bytes > 0:
        # Estimate: ~1500 bytes per page (conservative)
        estimated_pages = size_bytes // 1500
        # Normalise the value
        return min(estimated_pages / 2000, 1)
    return 0.


def pseudo_random(book_id: int, maximum) -> int:
    '''Use book_id to create a pseudo-random but consistent value per book.'''
    val = str(book_id or 0).encode()
    hash_val = int(hashlib.md5(val).hexdigest()[:8], 16)
    return hash_val % maximum


def elapsed_time(ref_time: float) -> float:
    '''Get elapsed time, in milliseconds.'''
    return (time() - ref_time) * 1000


# }}}


# Cover functions {{{

def py_dominant_color(self: QImage) -> QColor:
    img = self
    if img.width() > 100 or img.height() > 100:
        img = img.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    if (img.format() not in (QImage.Format.Format_RGB32, QImage.Format.Format_ARGB32)):
        img = img.convertToFormat(
            QImage.Format.Format_ARGB32 if img.hasAlphaChannel() else QImage.Format.Format_RGB32)
    color_counts = Counter()
    width, height = img.width(), img.height()
    stride = img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    view = memoryview(ptr)
    for y in range(height):
        row_start_idx = y * stride
        row_end_idx = row_start_idx + (width * 4)
        row_data = view[row_start_idx:row_end_idx]
        for i in range(0, len(row_data), 4):
            b, g, r = row_data[i:i+3]
            # Quantize to 32 levels per channel
            # Preserve color variety while grouping similar colors
            c = ((r//8)*8, (g//8)*8, (b//8)*8)
            color_counts[c] += 1
    if not color_counts:
        return QColor()
    # Find most common color, prefer saturated colors
    # Sort by frequency, then by saturation
    def color_score(item):
        (r, g, b), count = item
        # Calculate saturation (how colorful vs gray)
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        if max_val == 0:
            saturation = 0
        else:
            saturation = (max_val - min_val) / max_val
        # Weight by frequency and saturation
        return (count, saturation * 100)

    # Get top colors by frequency
    sorted_colors = sorted(color_counts.items(), key=color_score, reverse=True)

    # Avoid desaturated gray/brown colors
    dominant_color = sorted_colors[0][0]

    # Look for more vibrant alternative if needed
    r, g, b = dominant_color
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    saturation = (max_val - min_val) / max_val if max_val > 0 else 0

    # Try to find more colorful alternatives
    if saturation < 0.2 and len(sorted_colors) > 1:
        num_pixels = img.width() * img.height()
        for (r2, g2, b2), count in sorted_colors[1:5]:  # Check top 5 alternatives
            max_val2 = max(r2, g2, b2)
            min_val2 = min(r2, g2, b2)
            sat2 = (max_val2 - min_val2) / max_val2 if max_val2 > 0 else 0
            # Use if more saturated and reasonably frequent
            if sat2 > 0.3 and count > num_pixels * 0.05:  # At least 5% of pixels
                dominant_color = (r2, g2, b2)
                break
    return QColor(*dominant_color)


dominant_color = getattr(imageops, 'dominant_color', py_dominant_color)  # for people running from source


class ImageWithDominantColor(QImage):

    _dominant_color: QColor | None = None
    DEFAULT_DOMINANT_COLOR = QColor('#8B4513')

    @property
    def dominant_color(self) -> QColor:
        if self._dominant_color is not None:
            return self._dominant_color
        ans = self.DEFAULT_DOMINANT_COLOR if self.isNull() else dominant_color(self)
        if not ans.isValid():
            ans = self.DEFAULT_DOMINANT_COLOR
        self._dominant_color = ans
        return ans


class PixmapWithDominantColor(QPixmap):
    dominant_color: QColor = QColor()

    @staticmethod
    def fromImage(img: QImage) -> 'PixmapWithDominantColor':
        ans = PixmapWithDominantColor(QPixmap.fromImage(img))
        if not hasattr(img, 'dominant_color'):
            img = ImageWithDominantColor(img)
        ans.dominant_color = img.dominant_color
        return ans


@lru_cache(maxsize=2)
def default_cover_pixmap(width: int, height: int) -> PixmapWithDominantColor:
    i = QImage(I('default_cover_image.png'))
    _, i = resize_to_fit(i, width, height)
    return PixmapWithDominantColor.fromImage(ImageWithDominantColor(i))


class ThumbnailerWithDominantColor(Thumbnailer):
    thumbnail_class: type[QImage] = ImageWithDominantColor
    pixmap_class: type[QPixmap] = PixmapWithDominantColor

    def resize_to_fit(self, cover: QImage, width: int, height: int) -> ImageWithDominantColor:
        ans = super().resize_to_fit(cover, width, height)
        if not isinstance(ans, ImageWithDominantColor):
            ans = ImageWithDominantColor(ans)
        return ans

    def serialize_img(self, x: ImageWithDominantColor, buf: QBuffer) -> bool:
        buf.write(struct.pack('@fff', x.dominant_color.redF(), x.dominant_color.greenF(), x.dominant_color.blueF()))
        return super().serialize_img(x, buf)

    def unserialize_img(self, buf: memoryview) -> ImageWithDominantColor:
        try:
            r, g, b = struct.unpack_from('@fff', buf)
        except Exception:
            r = g = b = 0
        dc = QColor()
        dc.setRedF(r), dc.setGreenF(g), dc.setBlueF(b)
        qimg = super().unserialize_img(buf[struct.calcsize('@fff'):])
        ans = ImageWithDominantColor(qimg)
        ans._dominant_color = dc
        return ans
# }}}


GROUPINGS = {
    'authors',
    'series',
    'tags',
    'publisher',
    'pubdate',
    'timestamp',
    'rating',
    'languages',
}


class LayoutConstraints(NamedTuple):
    min_spine_width: int = 15
    max_spine_width: int = 60
    default_spine_width: int = 40
    spine_height: int = 150
    shelf_height: int = 20
    divider_width: int = 30
    horizontal_gap: int = 2
    shelf_gap: int = 20
    width: int = 0
    side_margin: int = 4
    hover_expanded_width: int = 110

    @property
    def step_height(self) -> int:
        return self.spine_height + self.shelf_height


def height_reduction_for_book_id(book_id: int) -> int:
    return book_id & 0b1111


class ShelfItem(NamedTuple):
    start_x: int
    case_start_y: int
    width: int
    reduce_height_by: int = 0
    book_id: int = 0
    group_name: str = ''

    @property
    def is_divider(self) -> bool:
        return self.book_id == 0

    def rect(self, lc: LayoutConstraints) -> QRect:
        return QRect(
            self.start_x + lc.side_margin,
            self.case_start_y + self.reduce_height_by + lc.shelf_gap,
            self.width,
            lc.spine_height - self.reduce_height_by - lc.shelf_gap
        )


class CaseItem:
    start_y: int = 0
    width: int = 0
    height: int = 0
    idx: int = 0
    items: list[ShelfItem] | None = None

    def __init__(self, y: int = 0, height: int = 0, is_shelf: bool = False, idx: int = 0):
        self.start_y = y
        self.height = height
        self.idx = idx
        if not is_shelf:
            self.items = []

    def book_or_divider_at_xpos(self, x: int) -> ShelfItem | None:
        if self.items:
            idx = bisect.bisect_right(self.items, x, key=attrgetter('start_x'))
            if idx > 0:
                candidate = self.items[idx-1]
                if x < candidate.start_x + candidate.width:
                    return candidate
        return None

    def _get_x_for_item(self, width: int, lc: LayoutConstraints) -> int | None:
        x = (self.width + lc.horizontal_gap) if self.width else 0
        if x + width + lc.horizontal_gap > lc.width:
            return None
        return x

    def add_group_divider(self, group_name: str, lc: LayoutConstraints) -> bool:
        if not group_name:
            return True
        if (x := self._get_x_for_item(lc.divider_width, lc)) is None:
            return False
        s = ShelfItem(start_x=x, group_name=group_name, width=lc.divider_width, case_start_y=self.start_y)
        self.items.append(s)
        self.width = s.start_x + s.width
        return True

    def add_book(self, book_id: int, width: int, group_name: str, lc: LayoutConstraints) -> bool:
        if (x := self._get_x_for_item(width, lc)) is None:
            return False
        s = ShelfItem(
            start_x=x, book_id=book_id, reduce_height_by=height_reduction_for_book_id(book_id),
            width=width, group_name=group_name, case_start_y=self.start_y)
        self.items.append(s)
        self.width = s.start_x + s.width
        return True

    @property
    def is_shelf(self) -> bool:
        return self.items is None


def get_grouped_iterator(dbref: weakref.ref[LibraryDatabase], book_ids_iter: Iterable[int], field_name: str = '') -> Iterator[tuple[str, Iterable[int]]]:
    formatter = lambda x: x  # noqa: E731
    sort_key = numeric_sort_key
    ldb = dbref()
    if ldb is None:
        return
    db = ldb.new_api
    get_books_in_group = lambda group: db.books_for_field(field_name, group)  # noqa: E731
    get_field_id_map = lambda: db.get_id_map(field_name)  # noqa: E731
    sort_map = {book_id: i for i, book_id in enumerate(book_ids_iter)}
    all_book_ids = set(sort_map)

    match field_name:
        case '':
            yield '', 0
            yield '', book_ids_iter
            return
        case 'rating':
            formatter = rating_to_stars
            sort_key = lambda x: -x  # noqa: E731
        case 'languages':
            lm = lang_map()
            formatter = lambda x: lm.get(x, x)  # noqa: E731
            sort_key = lambda x: numeric_sort_key(formatter(x))  # noqa: E731
        case 'pubdate':
            year_map = db.books_by_year(field=field_name, restrict_to_books=all_book_ids)
            get_books_in_group = year_map.__getitem__
            get_field_id_map = lambda: {x: x for x in year_map}  # noqa: E731
            sort_key = lambda x: -x  # noqa: E731
            formatter = str
        case 'timestamp':
            lsys = QLocale.system().monthName
            month_map = db.books_by_month(field=field_name, restrict_to_books=all_book_ids)
            get_books_in_group = month_map.__getitem__
            get_field_id_map = lambda: {x: x for x in month_map}  # noqa: E731
            sort_key = lambda x: (-x[0], -x[1])  # noqa: E731
            formatter = lambda x: f'{lsys(x[1], QLocale.FormatType.ShortFormat)} {x[0]}'  # noqa: E731

    field_id_map = get_field_id_map()
    yield '', len(field_id_map)
    seen = set()
    for group in sorted(field_id_map, key=lambda fid: sort_key(field_id_map[fid])):
        books_in_group = (get_books_in_group(group) & all_book_ids) - seen
        if books_in_group:
            seen |= books_in_group
            yield formatter(field_id_map[group]), sorted(books_in_group,  key=sort_map.__getitem__)


def get_spine_width(book_id: int, db: Cache, spine_size_template: str, template_cache: dict[str, str], lc: LayoutConstraints, cache: dict[int, int]) -> int:
    if (ans := cache.get(book_id)) is not None:
        return ans

    def linear(f: float):
        return lc.min_spine_width + int(max(0, min(f, 1)) * (lc.max_spine_width - lc.min_spine_width))

    def log(f: float):
        b = 10
        return linear(math.log(1+max(0, min(f, 1))*b, b+1))

    ans = -1
    match spine_size_template:
        case '':
            ans = lc.default_spine_width
        case '{size}' | 'size':
            ans = log(normalised_size(db.field_for('size', book_id, 0)))
        case '{random}' | 'random':
            # range: 0.25-0.75
            ans = linear((25+pseudo_random(book_id, 50))/100)
        case _:
            with suppress(Exception):
                if 0 <= (x := float(spine_size_template)) <= 1:
                    ans = linear(x)
            if ans < 0:
                with suppress(Exception):
                    mi = db.get_proxy_metadata(book_id)
                    rslt = mi.formatter.safe_format(spine_size_template, mi, TEMPLATE_ERROR, mi, template_cache=template_cache)
                    ans = linear(float(rslt))
    if ans < 0:
        ans = lc.default_spine_width
    cache[book_id] = ans
    return ans


class BookCase(QObject):
    items: list[CaseItem]
    layout_finished: bool = False
    height: int = 0

    shelf_added = pyqtSignal(object, object)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.row_to_book_id: tuple[int, ...] = ()
        self._book_id_to_row_map: dict[int, int] = {}
        self.lock = RLock()
        self.current_invalidate_event = Event()
        self.spine_width_cache: dict[int, int] = {}
        self.num_of_groups = 0
        self.invalidate()

    def shutdown(self):
        self.current_invalidate_event.set()
        self.current_invalidate_event = Event()
        if self.worker is not None:
            self.worker.join()
            self.worker = None

    def clear_spine_width_cache(self):
        self.spine_width_cache = {}

    def shelf_with_ypos(self, y: int) -> CaseItem | None:
        ' Return the container of books or shelf that contains the specified y position '
        for shelf in self.iter_shelves_from_ypos(y):
            return shelf
        return None

    def iter_shelves_from_ypos(self, y: int) -> Iterator[CaseItem]:
        with self.lock:
            idx = bisect.bisect_right(self.items, y, key=attrgetter('start_y'))
            if idx > 0:
                candidate: CaseItem = self.items[idx-1]
                if y < candidate.start_y + candidate.height:
                    for i in range(idx-1, len(self.items)):
                        yield self.items[i]

    @property
    def current_height(self) -> int:
        with self.lock:
            ans = 0
            if self.items:
                ans = self.items[-1].start_y + self.items[-1].height
            if not self.layout_finished:
                ans += self.layout_constraints.step_height
        return ans

    @property
    def max_possible_height(self) -> int:
        with self.lock:
            if self.layout_finished or self.layout_constraints.width == 0:
                return self.current_height

            num_of_rows = (self.num_of_groups + len(self.row_to_book_id)) * self.layout_constraints.max_spine_width // self.layout_constraints.width
            return (num_of_rows + 1) * self.layout_constraints.step_height

    def invalidate(
        self, layout_constraints: LayoutConstraints = LayoutConstraints(),
        model: BooksModel | None = None, group_field_name: str = ''
    ) -> None:
        with self.lock:
            self.current_invalidate_event.set()
            self.current_invalidate_event = Event()
            self.worker = None
            self.group_field_name = group_field_name
            self.items = []
            self.height = 0
            self.layout_constraints = layout_constraints
            self.book_id_to_item_map: dict[int, ShelfItem] = {}
            if model is not None and (db := model.db) is not None:
                # implies set of books to display has changed
                self.row_to_book_id = db.data.index_to_id_map()
                self._book_id_to_row_map = {}
                self.dbref = weakref.ref(db)
                self.group_itr = get_grouped_iterator(self.dbref, self.row_to_book_id, self.group_field_name)
                _, self.num_of_groups = next(self.group_itr)
            self.layout_finished = not bool(self.row_to_book_id)

    def ensure_worker(self) -> None:
        with self.lock:
            if self.worker is None and not self.layout_finished and self.layout_constraints.width:
                self.worker = Thread(
                    target=partial(
                        self.do_layout_in_worker, self.current_invalidate_event, self.group_itr, self.layout_constraints,
                        self.book_id_to_item_map
                    ),
                    name='BookCaseLayout', daemon=True
                )
                self.worker.start()

    @property
    def book_id_to_row_map(self) -> dict[int, int]:
        if self.row_to_book_id and not self._book_id_to_row_map:
            self._book_id_to_row_map = {bid: r for r, bid in enumerate(self.row_to_book_id)}
        return self._book_id_to_row_map

    def do_layout_in_worker(
        self, invalidate: Event, group_iter: Iterator[tuple[str, Iterable[int]]], lc: LayoutConstraints,
        book_id_to_item_map: dict[int, ShelfItem],
    ) -> None:
        if lc.width < lc.max_spine_width:
            return
        def commit_case_item(x: CaseItem) -> int:
            with self.lock:
                if invalidate.is_set():
                    return self.height
                self.items.append(x)
                self.height += lc.spine_height
                self.items.append(CaseItem(idx=len(self.items), y=self.height, height=lc.shelf_height, is_shelf=True))
                self.height += lc.shelf_height
                self.shelf_added.emit(x, self.items[-1])
                return self.height

        current_case_item = CaseItem(height=lc.spine_height)
        mdb = self.dbref()
        if mdb is None:
            return
        db = mdb.new_api
        spine_size_template = db.pref('bookshelf_spine_size_template') or db.backend.prefs.defaults['bookshelf_spine_size_template']
        template_cache = {}
        for group_name, book_ids_in_group in group_iter:
            if invalidate.is_set():
                return
            if not current_case_item.add_group_divider(group_name, lc):
                y = commit_case_item(current_case_item)
                current_case_item = CaseItem(y=y, height=lc.spine_height, idx=len(self.items))
                current_case_item.add_group_divider(group_name, lc)
            for book_id in book_ids_in_group:
                if invalidate.is_set():
                    return
                spine_width = get_spine_width(book_id, db, spine_size_template, template_cache, lc, self.spine_width_cache)
                if not current_case_item.add_book(book_id, spine_width, group_name, lc):
                    y = commit_case_item(current_case_item)
                    current_case_item = CaseItem(y=y, height=lc.spine_height, idx=len(self.items))
                    current_case_item.add_book(book_id, spine_width, group_name, lc)
                book_id_to_item_map[book_id] = current_case_item.items[-1]
        if current_case_item.items:
            commit_case_item(current_case_item)
        with self.lock:
            if invalidate.is_set():
                return
            self.layout_finished = True
            self.worker = None
            if len(self.items) > 1:
                self.shelf_added.emit(self.items[-2], self.items[-1])


class HoveredCover:
    '''Simple class to store the data related to the current hovered cover.'''

    OPACITY_START = 0.3
    FADE_TIME = 200  # Duration of the animation, in milliseconds

    row: int = -1
    book_id: int = -1
    shelf_item: ShelfItem | None = None
    progress: float = 0  # Animation progress (0.0 to 1.0)
    opacity: float = OPACITY_START  # Current opacity (0.3 to 1.0)
    shift: float = 0.0  # Current state of the shift animation (0.0 to 1.0)
    width: int = -1  # Current width
    height: int = -1  # Current height
    width_max: int = -1  # Maximum width
    height_end: int = -1  # Final height
    height_modifier: int = -1  # Height modifier
    base_x_pos: int = 0  # Base x position
    base_y_pos: int = 0  # Base y position
    spine_width: int = -1  # Spine width of this book
    spine_height: int = -1  # Spine height of this book
    dominant_color: QColor = QColor()  # Dominant color of this cover
    start_time: float | None = None  # Start time of fade-in animation

    def __init__(self):
        self.pixmap: QPixmap = QPixmap()  # Scaled cover for hover popup

    def is_valid(self) -> bool:
        '''Test if the HoveredCover is valid.'''
        return bool(self.row >= 0) and self.has_pixmap()

    def has_pixmap(self) -> bool:
        '''Test if contain a valid pixmap.'''
        return not self.pixmap.isNull()

    def is_row(self, row: int) -> bool:
        '''Test if the given row is the one of the hovered cover.'''
        return self.is_valid() and row == self.row

    def rect(self, lc: LayoutConstraints) -> QRect:
        '''Return the current QRect of the hover popup.'''
        offset_y = self.spine_height + lc.shelf_gap
        rslt = QRect(self.base_x_pos, self.base_y_pos + offset_y, self.width, self.height)
        if self.height_end < self.spine_height:
            modifier = self.height_modifier - round(self.height_modifier * self.shift)
            rslt.adjust(0, modifier, 0, 0)
        else:
            rslt.adjust(0, self.height_modifier, 0, 0)
        return rslt

    def spine_rect(self) -> QRect:
        '''Return the book spine QRect.'''
        rslt = QRect(self.base_x_pos, self.base_y_pos, self.spine_width, self.spine_height)
        rslt.adjust(0, self.height_modifier, 0, 0)
        return rslt

    def update(self):
        '''Update hover cover fade-in animation and shift progress.'''
        if not self.start_time:
            return

        elapse = elapsed_time(self.start_time)
        if elapse >= self.FADE_TIME:
            self.progress = 1.0
            self.opacity = 1.0
            self.shift = 1.0
            self.width = max(self.width_max, self.spine_width)
            self.height = self.height_end
            self.start_time = None
        else:
            self.progress = progress = elapse / self.FADE_TIME
            # Cubic ease-out curve (similar to JSX mock)
            # Ease-out cubic: 1 - (1 - t)^3
            self.shift = cubic = 1.0 - (1.0 - progress) ** 3
            # Interpolate opacity from 0.3 (start) to 1.0 (end)
            self.opacity = self.OPACITY_START + (1.0 - self.OPACITY_START) * cubic

            # Start the animation at the same width of the spine
            if self.width_max > self.spine_width:
                self.width = self.spine_width + math.ceil((self.width_max - self.spine_width) * cubic)
            else:
                # In the rare case when the spine is bigger than the cover
                self.width = self.spine_width

            # Scale also the height to smooth the animation
            if self.height_end < self.spine_height:
                self.height = self.spine_height - math.ceil((self.spine_height - self.height_end) * cubic)
            else:
                self.height = self.spine_height


@setup_dnd_interface
class BookshelfView(MomentumScrollMixin, QAbstractScrollArea):
    '''
    Enhanced bookshelf view displaying books as spines on shelves.

    This view provides an immersive browsing experience with sorting
    and grouping capabilities.
    '''

    files_dropped = pyqtSignal(object)
    books_dropped = pyqtSignal(object)

    # Dimensions
    layout_constraints: LayoutConstraints
    DIVIDER_LINE_WIDTH = 2  # Width of the gradient line in divider

    # Colors
    SHELF_COLOR_START = QColor('#4a3728')
    SHELF_COLOR_END = QColor('#3d2e20')
    TEXT_COLOR = QColor('#eee')
    TEXT_COLOR_DARK = QColor('#222')  # Dark text for light backgrounds
    SELECTION_HIGHLIGHT_COLOR = QColor('#ff0')
    DIVIDER_TEXT_COLOR = QColor('#b0b5c0')
    DIVIDER_LINE_COLOR = QColor('#4a4a6a')
    DIVIDER_GRADIENT_LINE_1 = DIVIDER_LINE_COLOR.toRgb()
    DIVIDER_GRADIENT_LINE_2 = DIVIDER_LINE_COLOR.toRgb()
    DIVIDER_GRADIENT_LINE_1.setAlphaF(0.0)  # Transparent at top/bottom
    DIVIDER_GRADIENT_LINE_2.setAlphaF(0.75)  # Visible in middle

    def __init__(self, gui):
        super().__init__(gui)
        self.gui = gui
        self._model: BooksModel | None = None
        self.context_menu: QMenu | None = None
        # Since layouting is expensive and dependent on width and the scrollbar
        # visibility in turn is dependent on layouting and affects width, we
        # keep scrollbar always on
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        QApplication.instance().palette_changed.connect(self.set_color)

        # Ensure viewport receives mouse events
        self.viewport().setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_MouseTracking, True)

        # Initialize drag and drop
        # so we set the attributes manually
        self.drag_allowed = True
        self.drag_start_pos = None
        self.bookcase = BookCase()
        self.bookcase.shelf_added.connect(self.on_shelf_layout_done, type=Qt.ConnectionType.QueuedConnection)

        # Selection tracking
        self._selected_rows: set[int] = set()
        self._current_row = -1
        self._selection_model: QItemSelectionModel = None
        self._syncing_from_main = False  # Flag to prevent feedback loops

        # Cover loading and caching
        self._height_modifiers: dict[int, int] = {}  # Cache for height modifiers (book_id -> height)
        self._hovered = HoveredCover()  # Currently hovered book
        self._hover_fade_timer = QTimer(self)  # Timer for fade-in animation
        self._hover_fade_timer.setSingleShot(False)
        self._hover_fade_timer.timeout.connect(self._update_hover_fade)
        self._hover_buffer_timer = QTimer(self)  # Timer for buffer the hover animation
        self._hover_buffer_timer.setSingleShot(False)
        self._hover_buffer_timer.timeout.connect(self._delayed_hover_load)
        self._hover_buffer_row = -1
        self._hover_buffer_time = None

        self.layout_constraints = LayoutConstraints()
        self.layout_constraints = lc = self.layout_constraints._replace(width=self._get_available_width())
        self.cover_cache = CoverThumbnailCache(
            name='bookshelf-thumbnail-cache', ram_limit=800,
            max_size=gprefs['bookshelf_disk_cache_size'], thumbnailer=ThumbnailerWithDominantColor(),
            thumbnail_size=(lc.max_spine_width, lc.spine_height), parent=self, version=2,
        )
        self.cover_cache.rendered.connect(self.update_viewport, type=Qt.ConnectionType.QueuedConnection)

        # Configuration
        self._grouping_mode = ''
        self.refresh_settings()

        # Cover template caching
        self.template_inited = False
        self.template_cache = {}
        self.template_title = ''
        self.template_statue = ''
        self.size_template = '{size}'
        self.template_title_is_empty = True
        self.template_statue_is_empty = True

    # Templates rendering methods

    def init_template(self, db):
        '''Initialize templates and database settings.'''
        if not db:
            return
        if self.template_inited and self.dbref() == db.new_api:
            return

        def db_pref(key):
            prefs = db.new_api.backend.prefs
            return prefs.get(key, prefs.defaults.get(key))

        self.template_cache = {}
        self.rules_color = db_pref('bookshelf_color_rules') or []
        self.template_title = db_pref('bookshelf_title_template') or ''
        self.template_title_is_title = self.template_title == '{title}'
        self.template_title_is_empty = not self.template_title.strip()
        self.template_inited = True

    def render_template_title(self, book_id: int, mi=None) -> str:
        '''Return the title generate for this book.'''
        self.init_template(self.dbref())
        if self.template_title_is_empty:
            return ''
        if not mi:
            mi = self.dbref().get_proxy_metadata(book_id)
        if self.template_title_is_title:
            return mi.title
        rslt = mi.formatter.safe_format(self.template_title, mi, TEMPLATE_ERROR, mi, column_name='title', template_cache=self.template_cache)
        if rslt:
            return rslt
        return _('Unknown')

    def render_color_indicator(self, book_id: int, mi: Metadata=None) -> QColor:
        '''Return the statue indicator color generate for this book.'''
        self.init_template(self.dbref())
        if not mi:
            mi = self.dbref().get_proxy_metadata(book_id)
        for i, (kind, column, rule) in enumerate(self.rules_color):
            rslt = QColor(mi.formatter.safe_format(rule, mi, TEMPLATE_ERROR, mi, column_name=f'color:{i}', template_cache=self.template_cache))
            if rslt.isValid():
                return rslt
        return None

    # Miscellaneous methods

    def refresh_settings(self):
        '''Refresh the gui and render settings.'''
        self._enable_shadow = gprefs['bookshelf_shadow']
        self._enable_thumbnail = gprefs['bookshelf_thumbnail']
        self._enable_centered = gprefs['bookshelf_centered']
        self._enable_variable_height = gprefs['bookshelf_variable_height']
        self._hovered.FADE_TIME = gprefs['bookshelf_fade_time']
        self.cover_cache.set_disk_cache_max_size(gprefs['bookshelf_disk_cache_size'])
        self.layout_constraints = self.layout_constraints._replace(width=self._get_available_width())
        self._update_ram_cache_size()
        self.set_color()
        self.bookcase.clear_spine_width_cache()
        self.invalidate()

    def set_color(self):
        resolve_bookshelf_color()
        r, g, b = resolve_bookshelf_color()
        tex = resolve_bookshelf_color(which='texture')
        pal = self.palette()
        bgcol = QColor(r, g, b)
        pal.setColor(QPalette.ColorRole.Base, bgcol)
        self.setPalette(pal)
        ss = f'background-color: {bgcol.name()}; border: 0px solid {bgcol.name()};'
        if tex:
            from calibre.gui2.preferences.texture_chooser import texture_path
            path = texture_path(tex)
            if path:
                path = os.path.abspath(path).replace(os.sep, '/')
                ss += f'background-image: url({path});'
                ss += 'background-attachment: fixed;'
                pm = QPixmap(path)
                if not pm.isNull():
                    val = pm.scaled(1, 1).toImage().pixel(0, 0)
                    r, g, b = qRed(val), qGreen(val), qBlue(val)
        self.setStyleSheet(f'QAbstractScrollArea {{ {ss} }}')

    def view_is_visible(self) -> bool:
        '''Return if the bookshelf view is visible.'''
        with suppress(AttributeError):
            return self.gui.bookshelf_view_button.is_visible
        return False

    def shutdown(self):
        self.cover_cache.shutdown()
        self.bookcase.shutdown()

    def setModel(self, model: BooksModel | None) -> None:
        '''Set the model for this view.'''
        signals = {
            'dataChanged': '_model_data_changed', 'rowsInserted': '_model_rows_changed',
            'rowsRemoved': '_model_rows_changed', 'modelReset': '_model_reset',
        }
        if self._model is not None:
            for s, tgt in signals.items():
                getattr(self._model, s).disconnect(getattr(self, tgt))
        self._model = model
        self._selection_model = None
        if model is not None:
            # Create selection model for sync
            self._selection_model = QItemSelectionModel(model, self)
            for s, tgt in signals.items():
                getattr(self._model, s).connect(getattr(self, tgt))
        self.invalidate(set_of_books_changed=True)

    def model(self) -> BooksModel | None:
        '''Return the model.'''
        return self._model

    def selectionModel(self) -> QItemSelectionModel:
        '''Return the selection model (required for AlternateViews integration).'''
        return self._selection_model

    def _model_data_changed(self, top_left, bottom_right, roles):
        '''Handle model data changes.'''
        self.update_viewport()

    def _model_rows_changed(self, parent, first, last):
        '''Handle model row changes.'''
        self.invalidate(set_of_books_changed=True)

    def _model_reset(self):
        '''Handle model reset.'''
        self.invalidate(set_of_books_changed=True)

    def dbref(self) -> Cache:
        '''Return the current database.'''
        if m := self.model():
            return m.db.new_api
        return self.gui.current_db.new_api

    def book_id_from_row(self, row: int) -> int | None:
        '''Return the book id at this row.'''
        with suppress(Exception):
            return self.bookcase.row_to_book_id[row]
        return None

    def row_from_book_id(self, book_id: int) -> int | None:
        '''Return the book id at this row.'''
        return self.bookcase.book_id_to_row_map.get(book_id)

    def event(self, ev: QEvent) -> bool:
        match ev.type():
            case QEvent.Type.Resize:
                super().event(ev)
                s = self.viewport().size()
                s.setWidth(s.width() - self.verticalScrollBar().size().width())
                self.viewport().resize(s)
                if self.layout_constraints.width != (new_width := self._get_available_width()):
                    self.layout_constraints = self.layout_constraints._replace(width=new_width)
                    self.invalidate()
                return True
        return super().event(ev)

    def _update_scrollbar_ranges(self):
        '''Update scrollbar ranges based on the current shelf layouts.'''
        total_height = self.bookcase.max_possible_height
        viewport_height = self.viewport().height()
        self.verticalScrollBar().setRange(0, max(0, total_height - viewport_height))
        self.verticalScrollBar().setPageStep(viewport_height)
        self.verticalScrollBar().setSingleStep(self.layout_constraints.step_height)
        self._update_ram_cache_size()

    def _get_available_width(self):
        '''Get the maximum available width for the shelf layouts.'''
        return self.viewport().rect().width() - (2 * self.layout_constraints.side_margin)

    def invalidate(self, set_of_books_changed=True):
        self.bookcase.invalidate(
            self.layout_constraints, model=self.model() if set_of_books_changed else None,
            group_field_name=self._grouping_mode)
        self._update_scrollbar_ranges()
        self.update_viewport()

    def on_shelf_layout_done(self, books: CaseItem, shelf: CaseItem) -> None:
        if self.view_is_visible():
            if self.bookcase.layout_finished:
                self._update_scrollbar_ranges()
            y = books.start_y
            height = books.height + shelf.height
            r = self.viewport().rect()
            r.moveTop(self.verticalScrollBar().value())
            if self.bookcase.layout_finished or r.intersects(QRect(r.left(), y, r.width(), height)):
                self.update_viewport()

    def _update_ram_cache_size(self):
        viewport_height = self.viewport().height()
        lc = self.layout_constraints
        shelves_per_screen = max(1, viewport_height / (lc.step_height))
        books_per_shelf = self._get_available_width() / lc.min_spine_width
        lm = gprefs['bookshelf_cache_size_multiple'] * books_per_shelf * shelves_per_screen
        self.cover_cache.set_ram_limit(max(0, int(lm)))

    # Paint and Drawing methods

    def shown(self):
        '''Called when this view becomes active.'''
        self.bookcase.ensure_worker()

    def update_viewport(self):
        '''Update viewport only if the bookshelf view is visible.'''
        if not self.view_is_visible():
            return
        self.viewport().update()

    def paintEvent(self, ev: QPaintEvent):
        '''Paint the bookshelf view.'''
        if not self.view_is_visible():
            return
        self.bookcase.ensure_worker()

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        # Get visible area
        scroll_y = self.verticalScrollBar().value()
        viewport_rect = self.viewport().rect()
        visible_rect = viewport_rect.translated(0, scroll_y)
        hovered_item: ShelfItem | None = None
        hovered_id = self._hovered.book_id if self._hovered.is_valid() else -1
        for shelf in self.bookcase.iter_shelves_from_ypos(scroll_y):
            if shelf.start_y > visible_rect.bottom():
                break
            if shelf.is_shelf:
                self._draw_shelf(painter, shelf, scroll_y, visible_rect.width())
                continue

            # Draw books and inline dividers on it
            for item in shelf.items:
                if item.is_divider:
                    self._draw_inline_divider(painter, item, scroll_y)
                    continue

                if item.book_id == hovered_id:
                    # This is the hovered book - it draw later
                    # Position cover at spine position - left edge aligned with spine left edge
                    # The cover replaces the spine, so left edge stays at original spine position
                    self._hovered.base_x_pos = item.start_x
                    self._hovered.base_y_pos = shelf.start_y
                    hovered_item = item
                else:
                    # Draw a book spine at this position
                    self._draw_spine(painter, item, scroll_y)

        # Draw the hover cover of the hovered book
        if hovered_item is not None:
            self._draw_hover_cover(painter, self._hovered, scroll_y, hovered_item)

    def _draw_shelf(self, painter: QPainter, shelf: ShelfItem, scroll_y: int, width: int):
        '''Draw the shelf background at the given y position.'''

        # Shelf surface (where books sit)
        shelf_rect = QRect(0, shelf.start_y, width, self.layout_constraints.shelf_height)
        shelf_rect.translate(0, -scroll_y)

        # Create gradient for shelf surface (horizontal gradient for wood grain effect)
        gradient = QLinearGradient(
            QPointF(shelf_rect.left(), shelf_rect.top()),
            QPointF(shelf_rect.width(), shelf_rect.top()),
        )
        gradient.setColorAt(0, self.SHELF_COLOR_START)
        gradient.setColorAt(0.5, self.SHELF_COLOR_END.lighter(105))
        gradient.setColorAt(1, self.SHELF_COLOR_START)

        # Draw shelf surface
        painter.fillRect(shelf_rect, QBrush(gradient))

        # Draw shelf front edge (3D effect - darker shadow)
        edge_rect = QRect(
            shelf_rect.left(),
            shelf_rect.top(),
            shelf_rect.width(),
            3,
        )
        painter.fillRect(edge_rect, self.SHELF_COLOR_END.darker(130))

        # Draw shelf back edge (lighter highlight for 3D depth)
        back_edge_rect = QRect(
            shelf_rect.left(),
            shelf_rect.top() + self.layout_constraints.shelf_height - 2,
            shelf_rect.width(),
            2,
        )
        painter.fillRect(back_edge_rect, self.SHELF_COLOR_START.lighter(110))

        # Draw subtle wood grain lines
        painter.setPen(QPen(self.SHELF_COLOR_END.darker(110), 1))
        for i in range(0, shelf_rect.width(), 20):
            line_pos = shelf_rect.top() + self.layout_constraints.shelf_height // 2
            painter.drawLine(
                shelf_rect.left() + i,
                line_pos,
                shelf_rect.left() + i + 10,
                line_pos,
            )

    def _draw_selection_highlight(self, painter: QPainter, spine_rect: QRect):
        '''Draw the selection highlight.'''
        painter.save()
        painter.setPen(self.SELECTION_HIGHLIGHT_COLOR)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(1.0)
        painter.drawRect(spine_rect.adjusted(1, 1, -1, -1))
        painter.restore()

    def _draw_statue_indicator(self, painter: QPainter, spine_rect: QRect, book_id: int, mi: Metadata=None) -> bool:
        '''Draw reading statue indicator.'''
        statue_color = self.render_color_indicator(book_id, mi)
        if isinstance(statue_color, QColor) and statue_color.isValid():
            painter.save()
            painter.setOpacity(1.0)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            dot_radius = 4
            dot_x = spine_rect.x() + spine_rect.width() // 2
            dot_y = spine_rect.y() + spine_rect.height() - dot_radius - 10
            painter.setBrush(QBrush(statue_color))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
            painter.drawEllipse(QPoint(dot_x, dot_y), dot_radius, dot_radius)
            painter.restore()
            return True
        return False

    def _get_sized_text(self, text: str, max_width: int, start: float, stop: float) -> tuple[str, QFont, QRect]:
        '''Return a text, a QFont and a QRect that fit into the max_width.'''
        font = QFont()
        for minus in range(round(start - stop) * 2):
            minus = minus / 2
            font.setPointSizeF(start - minus)
            fm = QFontMetrics(font)
            size = fm.boundingRect(text)
            offset = min(0, size.top() // 2)
            size.adjust(offset, 0, 0, 0)
            if size.width() <= max_width:
                break
        size.adjust(0, 0, offset - min(0, size.left()), 0)
        rslt = fm.elidedText(text, Qt.TextElideMode.ElideRight, max_width)
        return rslt, font, size

    def _draw_inline_divider(self, painter: QPainter, divider: ShelfItem, scroll_y: int):
        '''Draw an inline group divider with it group name write vertically and a gradient line.'''
        lc = self.layout_constraints
        rect = divider.rect(lc).translated(0, -scroll_y)
        divider_rect = QRect(
            -rect.height() // 2,
            -rect.width() // 2,
            rect.height(),
            rect.width(),
        )

        def rotate():
            painter.translate(rect.left() + rect.width() // 2, rect.top() + rect.height() // 2)
            painter.rotate(-90)

        # Bottom margin
        text_rect = divider_rect.adjusted(8, 0, 0, 0)
        elided_text, font, sized_rect = self._get_sized_text(divider.group_name, text_rect.width(), 12, 8)
        font.setBold(True)

        # Calculate line dimensions
        line_rect = text_rect.adjusted(sized_rect.width(), 0, 0, 0)
        overflow = (line_rect.height() - self.DIVIDER_LINE_WIDTH) // 2
        line_rect.adjust(0, overflow, 0, -overflow)

        # Draw vertical gradient line if long enough
        if line_rect.width() > 8:
            painter.save()
            rotate()
            gradient = QLinearGradient(
                QPointF(line_rect.left(), line_rect.left()),
                QPointF(line_rect.left() + line_rect.width(), line_rect.left()),
            )
            gradient.setColorAt(0, self.DIVIDER_GRADIENT_LINE_1)
            gradient.setColorAt(0.5, self.DIVIDER_GRADIENT_LINE_2)
            gradient.setColorAt(1, self.DIVIDER_GRADIENT_LINE_1)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRect(line_rect)
            painter.restore()

        painter.save()
        rotate()
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)
        painter.restore()

    def default_cover_pixmap(self) -> PixmapWithDominantColor:
        lc = self.layout_constraints
        return default_cover_pixmap(lc.hover_expanded_width, lc.spine_height)

    def _draw_spine(self, painter: QPainter, spine: ShelfItem, scroll_y: int):
        '''Draw a book spine.'''
        thumbnail = self.cover_cache.thumbnail_as_pixmap(spine.book_id)
        if thumbnail is None:  # not yet rendered
            return
        lc = self.layout_constraints
        if thumbnail.isNull():
            thumbnail = self.default_cover_pixmap()
        mi = self.dbref().get_proxy_metadata(spine.book_id)

        # Determine if selected
        is_selected = False

        # Get cover color
        spine_color = thumbnail.dominant_color
        if not spine_color.isValid():
            spine_color = self.default_cover_pixmap().dominant_color
        if is_selected:
            spine_color = spine_color.lighter(120)

        spine_rect = spine.rect(lc).translated(0, -scroll_y)

        # Draw spine background with gradient (darker edges, lighter center)
        self._draw_spine_background(painter, spine_rect, spine_color)

        # Draw cover thumbnail overlay
        if self._enable_thumbnail:
            self._draw_thumbnail_overlay(painter, spine_rect, thumbnail)

        # Draw reading statue indicator at bottom
        has_indicator = self._draw_statue_indicator(painter, spine_rect, spine.book_id, mi)

        # Draw title (rotated vertically)
        title = self.render_template_title(spine.book_id, mi)
        self._draw_spine_title(painter, spine_rect, spine_color, title, has_indicator)

        # Draw selection highlight around the spine
        if is_selected:
            self._draw_selection_highlight(painter, spine_rect)

    def _draw_spine_background(self, painter: QPainter, rect: QRect, spine_color: QColor):
        '''Draw spine background with gradient (darker edges, lighter center).'''
        painter.save()
        painter.setOpacity(1.0)
        gradient = QLinearGradient(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.width(), rect.top()),
        )
        gradient.setColorAt(0, spine_color.darker(115))
        gradient.setColorAt(0.5, spine_color)
        gradient.setColorAt(1, spine_color.darker(115))
        painter.fillRect(rect, QBrush(gradient))

        # Add subtle vertical gradient for depth
        vertical_gradient = QLinearGradient(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.left(), rect.height()),
        )
        vertical_gradient.setColorAt(0, QColor(255, 255, 255, 20))  # Slight highlight at top
        vertical_gradient.setColorAt(1, QColor(0, 0, 0, 30))  # Slight shadow at bottom
        painter.fillRect(rect, QBrush(vertical_gradient))
        painter.restore()

    def _draw_spine_title(self, painter: QPainter, rect: QRect, spine_color: QColor, title: str, has_indicator=False):
        '''Draw vertically the title on the spine.'''
        if not title:
            return
        painter.save()
        painter.translate(rect.left() + rect.width() // 2, rect.top() + rect.height() // 2)
        painter.rotate(-90)

        # Determine text color based on spine background brightness
        text_color = self._get_contrasting_text_color(spine_color)
        painter.setPen(text_color)

        text_rect = QRect(
            -rect.height() // 2,
            -rect.width() // 2,
            rect.height(),
            rect.width(),
        )
        # leave space for statue indicator and a margin with top of the spine
        text_rect.adjust(
            22 if has_indicator else 6,
            0,
            -4 if has_indicator else -6,
            0,
        )
        elided_text, font, _rect = self._get_sized_text(title, text_rect.width(), 12, 8)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided_text)
        painter.restore()

    def _draw_thumbnail_overlay(self, painter: QPainter, rect: QRect, thumbnail):
        '''Draw cover thumbnail overlay on spine.'''
        # Draw with opacity
        painter.save()
        painter.setOpacity(0.3)  # 30% opacity
        painter.drawPixmap(rect, thumbnail)
        painter.restore()

    def _draw_hover_cover(self, painter: QPainter, hovered: HoveredCover, scroll_y: int, book: ShelfItem):
        '''Draw the hover cover popup.

        The cover replaces the spine when hovered, appearing at the same position
        with full spine height (150px) and smooth fade-in animation.
        '''
        if not hovered.is_valid():
            return

        is_selected = hovered.row in self._selected_rows or hovered.row == self._current_row
        cover_rect = hovered.rect(self.layout_constraints)
        cover_rect.translate(0, -scroll_y)

        if self._enable_shadow:
            # Draw shadow with blur effect (like JSX mock: 6px 6px 18px rgba(0,0,0,0.45))
            # Qt doesn't have native blur, so we'll use a darker shadow
            rect = cover_rect.translated(6, 6)
            shadow_blur = 3
            # Draw multiple shadow layers for blur effect
            for i in range(shadow_blur):
                alpha = int(115 * (1 - i / shadow_blur))  # 0.45 opacity = ~115 alpha
                shadow_color = QColor(0, 0, 0, alpha)
                shadow_layer = rect.translated(i, i)
                painter.fillRect(shadow_layer, shadow_color)

        # Draw the dominant cover color as background to not fade-in from white
        if hovered.dominant_color is not None:
            painter.fillRect(cover_rect, hovered.dominant_color)
        # Draw cover with smooth fade-in opacity transition
        painter.save()
        painter.setOpacity(hovered.opacity)
        painter.drawPixmap(cover_rect, hovered.pixmap)
        painter.restore()

        # Add subtle gradient overlay (like JSX mock: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%))
        painter.save()
        overlay_gradient = QLinearGradient(
            QPointF(cover_rect.left(), cover_rect.top()),
            QPointF(cover_rect.width(), cover_rect.height()),
        )
        overlay_gradient.setColorAt(0, QColor(255, 255, 255, 31))  # 0.12 opacity = ~31 alpha
        overlay_gradient.setColorAt(0.5, QColor(255, 255, 255, 0))
        overlay_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(cover_rect, QBrush(overlay_gradient))
        painter.restore()

        # Draw reading statue indicator at same position that for the spine
        spine_rect = hovered.spine_rect()
        spine_rect.translate(0, -scroll_y)
        self._draw_statue_indicator(painter, spine_rect, hovered.book_id)

        if is_selected:
            # Draw selection highlight around the hovered cover
            self._draw_selection_highlight(painter, cover_rect)

    # Cover integration methods

    def _update_hover_fade(self):
        '''Update hover cover fade-in animation and shift progress.'''
        self._hovered.update()
        self.update_viewport()
        if not self._hovered.start_time:
            self._hover_fade_timer.stop()

    def _load_hover_cover(self):
        '''Load the cover and scale it for hover popup.'''
        try:
            book_id = self._hovered.book_id
            height_modifier = self._hovered.shelf_item.reduce_height_by
            cover_img = self.dbref().cover(book_id, as_image=True)
            if cover_img is None or cover_img.isNull():
                cover_pixmap = self.default_cover_pixmap()
                self._hovered.dominant_color = cover_pixmap.dominant_color
            else:
                _, cover_img = resize_to_fit(cover_img, self.layout_constraints.hover_expanded_width, self.layout_constraints.spine_height)
                cover_pixmap = QPixmap.fromImage(cover_img)
                thumb = self.cover_cache.thumbnail_as_pixmap(book_id)
                if thumb is not None and not thumb.isNull():
                    self._hovered.dominant_color = thumb.dominant_color
                else:
                    self._hovered.dominant_color = self.default_cover_pixmap().dominant_color

            self._hovered.pixmap = cover_pixmap
            self._hovered.spine_width = spine_width = self._hovered.shelf_item.width
            self._hovered.spine_height = spine_height = self.layout_constraints.spine_height
            self._hovered.height_modifier = height_modifier
            self._hovered.width = spine_width  # ensure that the animation start at the spine width
            self._hovered.height = spine_height  # ensure that the animation start at the spine height
            self._hovered.width_max = cover_pixmap.width()
            self._hovered.height_end = cover_pixmap.height()

            if self._hovered.FADE_TIME <= 0:
                # Fade-in animation is disable
                self._hovered.progress = 1.0
                self._hovered.opacity = 1.0
                self._hovered.shift = 1.0
                self._hovered.height = self._hovered.height_end
                self._hovered.width = max(self._hovered.width_max, self._hovered.spine_width)
            else:
                # Start timer for smooth fade-in animation
                self._hovered.start_time = time()
                if not self._hover_fade_timer.isActive():
                    self._hover_fade_timer.start(16)  # ~60fps updates

            # Trigger immediate repaint to show the cover
            self.update_viewport()
        except Exception:
            import traceback
            traceback.print_exc()
            self._hovered = HoveredCover()

    def _delayed_hover_load(self):
        '''
        Load the buffered row only after a short delay.

        When the mouse move, several rows are request but many of them are probably not desired
        since their are on the path of the cursor but are not the one on which the cusor end it path.
        This can lead to load too many and useless cover, which impact the performance.
        '''
        if self._hover_buffer_time:
            # Test if is too early to load a new hovered cover
            # 20ms of delay, unoticable but avoid the loading of unrelevant covers
            if elapsed_time(self._hover_buffer_time) < 20:
                return

        # Avoid concurrent load of the same cover
        if self._hovered.row == self._hover_buffer_row:
            self._hover_buffer_timer.stop()
            return

        # Delay passed, start load new hover cover
        self._hover_fade_timer.stop()
        self._hovered = HoveredCover()

        # Load hover cover if hovering over a book
        if self._hover_buffer_row >= 0:
            new_book_id = self.book_id_from_row(self._hover_buffer_row)
            if new_book_id != self._hovered.book_id and new_book_id is not None:
                if si := self.bookcase.book_id_to_item_map.get(new_book_id):
                    self._hovered.row = self._hover_buffer_row
                    self._hovered.book_id = new_book_id
                    self._hovered.shelf_item = si
                    self._load_hover_cover()

        self._hover_buffer_time = None
        self._hover_buffer_timer.stop()
        self.update_viewport()

    def _get_contrasting_text_color(self, background_color: QColor):
        '''
        Calculate text color based on background brightness for optimal contrast.

        :param background_color: QColor of the spine background
        :return: QColor for text
        '''
        if not background_color or not background_color.isValid():
            return self.TEXT_COLOR

        # Get RGB values
        r = background_color.red()
        g = background_color.green()
        b = background_color.blue()

        # Calculate relative luminance
        def normalize(value):
            val = value / 255.0
            if val <= 0.03928:
                return val / 12.92
            else:
                return ((val + 0.055) / 1.055) ** 2.4

        r_norm = normalize(r)
        g_norm = normalize(g)
        b_norm = normalize(b)

        luminance = 0.2126 * r_norm + 0.7152 * g_norm + 0.0722 * b_norm

        # Yellow/gold colors need darker text at lower luminance
        is_yellow_gold = (r > 180 and g > 150 and b < 150)

        if is_yellow_gold:
            if luminance > 0.35:
                return self.TEXT_COLOR_DARK
            else:
                return self.TEXT_COLOR
        elif luminance > 0.5:
            return self.TEXT_COLOR_DARK
        else:
            return self.TEXT_COLOR

    # Sort interface methods (required for SortByAction integration)

    def sort_by_named_field(self, field: str, order: bool | Qt.SortOrder, reset=True):
        '''Sort by a named field.'''
        if isinstance(order, Qt.SortOrder):
            order = order == Qt.SortOrder.AscendingOrder
        if m := self.model():
            m.sort_by_named_field(field, order, reset)
            self.update_viewport()

    def reverse_sort(self):
        '''Reverse the current sort order.'''
        if m := self.model():
            try:
                sort_col, order = m.sorted_on
            except (TypeError, AttributeError):
                sort_col, order = 'date', True
            self.sort_by_named_field(sort_col, not order)

    def resort(self):
        '''Re-apply the current sort.'''
        if m := self.model():
            m.resort(reset=True)
            self.update_viewport()

    def intelligent_sort(self, field: str, ascending: bool | Qt.SortOrder):
        '''Smart sort that toggles if already sorted on that field.'''
        if isinstance(ascending, Qt.SortOrder):
            ascending = ascending == Qt.SortOrder.AscendingOrder
        if m := self.model():
            pname = 'previous_sort_order_' + self.__class__.__name__
            previous = gprefs.get(pname, {})
            try:
                current_field = m.sorted_on[0]
            except (TypeError, AttributeError):
                current_field = None

            if field == current_field or field not in previous:
                self.sort_by_named_field(field, ascending)
                previous[field] = ascending
                gprefs[pname] = previous
            else:
                previous[current_field] = m.sorted_on[1] if hasattr(m, 'sorted_on') else True
                gprefs[pname] = previous
                self.sort_by_named_field(field, previous.get(field, True))

    def multisort(self, fields: Iterable[str], reset=True, only_if_different=False):
        '''Sort on multiple columns.'''
        if not len(fields):
            return

        # Delegate to model's multisort capability
        # This is a simplified version - full implementation would match BooksView
        for field, ascending in reversed(fields):
            if field in self.dbref().field_metadata.keys():
                self.sort_by_named_field(field, ascending, reset=reset)
                reset = False  # Only reset on first sort

    # Selection methods (required for AlternateViews integration)

    def set_current_row(self, row: int):
        '''Set the current row.'''
        if not self._selection_model:
            return
        if (m := self.model()) and 0 <= row < m.rowCount(QModelIndex()):
            self._current_row = row
            index = m.index(row, 0)
            if index.isValid():
                self._selection_model.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.update_viewport()
            # Scroll to make row visible
            self._scroll_to_row(row)

    def select_rows(self, rows: Iterable[int], using_ids=False):
        '''Select the specified rows.

        Args:
            rows: List of row indices or book IDs
            using_ids: If True, rows contains book IDs; if False, rows contains row indices
        '''
        m = self.model()
        if not self._selection_model or not m:
            return

        # Convert book IDs to row indices if needed
        if using_ids:
            row_indices = []
            for book_id in rows:
                row = m.db.data.id_to_index(book_id)
                if row >= 0:
                    row_indices.append(row)
            rows = row_indices

        self._selected_rows = set(rows)
        if rows:
            self._current_row = min(rows)
            # Update selection model
            selection = QItemSelection()
            for row in rows:
                index = m.index(row, 0)
                if index.isValid():
                    selection.select(index, index)
            self._selection_model.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            # Set current index
            if self._current_row >= 0:
                current_index = m.index(self._current_row, 0)
                if current_index.isValid():
                    self._selection_model.setCurrentIndex(current_index, QItemSelectionModel.SelectionFlag.NoUpdate)
        else:
            self._current_row = -1
        self.update_viewport()

    def _scroll_to_row(self, row: int) -> None:
        '''Scroll to make the specified row visible.'''
        si = self.bookcase.book_id_to_item_map.get(self.book_id_from_row(row))
        if si is not None:
            scroll_y = si.case_start_y - self.viewport().rect().height() // 2
            self.verticalScrollBar().setValue(scroll_y)
            self.update_viewport()

    # Database methods

    def set_database(self, newdb, stage=0):
        '''Set the database.'''
        if stage == 0:
            self._grouping_mode = newdb.new_api.pref('bookshelf_grouping_mode', '')
            if self._grouping_mode == 'none':  # old stored value
                self._grouping_mode = ''

            # Clear caches when database changes
            self.template_inited = False
            self.cover_cache.set_database(newdb)
            self.invalidate(set_of_books_changed=True)
            self.bookcase.clear_spine_width_cache()

    def set_context_menu(self, menu: QMenu):
        '''Set the context menu.'''
        self.context_menu = menu

    def contextMenuEvent(self, ev: QContextMenuEvent):
        '''Handle context menu events.'''
        # Create menu with grouping options
        m = QMenu(self)

        # Add grouping submenu
        grouping_menu = m.addMenu(_('Group by'))
        fm = self.gui.current_db.new_api.field_metadata

        def add(field: str, name: str) -> None:
            action = grouping_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(self._grouping_mode == field)
            action.triggered.connect(partial(self._set_grouping_mode, field))
        add('', _('Ungrouped'))
        grouping_menu.addSeparator()
        for k in sorted(GROUPINGS, key=lambda k: numeric_sort_key(fm[k]['name'])):
            add(k, fm[k]['name'])
        # Add standard context menu items if available
        if cm := self.context_menu:
            m.addSeparator()
            for action in cm.actions():
                m.addAction(action)

        m.popup(ev.globalPos())
        ev.accept()

    def _set_grouping_mode(self, mode: str):
        '''Set the grouping mode and refresh display.'''
        if mode != self._grouping_mode:
            self._grouping_mode = mode
            self.dbref().set_pref('bookshelf_grouping_mode', mode)
            self.invalidate()

    def get_selected_ids(self) -> list[int]:
        '''Get selected book IDs.'''
        return [self.book_id_from_row(r) for r in self._selected_rows]

    def current_book_state(self) -> int:
        '''Get current book state for restoration.'''
        if self._current_row >= 0 and self.model():
            return self.book_id_from_row(self._current_row)
        return 0

    def restore_current_book_state(self, state: int):
        '''Restore current book state.'''
        m = self.model()
        if not state or not m:
            return
        book_id = state
        row = m.db.data.id_to_index(book_id)
        self.set_current_row(row)
        self.select_rows([row])

    def marked_changed(self, old_marked: set[int], current_marked: set[int]):
        '''Handle marked books changes.'''
        # Refresh display if marked books changed
        self.update_viewport()

    def indices_for_merge(self, resolved=True):
        '''Get indices for merge operations.'''
        m = self.model()
        if not m:
            return []
        return [m.index(row, 0) for row in self._selected_rows]

    # Mouse and keyboard events

    def viewportEvent(self, ev: QEvent) -> bool:
        '''Handle viewport events - this is where mouse events on QAbstractScrollArea go.'''
        match ev.type():
            case QEvent.Type.MouseButtonPress:
                if self._handle_mouse_press(ev):
                    return True
            case QEvent.Type.MouseButtonDblClick:
                if self._handle_mouse_double_click(ev):
                    return True
            case QEvent.Type.MouseMove:
                self._handle_mouse_move(ev)
            case QEvent.Type.Leave:
                self._handle_mouse_leave(ev)
        return super().viewportEvent(ev)

    def _handle_mouse_move(self, ev: QEvent):
        '''Handle mouse move events for hover detection.'''
        self.bookcase.ensure_worker()
        pos = ev.pos()
        row = self._book_row_at_position(pos.x(), pos.y())
        if row != self._hovered.row:
            # Hover changed
            self._hover_buffer_row = row
            self._hover_buffer_time = time()
            if not self._hover_buffer_timer.isActive():
                self._hover_buffer_timer.start(10)

    def _handle_mouse_press(self, ev: QEvent) -> bool:
        '''Handle mouse press events on the viewport.'''
        self.bookcase.ensure_worker()
        # Get position in viewport coordinates
        pos = ev.pos()
        m = self.model()
        if not m:
            return False

        # Find which book was clicked (pass viewport coordinates, method will handle scroll)
        row = self._book_row_at_position(pos.x(), pos.y())
        if row >= 0:
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                # Toggle selection
                if row in self._selected_rows:
                    self._selected_rows.discard(row)
                    if self._selection_model:
                        index = m.index(row, 0)
                        if index.isValid():
                            self._selection_model.select(index, QItemSelectionModel.SelectionFlag.Deselect)
                else:
                    self._selected_rows.add(row)
                    self._current_row = row
                    if self._selection_model:
                        index = m.index(row, 0)
                        if index.isValid():
                            self._selection_model.select(index, QItemSelectionModel.SelectionFlag.Select)
                            self._selection_model.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                # Range selection
                if self._current_row >= 0:
                    start = min(self._current_row, row)
                    end = max(self._current_row, row)
                    self._selected_rows = set(range(start, end + 1))
                else:
                    self._selected_rows = {row}
                self._current_row = row
                # Update selection model
                if self._selection_model:
                    selection = QItemSelection()
                    for r in self._selected_rows:
                        idx = m.index(r, 0)
                        if idx.isValid():
                            selection.select(idx, idx)
                    self._selection_model.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                    current_index = m.index(self._current_row, 0)
                    if current_index.isValid():
                        self._selection_model.setCurrentIndex(current_index, QItemSelectionModel.SelectionFlag.NoUpdate)
            else:
                # Single selection
                self._selected_rows = {row}
                self._current_row = row
                # Update selection model
                if self._selection_model:
                    index = m.index(row, 0)
                    if index.isValid():
                        self._selection_model.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                        self._selection_model.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)

            # Sync selection with main library view
            self._sync_selection_to_main_view()

            self.update_viewport()
            ev.accept()
            return True

        # No book was clicked
        return False

    def _handle_mouse_double_click(self, ev: QEvent) -> bool:
        '''Handle mouse double-click events on the viewport.'''
        self.bookcase.ensure_worker()
        pos = ev.pos()
        row = self._book_row_at_position(pos.x(), pos.y())
        if row >= 0:
            # Set as current row first
            self._current_row = row
            # Open the book
            book_id = self.book_id_from_row(row)
            self.gui.iactions['View'].view_triggered(book_id)
            return True
        return False

    def _handle_mouse_leave(self, ev: QEvent):
        '''Handle mouse leave events on the viewport.'''
        self.bookcase.ensure_worker()
        # Clear hover when mouse leaves viewport
        self._hover_fade_timer.stop()
        self._hover_buffer_timer.stop()
        self._hovered = HoveredCover()
        self.update_viewport()

    def _main_current_changed(self, current, previous):
        '''Handle current row change from main library view.'''
        m = self.model()
        if self._syncing_from_main or not m:
            return

        if current.isValid():
            row = current.row()
            if 0 <= row < m.rowCount(QModelIndex()):
                self._syncing_from_main = True
                self.set_current_row(row)
                self._syncing_from_main = False
        else:
            self._syncing_from_main = True
            self._current_row = -1
            self.update_viewport()
            self._syncing_from_main = False

    def _main_selection_changed(self, selected, deselected):
        '''Handle selection change from main library view.'''
        if self._syncing_from_main:
            return

        library_view = self.gui.library_view
        if not library_view:
            return

        # Get selected rows from main view
        selected_indexes = library_view.selectionModel().selectedIndexes()
        rows = {idx.row() for idx in selected_indexes if idx.isValid()}

        self._syncing_from_main = True
        self.select_rows(list(rows), using_ids=False)
        self._syncing_from_main = False

    def _sync_selection_to_main_view(self):
        '''Sync selection with the main library view.'''
        if self._syncing_from_main or not self.gui:
            return

        library_view = self.gui.library_view
        if self._current_row >= 0 and self.model():
            # Get book ID from current row
            book_id = self.book_id_from_row(self._current_row)
            # Select in library view
            library_view.select_rows([book_id], using_ids=True)

    def _book_id_at_position(self, x: int, y: int) -> int:
        scroll_y = self.verticalScrollBar().value()
        content_y = y + scroll_y

        if self._hovered.is_valid() and self._hovered.rect(self.layout_constraints).contains(x, content_y):
            return self.bookcase.row_to_book_id[self._hovered.row]
        x -= self.layout_constraints.side_margin
        if (shelf := self.bookcase.shelf_with_ypos(content_y)) is not None:
            if (item := shelf.book_or_divider_at_xpos(x)) is not None and not item.is_divider:
                return item.book_id
        return -1

    def _book_row_at_position(self, x: int, y: int) -> int:
        '''
        Find which book is at the given position. x, y are in viewport coordinates.
        '''
        book_id = self._book_id_at_position(x, y)
        if book_id > 0:
            if (row := self.row_from_book_id(book_id)) is not None:
                return row
        return -1

    def indexAt(self, pos) -> QModelIndex:
        '''Return the model index at the given position (required for drag/drop).
        pos is a QPoint in viewport coordinates.'''
        row = self._book_row_at_position(pos.x(), pos.y())
        if row >= 0 and (m := self.model()):
            return m.index(row, 0)
        return QModelIndex()

    def currentIndex(self) -> QModelIndex:
        '''Return the current model index (required for drag/drop).'''
        if self._current_row >= 0 and (m := self.model()):
            return m.index(self._current_row, 0)
        return QModelIndex()

    # setup_dnd_interface
    # handled in viewportEvent()
    def handle_mouse_move_event(self, ev: QEvent):
        pass

    def handle_mouse_press_event(self, ev: QEvent):
        pass

    def handle_mouse_release_event(self, ev: QEvent):
        pass
