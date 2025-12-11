#!/usr/bin/env python
# License: GPLv3
# Copyright: Andy C <achuongdev@gmail.com>, un_pogaz <un.pogaz@gmail.com>, Kovid Goyal <kovid@kovidgoyal.net>


import hashlib
import math
import os
from collections import defaultdict
from collections.abc import Callable, Iterable
from contextlib import suppress
from datetime import datetime
from functools import partial
from io import BytesIO
from queue import LifoQueue
from threading import Thread
from time import time
from typing import Any, NamedTuple

from PIL import Image
from qt.core import (
    QAbstractScrollArea,
    QApplication,
    QBrush,
    QColor,
    QContextMenuEvent,
    QEvent,
    QFont,
    QFontMetrics,
    QItemSelection,
    QItemSelectionModel,
    QLinearGradient,
    QMenu,
    QModelIndex,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QPoint,
    QPointF,
    QRect,
    QResizeEvent,
    Qt,
    QTimer,
    pyqtSignal,
    qBlue,
    qGreen,
    qRed,
)

from calibre.db.cache import Cache
from calibre.ebooks.metadata import rating_to_stars
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import gprefs, resolve_bookshelf_color
from calibre.gui2.library.alternate_views import setup_dnd_interface
from calibre.gui2.library.caches import ThumbnailCache
from calibre.gui2.library.models import BooksModel
from calibre.gui2.momentum_scroll import MomentumScrollMixin
from calibre.utils import join_with_timeout
from calibre.utils.date import is_date_undefined
from calibre.utils.icu import numeric_sort_key
from calibre.utils.img import convert_PIL_image_to_pixmap

DEFAULT_SPINE_COLOR = QColor('#8B4513')  # Brown, will be recalculated later
DEFAULT_COVER = Image.open(I('default_cover.png'))
TEMPLATE_ERROR_COLOR = QColor('#9C27B0')
TEMPLATE_ERROR = _('TEMPLATE ERROR')
CACHE_FORMAT = 'PPM'


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
        estimated_pages = max(50, size_bytes // 1500)
        # Cap at reasonable max
        return min(estimated_pages, 2000) / 2000.
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

def extract_dominant_color(image: Image) -> QColor:
    '''
    Extract the dominant color from an image.
    '''
    if not image:
        return None

    # Resize for performance and color accuracy
    image.thumbnail((100, 100))

    # Convert to RGB if needed
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # Extract dominant color using improved algorithm
    # Use less aggressive quantization
    # Quantize to 32 levels per channel
    color_counts = defaultdict(int)
    pixels = image.getdata()

    for pixel in pixels:
        r, g, b = pixel
        # Quantize to 32 levels per channel
        # Preserve color variety while grouping similar colors
        r_q = (r // 8) * 8
        g_q = (g // 8) * 8
        b_q = (b // 8) * 8
        color_counts[(r_q, g_q, b_q)] += 1

    if not color_counts:
        return None

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
        for (r2, g2, b2), count in sorted_colors[1:5]:  # Check top 5 alternatives
            max_val2 = max(r2, g2, b2)
            min_val2 = min(r2, g2, b2)
            sat2 = (max_val2 - min_val2) / max_val2 if max_val2 > 0 else 0
            # Use if more saturated and reasonably frequent
            if sat2 > 0.3 and count > len(pixels) * 0.05:  # At least 5% of pixels
                dominant_color = (r2, g2, b2)
                break

    return QColor(dominant_color[0], dominant_color[1], dominant_color[2])


def generate_spine_thumbnail(image: Image, width: int, height: int) -> Image:
    '''
    Generate a thumbnail for display on the spine. Returns a PIL.Image.
    '''
    if not image:
        return None

    # Scale the image
    image.thumbnail((image.width, height))
    # Crops the image
    image = image.crop((0, 0, width, height))
    # Convert to RGB to sanitize the data
    if image.mode != 'RGB':
        image = image.convert('RGB')
    return image

# }}}


# Groupings functions {{{

def _group_sort_key(unknown: str, val: str) -> tuple[bool, str]:
    # Put the unknown/default value at the end
    return val == unknown, numeric_sort_key(val)


Groups = list[tuple[str, list[int]]]


def _group_books(
    rows: list[int], model: BooksModel, field: str, unknown: str, getter: Callable[[Any], str],
    key=None, reverse: bool = False
) -> Groups:
    cache = model.db.new_api
    idfunc = model.db.id
    try:
        field_obj = cache.fields[field]
    except KeyError:
        return [(unknown, rows)]
    ans = defaultdict(list)
    with cache.safe_read_lock:
        for row in rows:
            try:
                book_id = idfunc(row)
                val = getter(cache._fast_field_for(field_obj, book_id))
            except Exception:
                val = unknown
            ans[val].append(row)
    return sorted(ans.items(), reverse=reverse, key=key or (lambda x: _group_sort_key(unknown, x[0])))


def _group_books_for_string(rows: list[int], model: BooksModel, field: str, unknown: str) -> Groups:
    '''
    Group books for a string field. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books(rows, model, field, unknown, lambda x: x or unknown)


def _group_books_for_list(rows: list[int], model: BooksModel, field: str, unknown: str) -> Groups:
    '''
    Group books for a list field, use only the first value. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books(rows, model, field, unknown, lambda x: (x or (unknown,))[0])


def _group_books_for_datetime(rows: list[int], model: BooksModel, field: str, unknown: str, formatter: Callable[[datetime], str]) -> Groups:
    '''
    Group books for a datetime field, formatter to convert to string. Returns list of (group_name, row_indices) tuples.
    '''
    def getter(x: datetime) -> str:
        return unknown if is_date_undefined(x) else formatter(x)
    return _group_books(rows, model, field, unknown, getter)


def group_books_by_author(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by author. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_list(rows, model, 'authors', _('No Author'))


def group_books_by_publisher(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by publisher. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_string(rows, model, 'publisher', _('No Publisher'))


def group_books_by_language(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by language. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_list(rows, model, 'languages', _('No Language'))


def group_books_by_series(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by series name. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_string(rows, model, 'series', _('No Series'))


def group_books_by_genre(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by first tag (genre). Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_list(rows, model, 'tags', _('No Tags'))


def group_books_by_pubdate(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by publication decade. Returns list of (group_name, row_indices) tuples.
    '''
    def formatter(datetime):
        # Group by decade (e.g., 2020-2029 -> "2020s")
        decade = (datetime.year // 10) * 10
        return f'{decade}s'
    return _group_books_for_datetime(rows, model, 'pubdate', _('Unknown Date'), formatter)


def group_books_by_timestamp(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by month addition. Returns list of (group_name, row_indices) tuples.
    '''
    def formatter(datetime):
        # Group by month (e.g. "2020/05")
        return f'{datetime.year}/{datetime.month:02}'
    return _group_books_for_datetime(rows, model, 'timestamp', _('Unknown Date'), formatter)


def group_books_by_rating(rows: list[int], model: BooksModel) -> Groups:
    '''
    Group books by rating (star rating). Returns list of (group_name, row_indices) tuples.
    '''
    unknown = _('Unrated')
    unknown_sort = rating_to_stars(10) + 'z'
    def skey(name):
        if name == unknown:
            return unknown_sort
        return name
    return _group_books(rows, model, 'rating', unknown, lambda x: rating_to_stars(x) if x else unknown, key=skey, reverse=True)


GROUPINGS = {
    'authors': group_books_by_author,
    'series': group_books_by_series,
    'tags': group_books_by_genre,
    'publisher': group_books_by_publisher,
    'pubdate': group_books_by_pubdate,
    'timestamp': group_books_by_timestamp,
    'rating': group_books_by_rating,
    'languages': group_books_by_language,
}


def group_books(rows: list[int], model: BooksModel, grouping_mode: str) -> Groups:
    '''
    Group books according to the specified grouping mode.
    Returns list of (group_name, row_indices) tuples.
    '''
    if func := GROUPINGS.get(grouping_mode):
        return func(rows, model)
    # No grouping - return single group with all rows
    return [('', rows)]

# }}}


# recalculate DEFAULT_SPINE_COLOR from the DEFAULT_COVER
DEFAULT_SPINE_COLOR = extract_dominant_color(DEFAULT_COVER.copy())


class CoverTuple(NamedTuple):
    book_id: int
    has_cover: bool
    cache_valid: bool
    cdata: Image
    timestamp: int


class ShelfTuple(NamedTuple):
    items: list['SpineTuple | DividerTuple']
    rows: set[int]
    book_ids: set[int]
    start_x: int
    start_y: int
    width_spines: int
    width_total: int


class ShelfItemTuple(NamedTuple):
    '''intermediate type for build ShelfTuple'''
    spine: bool = None
    divider: bool = None
    pos_x: int = None
    width: int = None
    row: int = None
    book_id: int = None
    group_name: str = None
    is_star: bool = None


class SpineTuple(NamedTuple):
    start_x: int
    start_y: int
    width: int
    row: int
    book_id: int
    shelf: ShelfTuple


class DividerTuple(NamedTuple):
    start_x: int
    start_y: int
    width: int
    group_name: str
    is_star: bool


class HoveredCover:
    '''Simple class to store the data related to the current hovered cover.'''

    OPACITY_START = 0.3
    FADE_TIME = 200  # Duration of the animation, in milliseconds

    def __init__(self):
        self.row = -1  # Currently hovered book row
        self.book_id = -1  # Currently hovered book id
        self.pixmap: QPixmap = None  # Scaled cover for hover popup
        self.progress = 0.0  # Animation progress (0.0 to 1.0)
        self.opacity = self.OPACITY_START  # Current opacity (0.3 to 1.0)
        self.shift = 0.0  # Current state of the shift animation (0.0 to 1.0)
        self.width = -1  # Current width
        self.height = -1  # Current height
        self.width_max = -1  # Maximum width
        self.height_end = -1  # Final height
        self.height_modifier = -1  # Height modifier
        self.base_x_pos = 0  # Base x position
        self.base_y_pos = 0  # Base y position
        self.spine_width = -1  # Spine width of this book
        self.spine_height = -1  # Spine height of this book
        self.dominant_color = DEFAULT_SPINE_COLOR  # Dominant color of this cover
        self.start_time = None  # Start time of fade-in animation

    def is_valid(self) -> bool:
        '''Test if the HoveredCover is valid.'''
        return bool(self.row >= 0) and self.has_pixmap()

    def has_pixmap(self) -> bool:
        '''Test if contain a valid pixmap.'''
        return bool(self.pixmap) and not self.pixmap.isNull()

    def is_row(self, row: int) -> bool:
        '''Test if the given row is the one of the hovered cover.'''
        return self.is_valid() and row == self.row

    def rect(self) -> QRect:
        '''Return the current QRect of the hover popup.'''
        offset_y = self.spine_height - self.height
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

    update_cover = pyqtSignal()
    files_dropped = pyqtSignal(object)
    books_dropped = pyqtSignal(object)

    # Dimensions
    SPINE_HEIGHT = 150
    SPINE_WIDTH_MIN = 15  # Minimum for very short books
    SPINE_WIDTH_MAX = 60  # Maximum for very long books
    SPINE_WIDTH_DEFAULT = 40  # Default for error or fix width
    SHELF_HEIGHT = 20  # Height of a shelf
    SHELF_GAP = 20  # Gap space between shelves
    SHELF_CONTENT_HEIGHT = SPINE_HEIGHT + SHELF_HEIGHT  # Height of a shelf and it content
    THUMBNAIL_WIDTH = 10  # Thumbnail size for spine
    HOVER_EXPANDED_WIDTH = 110  # Max expanded width on hover
    DIVIDER_WIDTH = 30  # Width of divider element
    DIVIDER_LINE_WIDTH = 2  # Width of the gradient line in divider
    ITEMS_GAP = 2  # Gap space between the row items

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

    def __init__(self, parent):
        super().__init__(parent)
        from calibre.gui2.ui import get_gui
        self.gui = get_gui()
        self._model: BooksModel = None
        self.context_menu: QMenu = None

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

        # Selection tracking
        self._selected_rows: set[int] = set()
        self._current_row = -1
        self._selection_model: QItemSelectionModel = None
        self._syncing_from_main = False  # Flag to prevent feedback loops
        self._current_shelf_layouts: list[ShelfTuple] = []

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

        # Up the version number if anything changes in how images are stored in the cache.
        self.thumbnail_cache = ThumbnailCache(
            name='bookshelf-thumbnail-cache',
            max_size=gprefs['bookshelf_view_cache_size'],
            thumbnail_size=(self.THUMBNAIL_WIDTH, self.SPINE_HEIGHT),
            version=1,
        )
        self.fetch_thread = None
        self.render_queue = LifoQueue()
        self.update_cover.connect(self.update_viewport)
        self.color_cache: dict[int, QColor] = {}  # Cache for cover colors (book_id -> QColor)

        # Configuration
        self._grouping_mode = 'none'
        self.refresh_settings()

        # Cover template caching
        self.template_inited = False
        self.template_cache = {}
        self.template_title_error_reported = False
        self.template_statue_error_reported = False
        self.template_pages_error_reported = False
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
        self.template_title_error_reported = False
        self.template_statue_error_reported = False
        self.template_pages_error_reported = False
        self.rules_color = db_pref('bookshelf_color_rules') or []
        self.template_title = db_pref('bookshelf_title_template') or ''
        self.size_template = (db_pref('bookshelf_spine_size_template') or '').strip()
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
        self._hover_shift = gprefs['bookshelf_hover_shift']
        HoveredCover.FADE_TIME = gprefs['bookshelf_fade_time']
        self.thumbnail_cache.set_size(gprefs['bookshelf_view_cache_size'])
        self.set_color()

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
        return self.gui.bookshelf_view_button.is_visible

    def shutdown(self):
        self.thumbnail_cache.shutdown()
        self.render_queue.put(None)
        self.thumbnail_cache.shutdown()

    def setModel(self, model):
        '''Set the model for this view.'''
        if self._model:
            # Disconnect old model signals if needed
            pass
        self._model = model
        if model:
            # Create selection model for sync
            self._selection_model = QItemSelectionModel(model, self)
            model.dataChanged.connect(self._model_data_changed)
            model.rowsInserted.connect(self._model_rows_changed)
            model.rowsRemoved.connect(self._model_rows_changed)
            model.modelReset.connect(self._model_reset)
        else:
            self._selection_model = None

    def model(self) -> BooksModel:
        '''Return the model.'''
        return self._model

    def selectionModel(self) -> QItemSelectionModel:
        '''Return the selection model (required for AlternateViews integration).'''
        return self._selection_model

    def _model_data_changed(self, top_left, bottom_right, roles):
        '''Handle model data changes.'''
        self._update_current_shelf_layouts()

    def _model_rows_changed(self, parent, first, last):
        '''Handle model row changes.'''
        self._update_current_shelf_layouts()

    def _model_reset(self):
        '''Handle model reset.'''
        self._update_current_shelf_layouts()

    def dbref(self) -> Cache:
        '''Return the current database.'''
        return self._model.db.new_api

    def book_id_from_row(self, row: int) -> int:
        '''Return the book id at this row.'''
        index = self._model.index(row, 0)
        if not index.isValid():
            return None
        return self._model.id(index)

    def resizeEvent(self, ev: QResizeEvent):
        '''Handle resize events.'''
        super().resizeEvent(ev)
        self._update_current_shelf_layouts()

    def _get_left_margin(self):
        '''Get left margin for the shelf layouts.'''
        # Remove left margin when books are grouped (replaced by divider)
        return 2 if self._grouping_mode != 'none' else 12

    def _get_available_width(self):
        '''Get the maximum available width for the shelf layouts.'''
        # Reserve space for hover expansion
        right_margin = self.HOVER_EXPANDED_WIDTH + 10
        return self.viewport().rect().width() - self._get_left_margin() - right_margin

    def _get_flattened_items(self) -> list[tuple[str, int]]:
        '''Get a list (row, group_name) tuples of the items.'''
        # Get all rows and group them, then flatten for inline rendering
        row_count = self._model.rowCount(QModelIndex())
        if row_count == 0:
            return []

        all_rows = list(range(row_count))
        groups = group_books(all_rows, self._model, self._grouping_mode)

        # Flatten groups for inline rendering
        flattened_items = []
        for group_name, group_rows in groups:
            for row in group_rows:
                flattened_items.append((row, group_name))

        return flattened_items

    def _get_shelf_layouts(self) -> list[ShelfTuple]:
        '''
        Get the shelf layouts showing which books go on which shelf.
        '''
        # Calculate shelf layouts
        return self._calculate_shelf_layouts(self._get_flattened_items())

    def _calculate_shelf_layouts(self, flattened_items: list[tuple[str, int]]) -> list[ShelfTuple]:
        '''
        Calculate which books go on which shelf, accounting for:
        1. Hover expansion space (reserve space on right for expansion)
        2. Left-aligned books with proper margins
        '''
        if not flattened_items:
            return []

        left_margin = self._get_left_margin()
        available_width = self._get_available_width()
        viewport_width = self.viewport().rect().width()

        def iter_shelf_items(shelf: ShelfTuple, items: Iterable[ShelfItemTuple]):
            for item in items:
                if item.spine:
                    yield SpineTuple(
                        start_x=shelf.start_x + item.pos_x,
                        start_y=shelf.start_y,
                        width=item.width,
                        row=item.row,
                        book_id=item.book_id,
                        shelf=shelf,
                    )
                if item.divider:
                    yield DividerTuple(
                        start_x=shelf.start_x + item.pos_x,
                        start_y=shelf.start_y,
                        width=item.width,
                        group_name=item.group_name,
                        is_star=item.is_star,
                    )

        def is_spine(x: ShelfItemTuple):
            return x.spine

        def create_shelf(start_x, start_y, items: Iterable[ShelfItemTuple]):
            shelf = ShelfTuple(
                items=[],
                rows={x.row for x in filter(is_spine, items)},
                book_ids={x.book_id for x in filter(is_spine, items)},
                width_spines=sum(x.width for x in filter(is_spine, items)),
                width_total=sum(x.width for x in items) + (self.SHELF_GAP * len(items)-1),
                start_x=start_x,
                start_y=start_y,
            )
            shelf.items.extend(iter_shelf_items(shelf, items))
            return shelf

        def get_start_x(shelf_width):
            if not self._enable_centered:
                return left_margin
            margin = viewport_width - shelf_width - 20
            return max(0, margin // 2)

        shelves = []
        current_shelf = []
        shelf_width = 0
        last_group_name = None
        shelf_y = self.SHELF_GAP
        for row, group_name in flattened_items:
            # Account for divider when group changes
            offset = 0
            divider = None
            if self._grouping_mode != 'none' and group_name != last_group_name:
                divider = ShelfItemTuple(
                    divider=True, pos_x=shelf_width + offset, width=self.DIVIDER_WIDTH, group_name=group_name, is_star=self._grouping_mode=='rating',
                )
                offset = divider.width + self.ITEMS_GAP

            # Get spine width
            book_id = self.book_id_from_row(row)
            spine_width = self._get_spine_width(book_id)
            spine = ShelfItemTuple(
                spine=True, pos_x=shelf_width + offset, width=spine_width, row=row, book_id=book_id,
            )
            item_width = offset + spine.width + self.ITEMS_GAP

            # Check for shelf overflow
            if shelf_width + item_width > available_width and current_shelf:
                # Finish current shelf - left-aligned with margin
                shelves.append(create_shelf(
                    start_x=get_start_x(shelf_width),
                    start_y=shelf_y,
                    items=current_shelf,
                ))
                # Start new shelf
                current_shelf = []
                shelf_y += self.SHELF_CONTENT_HEIGHT + self.SHELF_GAP
                # Reset for new shelf
                shelf_width = 0
                item_width = 0
                if group_name:
                    divider = ShelfItemTuple(
                        divider=True, pos_x=shelf_width, width=self.DIVIDER_WIDTH, group_name=group_name, is_star=self._grouping_mode=='rating',
                    )
                    item_width = divider.width + self.ITEMS_GAP
                data = spine._asdict()
                data['pos_x'] = item_width
                spine = ShelfItemTuple(**data)
                item_width += spine.width + self.ITEMS_GAP

            # Add item to current shelf
            if divider:
                current_shelf.append(divider)
            current_shelf.append(spine)
            shelf_width += item_width
            last_group_name = group_name

        # Add final shelf
        if current_shelf:
            shelves.append(create_shelf(
                start_x=get_start_x(shelf_width),
                start_y=shelf_y,
                items=current_shelf,
            ))
        return shelves

    def _update_current_shelf_layouts(self):
        '''Update current shelf layouts.'''
        if not self.view_is_visible():
            return
        self._current_shelf_layouts = self._get_shelf_layouts()
        self._update_scrollbar_ranges()
        self.update_viewport()

    def _update_scrollbar_ranges(self):
        '''Update scrollbar ranges based on the current shelf layouts.'''
        if not self.view_is_visible():
            return
        if not self._current_shelf_layouts:
            self.verticalScrollBar().setRange(0, 0)
            return

        # Add the shelf spacing to have the real height
        total_height = self._current_shelf_layouts[-1].start_y + self.SHELF_CONTENT_HEIGHT
        viewport_height = self.viewport().height()
        max_scroll = max(0, total_height - viewport_height)
        self.verticalScrollBar().setRange(0, max_scroll)
        self.verticalScrollBar().setPageStep(viewport_height)

    # Paint and Drawing methods

    def shown(self):
        '''Called when this view becomes active.'''
        if self.fetch_thread is None:
            self.fetch_thread = Thread(target=self._fetch_thumbnails_cache)
            self.fetch_thread.daemon = True
            self.fetch_thread.start()
        self._update_current_shelf_layouts()

    def update_viewport(self):
        '''Update viewport only if the bookshelf view is visible.'''
        if not self.view_is_visible():
            return
        self.viewport().update()

    def paintEvent(self, ev: QPaintEvent):
        '''Paint the bookshelf view.'''
        if not self.view_is_visible():
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get visible area
        scroll_y = self.verticalScrollBar().value()
        viewport_rect = self.viewport().rect()
        visible_rect = viewport_rect.translated(0, scroll_y)

        if not self._current_shelf_layouts:
            self._update_current_shelf_layouts()

        for shelf in self._current_shelf_layouts:
            # Early exit if we've scrolled past the point
            if shelf.start_y > visible_rect.bottom():
                break

            # Check if shelf is visible
            if shelf.start_y + self.SHELF_CONTENT_HEIGHT < visible_rect.top() + 1:
                continue

            # Draw the shelf
            self._draw_shelf(painter, shelf, scroll_y, visible_rect.width())

            # Draw books and inline dividers on it
            offset_x = 0
            for item in shelf.items:
                if isinstance(item, DividerTuple):
                    self._draw_inline_divider(painter, item, scroll_y, offset_x)
                    continue

                if isinstance(item, SpineTuple):
                    # Determine if we should apply shift to this shelf
                    if self._hovered.is_row(item.row) and self._hover_shift:
                        offset_x = self._hovered.width - item.width

                    if self._hovered.is_row(item.row):
                        # This is the hovered book - it draw later
                        # Position cover at spine position - left edge aligned with spine left edge
                        # The cover replaces the spine, so left edge stays at original spine position
                        self._hovered.base_x_pos = item.start_x
                        self._hovered.base_y_pos = item.start_y
                    else:
                        # Draw a book spine at this position
                        self._draw_spine(painter, item, scroll_y, offset_x)

        # Draw the hover cover of the hovered book
        if self._hovered.is_valid():
            self._draw_hover_cover(painter, self._hovered, scroll_y)

    def _draw_shelf(self, painter: QPainter, shelf: ShelfTuple, scroll_y: int, width: int):
        '''Draw the shelf background at the given y position.'''

        # Shelf surface (where books sit)
        shelf_rect = QRect(
            0,
            shelf.start_y + self.SPINE_HEIGHT,
            width,
            self.SHELF_HEIGHT,
        )
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
            shelf_rect.top() + self.SHELF_HEIGHT - 2,
            shelf_rect.width(),
            2,
        )
        painter.fillRect(back_edge_rect, self.SHELF_COLOR_START.lighter(110))

        # Draw subtle wood grain lines
        painter.setPen(QPen(self.SHELF_COLOR_END.darker(110), 1))
        for i in range(0, shelf_rect.width(), 20):
            line_pos = shelf_rect.top() + self.SHELF_HEIGHT // 2
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

    def _draw_inline_divider(self, painter: QPainter, divider: DividerTuple, scroll_y: int, offset_x: int):
        '''Draw an inline group divider with it group name write vertically and a gradient line.'''
        rect = QRect(
            divider.start_x + offset_x,
            divider.start_y - scroll_y,
            divider.width,
            self.SPINE_HEIGHT,
        )
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

    def _draw_spine(self, painter: QPainter, spine: SpineTuple, scroll_y: int, offset_x: int):
        '''Draw a book spine.'''
        mi = self.dbref().get_proxy_metadata(spine.book_id)

        # Determine if selected
        is_selected = spine.row in self._selected_rows or spine.row == self._current_row

        # Get cover color
        spine_color = self._get_spine_color(spine.book_id)
        # Ensure we have a valid color
        if not spine_color or not spine_color.isValid():
            spine_color = DEFAULT_SPINE_COLOR

        if is_selected:
            spine_color = spine_color.lighter(120)

        height_mod = self._get_height_modifier(spine.book_id)
        spine_rect = QRect(
            spine.start_x + offset_x,
            spine.start_y - scroll_y,
            spine.width,
            self.SPINE_HEIGHT,
        )
        spine_rect.adjust(0, height_mod, 0, 0)

        # Draw spine background with gradient (darker edges, lighter center)
        self._draw_spine_background(painter, spine_rect, spine_color)

        # Draw cover thumbnail overlay
        if self._enable_thumbnail:
            self._draw_thumbnail_overlay(painter, spine_rect, spine.book_id)

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

    def _draw_thumbnail_overlay(self, painter: QPainter, rect: QRect, book_id: int):
        '''Draw cover thumbnail overlay on spine.'''
        thumbnail = self._get_spine_thumbnail(book_id)
        if not thumbnail or thumbnail.isNull():
            return

        # Draw with opacity
        painter.save()
        painter.setOpacity(0.3)  # 30% opacity
        rect = rect.translated(0, 0)
        rect.setWidth(thumbnail.width())
        painter.drawPixmap(rect, thumbnail)
        painter.restore()

    def _draw_hover_cover(self, painter: QPainter, hovered: HoveredCover, scroll_y: int):
        '''Draw the hover cover popup.

        The cover replaces the spine when hovered, appearing at the same position
        with full spine height (150px) and smooth fade-in animation.
        '''
        if not hovered.is_valid():
            return

        is_selected = hovered.row in self._selected_rows or hovered.row == self._current_row
        cover_rect = hovered.rect()
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
            has_cover, cdata, timestamp = self.dbref().cover_or_cache(book_id, 0, as_what='pil_image')

            if not has_cover or not cdata:
                cdata = DEFAULT_COVER.copy()

            # Scale to hover size - resize to the spine height or a reasonable max width
            height_modifier = self._get_height_modifier(book_id)
            cdata.thumbnail((self.HOVER_EXPANDED_WIDTH, self.SPINE_HEIGHT))

            self._hovered.pixmap = pixmap = convert_PIL_image_to_pixmap(cdata)
            self._hovered.dominant_color = extract_dominant_color(cdata) or DEFAULT_SPINE_COLOR
            self._hovered.spine_width = spine_width = self._get_spine_width(book_id)
            self._hovered.spine_height = spine_height = self.SPINE_HEIGHT
            self._hovered.height_modifier = height_modifier
            self._hovered.width = spine_width  # ensure that the animation start at the spine width
            self._hovered.height = spine_height  # ensure that the animation start at the spine height
            self._hovered.width_max = pixmap.width()
            self._hovered.height_end = pixmap.height()

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
            self._hovered.row = self._hover_buffer_row
            self._hovered.book_id = self.book_id_from_row(self._hover_buffer_row)
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

    def _get_spine_color(self, book_id: int) -> QColor:
        '''Get the spine color for a book from cache or by extraction.'''
        color = self.color_cache.get(book_id)
        if color and color.isValid():
            return color
        self.color_cache.pop(book_id, None)

        color = self._create_cover_color(book_id)

        if not color or not color.isValid():
            color = DEFAULT_SPINE_COLOR
        self.color_cache[book_id] = color
        return color

    def _get_spine_thumbnail(self, book_id: int) -> QPixmap:
        '''Get the spine thumbnail for a book from cache.'''
        cover_tuple = self._get_cached_thumbnail(book_id)
        if cover_tuple.cache_valid:
            return convert_PIL_image_to_pixmap(cover_tuple.cdata)
        if cover_tuple.cdata:
            self.render_queue.put(book_id)
        self.color_cache.pop(book_id, None)
        return None

    def _get_cached_thumbnail(self, book_id: int) -> CoverTuple:
        '''
        Fetches the cover from the cache if it exists, otherwise the cover.jpg stored in the library.

        Return a CoverTuple containing the following cover and cache data:

        book_id: The id of the book for which a cover is wanted.
        has_cover: True if the book has an associated cover image file.
        cdata: Cover data. Can be None (no cover data), or a rendered cover image.
        cache_valid: True if the cache has correct data, False if a cover exists
                     but isn't in the cache, None if the cache has data but the
                     cover has been deleted.
        timestamp: the cover file modtime if the cover came from the file system,
                   the timestamp in the cache if a valid cover is in the cache,
                   otherwise None.
        '''
        db = self.dbref()
        if db is None:
            return None
        tc = self.thumbnail_cache
        cdata, timestamp = tc[book_id]  # None, None if not cached.
        if timestamp is None:
            # Cover not in cache. Try to read the cover from the library.
            has_cover, cdata, timestamp = db.new_api.cover_or_cache(book_id, 0, as_what='pil_image')
            if has_cover:
                # There is a cover.jpg, already rendered as a pil_image
                cache_valid = False
            else:
                # No cover.jpg
                cache_valid = None
        else:
            # A cover is in the cache. Check whether it is up to date.
            # Note that if tcdata is not None then it is already a PIL image.
            has_cover, tcdata, timestamp = db.new_api.cover_or_cache(book_id, timestamp, as_what='pil_image')
            if has_cover:
                if tcdata is None:
                    # The cached cover is up-to-date
                    cache_valid = True
                    cdata = Image.open(BytesIO(cdata))
                else:
                    # The cached cover is stale
                    cache_valid = False
                    cdata = tcdata
        if has_cover and cdata is None:
            has_cover = False
            cache_valid = None
        return CoverTuple(book_id=book_id, has_cover=has_cover, cache_valid=cache_valid, cdata=cdata, timestamp=timestamp)

    def _fetch_thumbnails_cache(self):
        q = self.render_queue
        while True:
            book_id = q.get()
            if book_id is None:
                return

            cover_tuple = self._get_cached_thumbnail(book_id)
            if cover_tuple.cdata:
                self._create_thumbnail_cache(book_id, cover_tuple)

            self.update_cover.emit()
            q.task_done()

    def _create_cover_color(self, book_id: int):
        db = self.dbref()
        if db is None:
            return
        has_cover, cdata, timestamp = db.new_api.cover_or_cache(book_id, 0, as_what='pil_image')
        if has_cover and cdata:
            color = extract_dominant_color(cdata)
            if color and color.isValid():
                return color
        return None

    def _create_thumbnail_cache(self, book_id: int, cover_tuple: CoverTuple):
        '''Generate the thumbnail and cache it.'''
        thumb = generate_spine_thumbnail(cover_tuple.cdata, self.THUMBNAIL_WIDTH, self.SPINE_HEIGHT)
        if thumb:
            tc = self.thumbnail_cache
            try:
                with BytesIO() as buf:
                    thumb.save(buf, format=CACHE_FORMAT)
                    # use getbuffer() instead of getvalue() to avoid a copy
                    tc.insert(book_id, cover_tuple.timestamp, buf.getbuffer())
            except Exception:
                tc.invalidate((book_id,))
                self.color_cache.pop(book_id, None)
                import traceback
                traceback.print_exc()

    def _get_spine_width(self, book_id: int) -> int:
        '''Get the spine width for a book from cache or by generation.'''
        db = self.dbref()
        self.init_template(db)

        def frac(f: float):
            return self.SPINE_WIDTH_MIN + int(max(0, min(f, 1)) * (self.SPINE_WIDTH_MAX - self.SPINE_WIDTH_MIN))

        def choice(choice: float) -> int:
            choice = max(0, min(choice, 7))
            if choice <= 1:
                ans = self.SPINE_WIDTH_MIN + 3 * choice
            elif choice <= 2:
                ans = self.SPINE_WIDTH_MIN + 3 + 4 * (choice - 1)
            elif choice <= 3:
                ans = self.SPINE_WIDTH_MIN + 7 + 6 * (choice - 2)
            elif choice <= 4:
                ans = self.SPINE_WIDTH_MIN + 13 + 7 * (choice - 3)
            elif choice <= 5:
                ans = self.SPINE_WIDTH_MIN + 20 + 8 * (choice - 4)
            elif choice <= 6:
                ans = self.SPINE_WIDTH_MIN + 28 + 7 * (choice - 5)
            elif choice <= 7:
                ans = self.SPINE_WIDTH_MIN + 35 + 10 * (choice - 6)
            return min(ans, self.SPINE_WIDTH_MAX)

        match self.size_template:
            case '':
                return self.SPINE_WIDTH_DEFAULT
            case '{size}' | 'size':
                return frac(normalised_size(db.field_for('size', book_id, 0)))
            case '{random}' | 'random':
                return choice(book_id & 7)
            case _:
                with suppress(Exception):
                    if 0 <= (x := float(self.size_template)) <= 7:
                        return choice(x)
                with suppress(Exception):
                    mi = db.get_proxy_metadata(book_id)
                    rslt = mi.formatter.safe_format(self.template_pages, mi, TEMPLATE_ERROR, mi, template_cache=self.template_cache)
                    return choice(float(rslt))
        return self.SPINE_WIDTH_DEFAULT

    def _get_height_modifier(self, book_id: int) -> int:
        '''
        Return a pseudo random number, to change the height of the spine.
        Range: [-10, 10]
        '''
        if not self._enable_variable_height:
            return 0
        rslt = self._height_modifiers.get(book_id)
        if rslt:
            return rslt
        rslt = 10 - pseudo_random(book_id, 20)
        self._height_modifiers[book_id] = rslt
        return rslt

    # Sort interface methods (required for SortByAction integration)

    def sort_by_named_field(self, field: str, order: bool | Qt.SortOrder, reset=True):
        '''Sort by a named field.'''
        if isinstance(order, Qt.SortOrder):
            order = order == Qt.SortOrder.AscendingOrder
        self._model.sort_by_named_field(field, order, reset)
        self.update_viewport()

    def reverse_sort(self):
        '''Reverse the current sort order.'''
        m = self.model()
        try:
            sort_col, order = m.sorted_on
        except (TypeError, AttributeError):
            sort_col, order = 'date', True
        self.sort_by_named_field(sort_col, not order)

    def resort(self):
        '''Re-apply the current sort.'''
        self._model.resort(reset=True)
        self.update_viewport()

    def intelligent_sort(self, field: str, ascending: bool | Qt.SortOrder):
        '''Smart sort that toggles if already sorted on that field.'''
        if isinstance(ascending, Qt.SortOrder):
            ascending = ascending == Qt.SortOrder.AscendingOrder
        m = self.model()
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
        if 0 <= row < self._model.rowCount(QModelIndex()):
            self._current_row = row
            index = self._model.index(row, 0)
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
        if not self._selection_model:
            return

        # Convert book IDs to row indices if needed
        if using_ids:
            row_indices = []
            for book_id in rows:
                row = self._model.db.data.id_to_index(book_id)
                if row >= 0:
                    row_indices.append(row)
            rows = row_indices

        self._selected_rows = set(rows)
        if rows:
            self._current_row = min(rows)
            # Update selection model
            selection = QItemSelection()
            for row in rows:
                index = self._model.index(row, 0)
                if index.isValid():
                    selection.select(index, index)
            self._selection_model.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            # Set current index
            if self._current_row >= 0:
                current_index = self._model.index(self._current_row, 0)
                if current_index.isValid():
                    self._selection_model.setCurrentIndex(current_index, QItemSelectionModel.SelectionFlag.NoUpdate)
        else:
            self._current_row = -1
        self.update_viewport()

    def _scroll_to_row(self, row: int):
        '''Scroll to make the specified row visible.'''
        for shelf in self._current_shelf_layouts:
            if row in shelf.rows:
                scroll_y = shelf.start_y - self.viewport().rect().height() // 2
                self.verticalScrollBar().setValue(scroll_y)
        self.update_viewport()

    # Database methods

    def set_database(self, newdb, stage=0):
        '''Set the database.'''
        self._grouping_mode = newdb.new_api.pref('bookshelf_grouping_mode', 'none')
        if stage == 0:
            # Clear caches when database changes
            self.color_cache.clear()
            self.template_inited = False
            with suppress(AttributeError):
                self.model().db.new_api.remove_cover_cache(self.thumbnail_cache)
            newdb.new_api.add_cover_cache(self.thumbnail_cache)
            # This must be done here so the UUID in the cache is changed when libraries are switched.
            self.thumbnail_cache.set_database(newdb)
            try:
                # Use a timeout so that if, for some reason, the render thread
                # gets stuck, we don't deadlock, future covers won't get
                # rendered, but this is better than a deadlock
                join_with_timeout(self.render_queue)
            except RuntimeError:
                print('Cover rendering thread is stuck!')

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
        add('none', _('Ungrouped'))
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
        self._grouping_mode = mode
        self.dbref().set_pref('bookshelf_grouping_mode', mode)
        self._update_current_shelf_layouts()

    def get_selected_ids(self) -> list[int]:
        '''Get selected book IDs.'''
        return [self.book_id_from_row(r) for r in self._selected_rows]

    def current_book_state(self) -> int:
        '''Get current book state for restoration.'''
        if self._current_row >= 0 and self._model:
            return self.book_id_from_row(self._current_row)
        return None

    def restore_current_book_state(self, state: int):
        '''Restore current book state.'''
        if not state:
            return
        book_id = state
        row = self._model.db.data.id_to_index(book_id)
        self.set_current_row(row)
        self.select_rows([row])

    def marked_changed(self, old_marked: set[int], current_marked: set[int]):
        '''Handle marked books changes.'''
        # Refresh display if marked books changed
        self.update_viewport()

    def indices_for_merge(self, resolved=True):
        '''Get indices for merge operations.'''
        return [self._model.index(row, 0) for row in self._selected_rows]

    # Mouse and keyboard events

    def viewportEvent(self, ev: QEvent) -> bool:
        '''Handle viewport events - this is where mouse events on QAbstractScrollArea go.'''
        if ev.type() == QEvent.Type.MouseButtonPress:
            handled = self._handle_mouse_press(ev)
            if handled:
                return True
        elif ev.type() == QEvent.Type.MouseButtonDblClick:
            handled = self._handle_mouse_double_click(ev)
            if handled:
                return True
        elif ev.type() == QEvent.Type.MouseMove:
            self._handle_mouse_move(ev)
        elif ev.type() == QEvent.Type.Leave:
            self._handle_mouse_leave(ev)
        return super().viewportEvent(ev)

    def _handle_mouse_move(self, ev: QEvent):
        '''Handle mouse move events for hover detection.'''
        pos = ev.pos()
        row = self._book_at_position(pos.x(), pos.y())
        if row != self._hovered.row:
            # Hover changed
            self._hover_buffer_row = row
            self._hover_buffer_time = time()
            if not self._hover_buffer_timer.isActive():
                self._hover_buffer_timer.start(10)

    def _handle_mouse_press(self, ev: QEvent) -> bool:
        '''Handle mouse press events on the viewport.'''
        # Get position in viewport coordinates
        pos = ev.pos()

        # Find which book was clicked (pass viewport coordinates, method will handle scroll)
        row = self._book_at_position(pos.x(), pos.y())
        if row >= 0:
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                # Toggle selection
                if row in self._selected_rows:
                    self._selected_rows.discard(row)
                    if self._selection_model:
                        index = self._model.index(row, 0)
                        if index.isValid():
                            self._selection_model.select(index, QItemSelectionModel.SelectionFlag.Deselect)
                else:
                    self._selected_rows.add(row)
                    self._current_row = row
                    if self._selection_model:
                        index = self._model.index(row, 0)
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
                        idx = self._model.index(r, 0)
                        if idx.isValid():
                            selection.select(idx, idx)
                    self._selection_model.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                    current_index = self._model.index(self._current_row, 0)
                    if current_index.isValid():
                        self._selection_model.setCurrentIndex(current_index, QItemSelectionModel.SelectionFlag.NoUpdate)
            else:
                # Single selection
                self._selected_rows = {row}
                self._current_row = row
                # Update selection model
                if self._selection_model:
                    index = self._model.index(row, 0)
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
        pos = ev.pos()
        row = self._book_at_position(pos.x(), pos.y())
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
        # Clear hover when mouse leaves viewport
        self._hover_fade_timer.stop()
        self._hover_buffer_timer.stop()
        self._hovered = HoveredCover()
        self.update_viewport()

    def _main_current_changed(self, current, previous):
        '''Handle current row change from main library view.'''
        if self._syncing_from_main:
            return

        if current.isValid():
            row = current.row()
            if 0 <= row < self._model.rowCount(QModelIndex()):
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
        if self._current_row >= 0 and self._model:
            # Get book ID from current row
            book_id = self.book_id_from_row(self._current_row)
            # Select in library view
            library_view.select_rows([book_id], using_ids=True)

    def _book_at_position(self, x: int, y: int) -> int:
        '''
        Find which book is at the given position. x, y are in viewport coordinates.
        '''
        # Convert viewport coordinates to content coordinates
        scroll_y = self.verticalScrollBar().value()
        content_y = y + scroll_y

        if self._hovered.is_valid():
            if self._hovered.rect().contains(x, content_y):
                return self._hovered.row

        for shelf in self._current_shelf_layouts:
            if content_y < shelf.start_y:
                continue
            if shelf.start_y >= content_y + self.SPINE_HEIGHT:
                break
            for item in shelf.items:
                if not isinstance(item, SpineTuple):
                    continue
                spine_rect = QRect(item.start_x, item.start_y, item.width, self.SPINE_HEIGHT)
                if spine_rect.contains(x, content_y):
                    return item.row

        return -1

    def indexAt(self, pos) -> QModelIndex:
        '''Return the model index at the given position (required for drag/drop).
        pos is a QPoint in viewport coordinates.'''
        row = self._book_at_position(pos.x(), pos.y())
        if row >= 0 and self._model:
            return self._model.index(row, 0)
        return QModelIndex()

    def currentIndex(self) -> QModelIndex:
        '''Return the current model index (required for drag/drop).'''
        if self._current_row >= 0 and self._model:
            return self._model.index(self._current_row, 0)
        return QModelIndex()

    # setup_dnd_interface
    # handled in viewportEvent()
    def handle_mouse_move_event(self, ev: QEvent):
        pass

    def handle_mouse_press_event(self, ev: QEvent):
        pass

    def handle_mouse_release_event(self, ev: QEvent):
        pass
