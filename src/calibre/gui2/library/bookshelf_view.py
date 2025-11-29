#!/usr/bin/env python
# License: GPLv3
# Copyright: Andy C <achuongdev@gmail.com>, un_pogaz <un.pogaz@gmail.com>, Kovid Goyal <kovid@kovidgoyal.net>


import hashlib
from collections import defaultdict
from contextlib import suppress
from functools import partial
from io import BytesIO
from time import time

from PIL import Image
from qt.core import (
    QAbstractScrollArea,
    QApplication,
    QBrush,
    QBuffer,
    QByteArray,
    QColor,
    QEvent,
    QFont,
    QFontMetrics,
    QImage,
    QItemSelection,
    QItemSelectionModel,
    QLinearGradient,
    QMenu,
    QModelIndex,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPoint,
    QPointF,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
)

from calibre.constants import islinux
from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2 import gprefs
from calibre.gui2.library.alternate_views import setup_dnd_interface
from calibre.utils.date import is_date_undefined
from calibre.utils.icu import numeric_sort_key
from calibre.utils.img import convert_PIL_image_to_pixmap

DEFAULT_SPINE_COLOR = QColor('#8B4513')  # Brown, will be recalculated later
DEFAULT_COVER = QImage(I('default_cover.png'))
TEMPLATE_ERROR_COLOR = QColor('#9C27B0')
TEMPLATE_ERROR = _('TEMPLATE ERROR')


# Utility functions {{{

def get_reading_statue(book_id, db, mi=None):
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


def size_to_page_count(size_bytes):
    '''Estimate page count from file size.'''
    # Average ebook: ~1-2KB per page, so estimate pages from size
    if size_bytes and size_bytes > 0:
        # Estimate: ~1500 bytes per page (conservative)
        estimated_pages = max(50, int(size_bytes / 1500))
        # Cap at reasonable max
        return min(estimated_pages, 2000)
    return None


def get_random_page_count(book_id):
    # Use book_id to create a pseudo-random but consistent value per book
    # Range: 50-350 pages (covers tiers 3-5 for visual variety)
    val = str(book_id or 0).encode()
    hash_val = int(hashlib.md5(val).hexdigest()[:8], 16)
    # Map hash to 50-350 page range
    return 50 + (hash_val % 300)


def elapsed_time(ref_time):
    '''Get elapsed time, in milliseconds.'''
    return (time() - ref_time) * 1000


# }}}


# Cover functions {{{

def extract_dominant_color(image_data):
    '''
    Extract the dominant color from an image. Returns a QColor.
    '''
    if not image_data:
        return DEFAULT_SPINE_COLOR

    # Convert to PIL Image if needed
    image = None
    if isinstance(image_data, QPixmap):
        image_data = image_data.toImage()
    if isinstance(image_data, QImage):
        ba = QByteArray()
        buffer = QBuffer(ba)
        image_data.save(buffer, 'PNG')
        image_data = BytesIO(buffer.data())
    if isinstance(image_data, bytes):
        image_data = BytesIO(image_data)
    if isinstance(image_data, BytesIO):
        image_data = Image.open(image_data)

    if not isinstance(image_data, Image.Image):
        raise TypeError(f'Cannot extract dominant color from {type(image_data).__name__}')
    image = image_data

    if not image:
        return DEFAULT_SPINE_COLOR

    # Resize for performance and color accuracy
    image.thumbnail((100, 100), Image.Resampling.LANCZOS)

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
        return DEFAULT_SPINE_COLOR

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


def get_cover_color(book_id, db):
    '''
    Get the dominant color from a book's cover. Returns a QColor.
    '''
    color = None
    cover_data = db.new_api.cover(book_id)  # read bytes for performance in extract_dominant_color()
    if cover_data:
        color = extract_dominant_color(cover_data)

    if color and color.isValid():
        return color

    return DEFAULT_SPINE_COLOR


def generate_spine_thumbnail(cover_data, width, height):
    '''
    Generate a thumbnail for display on the spine. Returns a QPixmap or None.
    '''
    if not cover_data:
        return None

    # Convert to QImage
    qimg = None
    if isinstance(cover_data, Image.Image):
        cover_data = convert_PIL_image_to_pixmap(cover_data)
    if isinstance(cover_data, QPixmap):
        cover_data = cover_data.toImage()
    if isinstance(cover_data, bytes):
        cover_data = QImage()
        if not cover_data.loadFromData(cover_data):
            return None

    if not isinstance(cover_data, QImage):
        raise TypeError(f'Cannot generate thumbnail from {type(cover_data).__name__}')
    qimg = cover_data

    if qimg.isNull():
        return None

    # Maintain aspect ratio while scaling
    original_width = qimg.width()
    original_height = qimg.height()
    if original_height == 0:
        return None

    # Scale the image
    aspect_ratio = original_width / original_height
    target_height = height
    target_width = int(target_height * aspect_ratio)
    scaled = qimg.scaled(
        target_width, target_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    # Crops the image
    scaled = scaled.copy(QRect(0, 0, width, height))

    if scaled.isNull():
        return None

    return QPixmap.fromImage(scaled)

# }}}


# Groupings functions {{{

def _group_sort_key(unknown, val):
    # Put the unknown/default value at the end
    return (val == unknown, numeric_sort_key(val))


def _group_books_for_string(rows, model, field, unknown):
    '''
    Group books for a string field. Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)
    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[unknown].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.new_api.get_proxy_metadata(book_id)
            value = mi.get(field)

            if value:
                groups[value].append(row)
            else:
                groups[unknown].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[unknown].append(row)

    # Sort groups by name
    sorted_groups = list(groups.items())
    sorted_groups.sort(key=lambda x: _group_sort_key(unknown, x[0]))
    return sorted_groups


def _group_books_for_list(rows, model, field, unknown):
    '''
    Group books for a list field, use only the first value. Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)
    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[unknown].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.new_api.get_proxy_metadata(book_id)
            values = mi.get(field) or []

            if values:
                # Use first value
                value = values[0]
                groups[value].append(row)
            else:
                groups[unknown].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[unknown].append(row)

    # Sort groups by name
    sorted_groups = list(groups.items())
    sorted_groups.sort(key=lambda x: _group_sort_key(unknown, x[0]))
    return sorted_groups


def _group_books_for_datetime(rows, model, field, unknown, formatter):
    '''
    Group books for a datetime field, formatter to convert to string. Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)
    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[unknown].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.new_api.get_proxy_metadata(book_id)
            date = mi.get(field)

            if not is_date_undefined(date):
                groups[formatter(date)].append(row)
            else:
                groups[unknown].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[unknown].append(row)

    # Sort groups by name
    sorted_groups = list(groups.items())
    sorted_groups.sort(key=lambda x: _group_sort_key(unknown, x[0]))
    return sorted_groups


def group_books_by_author(rows, model):
    '''
    Group books by author. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_list(rows, model, 'authors', _('No Author'))


def group_books_by_publisher(rows, model):
    '''
    Group books by publisher. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_string(rows, model, 'publisher', _('No Publisher'))


def group_books_by_language(rows, model):
    '''
    Group books by language. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_list(rows, model, 'languages', _('No Language'))


def group_books_by_series(rows, model):
    '''
    Group books by series name. Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_string(rows, model, 'series', _('No Series'))


def group_books_by_genre(rows, model):
    '''
    Group books by first tag (genre). Returns list of (group_name, row_indices) tuples.
    '''
    return _group_books_for_list(rows, model, 'tags', _('No Genre'))


def group_books_by_pubdate(rows, model):
    '''
    Group books by publication decade. Returns list of (group_name, row_indices) tuples.
    '''
    def formatter(datetime):
        # Group by decade (e.g., 2020-2029 -> "2020s")
        decade = (datetime.year // 10) * 10
        return f'{decade}s'
    return _group_books_for_datetime(rows, model, 'pubdate', _('Unknown Date'), formatter)


def group_books_by_timestamp(rows, model):
    '''
    Group books by month addition. Returns list of (group_name, row_indices) tuples.
    '''
    def formatter(datetime):
        # Group by month (e.g. "2020/05")
        return f'{datetime.year}/{datetime.month:02}'
    return _group_books_for_datetime(rows, model, 'timestamp', _('Unknown Date'), formatter)


def group_books_by_rating(rows, model):
    '''
    Group books by rating (star rating). Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)
    unknown = _('No Rating')

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[unknown].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.new_api.get_proxy_metadata(book_id)
            rating = mi.get('rating')

            if rating and rating > 0:
                groups[rating_to_stars(rating)].append(row)
            else:
                groups[unknown].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[unknown].append(row)

    # Sort groups by rating (descending)
    def sort_key(group_name):
        if group_name == unknown:
            return (1, 0)  # Put unrated at end
        stars = len(group_name)  # Count star characters
        return (0, -stars)  # Negative for descending

    sorted_groups = list(groups.items())
    sorted_groups.sort(key=lambda x: sort_key(x[0]))
    return sorted_groups


def group_books(rows, model, grouping_mode):
    '''
    Group books according to the specified grouping mode.
    Returns list of (group_name, row_indices) tuples.
    '''
    mode = GROUPINGS.get(grouping_mode)
    if mode:
        func = mode.get('func')
        if func:
            return func(rows, model)
    # No grouping - return single group with all rows
    return [('', rows)]

# }}}


GROUPINGS = {
    'none': {'name': _('None'), 'func': None},
    '1': None,  # separator
    'author': {'name': _('Author'), 'func': group_books_by_author},
    'series': {'name': _('Series'), 'func': group_books_by_series},
    'genre': {'name': _('Genre'), 'func': group_books_by_genre},
    'publisher': {'name': _('Publisher'), 'func': group_books_by_publisher},
    'pubdate': {'name': _('Published'), 'func': group_books_by_pubdate},
    'timestamp': {'name': _('Date'), 'func': group_books_by_timestamp},
    'rating': {'name': _('Rating'), 'func': group_books_by_rating},
    'language': {'name': _('Language'), 'func': group_books_by_language},
}

# recalculate DEFAULT_SPINE_COLOR from the DEFAULT_COVER
DEFAULT_SPINE_COLOR = extract_dominant_color(DEFAULT_COVER)


class HoveredCover:
    '''Simple class to contain the data related to the current hovered cover.'''

    OPACITY_START = 0.3

    def __init__(self):
        self.row = -1  # Currently hovered book row
        self.book_id = -1  # Currently hovered book id
        self.pixmap = None  # Scaled cover for hover popup
        self.progress = 0.0  # Animation progress (0.0 to 1.0)
        self.opacity = self.OPACITY_START  # Current opacity (0.3 to 1.0)
        self.shift = 0.0  # Current state of the shift animation (0.0 to 1.0)
        self.width = -1  # Current width
        self.width_max = -1  # Maximum width
        self.height = -1  # Current height
        self.base_x_pos = 0  # Base x position
        self.base_y_pos = 0  # Base y position
        self.spine_width = -1  # Spine width of this book
        self.spine_height = -1  # Spine height of this book
        self.dominant_color = DEFAULT_SPINE_COLOR  # Dominant color of this cover
        self.start_time = None  # Start time of fade-in animation

    def is_valid(self):
        '''Test if the HoveredCover is valid.'''
        return bool(self.row >= 0) and self.has_pixmap()

    def has_pixmap(self):
        '''Test if contain a valid pixmap.'''
        return bool(self.pixmap) and not self.pixmap.isNull()

    def is_row(self, row):
        '''Test if the given row is the one of the hovered cover.'''
        return self.is_valid() and row == self.row

    def rect(self):
        '''Return the current QRect the hover popup.'''
        # Vertical offset of the hover cover
        # that is the difference between the spine and cover height
        offset_y = self.spine_height - self.height
        return QRect(self.base_x_pos, self.base_y_pos + offset_y, self.width, self.height)

    def spine_rect(self):
        '''Return the QRect the book spine.'''
        return QRect(self.base_x_pos, self.base_y_pos, self.spine_width, self.spine_height)


@setup_dnd_interface
class BookshelfView(QAbstractScrollArea):
    '''
    Enhanced bookshelf view displaying books as spines on shelves.

    This view provides an immersive browsing experience with sorting
    and grouping capabilities.
    '''

    files_dropped = pyqtSignal(object)
    books_dropped = pyqtSignal(object)

    # Dimensions
    SPINE_HEIGHT = 150
    SPINE_WIDTH_MIN = 15  # Minimum for very short books
    SPINE_WIDTH_MAX = 60  # Maximum for very long books
    SPINE_WIDTH_DEFAULT = 40  # Default for error or fix width
    SHELF_HEIGHT = 20  # Height of a shelf
    SHELF_GAP = 10  # Gap space between shelves
    SHELF_SPACING = SPINE_HEIGHT + SHELF_HEIGHT + SHELF_GAP  # Total height space between shelves
    THUMBNAIL_WIDTH = 10  # Thumbnail size for spine
    HOVER_EXPANDED_WIDTH = 110  # Max expanded width on hover
    DIVIDER_WIDTH = 30  # Width of divider element
    MARGIN_TOP = 10  # Top content margin of the view
    ITEMS_GAP = 2  # Gap space between the row items

    # Colors
    SHELF_COLOR_START = QColor('#4a3728')
    SHELF_COLOR_END = QColor('#3d2e20')
    TEXT_COLOR = QColor('#eee')
    TEXT_COLOR_DARK = QColor('#222')  # Dark text for light backgrounds
    SELECTION_HIGHLIGHT_COLOR = QColor('#ff0')
    DIVIDER_TEXT_COLOR = QColor('#b0b5c0')

    def __init__(self, parent):
        QAbstractScrollArea.__init__(self, parent)
        from calibre.gui2.ui import get_gui
        self.gui = get_gui()
        self._model = None
        self.context_menu = None
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self.setAutoFillBackground(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Ensure viewport receives mouse events
        self.viewport().setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_MouseTracking, True)

        # Initialize drag and drop
        # so we set the attributes manually
        self.drag_allowed = True
        self.drag_start_pos = None

        # Selection tracking
        self._selected_rows = set()
        self._current_row = -1
        self._selection_model = None
        self._syncing_from_main = False  # Flag to prevent feedback loops
        self._current_shelf_layouts = []

        # Set background on viewport
        viewport = self.viewport()
        viewport.setAutoFillBackground(True)

        # Cover loading and caching
        self._cover_colors = {}  # Cache for cover colors (book_id -> QColor)
        self._spine_thumbnails = {}  # Cache for spine thumbnails (book_id -> QPixmap)
        self._pages_widths = {}  # Cache for spine widths (int(pages) -> int(width))
        self._hovered = HoveredCover()  # Currently hovered book
        self._hover_fade_timer = QTimer(self)  # Timer for fade-in animation
        self._hover_fade_timer.setSingleShot(False)
        self._hover_fade_timer.timeout.connect(self._update_hover_fade)
        self._hover_buffer_timer = QTimer(self)  # Timer for buffer the hover animation
        self._hover_buffer_timer.setSingleShot(False)
        self._hover_buffer_timer.timeout.connect(self._delayed_hover_load)
        self._hover_last_row = -1
        self._hover_last_time = None

        # Grouping configuration
        self._grouping_mode = 'none'

        # Render options
        self._enable_shadow = gprefs['bs_shadow']
        self._enable_thumbnail = gprefs['bs_thumbnail']
        self._enable_centered = gprefs['bs_centered']
        self._fade_time = gprefs['bs_fade_time']
        self._hover_shift = gprefs['bs_hover_shift']

        # Cover template caching
        self.template_inited = False
        self.template_title_cache = {}
        self.template_statue_cache = {}
        self.template_pages_cache = {}
        self.template_title_error_reported = False
        self.template_statue_error_reported = False
        self.template_pages_error_reported = False
        self.template_title = ''
        self.template_statue = ''
        self.template_pages = ''
        self.pages_use_book_size = False
        self.template_title_is_empty = True
        self.template_statue_is_empty = True
        self.template_pages_is_empty = True

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

        self.template_title_cache = {}
        self.template_statue_cache = {}
        self.template_pages_cache = {}
        self.template_title_error_reported = False
        self.template_statue_error_reported = False
        self.template_pages_error_reported = False
        self.template_title = db_pref('bs_title_template') or ''
        self.template_statue = db_pref('bs_statue_template') or ''
        self.template_pages = db_pref('bs_pages_template') or ''
        self.pages_use_book_size = bool(db_pref('bs_use_book_size'))
        self.template_title_is_title = self.template_title == '{title}'
        self.template_title_is_empty = not self.template_title.strip()
        self.template_statue_is_empty = not self.template_statue.strip()
        self.template_pages_is_empty = not self.template_pages.strip()
        self.template_inited = True

    def render_template_title(self, book_id, mi=None):
        '''Return the pages title (str) generate for this book.'''
        self.init_template(self.dbref())
        if self.template_title_is_empty:
            return None
        if not mi:
            mi = self.dbref().get_proxy_metadata(book_id)
        if self.template_title_is_title:
            return mi.title
        title = mi.formatter.safe_format(self.template_title, mi, TEMPLATE_ERROR, mi, template_cache=self.template_title_cache)
        if title:
            return title
        return _('Unknown')

    def render_template_statue(self, book_id, mi=None):
        '''Return the statue indicator (QColor) generate for this book.'''
        self.init_template(self.dbref())
        if self.template_statue_is_empty:
            return None
        if not mi:
            mi = self.dbref().get_proxy_metadata(book_id)
        statue_color = mi.formatter.safe_format(self.template_statue, mi, TEMPLATE_ERROR, mi, template_cache=self.template_statue_cache)
        if statue_color.startswith(TEMPLATE_ERROR):
            print(statue_color)
            return TEMPLATE_ERROR_COLOR
        if statue_color:
            with suppress(Exception):
                statue_color = QColor(statue_color)
                if statue_color.isValid():
                    return statue_color
            return TEMPLATE_ERROR_COLOR
        return None

    def render_template_pages(self, book_id, mi=None):
        '''Return the pages count (int) generate for this book.'''
        self.init_template(self.dbref())
        if self.template_pages_is_empty:
            return None
        if not mi:
            mi = self.dbref().get_proxy_metadata(book_id)
        pages = mi.formatter.safe_format(self.template_pages, mi, TEMPLATE_ERROR, mi, template_cache=self.template_pages_cache)
        if pages.startswith(TEMPLATE_ERROR):
            print(pages)
            return -1
        if pages:
            with suppress(Exception):
                pages = int(pages)
                if pages >= 0:
                    return pages
            return -1
        return None

    # Settings methods

    def enableShadow(self, value):
        '''Set the enable state for render a shadow for hovered book.'''
        if value == self._enable_shadow:
            return
        self._enable_shadow = value
        self._update_viewport()

    def enableThumbnail(self, value):
        '''Set the enable state for render thumbnail on book spine.'''
        if value == self._enable_thumbnail:
            return
        self._enable_thumbnail = value
        self._update_viewport()

    def enableCentered(self, value):
        '''Set the enable state for render the books centered on the rows.'''
        if value == self._enable_centered:
            return
        self._enable_centered = value
        self.viewport().update()

    def enableHoverShift(self, value):
        '''Set if the hovered book shift the others on the row.'''
        if value == self._hover_shift:
            return
        self._hover_shift = value
        self.viewport().update()

    def setFadeTime(self, value):
        '''Set the fade-in time for hovered cover.'''
        value = max(0, value)
        if value == self._fade_time:
            return
        self._fade_time = value

    # Miscellaneous methods

    def is_bookshelf_browser_visible(self):
        '''Return if the bookshelf view is visible.'''
        return getattr(self.gui.layout_container.is_visible, 'bookshelf_browser')

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

        # Connect to main library view's selection model
        self._connect_to_main_view_selection()

        self._update_current_shelf_layouts()

    def selectionModel(self):
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

    def model(self):
        '''Return the model.'''
        return self._model

    def dbref(self):
        '''Return the current database.'''
        if not self._model:
            return None
        return self._model.db.new_api

    def book_id_from_row(self, row):
        '''Return the book id at this row.'''
        if not self._model:
            return None
        index = self._model.index(row, 0)
        if not index.isValid():
            return None
        return self._model.id(index)

    def resizeEvent(self, ev):
        '''Handle resize events.'''
        super().resizeEvent(ev)
        self._update_current_shelf_layouts()

    def _get_flattened_items(self):
        '''Get a list (row, group_name) tuples of the items.'''
        if not self._model:
            return []

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

    def _get_shelf_layouts(self):
        '''
        Get the shelf layouts showing which books go on which shelf.

        Returns a list of shelf dictionaries with:
        - 'items': list of (row, group_name, spine_width) tuples
        - 'start_x': starting x position (left-aligned with margin)
        - 'start_y': starting y position (top-aligned with margin)
        - 'start_row': first row on this shelf
        '''
        if not self._model:
            return []

        # Calculate shelf layouts
        return self._calculate_shelf_layouts(self._get_flattened_items(), self.viewport().rect())

    def _calculate_shelf_layouts(self, flattened_items, viewport):
        '''
        Calculate which books go on which shelf, accounting for:
        1. Hover expansion space (reserve space on right for expansion)
        2. Left-aligned books with proper margins

        Returns a list of shelf dictionaries with:
        - 'items': list of (row, group_name, spine_width) tuples
        - 'start_x': starting x position (left-aligned with margin)
        - 'start_y': starting y position (top-aligned with margin)
        - 'start_row': first row on this shelf
        '''
        if not flattened_items:
            return []

        shelves = []
        current_shelf = []
        shelf_width = 0
        shelf_start_row = 0
        last_group_name = None

        # Remove left margin when books are grouped (replaced by divider)
        left_margin = 2 if self._grouping_mode != 'none' else 12
        # Reserve space for hover expansion
        right_margin = self.HOVER_EXPANDED_WIDTH + 10
        available_width = viewport.width() - left_margin - right_margin

        def get_start_x(shelf_width):
            if not self._enable_centered:
                return left_margin
            margin = viewport.width() - shelf_width - 20
            return max(0, int(margin / 2))

        shelf_y = self.MARGIN_TOP
        for row, group_name in flattened_items:
            # Account for divider when group changes
            divider_width = 0
            if self._grouping_mode != 'none' and group_name != last_group_name:
                divider_width = self.DIVIDER_WIDTH + self.ITEMS_GAP

            # Get spine width
            book_id = self.book_id_from_row(row)
            spine_width = self._get_spine_width(book_id)

            item_width = divider_width + spine_width + self.ITEMS_GAP

            # Check for shelf overflow
            if shelf_width + item_width > available_width and current_shelf:
                # Finish current shelf - left-aligned with margin
                shelves.append({
                    'items': current_shelf,
                    'start_x': get_start_x(shelf_width),
                    'start_y': shelf_y,
                    'start_row': shelf_start_row,
                })
                # Start new shelf
                current_shelf = []
                shelf_width = 0
                shelf_start_row = row
                last_group_name = None  # Reset for new shelf
                shelf_y += self.SHELF_SPACING

            # Add item to current shelf
            current_shelf.append((row, group_name, spine_width))
            shelf_width += item_width
            last_group_name = group_name

        # Add final shelf
        if current_shelf:
            shelves.append({
                'items': current_shelf,
                'start_x': get_start_x(shelf_width),
                'start_y': shelf_y,
                'start_row': shelf_start_row,
            })
        return shelves

    def _update_current_shelf_layouts(self):
        '''Update current shelf layouts.'''
        if not self.is_bookshelf_browser_visible():
            return
        self._current_shelf_layouts = self._get_shelf_layouts()
        self._update_scrollbar_ranges()
        self._update_viewport()

    def _update_scrollbar_ranges(self):
        '''Update scrollbar ranges based on the current shelf layouts.'''
        if not self.is_bookshelf_browser_visible():
            return
        if not self._model:
            self.verticalScrollBar().setRange(0, 0)
            return
        if not self._current_shelf_layouts:
            self.verticalScrollBar().setRange(0, 0)
            return

        # Add the shelf spacing to have the real height
        total_height = self._current_shelf_layouts[-1]['start_y'] + self.SHELF_SPACING
        viewport_height = self.viewport().height()
        max_scroll = max(0, total_height - viewport_height)
        self.verticalScrollBar().setRange(0, max_scroll)
        self.verticalScrollBar().setPageStep(viewport_height)

    # Paint and Drawing methods

    def _update_viewport(self):
        '''Update viewport only if the bookshelf view is visible.'''
        if not self.is_bookshelf_browser_visible():
            return
        self.viewport().update()

    def paintEvent(self, ev):
        '''Paint the bookshelf view.'''
        if not self.is_bookshelf_browser_visible():
            return
        if not self._model:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get visible area
        scroll_y = self.verticalScrollBar().value()
        viewport_rect = self.viewport().rect()
        visible_rect = viewport_rect.translated(0, scroll_y)

        if not self._current_shelf_layouts:
            self._update_current_shelf_layouts()

        shelf_y = self.MARGIN_TOP + scroll_y
        for shelf_items in self._current_shelf_layouts:
            # Get starting x position for this shelf
            base_x_pos = shelf_items['start_x']
            base_y_pos = shelf_items['start_y']

            # Check if shelf is visible
            if base_y_pos + self.SHELF_SPACING >= visible_rect.top():
                # Draw the shelf
                self._draw_shelf(painter, shelf_y, visible_rect)

                # Draw books and inline dividers on it
                last_group_name = None
                for row, group_name, spine_width in shelf_items['items']:
                    # Draw inline divider when group changes
                    if self._grouping_mode != 'none' and group_name != last_group_name:
                        # Divider drawn at current position
                        self._draw_inline_divider(painter, group_name, base_x_pos, shelf_y)
                        base_x_pos += self.DIVIDER_WIDTH + self.ITEMS_GAP  # Update base position

                    last_group_name = group_name

                    # Determine if we should apply shift to this book
                    if self._hovered.is_row(row) and self._hover_shift:
                        display_width = self._hovered.width
                    else:
                        display_width = spine_width

                    if self._hovered.is_row(row):
                        # This is the hovered book - it draw later
                        # Position cover at spine position - left edge aligned with spine left edge
                        # The cover replaces the spine, so left edge stays at original spine position
                        self._hovered.base_x_pos = base_x_pos
                        self._hovered.base_y_pos = base_y_pos
                    else:
                        # Draw a book spine at this position
                        spine_rect = QRect(base_x_pos, shelf_y, spine_width, self.SPINE_HEIGHT)
                        self._draw_spine(painter, row, spine_rect)

                    # Update position for next book
                    base_x_pos += display_width + self.ITEMS_GAP

            # Move to next shelf
            shelf_y += self.SHELF_SPACING

            # Early exit if we've scrolled past the point
            if shelf_y > visible_rect.bottom():
                break

        # Draw the hover cover of the hovered book
        if self._hovered.is_valid():
            self._draw_hover_cover(painter, self._hovered)

    def _draw_inline_divider(self, painter, group_name, x_pos, shelf_y):
        '''Draw an inline group divider (small vertical element like JSX).

        Like the JSX Divider component: small vertical element that sits alongside books,
        with a label at the bottom and a gradient line going upward. The divider is the
        same height as books (150px) and bottom-aligned.

        :param painter: QPainter instance
        :param group_name: Name of the group
        :param x_pos: X position where divider should be drawn
        :param shelf_y: Current shelf y position (top of books)
        '''
        margin_bottom = 10
        divider_line_width = 2  # Width of vertical line

        # Calculate label position from top
        label_y = shelf_y + (self.SPINE_HEIGHT - margin_bottom)

        # Measure and truncate text
        available_vertical_space = self.SPINE_HEIGHT - margin_bottom - 5  # Leave 5px margin at top
        max_width = min(available_vertical_space, 300)  # Allow up to 300px for longer text

        # Try several sizes for name to fit without truncate
        zwsp = '\u200b'  # Zero Width Space
        group_name += zwsp
        font = QFont()
        font.setBold(True)
        for minus in range(8):
            minus = minus / 2
            font.setPointSizeF(12 - minus)

            fm = QFontMetrics(font)
            elided_name = fm.elidedText(group_name, Qt.TextElideMode.ElideRight, max_width)
            if elided_name.endswith(zwsp):  # no truncate perform for this size
                break
        elided_name = elided_name.replace(zwsp, '')
        elided_name = elided_name.replace(' …', '…')

        text_width = fm.horizontalAdvance(elided_name)

        # Calculate text dimensions
        label_x = x_pos + self.DIVIDER_WIDTH / 2  # Center of divider horizontally

        # After -90 rotation, text extends upward from label_y
        # Text height after rotation
        text_top_y = label_y - text_width  # Top of text (where text ends)

        # Line starts at top of text and extends to top of books
        line_x = label_x - divider_line_width / 2  # Center line in divider
        line_bottom = text_top_y  # Start at top of text
        line_top = shelf_y + 5  # Extend to top of books (with 5px margin)
        line_height = max(0, line_bottom - line_top)  # Auto-size based on text

        # Draw vertical gradient line
        if line_height > 0:
            painter.save()
            gradient = QLinearGradient(
                QPointF(line_x, line_top),
                QPointF(line_x, line_bottom),
            )
            gradient.setColorAt(0, QColor(74, 74, 106, 0))  # Transparent at top
            gradient.setColorAt(0.5, QColor(74, 74, 106, 200))  # Visible in middle
            gradient.setColorAt(1, QColor(74, 74, 106, 0))  # Transparent at bottom

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRect(int(line_x), int(line_top), divider_line_width, int(line_height))
            painter.restore()

        # Draw label text (rotated -90 degrees, reads upward)
        # Use exact same approach as _draw_spine() for consistency
        painter.save()
        painter.setFont(font)
        # Use a brighter color for better visibility, especially for longer text
        painter.setPen(self.DIVIDER_TEXT_COLOR)

        # Translate to label position (like JSX: marginBottom: '10px' from bottom of 150px container)
        # label_y is calculated as shelf_y + (SPINE_HEIGHT - 10), which is 10px from bottom
        # This is the bottom edge of where the text should be positioned
        painter.translate(label_x, label_y)
        painter.rotate(-90)  # Rotate -90 degrees (text reads upward, like JSX rotate(180deg) with vertical-rl)

        # After -90 rotation: coordinate system changes
        # x-axis becomes vertical (up/down), y-axis becomes horizontal (left/right)
        # We're at (0,0) which is the label position (bottom of text, center horizontally)
        # Text should extend upward (positive x direction) and be centered horizontally (y=0)

        # Create text rect - text extends upward from (0,0) and is centered horizontally
        # After -90 rotation: x controls vertical, y controls horizontal
        # Text starts at x=0 (bottom) and extends to x=text_width (top)
        # Text is centered at y=0 (horizontally)
        text_rect = QRect(
            0,  # x: start at bottom (x=0, text extends upward)
            int(-text_width / 2),  # y: center horizontally (y centered around 0)
            int(text_width),  # width: vertical extent (text extends this far upward)
            int(text_width),  # height: horizontal extent (wide enough to center text)
        )

        # Draw text with center alignment
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided_name)
        painter.restore()

    def _draw_shelf(self, painter, shelf_y, visible_rect):
        '''Draw the shelf background at the given y position.'''
        # Shelf surface (where books sit)
        shelf_surface_y = shelf_y + self.SPINE_HEIGHT

        # Create gradient for shelf surface (horizontal gradient for wood grain effect)
        gradient = QLinearGradient(
            QPointF(visible_rect.left(), shelf_surface_y),
            QPointF(visible_rect.right(), shelf_surface_y),
        )
        gradient.setColorAt(0, self.SHELF_COLOR_START)
        gradient.setColorAt(0.5, self.SHELF_COLOR_END.lighter(105))
        gradient.setColorAt(1, self.SHELF_COLOR_START)

        # Draw shelf surface
        shelf_rect = QRect(
            visible_rect.left(),
            shelf_surface_y,
            visible_rect.width(),
            self.SHELF_HEIGHT,
        )
        painter.fillRect(shelf_rect, QBrush(gradient))

        # Draw shelf front edge (3D effect - darker shadow)
        edge_rect = QRect(
            visible_rect.left(),
            shelf_surface_y,
            visible_rect.width(),
            3,
        )
        painter.fillRect(edge_rect, self.SHELF_COLOR_END.darker(130))

        # Draw shelf back edge (lighter highlight for 3D depth)
        back_edge_rect = QRect(
            visible_rect.left(),
            shelf_surface_y + self.SHELF_HEIGHT - 2,
            visible_rect.width(),
            2,
        )
        painter.fillRect(back_edge_rect, self.SHELF_COLOR_START.lighter(110))

        # Draw subtle wood grain lines
        painter.setPen(QPen(self.SHELF_COLOR_END.darker(110), 1))
        for i in range(0, visible_rect.width(), 20):
            line_y = shelf_surface_y + self.SHELF_HEIGHT // 2
            painter.drawLine(
                visible_rect.left() + i,
                line_y,
                visible_rect.left() + i + 10,
                line_y,
            )

    def _draw_selection_highlight(self, painter, rect):
        '''Draw the selection highlight.'''
        painter.save()
        painter.setPen(self.SELECTION_HIGHLIGHT_COLOR)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(1.0)
        painter.drawRect(rect.adjusted(1, 1, -1, -1))
        painter.restore()

    def _draw_statue_indicator(self, painter, rect, book_id, mi=None):
        '''Draw reading statue indicator.'''
        statue_color = self.render_template_statue(book_id, mi)
        if isinstance(statue_color, QColor):
            painter.save()
            painter.setOpacity(1.0)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            dot_radius = 4
            dot_x = rect.x() + rect.width() // 2
            dot_y = rect.y() + rect.height() - dot_radius - 10
            painter.setBrush(QBrush(statue_color))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
            painter.drawEllipse(QPoint(dot_x, dot_y), dot_radius, dot_radius)
            painter.restore()

    def _draw_spine(self, painter, row, rect):
        '''Draw a book spine.'''
        book_id = self.book_id_from_row(row)
        mi = self.dbref().get_proxy_metadata(book_id)

        # Determine if selected
        is_selected = row in self._selected_rows or row == self._current_row

        # Get cover color
        spine_color = self._get_spine_color(book_id)
        # Ensure we have a valid color
        if not spine_color or not spine_color.isValid():
            spine_color = DEFAULT_SPINE_COLOR

        if is_selected:
            spine_color = spine_color.lighter(120)

        # Draw spine background with gradient (darker edges, lighter center)
        self._draw_spine_background(painter, rect, spine_color)

        # Draw cover thumbnail overlay - only if not hovered
        if self._enable_thumbnail:
            self._draw_thumbnail_overlay(painter, rect, book_id)

        # Draw selection highlight around the spine
        if is_selected:
            self._draw_selection_highlight(painter, rect)

        # Draw title (rotated vertically) - only if not hovered
        title = self.render_template_title(book_id, mi)
        self._draw_spine_title(painter, rect, spine_color, title)

        # Draw reading statue indicator at bottom
        self._draw_statue_indicator(painter, rect, book_id, mi)

    def _draw_spine_background(self, painter, rect, spine_color):
        '''Draw spine background with gradient (darker edges, lighter center).'''
        painter.save()
        painter.setOpacity(1.0)
        gradient = QLinearGradient(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.right(), rect.top()),
        )
        gradient.setColorAt(0, spine_color.darker(115))
        gradient.setColorAt(0.5, spine_color)
        gradient.setColorAt(1, spine_color.darker(115))
        painter.fillRect(rect, QBrush(gradient))

        # Add subtle vertical gradient for depth
        vertical_gradient = QLinearGradient(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.left(), rect.bottom()),
        )
        vertical_gradient.setColorAt(0, QColor(255, 255, 255, 20))  # Slight highlight at top
        vertical_gradient.setColorAt(1, QColor(0, 0, 0, 30))  # Slight shadow at bottom
        painter.fillRect(rect, QBrush(vertical_gradient))
        painter.restore()

    def _draw_spine_title(self, painter, rect, spine_color, title):
        '''Draw vertically the title on the spine'''
        painter.save()
        painter.setOpacity(1)
        painter.translate(rect.left() + rect.width() / 2, rect.top() + rect.height() / 2)
        painter.rotate(-90)

        # Determine text color based on spine background brightness
        text_color = self._get_contrasting_text_color(spine_color)
        painter.setPen(text_color)

        # Try several sizes for title to fit without truncate
        zwsp = '\u200b'  # Zero Width Space
        title += zwsp
        max_width = rect.height() - 30  # leave space for statue indicator
        font = QFont()
        for minus in range(8):
            offset_y = (8 - minus) / 2
            minus = minus / 2
            font.setPointSizeF(11 - minus)

            fm = QFontMetrics(font)
            elided_title = fm.elidedText(title, Qt.TextElideMode.ElideRight, max_width)
            if elided_title.endswith(zwsp):  # no truncate perform for this size
                break
        elided_title = elided_title.replace(zwsp, '')
        elided_title = elided_title.replace(' …', '…')

        # Shift text up to avoid overlapping statue indicator
        text_offset_y = -(offset_y // 2)
        text_offset_x = 5
        text_rect = QRect(
            int(-rect.height() / 2 + text_offset_x),
            int(-rect.width() / 2 + text_offset_y),
            int(rect.height()),
            int(rect.width()),
        )
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided_title)
        painter.restore()

    def _draw_thumbnail_overlay(self, painter, rect, book_id):
        '''Draw cover thumbnail overlay on spine.'''
        with suppress(Exception):
            thumbnail = self._get_spine_thumbnail(book_id)
            if not thumbnail or thumbnail.isNull():
                return

        if thumbnail.width() > 0:
            # Draw with opacity
            painter.save()
            painter.setOpacity(0.3)  # 30% opacity
            painter.drawPixmap(rect.left(), rect.top(), thumbnail)
            painter.restore()

    def _draw_hover_cover(self, painter, hovered):
        '''Draw the hover cover popup.

        The cover replaces the spine when hovered, appearing at the same position
        with full spine height (150px) and smooth fade-in animation.
        '''
        if not hovered.is_valid():
            return

        is_selected = hovered.row in self._selected_rows or hovered.row == self._current_row
        cover_rect = hovered.rect()

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
            QPointF(cover_rect.right(), cover_rect.bottom()),
        )
        overlay_gradient.setColorAt(0, QColor(255, 255, 255, 31))  # 0.12 opacity = ~31 alpha
        overlay_gradient.setColorAt(0.5, QColor(255, 255, 255, 0))
        overlay_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(cover_rect, QBrush(overlay_gradient))
        painter.restore()

        if is_selected:
            # Draw selection highlight around the hovered cover
            self._draw_selection_highlight(painter, cover_rect)

        # Draw reading statue indicator at same position that for the spine
        self._draw_statue_indicator(painter, hovered.spine_rect(), hovered.book_id)

    # Cover integration methods

    def _update_hover_fade(self):
        '''Update hover cover fade-in animation and shift progress.'''
        if not self._hovered.start_time:
            self._hover_fade_timer.stop()
            return

        elapse = elapsed_time(self._hovered.start_time)
        if elapse >= self._fade_time:
            self._hovered.progress = 1.0
            self._hovered.opacity = 1.0
            self._hovered.shift = 1.0
            self._hovered.width = max(self._hovered.width_max, self._hovered.spine_width)
            self._hovered.start_time = None
            self._hover_fade_timer.stop()
        else:
            self._hovered.progress = progress = elapse / self._fade_time
            # Cubic ease-out curve (similar to JSX mock)
            # Ease-out cubic: 1 - (1 - t)^3
            self._hovered.shift = shift = 1.0 - (1.0 - progress) ** 3
            # Interpolate opacity from 0.3 (start) to 1.0 (end)
            self._hovered.opacity = self._hovered.OPACITY_START + (1.0 - self._hovered.OPACITY_START) * shift
            # Start the animation at the same width of the spine
            if self._hovered.width_max > self._hovered.spine_width:
                self._hovered.width = int((self._hovered.width_max - self._hovered.spine_width) * shift) + self._hovered.spine_width
            else:
                # In the rare case when the spine is bigger than the cover
                self._hovered.width = self._hovered.spine_width
        self._update_viewport()

    def _load_hover_cover(self):
        '''Load the cover and scale it for hover popup.'''
        try:
            cover_data = self.dbref().cover(self._hovered.book_id, as_image=True)

            if not cover_data or cover_data.isNull():
                cover_data = DEFAULT_COVER

            # Scale to hover size - use full spine height, calculate width from aspect ratio
            cover_height = self.SPINE_HEIGHT

            # Calculate proper aspect ratio to determine width
            cover_aspect = cover_data.width() / cover_data.height()
            # Calculate width to maintain aspect ratio with spine height
            cover_width = int(cover_height * cover_aspect)
            # But limit to reasonable max width
            cover_width = min(cover_width, self.HOVER_EXPANDED_WIDTH)

            self._hovered.pixmap = QPixmap.fromImage(cover_data).scaled(
                cover_width, cover_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._hovered.dominant_color = self._get_spine_color(self._hovered.book_id)
            self._hovered.spine_height = self.SPINE_HEIGHT
            self._hovered.spine_width = self._get_spine_width(self._hovered.book_id)
            self._hovered.width = self._hovered.spine_width  # ensure that the animation start at the spine width
            self._hovered.width_max = self._hovered.pixmap.width()
            self._hovered.height = self._hovered.pixmap.height()

            if self._fade_time == 0:
                # Fade-in animation is disable
                self._hovered.progress = 1.0
                self._hovered.opacity = 1.0
                self._hovered.shift = 1.0
                self._hovered.width = max(self._hovered.width_max, self._hovered.spine_width)
            else:
                # Start timer for smooth fade-in animation
                self._hovered.start_time = time()
                if not self._hover_fade_timer.isActive():
                    self._hover_fade_timer.start(16)  # ~60fps updates

            # Trigger immediate repaint to show the cover
            self._update_viewport()
        except Exception:
            self._hovered = HoveredCover()

    def _delayed_hover_load(self):
        '''
        Load the buffered row only after a short delay.

        When the mouse move, several rows are request but many of them are probably not desired
        since their are on the path of the cursor but are not the one on which the cusor end it path.
        This can lead to load too many and useless cover, which impact the performance.
        '''
        # Avoid concurrent load of the same cover
        if self._hovered.row == self._hover_last_row:
            return

        if self._hover_last_time:
            # Test if is too early to load a new hovered cover
            # 20ms of delay, unoticable but avoid the loading of unrelevant covers
            if elapsed_time(self._hover_last_time) < 20:
                return

        # Delay passed, start load new hover cover
        self._hover_fade_timer.stop()
        self._hovered = HoveredCover()
        self._hovered.row = self._hover_last_row

        # Load hover cover if hovering over a book
        if self._hovered.row >= 0:
            self._hovered.book_id = self.book_id_from_row(self._hovered.row)
            self._load_hover_cover()

        self._hover_last_time = None
        self._hover_buffer_timer.stop()
        self._update_viewport()

    def _get_contrasting_text_color(self, background_color):
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

    def _get_spine_color(self, book_id):
        '''Get the spine color for a book from cache or by extraction.'''
        color = self._cover_colors.get(book_id)
        if color and color.isValid():
            return color
        self._cover_colors.pop(book_id, None)

        color = get_cover_color(book_id, self.dbref())

        if not color or not color.isValid():
            color = DEFAULT_SPINE_COLOR
        self._cover_colors[book_id] = color
        return color

    def _get_spine_thumbnail(self, book_id):
        '''Get the spine thumbnail for a book from cache or by generation.'''
        thumbnail = self._spine_thumbnails.get(book_id)
        if thumbnail and not thumbnail.isNull():
            return thumbnail
        self._spine_thumbnails.pop(book_id, None)

        cover_data = self.dbref().cover(book_id, as_image=True)
        if cover_data and not cover_data.isNull():
            thumbnail = generate_spine_thumbnail(cover_data, self.THUMBNAIL_WIDTH, self.SPINE_HEIGHT)
            if thumbnail and not thumbnail.isNull():
                self._spine_thumbnails[book_id] = thumbnail
                return thumbnail

        return None

    def _get_spine_width(self, book_id, mi=None):
        '''Get the spine width for a book from cache or by generation.'''
        self.init_template(self.dbref())
        if self.template_pages_is_empty and not self.pages_use_book_size:
            return self.SPINE_WIDTH_DEFAULT

        if not mi:
            mi = self.dbref().get_proxy_metadata(book_id)

        if not self.template_pages_is_empty:
            pages = self.render_template_pages(book_id, mi)
            if isinstance(pages, int) and pages >= 0:
                return self._calculate_spine_width(pages)

        if self.pages_use_book_size:
            pages = size_to_page_count(mi.book_size)
            if isinstance(pages, int) and pages >= 0:
                return self._calculate_spine_width(pages)

        if self.template_pages_is_empty:
            return self.SPINE_WIDTH_DEFAULT
        return self._calculate_spine_width(get_random_page_count(book_id))

    def _calculate_spine_width(self, pages):
        '''Calculate spine width from page count with 8-tier granular scaling.

        Args:
            pages: Number of pages in the book

        Returns:
            Spine width in pixels (between SPINE_WIDTH_MIN and SPINE_WIDTH_MAX)

        Tier breakdown for clear visual differences (reduced scale):
        Tier 1: 0-20 pages    → 15-18px  (very short articles)
        Tier 2: 20-50 pages   → 18-22px  (short articles)
        Tier 3: 50-100 pages  → 22-28px  (articles/short docs)
        Tier 4: 100-200 pages → 28-35px  (short books)
        Tier 5: 200-350 pages → 35-43px  (medium books)
        Tier 6: 350-500 pages → 43-50px  (long books)
        Tier 7: 500-750 pages → 50-56px  (very long books)
        Tier 8: 750+ pages    → 56-60px  (epic books)
        '''
        # Ensure pages is a valid number
        if not pages:
            return self.SPINE_WIDTH_DEFAULT
        try:
            pages = float(pages)
        except (TypeError, ValueError):
            return self.SPINE_WIDTH_DEFAULT

        # Ensure pages is within bounds
        pages = max(0, min(1500, pages))

        rslt = self._pages_widths.get(round(pages))
        if rslt:
            return rslt

        if pages <= 0:
            rslt = self.SPINE_WIDTH_MIN
        elif pages < 20:
            # Tier 1: Very short articles (0-20 pages) → 15-18px
            # 10 pages = 16.5px, 20 pages = 18px
            rslt = 15.0 + (pages / 20.0) * 3.0
        elif pages < 50:
            # Tier 2: Short articles (20-50 pages) → 18-22px
            # 20 pages = 18px, 35 pages = 20px, 50 pages = 22px
            rslt = 18.0 + ((pages - 20) / 30.0) * 4.0
        elif pages < 100:
            # Tier 3: Articles/short docs (50-100 pages) → 22-28px
            # 50 pages = 22px, 75 pages = 25px, 100 pages = 28px
            rslt = 22.0 + ((pages - 50) / 50.0) * 6.0
        elif pages < 200:
            # Tier 4: Short books (100-200 pages) → 28-35px
            # 100 pages = 28px, 150 pages = 31.5px, 200 pages = 35px
            rslt = 28.0 + ((pages - 100) / 100.0) * 7.0
        elif pages < 350:
            # Tier 5: Medium books (200-350 pages) → 35-43px
            # 200 pages = 35px, 275 pages = 39px, 350 pages = 43px
            rslt = 35.0 + ((pages - 200) / 150.0) * 8.0
        elif pages < 500:
            # Tier 6: Long books (350-500 pages) → 43-50px
            # 350 pages = 43px, 425 pages = 46.5px, 500 pages = 50px
            rslt = 43.0 + ((pages - 350) / 150.0) * 7.0
        elif pages < 750:
            # Tier 7: Very long books (500-750 pages) → 50-56px
            # 500 pages = 50px, 625 pages = 53px, 750 pages = 56px
            rslt = 50.0 + ((pages - 500) / 250.0) * 6.0
        else:
            # Tier 8: Epic books (750+ pages) → 56-60px
            # 750 pages = 56px, 1000 pages = 58px, 1500+ pages = 60px
            rslt = 56.0 + (pages - 750) / 187.5  # ~1px per 187 pages, max 4px

        # Ensure result is within bounds
        rslt = max(self.SPINE_WIDTH_MIN, min(self.SPINE_WIDTH_MAX, round(rslt)))

        self._pages_widths[round(pages)] = rslt
        return rslt

    def invalidate_cache(self, book_ids):
        '''Invalidate the cache for the given ids.'''
        if isinstance(book_ids, int):
            book_ids = (book_ids,)
        for idx in book_ids:
            self._cover_colors.pop(idx, None)
            self._spine_thumbnails.pop(idx, None)
        self._update_viewport()

    # Sort interface methods (required for SortByAction integration)

    def sort_by_named_field(self, field, order, reset=True):
        '''Sort by a named field.'''
        if not self._model:
            return
        if isinstance(order, Qt.SortOrder):
            order = order == Qt.SortOrder.AscendingOrder
        self._model.sort_by_named_field(field, order, reset)
        self._update_viewport()

    def reverse_sort(self):
        '''Reverse the current sort order.'''
        if not self._model:
            return
        m = self.model()
        try:
            sort_col, order = m.sorted_on
        except (TypeError, AttributeError):
            sort_col, order = 'date', True
        self.sort_by_named_field(sort_col, not order)

    def resort(self):
        '''Re-apply the current sort.'''
        if not self._model:
            return
        self._model.resort(reset=True)
        self._update_viewport()

    def intelligent_sort(self, field, ascending):
        '''Smart sort that toggles if already sorted on that field.'''
        if not self._model:
            return
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

    def multisort(self, fields, reset=True, only_if_different=False):
        '''Sort on multiple columns.'''
        if not self._model or not len(fields):
            return

        # Delegate to model's multisort capability
        # This is a simplified version - full implementation would match BooksView
        for field, ascending in reversed(fields):
            if field in list(self.dbref().field_metadata.keys()):
                self.sort_by_named_field(field, ascending, reset=reset)
                reset = False  # Only reset on first sort

    # Selection methods (required for AlternateViews integration)

    def set_current_row(self, row):
        '''Set the current row.'''
        if not self._model or not self._selection_model:
            return
        if 0 <= row < self._model.rowCount(QModelIndex()):
            self._current_row = row
            index = self._model.index(row, 0)
            if index.isValid():
                self._selection_model.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self._update_viewport()
            # Scroll to make row visible
            self._scroll_to_row(row)

    def select_rows(self, rows, using_ids=False):
        '''Select the specified rows.

        Args:
            rows: List of row indices or book IDs
            using_ids: If True, rows contains book IDs; if False, rows contains row indices
        '''
        if not self._model or not self._selection_model:
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
        self._update_viewport()

    def _scroll_to_row(self, row):
        '''Scroll to make the specified row visible.'''
        # Simplified scrolling - will improve in Phase 2
        # For now, just update viewport
        self._update_viewport()

    # Database methods

    def set_database(self, db, stage=0):
        '''Set the database.'''
        self._grouping_mode = db.new_api.pref('bookshelf_grouping_mode', 'none')
        # Ensure connection to main view selection is established
        # (in case it wasn't ready when setModel was called)
        self._connect_to_main_view_selection()
        if stage == 0:
            # Clear caches when database changes
            self.refresh_colors()
            self.template_inited = False

    def refresh_colors(self):
        '''Force refresh of all spine colors.'''
        self._cover_colors.clear()
        self._spine_thumbnails.clear()
        self._update_viewport()

    def shown(self):
        '''Called when this view becomes active.'''
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._update_current_shelf_layouts()

    def set_context_menu(self, menu):
        '''Set the context menu.'''
        self.context_menu = menu

    def contextMenuEvent(self, ev):
        '''Handle context menu events.'''
        # Create menu with grouping options
        m = QMenu(self)

        # Add grouping submenu
        grouping_menu = m.addMenu(_('Group by'))

        for k, v in GROUPINGS.items():
            if not v:
                grouping_menu.addSeparator()
                continue

            action = grouping_menu.addAction(v['name'])
            action.setCheckable(True)
            action.setChecked(self._grouping_mode == k)
            action.triggered.connect(partial(self._set_grouping_mode, k))

        # Add standard context menu items if available
        if self.context_menu:
            m.addSeparator()
            # Clone actions to avoid issues with menu ownership
            for action in self.context_menu.actions():
                m.addAction(action)

        m.popup(ev.globalPos())
        ev.accept()

    def _set_grouping_mode(self, mode):
        '''Set the grouping mode and refresh display.'''
        self._grouping_mode = mode
        self._model.db.new_api.set_pref('bookshelf_grouping_mode', mode)
        self._update_current_shelf_layouts()

    def get_selected_ids(self):
        '''Get selected book IDs.'''
        if not self._model:
            return []
        return [self.book_id_from_row(r) for r in self._selected_rows]

    def current_book_state(self):
        '''Get current book state for restoration.'''
        if self._current_row >= 0 and self._model:
            return self.book_id_from_row(self._current_row)
        return None

    def restore_current_book_state(self, state):
        '''Restore current book state.'''
        if not state or not self._model:
            return
        book_id = state
        row = self._model.db.data.id_to_index(book_id)
        self.set_current_row(row)
        self.select_rows([row])

    def marked_changed(self, old_marked, current_marked):
        '''Handle marked books changes.'''
        # Refresh display if marked books changed
        self._update_viewport()

    def indices_for_merge(self, resolved=True):
        '''Get indices for merge operations.'''
        if not self._model:
            return []
        return [self._model.index(row, 0) for row in self._selected_rows]

    # Mouse and keyboard events

    def viewportEvent(self, ev):
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

    def _handle_mouse_move(self, ev):
        '''Handle mouse move events for hover detection.'''
        if not self._model:
            return

        pos = ev.pos()
        row = self._book_at_position(pos.x(), pos.y())

        if row != self._hovered.row:
            # Hover changed
            self._hover_last_row = row
            self._hover_last_time = time()
            if not self._hover_buffer_timer.isActive():
                self._hover_buffer_timer.start(10)

    def _handle_mouse_press(self, ev):
        '''Handle mouse press events on the viewport.'''
        if not self._model:
            return False

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

            self._update_viewport()
            ev.accept()
            return True

        # No book was clicked
        return False

    def _handle_mouse_double_click(self, ev):
        '''Handle mouse double-click events on the viewport.'''
        if not self._model:
            return False

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

    def _handle_mouse_leave(self, ev):
        '''Handle mouse leave events on the viewport.'''
        # Clear hover when mouse leaves viewport
        self._hover_fade_timer.stop()
        self._hover_buffer_timer.stop()
        self._hovered = HoveredCover()
        self._update_viewport()

    def _connect_to_main_view_selection(self):
        '''Connect to the main library view's selection model to sync selection.'''
        if not self.gui:
            return

        library_view = self.gui.library_view
        if not library_view:
            return

        selection_model = library_view.selectionModel()
        if selection_model:
            # Disconnect any existing connections to avoid duplicates
            with suppress(Exception):
                selection_model.currentChanged.disconnect(self._main_current_changed)
            with suppress(Exception):
                selection_model.selectionChanged.disconnect(self._main_selection_changed)

            # Connect to selection changes from main view
            selection_model.currentChanged.connect(self._main_current_changed)
            selection_model.selectionChanged.connect(self._main_selection_changed)

    def _main_current_changed(self, current, previous):
        '''Handle current row change from main library view.'''
        if self._syncing_from_main or not self._model:
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
            self._update_viewport()
            self._syncing_from_main = False

    def _main_selection_changed(self, selected, deselected):
        '''Handle selection change from main library view.'''
        if self._syncing_from_main or not self._model:
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

    def mouseDoubleClickEvent(self, ev):
        '''Handle double-click to open book.'''
        # Double-click is handled in viewportEvent
        super().mouseDoubleClickEvent(ev)

    def _book_at_position(self, x, y):
        '''Find which book is at the given position.
        x, y are in viewport coordinates.
        Returns row or -1.'''
        if not self._model:
            return -1

        # Convert viewport coordinates to content coordinates
        scroll_y = self.verticalScrollBar().value()
        content_y = y + scroll_y
        shelf_y = self.MARGIN_TOP

        for shelf_items in self._current_shelf_layouts:
            # Get starting x position for this shelf
            base_x_pos = shelf_items['start_x']
            base_y_pos = shelf_items['start_y']

            # Check if shelf is visible
            if base_y_pos + self.SPINE_HEIGHT >= content_y:
                last_group_name = None

                for row, group_name, spine_width in shelf_items['items']:
                    # Account for inline divider when group changes
                    if self._grouping_mode != 'none' and group_name != last_group_name:
                        base_x_pos += self.DIVIDER_WIDTH + self.ITEMS_GAP
                    last_group_name = group_name

                    # Calculate display position and width (same as paintEvent with cumulative positioning)
                    if self._hovered.is_row(row) and self._hover_shift:
                        # This is the hovered book - use expanded width at base position
                        display_width = self._hovered.width
                    else:
                        # Non-hovered book: use spine width at base position
                        display_width = spine_width

                    spine_rect = QRect(base_x_pos, shelf_y, display_width, self.SPINE_HEIGHT)

                    # Check if point is within this spine
                    if spine_rect.contains(x, content_y):
                        return row

                    # Update base_x_pos for next book - use actual width (expanded for hovered, spine for others)
                    base_x_pos += display_width + self.ITEMS_GAP

            # Move to next shelf
            shelf_y += self.SHELF_SPACING

            # Early exit if we've scrolled past the point
            if shelf_y > content_y + self.SPINE_HEIGHT:
                break

        return -1

    def indexAt(self, pos):
        '''Return the model index at the given position (required for drag/drop).
        pos is a QPoint in viewport coordinates.'''
        row = self._book_at_position(pos.x(), pos.y())
        if row >= 0 and self._model:
            return self._model.index(row, 0)
        return QModelIndex()

    def currentIndex(self):
        '''Return the current model index (required for drag/drop).'''
        if self._current_row >= 0 and self._model:
            return self._model.index(self._current_row, 0)
        return QModelIndex()

    def handle_mouse_press_event(self, ev):
        '''Handle mouse press events (called by setup_dnd_interface).'''
        # This is called by the setup_dnd_interface mousePressEvent
        # Our actual mousePressEvent already handles selection, so this can be a no-op
        # or we can delegate to it
        pass

    def handle_mouse_move_event(self, ev):
        '''Handle mouse move events (called by setup_dnd_interface).'''
        # Phase 2: Handle hover detection
        # Delegate to _handle_mouse_move to avoid code duplication
        self._handle_mouse_move(ev)

    def handle_mouse_release_event(self, ev):
        '''Handle mouse release events (called by setup_dnd_interface).'''
        # This is called by the setup_dnd_interface mouseReleaseEvent
        # We don't need special handling for mouse release
        pass

    def wheelEvent(self, ev):
        '''Handle wheel events for scrolling.'''
        number_of_pixels = ev.pixelDelta()
        number_of_degrees = ev.angleDelta() / 8.0
        b = self.verticalScrollBar()
        if number_of_pixels.isNull() or islinux:
            dy = number_of_degrees.y() / 15.0
            dy = int((dy) * b.singleStep() / 2.0)
        else:
            dy = number_of_pixels.y()
        if abs(dy) > 0:
            b.setValue(b.value() - dy)
        ev.accept()
