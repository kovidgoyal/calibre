#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict
from io import BytesIO
from threading import Lock
from time import time

from qt.core import (
    QAbstractScrollArea,
    QApplication,
    QBrush,
    QColor,
    QEvent,
    QFont,
    QFontMetrics,
    QImage,
    QItemSelection,
    QItemSelectionModel,
    QLinearGradient,
    QModelIndex,
    QPainter,
    QPalette,
    QPen,
    QPoint,
    QPointF,
    QPixmap,
    QRect,
    QSize,
    Qt,
    QTimer,
    QWidget,
    pyqtSignal,
    qBlue,
    qGreen,
    qRed,
)

from calibre.gui2 import gprefs
from calibre.gui2.library.alternate_views import setup_dnd_interface
from calibre.utils.localization import _

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Color cache to avoid re-extracting colors for the same covers
_color_cache = {}
_color_cache_lock = Lock()

# Thumbnail cache for spine thumbnails
_thumbnail_cache = {}
_thumbnail_cache_lock = Lock()


# Utility functions {{{

def extract_dominant_color(image_data, fallback_color='#8B4513'):
    '''
    Extract the dominant color from an image. Returns a QColor.
    '''
    if image_data is None:
        return QColor(fallback_color)

    # Convert to PIL Image if needed
    pil_image = None
    if PIL_AVAILABLE:
        if isinstance(image_data, (QImage, QPixmap)):
            # Convert QImage/QPixmap to PIL Image
            if isinstance(image_data, QPixmap):
                qimg = image_data.toImage()
            else:
                qimg = image_data
            # Convert to bytes
            buffer = BytesIO()
            qimg.save(buffer, 'PNG')
            buffer.seek(0)
            pil_image = Image.open(buffer)
        elif isinstance(image_data, Image.Image):
            pil_image = image_data
        elif isinstance(image_data, bytes):
            pil_image = Image.open(BytesIO(image_data))
    else:
        # Fallback: use QImage directly
        if isinstance(image_data, QPixmap):
            qimg = image_data.toImage()
        elif isinstance(image_data, QImage):
            qimg = image_data
        elif isinstance(image_data, bytes):
            qimg = QImage()
            qimg.loadFromData(image_data)
        else:
            return QColor(fallback_color)

        if qimg.isNull():
            return QColor(fallback_color)

        # Improved color extraction from QImage
        # Resize to larger size for better color accuracy
        small = qimg.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if small.isNull():
            return QColor(fallback_color)

        # Get pixel data with saturation preference
        width = small.width()
        height = small.height()
        color_counts = defaultdict(int)

        for y in range(height):
            for x in range(width):
                pixel = small.pixel(x, y)
                r = qRed(pixel)
                g = qGreen(pixel)
                b = qBlue(pixel)
                # Quantize to 32 levels (8 levels per channel)
                r_q = (r // 8) * 8
                g_q = (g // 8) * 8
                b_q = (b // 8) * 8
                color_counts[(r_q, g_q, b_q)] += 1

        if not color_counts:
            return QColor(fallback_color)

        # Find most common color with saturation preference
        def color_score(item):
            (r, g, b), count = item
            max_val = max(r, g, b)
            min_val = min(r, g, b)
            if max_val == 0:
                saturation = 0
            else:
                saturation = (max_val - min_val) / max_val
            return (count, saturation * 100)

        sorted_colors = sorted(color_counts.items(), key=color_score, reverse=True)
        dominant_color = sorted_colors[0][0]

        # Prefer saturated over gray colors
        r, g, b = dominant_color
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        saturation = (max_val - min_val) / max_val if max_val > 0 else 0

        if saturation < 0.2 and len(sorted_colors) > 1:
            total_pixels = width * height
            for (r2, g2, b2), count in sorted_colors[1:5]:
                max_val2 = max(r2, g2, b2)
                min_val2 = min(r2, g2, b2)
                sat2 = (max_val2 - min_val2) / max_val2 if max_val2 > 0 else 0
                if sat2 > 0.3 and count > total_pixels * 0.05:
                    dominant_color = (r2, g2, b2)
                    break

        return QColor(dominant_color[0], dominant_color[1], dominant_color[2])

    if pil_image is None:
        return QColor(fallback_color)

    # Resize for performance and color accuracy
    pil_image.thumbnail((100, 100), Image.Resampling.LANCZOS)

    # Convert to RGB if needed
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')

    # Extract dominant color using improved algorithm
    # Use less aggressive quantization
    # Quantize to 32 levels per channel
    color_counts = defaultdict(int)
    pixels = pil_image.getdata()

    for pixel in pixels:
        r, g, b = pixel
        # Quantize to 32 levels per channel
        # Preserve color variety while grouping similar colors
        r_q = (r // 8) * 8
        g_q = (g // 8) * 8
        b_q = (b // 8) * 8
        color_counts[(r_q, g_q, b_q)] += 1

    if not color_counts:
        return QColor(fallback_color)

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


def get_cover_color(book_id, db, cache_key=None):
    '''
    Get the dominant color from a book's cover, with caching. Returns a QColor.
    '''
    if cache_key is None:
        cache_key = book_id

    # Check cache first
    with _color_cache_lock:
        if cache_key in _color_cache:
            cached = _color_cache[cache_key]
            if cached is not None and cached.isValid():
                return cached
            # Remove invalid cached color
            _color_cache.pop(cache_key, None)

    # Load cover - try multiple methods
    # Try multiple cover loading methods
    color = None
    cover_data = None

    # Preferred method: new_api.cover_or_cache
    try:
        if hasattr(db, 'new_api') and hasattr(db.new_api, 'cover_or_cache'):
            has_cover, cdata, timestamp = db.new_api.cover_or_cache(book_id, 0, as_what='pil_image')
            if has_cover and cdata is not None:
                # cdata is a PIL Image when as_what='pil_image'
                color = extract_dominant_color(cdata)
                if color is not None and color.isValid() and color != QColor('#8B4513'):
                    pass
                else:
                    color = None  # Try other methods
    except Exception:
        pass

    # Try as_image with index_is_id
    if color is None or not color.isValid():
        try:
            try:
                cover_data = db.cover(book_id, index_is_id=True, as_image=True)
            except (TypeError, AttributeError):
                cover_data = db.cover(book_id, as_image=True)
            if cover_data is not None and not cover_data.isNull():
                color = extract_dominant_color(cover_data)
        except Exception:
            pass

    # Method 3: If that failed, try as_pixmap
    if color is None or not color.isValid():
        try:
            try:
                cover_data = db.cover(book_id, index_is_id=True, as_pixmap=True)
            except (TypeError, AttributeError):
                cover_data = db.cover(book_id, as_pixmap=True)
            if cover_data is not None and not cover_data.isNull():
                color = extract_dominant_color(cover_data)
        except Exception:
            pass

    # Method 4: If still failed, try loading from bytes
    if color is None or not color.isValid():
        try:
            try:
                cover_bytes = db.cover(book_id, index_is_id=True)
            except (TypeError, AttributeError):
                cover_bytes = db.cover(book_id)
            if cover_bytes:
                qimg = QImage()
                if qimg.loadFromData(cover_bytes):
                    if not qimg.isNull():
                        color = extract_dominant_color(qimg)
        except Exception:
            pass

    # Method 5: If still failed, try as_path
    if color is None or not color.isValid():
        try:
            try:
                cover_path = db.cover(book_id, index_is_id=True, as_path=True)
            except (TypeError, AttributeError):
                cover_path = db.cover(book_id, as_path=True)
            if cover_path:
                qimg = QImage(cover_path)
                if not qimg.isNull():
                    color = extract_dominant_color(qimg)
        except Exception:
            pass

    # Use default if extraction failed
    if color is None or not color.isValid():
        return QColor('#8B4513')  # Default brown (not cached)

    # Cache extracted colors
    if color.rgb() != QColor('#8B4513').rgb():
        with _color_cache_lock:
            _color_cache[cache_key] = color
            # Limit cache size to 1000 entries
            if len(_color_cache) > 1000:
                # Remove oldest entries (simple FIFO)
                keys_to_remove = list(_color_cache.keys())[:100]
                for key in keys_to_remove:
                    _color_cache.pop(key, None)

    return color


def generate_spine_thumbnail(cover_data, target_height=20):
    '''
    Generate a small thumbnail for display on the spine. Returns a QPixmap or None.
    '''
    if cover_data is None:
        return None

    # Convert to QImage
    qimg = None
    if isinstance(cover_data, QPixmap):
        qimg = cover_data.toImage()
    elif isinstance(cover_data, QImage):
        qimg = cover_data
    elif isinstance(cover_data, bytes):
        qimg = QImage()
        if not qimg.loadFromData(cover_data):
            return None
    elif PIL_AVAILABLE and isinstance(cover_data, Image.Image):
        # Convert PIL Image to QImage
        from calibre.utils.img import convert_PIL_image_to_pixmap
        pixmap = convert_PIL_image_to_pixmap(cover_data)
        qimg = pixmap.toImage()
    else:
        return None

    if qimg.isNull():
        return None

    # Maintain aspect ratio while scaling
    original_width = qimg.width()
    original_height = qimg.height()
    if original_height == 0:
        return None

    aspect_ratio = original_width / original_height
    target_width = int(target_height * aspect_ratio)

    # Scale the image
    scaled = qimg.scaled(
        target_width, target_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )

    if scaled.isNull():
        return None

    return QPixmap.fromImage(scaled)


def get_spine_thumbnail(book_id, db, target_height=20, cache_key=None):
    '''
    Get a thumbnail for display on the spine, with caching. Returns a QPixmap or None.
    '''
    if cache_key is None:
        cache_key = (book_id, target_height)

    # Check cache first
    with _thumbnail_cache_lock:
        if cache_key in _thumbnail_cache:
            return _thumbnail_cache[cache_key]

    # Load cover
    try:
        cover_data = db.cover(book_id, as_image=True)
        if cover_data is None or cover_data.isNull():
            thumbnail = None
        else:
            thumbnail = generate_spine_thumbnail(cover_data, target_height)
    except Exception:
        thumbnail = None

    # Cache the result
    if thumbnail is not None:
        with _thumbnail_cache_lock:
            _thumbnail_cache[cache_key] = thumbnail
            # Limit cache size to 500 entries
            if len(_thumbnail_cache) > 500:
                # Remove oldest entries (simple FIFO)
                keys_to_remove = list(_thumbnail_cache.keys())[:50]
                for key in keys_to_remove:
                    _thumbnail_cache.pop(key, None)

    return thumbnail


def get_cover_texture_edge(cover_data, edge_width=10, opacity=0.3):
    '''
    Extract the left edge of a cover image for use as a texture overlay. Returns a QPixmap or None.
    '''
    if cover_data is None:
        return None

    # Convert to QImage
    qimg = None
    if isinstance(cover_data, QPixmap):
        qimg = cover_data.toImage()
    elif isinstance(cover_data, QImage):
        qimg = cover_data
    elif isinstance(cover_data, bytes):
        qimg = QImage()
        if not qimg.loadFromData(cover_data):
            return None
    elif PIL_AVAILABLE and isinstance(cover_data, Image.Image):
        from calibre.utils.img import convert_PIL_image_to_pixmap
        pixmap = convert_PIL_image_to_pixmap(cover_data)
        qimg = pixmap.toImage()
    else:
        return None

    if qimg.isNull():
        return None

    # Extract left edge
    height = qimg.height()
    edge_rect = QRect(0, 0, min(edge_width, qimg.width()), height)
    edge_image = qimg.copy(edge_rect)

    # Apply opacity
    if opacity < 1.0:
        # Create a new image with alpha channel
        rgba_image = QImage(edge_image.size(), QImage.Format.Format_ARGB32)
        rgba_image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(rgba_image)
        painter.setOpacity(opacity)
        painter.drawImage(0, 0, edge_image)
        painter.end()
        edge_image = rgba_image

    return QPixmap.fromImage(edge_image)


def invalidate_caches(book_ids=None):
    '''
    Invalidate cached colors and thumbnails for specified books, or all if book_ids is None.
    '''
    global _color_cache, _thumbnail_cache

    with _color_cache_lock:
        if book_ids is None:
            _color_cache.clear()
        else:
            # Remove matching entries
            keys_to_remove = []
            for key in _color_cache.keys():
                if isinstance(key, tuple):
                    if key[0] in book_ids:
                        keys_to_remove.append(key)
                elif key in book_ids:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                _color_cache.pop(key, None)

    with _thumbnail_cache_lock:
        if book_ids is None:
            _thumbnail_cache.clear()
        else:
            # Remove entries matching any book_id
            keys_to_remove = []
            for key in _thumbnail_cache.keys():
                if isinstance(key, tuple):
                    if key[0] in book_ids:
                        keys_to_remove.append(key)
                elif isinstance(key, (int, str)) and key in book_ids:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                _thumbnail_cache.pop(key, None)


def group_books_by_author(rows, model):
    '''
    Group books by author. Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[_('No Author')].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.get_metadata(book_id, index_is_id=True)
            authors = getattr(mi, 'authors', []) or []

            if authors:
                # Use first author
                author = authors[0]
                groups[author].append(row)
            else:
                groups[_('No Author')].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[_('No Author')].append(row)

    # Sort groups by name
    sorted_groups = []
    for group_name in sorted(groups.keys(), key=lambda x: (x == _('No Author'), x.lower())):
        group_rows = groups[group_name]
        sorted_groups.append((group_name, group_rows))

    return sorted_groups


def group_books_by_publisher(rows, model):
    '''
    Group books by publisher. Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[_('No Publisher')].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.get_metadata(book_id, index_is_id=True)
            publisher = getattr(mi, 'publisher', None)

            if publisher:
                groups[publisher].append(row)
            else:
                groups[_('No Publisher')].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[_('No Publisher')].append(row)

    # Sort groups by name
    sorted_groups = []
    for group_name in sorted(groups.keys(), key=lambda x: (x == _('No Publisher'), x.lower())):
        group_rows = groups[group_name]
        sorted_groups.append((group_name, group_rows))

    return sorted_groups


def group_books_by_rating(rows, model):
    '''
    Group books by rating (star rating). Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[_('No Rating')].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.get_metadata(book_id, index_is_id=True)
            rating = getattr(mi, 'rating', None)

            if rating and rating > 0:
                # Calibre ratings are 0-10, display as stars (0-5)
                stars = int(rating / 2)
                group_name = '★' * stars if stars > 0 else _('No Rating')
                groups[group_name].append(row)
            else:
                groups[_('No Rating')].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[_('No Rating')].append(row)

    # Sort groups by rating (descending)
    def rating_sort_key(group_name):
        if group_name == _('No Rating'):
            return (1, 0)  # Put unrated at end
        try:
            stars = len(group_name)  # Count star characters
            return (0, -stars)  # Negative for descending
        except (ValueError, AttributeError):
            return (1, 0)

    sorted_groups = []
    for group_name in sorted(groups.keys(), key=rating_sort_key):
        group_rows = groups[group_name]
        sorted_groups.append((group_name, group_rows))

    return sorted_groups


def group_books_by_language(rows, model):
    '''
    Group books by language. Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[_('No Language')].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.get_metadata(book_id, index_is_id=True)
            languages = getattr(mi, 'languages', []) or []

            if languages:
                # Use first language
                lang = languages[0]
                groups[lang].append(row)
            else:
                groups[_('No Language')].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[_('No Language')].append(row)

    # Sort groups by name
    sorted_groups = []
    for group_name in sorted(groups.keys(), key=lambda x: (x == _('No Language'), x.lower())):
        group_rows = groups[group_name]
        sorted_groups.append((group_name, group_rows))

    return sorted_groups


def group_books_by_series(rows, model):
    '''
    Group books by series name. Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[_('No Series')].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.get_metadata(book_id, index_is_id=True)
            series = getattr(mi, 'series', None)

            if series:
                groups[series].append(row)
            else:
                groups[_('No Series')].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[_('No Series')].append(row)

    # Sort groups by name, preserve model order within groups
    sorted_groups = []
    for group_name in sorted(groups.keys(), key=lambda x: (x == _('No Series'), x.lower())):
        group_rows = groups[group_name]
        # Preserve model sort order
        # Model already sorted per user's preference
        sorted_groups.append((group_name, group_rows))

    return sorted_groups


def group_books_by_genre(rows, model):
    '''
    Group books by first tag (genre). Returns list of (group_name, row_indices) tuples.
    '''
    groups = defaultdict(list)

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[_('No Genre')].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.get_metadata(book_id, index_is_id=True)
            tags = getattr(mi, 'tags', []) or []

            if tags:
                # Use first tag as genre
                genre = tags[0]
                groups[genre].append(row)
            else:
                groups[_('No Genre')].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[_('No Genre')].append(row)

    # Sort groups by name
    sorted_groups = []
    for group_name in sorted(groups.keys(), key=lambda x: (x == _('No Genre'), x.lower())):
        sorted_groups.append((group_name, groups[group_name]))

    return sorted_groups


def group_books_by_time_period(rows, model):
    '''
    Group books by publication decade. Returns list of (group_name, row_indices) tuples.
    '''
    from calibre.utils.date import parse_date

    groups = defaultdict(list)

    for row in rows:
        try:
            index = model.index(row, 0)
            if not index.isValid():
                groups[_('Unknown Date')].append(row)
                continue

            book_id = model.id(index)
            mi = model.db.get_metadata(book_id, index_is_id=True)
            pubdate = getattr(mi, 'pubdate', None)

            if pubdate:
                try:
                    # Parse date and extract year
                    if hasattr(pubdate, 'year'):
                        year = pubdate.year
                    else:
                        dt = parse_date(str(pubdate))
                        year = dt.year if dt else None

                    if year:
                        # Group by decade (e.g., 2020-2029 -> "2020s")
                        decade = (year // 10) * 10
                        group_name = f'{decade}s'
                        groups[group_name].append(row)
                    else:
                        groups[_('Unknown Date')].append(row)
                except (ValueError, AttributeError, TypeError):
                    groups[_('Unknown Date')].append(row)
            else:
                groups[_('Unknown Date')].append(row)
        except (AttributeError, IndexError, KeyError, TypeError):
            groups[_('Unknown Date')].append(row)

    # Sort groups by decade (numerically)
    def decade_sort_key(group_name):
        if group_name == _('Unknown Date'):
            return (1, 0)  # Put unknown at end
        try:
            decade = int(group_name.replace('s', ''))
            return (0, decade)
        except (ValueError, AttributeError):
            return (1, 0)

    sorted_groups = []
    for group_name in sorted(groups.keys(), key=decade_sort_key):
        sorted_groups.append((group_name, groups[group_name]))

    return sorted_groups


def group_books(rows, model, grouping_mode):
    '''
    Group books according to the specified grouping mode.
    Returns list of (group_name, row_indices) tuples.
    '''
    if grouping_mode == 'none' or not grouping_mode:
        # No grouping - return single group with all rows
        return [('', rows)]
    elif grouping_mode == 'author':
        return group_books_by_author(rows, model)
    elif grouping_mode == 'series':
        return group_books_by_series(rows, model)
    elif grouping_mode == 'genre':
        return group_books_by_genre(rows, model)
    elif grouping_mode == 'publisher':
        return group_books_by_publisher(rows, model)
    elif grouping_mode == 'rating':
        return group_books_by_rating(rows, model)
    elif grouping_mode == 'language':
        return group_books_by_language(rows, model)
    elif grouping_mode == 'time_period':
        return group_books_by_time_period(rows, model)
    else:
        # Unknown mode - return no grouping
        return [('', rows)]

# }}}


@setup_dnd_interface
class BookshelfView(QAbstractScrollArea):  # {{{

    '''
    Enhanced bookshelf view displaying books as spines on shelves.

    This view provides an immersive browsing experience with sorting
    and grouping capabilities.
    '''

    files_dropped = pyqtSignal(object)
    books_dropped = pyqtSignal(object)

    # Spine dimensions
    SPINE_HEIGHT = 150
    SPINE_MIN_WIDTH = 15  # Minimum for very short articles/documents
    SPINE_MAX_WIDTH = 60  # Maximum for very long books
    SHELF_DEPTH = 20
    SHELF_SPACING = 180  # Space between shelves (spine height + gap)

    # Colors
    SHELF_COLOR_START = QColor('#4a3728')
    SHELF_COLOR_END = QColor('#3d2e20')
    BACKGROUND_COLOR = QColor('#0d0d18')
    TEXT_COLOR = QColor('#eee')
    TEXT_COLOR_DARK = QColor('#222')  # Dark text for light backgrounds
    DEFAULT_SPINE_COLOR = QColor('#8B4513')  # Brown fallback

    def __init__(self, parent):
        QAbstractScrollArea.__init__(self, parent)
        self.gui = parent
        self._model = None
        self.dbref = lambda: None
        self.context_menu = None
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self.setAutoFillBackground(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Ensure viewport receives mouse events
        self.viewport().setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_MouseTracking, True)

        # Selection tracking
        self._selected_rows = set()
        self._current_row = -1
        self._selection_model = None
        self._syncing_from_main = False  # Flag to prevent feedback loops

        # Set background on viewport
        viewport = self.viewport()
        viewport.setAutoFillBackground(True)
        palette = viewport.palette()
        palette.setColor(QPalette.ColorRole.Base, self.BACKGROUND_COLOR)
        viewport.setPalette(palette)

        # Initialize drag and drop
        # so we set the attributes manually
        self.drag_allowed = True
        self.drag_start_pos = None

        # Cover loading and caching
        self._cover_colors = {}  # Cache for cover colors (book_id -> QColor)
        self._spine_thumbnails = {}  # Cache for spine thumbnails (book_id -> QPixmap)
        self._hovered_row = -1  # Currently hovered book row
        self._hover_cover_pixmap = None  # Full cover for hover popup
        self._hover_cover_row = -1  # Row for which hover cover is loaded
        self._hover_cover_opacity = 1.0  # Opacity for hover cover (for smooth fade-in)
        self._hover_shift_progress = 0.0  # Progress of shift animation (0.0 to 1.0)
        self._hover_fade_timer = QTimer(self)  # Timer for fade-in animation
        self._hover_fade_timer.setSingleShot(False)
        self._hover_fade_timer.timeout.connect(self._update_hover_fade)
        self._hover_fade_start_time = None  # Start time for fade animation

        # Thumbnail size for spine
        self.THUMBNAIL_HEIGHT = 20

        # Hover cover popup size
        self.HOVER_COVER_WIDTH = 100
        # Max expanded width on hover
        self.HOVER_EXPANDED_WIDTH = 105

        # Timer for lazy loading covers
        self._load_covers_timer = QTimer(self)
        self._load_covers_timer.setSingleShot(True)
        self._load_covers_timer.timeout.connect(self._load_visible_covers)

        # Grouping configuration
        self._grouping_mode = gprefs.get('bookshelf_grouping_mode', 'none')

    def setModel(self, model):
        '''Set the model for this view.'''
        if self._model is not None:
            # Disconnect old model signals if needed
            pass
        self._model = model
        if model is not None:
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

        self._update_scrollbar_ranges()
        self.viewport().update()

    def selectionModel(self):
        '''Return the selection model (required for AlternateViews integration).'''
        return self._selection_model

    def _model_data_changed(self, topLeft, bottomRight, roles):
        '''Handle model data changes.'''
        self.viewport().update()

    def _model_rows_changed(self, parent, first, last):
        '''Handle model row changes.'''
        # Invalidate caches for removed books
        # Simplified cache invalidation
        self._update_scrollbar_ranges()
        self.viewport().update()

    def _model_reset(self):
        '''Handle model reset.'''
        self._update_scrollbar_ranges()
        self.viewport().update()

    def model(self):
        '''Return the model.'''
        return self._model

    def _update_scrollbar_ranges(self):
        '''Update scrollbar ranges based on number of books.'''
        if self._model is None:
            self.verticalScrollBar().setRange(0, 0)
            return

        row_count = self._model.rowCount(QModelIndex())
        if row_count == 0:
            self.verticalScrollBar().setRange(0, 0)
            return

        # Calculate total height with inline grouping
        viewport_width = self.viewport().width()
        x_pos = 10  # Start position (no label area - dividers are inline)
        shelf_y = 10
        db = self._model.db

        # Get all rows and group them, then flatten for inline rendering
        all_rows = list(range(row_count))
        groups = group_books(all_rows, self._model, self._grouping_mode)

        # Flatten groups into a list of (row, group_name) tuples
        flattened_items = []
        for group_name, group_rows in groups:
            for row in group_rows:
                flattened_items.append((row, group_name))

        last_group_name = None
        for row, group_name in flattened_items:
            # Divider when group changes
            if self._grouping_mode != 'none' and group_name != last_group_name and last_group_name is not None:
                x_pos += 32  # DIVIDER_WIDTH (30) + gap (2)
            last_group_name = group_name

            # Calculate spine width
            try:
                index = self._model.index(row, 0)
                if index.isValid():
                    book_id = self._model.id(index)
                    mi = db.get_metadata(book_id, index_is_id=True)
                    pages = self._get_page_count(book_id, db, mi)
                    spine_width = self._calculate_spine_width(pages)
                else:
                    spine_width = 40
            except (AttributeError, IndexError, KeyError, TypeError):
                spine_width = 40

            x_pos += int(spine_width) + 2

            # If we've filled the shelf, move to next shelf
            if x_pos + spine_width > viewport_width - 10:
                x_pos = 10  # Reset to start position
                shelf_y += self.SHELF_SPACING
                last_group_name = None  # Reset group tracking for new shelf

        # Add one more shelf for the last row
        total_height = shelf_y + self.SHELF_SPACING
        viewport_height = self.viewport().height()
        max_scroll = max(0, total_height - viewport_height)
        self.verticalScrollBar().setRange(0, max_scroll)
        self.verticalScrollBar().setPageStep(viewport_height)

    def resizeEvent(self, ev):
        '''Handle resize events.'''
        super().resizeEvent(ev)
        self._update_scrollbar_ranges()
        self.viewport().update()

    def _calculate_shelf_layouts(self, flattened_items, viewport_width):
        '''
        Pre-calculate which books go on which shelf, accounting for:
        1. Hover expansion space (reserve space on right for expansion)
        2. Left-aligned books with proper margins

        Returns a list of shelf dictionaries with:
        - 'items': list of (row, group_name) tuples
        - 'start_x': starting x position (left-aligned with margin)
        - 'start_row': first row on this shelf
        '''
        if not flattened_items:
            return []

        db = self._model.db
        shelves = []
        current_shelf = []
        shelf_width = 0
        shelf_start_row = 0
        last_group_name = None

        # Reserve space for hover expansion
        # Reserve space for expansion
        # Reserve space for hover expansion
        LEFT_MARGIN = 20
        RIGHT_MARGIN = (self.HOVER_EXPANDED_WIDTH - 40) + 20
        available_width = viewport_width - LEFT_MARGIN - RIGHT_MARGIN

        for row, group_name in flattened_items:
            # Account for divider when group changes
            divider_width = 0
            if self._grouping_mode != 'none' and group_name != last_group_name and last_group_name is not None:
                divider_width = 32  # DIVIDER_WIDTH (30) + gap (2)

            # Calculate spine width
            try:
                index = self._model.index(row, 0)
                if index.isValid():
                    book_id = self._model.id(index)
                    mi = db.get_metadata(book_id, index_is_id=True)
                    pages = self._get_page_count(book_id, db, mi)
                    spine_width = self._calculate_spine_width(pages)
                else:
                    spine_width = 40
            except (AttributeError, IndexError, KeyError, TypeError):
                spine_width = 40

            item_width = divider_width + spine_width + 2  # spine + gap

            # Check for shelf overflow
            if shelf_width + item_width > available_width and current_shelf:
                # Finish current shelf - left-aligned with margin
                shelves.append({
                    'items': current_shelf,
                    'start_x': LEFT_MARGIN,
                    'start_row': shelf_start_row
                })
                # Start new shelf
                current_shelf = []
                shelf_width = 0
                shelf_start_row = row
                last_group_name = None  # Reset for new shelf

            # Add item to current shelf
            current_shelf.append((row, group_name))
            shelf_width += item_width
            last_group_name = group_name

        # Add final shelf
        if current_shelf:
            shelves.append({
                'items': current_shelf,
                'start_x': LEFT_MARGIN,
                'start_row': shelf_start_row
            })

        return shelves

    def paintEvent(self, ev):
        '''Paint the bookshelf view.'''
        if self._model is None:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get visible area
        scroll_y = self.verticalScrollBar().value()
        viewport_rect = self.viewport().rect()
        visible_rect = QRect(
            viewport_rect.x(),
            viewport_rect.y() + scroll_y,
            viewport_rect.width(),
            viewport_rect.height()
        )

        # Get all rows and group them, then flatten for inline rendering
        row_count = self._model.rowCount(QModelIndex())
        if row_count == 0:
            return

        all_rows = list(range(row_count))
        groups = group_books(all_rows, self._model, self._grouping_mode)

        # Flatten groups for inline rendering
        flattened_items = []
        for group_name, group_rows in groups:
            for row in group_rows:
                flattened_items.append((row, group_name))

        # Track hovered book info for shift calculation
        hover_spine_width = 0
        if self._hovered_row >= 0:
            try:
                hover_index = self._model.index(self._hovered_row, 0)
                if hover_index.isValid():
                    db = self._model.db
                    hover_book_id = self._model.id(hover_index)
                    hover_mi = db.get_metadata(hover_book_id, index_is_id=True)
                    hover_pages = self._get_page_count(hover_book_id, db, hover_mi)
                    hover_spine_width = self._calculate_spine_width(hover_pages)
            except (AttributeError, IndexError, KeyError, TypeError):
                pass

        # Pre-calculate shelf layouts
        # Calculate shelf positions
        shelf_layouts = self._calculate_shelf_layouts(flattened_items, viewport_rect.width())

        # Draw books with inline dividers (like JSX)
        # Hovered item expands in place, items to right shift
        shelf_y = 10 + scroll_y
        db = self._model.db
        shelf_started = False
        current_shelf_idx = 0

        # Pre-calculate hover shift amount once
        hover_shift_amount = 0
        if self._hovered_row >= 0:
            if self._hover_cover_pixmap is not None and not self._hover_cover_pixmap.isNull():
                expanded_width = min(self._hover_cover_pixmap.width(), self.HOVER_EXPANDED_WIDTH)
            else:
                expanded_width = self.HOVER_EXPANDED_WIDTH
            hover_shift_amount = max(0, expanded_width - hover_spine_width) * self._hover_shift_progress

        for shelf_idx, shelf_items in enumerate(shelf_layouts):
            # Get starting x position for this shelf (centered)
            shelf_start_x = shelf_items['start_x']
            base_x_pos = shelf_start_x
            shelf_start_row = shelf_items['start_row']
            last_group_name = None
            cumulative_shift = 0

            for row, group_name in shelf_items['items']:
                if row >= row_count:
                    break

                # Draw inline divider when group changes
                if self._grouping_mode != 'none' and group_name != last_group_name and last_group_name is not None:
                    # Divider drawn at current position
                    divider_width = self._draw_inline_divider(painter, group_name, base_x_pos, shelf_y, visible_rect)
                    base_x_pos += divider_width + 2  # Update base position

                last_group_name = group_name

                # Calculate spine width from page count
                try:
                    index = self._model.index(row, 0)
                    if index.isValid():
                        book_id = self._model.id(index)
                        mi = db.get_metadata(book_id, index_is_id=True)
                        pages = self._get_page_count(book_id, db, mi)
                        spine_width = self._calculate_spine_width(pages)
                    else:
                        spine_width = 40
                except (AttributeError, IndexError, KeyError, TypeError):
                    spine_width = 40

                # Check if this book is hovered
                is_hovered = row == self._hovered_row

                # Determine if we should apply shift to this book
                # Shift applied after hovered book
                if is_hovered:
                    # This is the hovered book - it expands in place
                    if self._hover_cover_pixmap is not None and not self._hover_cover_pixmap.isNull():
                        cover_display_width = min(self._hover_cover_pixmap.width(), self.HOVER_EXPANDED_WIDTH)
                    else:
                        cover_display_width = self.HOVER_EXPANDED_WIDTH
                    current_x = base_x_pos
                    display_width = int(cover_display_width)
                    # Increase base_x_pos by expanded width
                    width_to_add = cover_display_width
                    # Increase cumulative shift for subsequent items
                    cumulative_shift += hover_shift_amount
                else:
                    # Draw at base position
                    current_x = base_x_pos
                    display_width = int(spine_width)
                    # Add only spine width to base position
                    width_to_add = spine_width

                # Draw shelf before first book on this shelf
                if not shelf_started:
                    if shelf_y + self.SPINE_HEIGHT >= visible_rect.top() and shelf_y <= visible_rect.bottom():
                        self._draw_shelf(painter, shelf_y, visible_rect)
                    shelf_started = True

                # Check if spine is visible
                clamped_x = max(visible_rect.left(), int(current_x))
                if clamped_x != int(current_x):
                    display_width = max(1, display_width - (clamped_x - int(current_x)))

                spine_rect = QRect(clamped_x, shelf_y, display_width, self.SPINE_HEIGHT)

                if spine_rect.bottom() >= visible_rect.top() and spine_rect.top() <= visible_rect.bottom():
                    # Pre-load color if not cached
                    try:
                        book_id = self._model.id(self._model.index(row, 0))
                        if book_id not in self._cover_colors:
                            self._get_spine_color(book_id, db)
                    except (AttributeError, IndexError, KeyError, TypeError):
                        pass
                    self._draw_spine(painter, row, spine_rect)

                # Update position for next book
                base_x_pos += int(width_to_add) + 2  # Small gap between spines

            # Move to next shelf
            shelf_y += self.SHELF_SPACING
            shelf_started = False

        # Trigger lazy loading of visible covers
        if not self._load_covers_timer.isActive():
            self._load_covers_timer.start(100)  # Delay 100ms to avoid loading during scroll

    def _draw_inline_divider(self, painter, group_name, x_pos, shelf_y, visible_rect):
        '''Draw an inline group divider (small vertical element like JSX).

        Like the JSX Divider component: small vertical element that sits alongside books,
        with a label at the bottom and a gradient line going upward. The divider is the
        same height as books (150px) and bottom-aligned.

        :param painter: QPainter instance
        :param group_name: Name of the group
        :param x_pos: X position where divider should be drawn
        :param shelf_y: Current shelf y position (top of books)
        :param visible_rect: Visible rectangle
        :return: Width of the divider (for positioning next item)
        '''
        if not group_name:
            return 0

        # Divider dimensions
        # Divider positioning
        DIVIDER_WIDTH = 30  # Width of divider element
        DIVIDER_LINE_WIDTH = 2  # Width of vertical line
        LABEL_MARGIN_BOTTOM = 10

        # Calculate label position from top
        book_bottom = shelf_y + self.SPINE_HEIGHT  # Bottom of book container (where books sit on shelf)
        label_y = shelf_y + (self.SPINE_HEIGHT - LABEL_MARGIN_BOTTOM)  # Label position: 10px from bottom of container

        # Only draw if visible
        if book_bottom < visible_rect.top() or shelf_y > visible_rect.bottom():
            return DIVIDER_WIDTH

        # Adjust font size for better visibility
        text_length = len(group_name)
        if text_length > 25:
            font_size = 12  # Slightly larger for longer text
        elif text_length > 15:
            font_size = 11  # Standard size
        else:
            font_size = 11  # Standard size

        font = QFont()
        font.setPointSize(font_size)
        font.setBold(True)
        fm = QFontMetrics(font)

        # Measure and truncate text
        available_vertical_space = self.SPINE_HEIGHT - LABEL_MARGIN_BOTTOM - 5  # Leave 5px margin at top
        max_text_width = min(available_vertical_space, 300)  # Allow up to 300px for longer text

        text_width = fm.horizontalAdvance(group_name)
        if text_width > max_text_width:
            elided_name = fm.elidedText(group_name, Qt.TextElideMode.ElideRight, max_text_width)
            text_width = fm.horizontalAdvance(elided_name)
        else:
            elided_name = group_name

        # Calculate text dimensions
        label_x = x_pos + DIVIDER_WIDTH / 2  # Center of divider horizontally

        # After -90 rotation, text extends upward from label_y
        # Text height after rotation
        text_top_y = label_y - text_width  # Top of text (where text ends)

        # Line starts at top of text and extends to top of books
        line_x = label_x - DIVIDER_LINE_WIDTH / 2  # Center line in divider
        line_bottom = text_top_y  # Start at top of text
        line_top = shelf_y + 5  # Extend to top of books (with 5px margin)
        line_height = max(0, line_bottom - line_top)  # Auto-size based on text

        # Draw vertical gradient line
        if line_height > 0:
            painter.save()
            gradient = QLinearGradient(
                QPointF(line_x, line_top),
                QPointF(line_x, line_bottom)
            )
            gradient.setColorAt(0, QColor(74, 74, 106, 0))  # Transparent at top
            gradient.setColorAt(0.5, QColor(74, 74, 106, 200))  # Visible in middle
            gradient.setColorAt(1, QColor(74, 74, 106, 0))  # Transparent at bottom

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRect(int(line_x), int(line_top), DIVIDER_LINE_WIDTH, int(line_height))
            painter.restore()

        # Draw label text (rotated -90 degrees, reads upward)
        # Use exact same approach as _draw_spine for consistency
        painter.save()
        painter.setFont(font)
        # Use a brighter color for better visibility, especially for longer text
        text_color = QColor('#b0b5c0')  # Brighter grey for better visibility
        painter.setPen(text_color)

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
            int(text_width)  # height: horizontal extent (wide enough to center text)
        )

        # Draw text with center alignment
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided_name)
        painter.restore()

        return DIVIDER_WIDTH


    def _draw_shelf(self, painter, shelf_y, visible_rect):
        '''Draw the shelf background at the given y position.'''
        # Shelf surface (where books sit)
        shelf_surface_y = shelf_y + self.SPINE_HEIGHT
        shelf_depth = self.SHELF_DEPTH

        # Create gradient for shelf surface (horizontal gradient for wood grain effect)
        gradient = QLinearGradient(
            QPointF(visible_rect.left(), shelf_surface_y),
            QPointF(visible_rect.right(), shelf_surface_y)
        )
        gradient.setColorAt(0, self.SHELF_COLOR_START)
        gradient.setColorAt(0.5, self.SHELF_COLOR_END.lighter(105))
        gradient.setColorAt(1, self.SHELF_COLOR_START)

        # Draw shelf surface
        shelf_rect = QRect(
            visible_rect.left(),
            shelf_surface_y,
            visible_rect.width(),
            shelf_depth
        )
        painter.fillRect(shelf_rect, QBrush(gradient))

        # Draw shelf front edge (3D effect - darker shadow)
        edge_rect = QRect(
            visible_rect.left(),
            shelf_surface_y,
            visible_rect.width(),
            3
        )
        painter.fillRect(edge_rect, self.SHELF_COLOR_END.darker(130))

        # Draw shelf back edge (lighter highlight for 3D depth)
        back_edge_rect = QRect(
            visible_rect.left(),
            shelf_surface_y + shelf_depth - 2,
            visible_rect.width(),
            2
        )
        painter.fillRect(back_edge_rect, self.SHELF_COLOR_START.lighter(110))

        # Draw subtle wood grain lines
        painter.setPen(QPen(self.SHELF_COLOR_END.darker(110), 1))
        for i in range(0, visible_rect.width(), 20):
            line_y = shelf_surface_y + shelf_depth // 2
            painter.drawLine(
                visible_rect.left() + i,
                line_y,
                visible_rect.left() + i + 10,
                line_y
            )

    def _get_page_count(self, book_id, db, mi):
        '''Get page count for a book, trying multiple methods.

        Calibre stores pages as an arbitrary attribute on the Metadata object.
        If not available, we can estimate from file size or use a default.

        Returns:
            int: Page count, or estimated value if not available
        '''
        # Method 1: Try metadata object attribute (most common)
        # Pages is stored as an arbitrary attribute on Metadata objects
        try:
            pages = getattr(mi, 'pages', None)
            if pages is not None:
                try:
                    pages = int(pages)
                    if pages > 0:
                        return pages
                except (ValueError, TypeError):
                    pass
        except AttributeError:
            pass

        # Method 2: Try accessing via _data dict (Metadata internal storage)
        try:
            if hasattr(mi, '_data'):
                pages = mi._data.get('pages', None)
                if pages is not None:
                    try:
                        pages = int(pages)
                        if pages > 0:
                            return pages
                    except (ValueError, TypeError):
                        pass
        except (AttributeError, KeyError):
            pass

        # Method 3: Try new_api field_for
        try:
            if hasattr(db, 'new_api'):
                pages = db.new_api.field_for('pages', book_id, default_value=None)
                if pages is not None:
                    try:
                        pages = int(pages)
                        if pages > 0:
                            return pages
                    except (ValueError, TypeError):
                        pass
        except (AttributeError, KeyError, TypeError):
            pass

        # Method 4: Try custom column #pages
        try:
            if hasattr(db, 'field_for'):
                pages = db.field_for('#pages', book_id, default_value=None)
                if pages is not None:
                    try:
                        pages = int(pages)
                        if pages > 0:
                            return pages
                    except (ValueError, TypeError):
                        pass
        except (AttributeError, KeyError, TypeError):
            pass

        # Method 5: Estimate from file size as fallback
        # Average ebook: ~1-2KB per page, so estimate pages from size
        try:
            if hasattr(db, 'new_api'):
                formats = db.new_api.formats(book_id, verify_formats=False)
                if formats:
                    # Get size of first available format
                    for fmt in formats:
                        try:
                            fmt_meta = db.new_api.format_metadata(book_id, fmt)
                            size_bytes = fmt_meta.get('size', 0)
                            if size_bytes and size_bytes > 0:
                                # Estimate: ~1500 bytes per page (conservative)
                                estimated_pages = max(50, int(size_bytes / 1500))
                                # Cap at reasonable max
                                return min(estimated_pages, 2000)
                        except (AttributeError, KeyError, TypeError):
                            continue
        except (AttributeError, KeyError, TypeError):
            pass

        # Default fallback: vary based on book_id to ensure visual differences
        # This ensures books have different widths even without page data
        # Use book_id to create a pseudo-random but consistent value per book
        # Range: 50-400 pages (covers tiers 2-5 for visual variety)
        import hashlib
        book_id_str = str(book_id) if book_id else '0'
        hash_val = int(hashlib.md5(book_id_str.encode()).hexdigest()[:8], 16)
        # Map hash to 50-400 page range
        default_pages = 50 + (hash_val % 350)
        return default_pages

    def _calculate_spine_width(self, pages):
        '''Calculate spine width from page count with 8-tier granular scaling.

        Args:
            pages: Number of pages in the book

        Returns:
            Spine width in pixels (between SPINE_MIN_WIDTH and SPINE_MAX_WIDTH)

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
        try:
            pages = float(pages) if pages else 0.0
        except (TypeError, ValueError):
            pages = 0.0

        if pages <= 0:
            return float(self.SPINE_MIN_WIDTH)
        elif pages < 20:
            # Tier 1: Very short articles (0-20 pages) → 15-18px
            # 10 pages = 16.5px, 20 pages = 18px
            return 15.0 + (pages / 20.0) * 3.0
        elif pages < 50:
            # Tier 2: Short articles (20-50 pages) → 18-22px
            # 20 pages = 18px, 35 pages = 20px, 50 pages = 22px
            return 18.0 + ((pages - 20) / 30.0) * 4.0
        elif pages < 100:
            # Tier 3: Articles/short docs (50-100 pages) → 22-28px
            # 50 pages = 22px, 75 pages = 25px, 100 pages = 28px
            return 22.0 + ((pages - 50) / 50.0) * 6.0
        elif pages < 200:
            # Tier 4: Short books (100-200 pages) → 28-35px
            # 100 pages = 28px, 150 pages = 31.5px, 200 pages = 35px
            return 28.0 + ((pages - 100) / 100.0) * 7.0
        elif pages < 350:
            # Tier 5: Medium books (200-350 pages) → 35-43px
            # 200 pages = 35px, 275 pages = 39px, 350 pages = 43px
            return 35.0 + ((pages - 200) / 150.0) * 8.0
        elif pages < 500:
            # Tier 6: Long books (350-500 pages) → 43-50px
            # 350 pages = 43px, 425 pages = 46.5px, 500 pages = 50px
            return 43.0 + ((pages - 350) / 150.0) * 7.0
        elif pages < 750:
            # Tier 7: Very long books (500-750 pages) → 50-56px
            # 500 pages = 50px, 625 pages = 53px, 750 pages = 56px
            return 50.0 + ((pages - 500) / 250.0) * 6.0
        else:
            # Tier 8: Epic books (750+ pages) → 56-60px
            # 750 pages = 56px, 1000 pages = 58px, 1500+ pages = 60px
            base = 56.0
            additional = min(4.0, (pages - 750) / 187.5)  # ~1px per 187 pages, max 4px
            result = base + additional
            # Ensure result is within bounds
            return max(float(self.SPINE_MIN_WIDTH), min(float(self.SPINE_MAX_WIDTH), result))

    def _draw_spine(self, painter, row, rect):
        '''Draw a book spine.'''
        if self._model is None:
            return

        index = self._model.index(row, 0)
        if not index.isValid():
            return

        # Get book metadata
        try:
            book_id = self._model.id(index)
            db = self._model.db
            mi = db.get_metadata(book_id, index_is_id=True)
            title = mi.title or _('Unknown')
            # Calculate spine width from page count
            pages = self._get_page_count(book_id, db, mi)
            spine_width = self._calculate_spine_width(pages)
            # Update rect width if needed
            if rect.width() != spine_width:
                rect.setWidth(int(spine_width))
        except (AttributeError, IndexError, KeyError, TypeError):
            title = _('Unknown')
            spine_width = 40

        # Determine if selected or hovered
        is_selected = row in self._selected_rows or row == self._current_row
        is_hovered = row == self._hovered_row

        # Get cover color (Phase 2)
        spine_color = self._get_spine_color(book_id, db)
        # Ensure we have a valid color
        if spine_color is None or not spine_color.isValid():
            spine_color = self.DEFAULT_SPINE_COLOR

        if is_selected:
            spine_color = spine_color.lighter(120)
        elif is_hovered:
            spine_color = spine_color.lighter(110)

        # When hovered, make spine transparent (like JSX mock)
        # The cover will be shown instead
        spine_opacity = 0.0 if is_hovered else 1.0

        # Draw spine background with gradient (darker edges, lighter center)
        painter.save()
        painter.setOpacity(spine_opacity)
        gradient = QLinearGradient(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.right(), rect.top())
        )
        gradient.setColorAt(0, spine_color.darker(115))
        gradient.setColorAt(0.5, spine_color)
        gradient.setColorAt(1, spine_color.darker(115))
        painter.fillRect(rect, QBrush(gradient))

        # Add subtle vertical gradient for depth
        vertical_gradient = QLinearGradient(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.left(), rect.bottom())
        )
        vertical_gradient.setColorAt(0, QColor(255, 255, 255, 20))  # Slight highlight at top
        vertical_gradient.setColorAt(1, QColor(0, 0, 0, 30))  # Slight shadow at bottom
        painter.fillRect(rect, QBrush(vertical_gradient))
        painter.restore()

        # Draw cover texture overlay (Phase 2) - only if not hovered
        if not is_hovered:
            painter.save()
            painter.setOpacity(spine_opacity)
            self._draw_texture_overlay(painter, book_id, db, rect)
            painter.restore()

        # Draw selection highlight
        if is_selected:
            painter.setPen(QColor('#ffff00'))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))

        # Thumbnail drawing removed per user request

        # Draw title (rotated vertically) - only if not hovered
        if not is_hovered:
            painter.save()
            painter.setOpacity(spine_opacity)
            painter.translate(rect.left() + rect.width() / 2, rect.top() + rect.height() / 2)
            painter.rotate(-90)

            # Determine text color based on spine background brightness
            text_color = self._get_contrasting_text_color(spine_color)
            painter.setPen(text_color)

            font = QFont()
            font.setPointSize(11)  # Increased from 9
            painter.setFont(font)

            # Truncate title to fit and leave space for status indicator
            fm = QFontMetrics(font)
            max_width = rect.height() - 40
            elided_title = fm.elidedText(title, Qt.TextElideMode.ElideRight, max_width)

            # Shift text up to avoid overlapping status indicator
            text_y_offset = -5
            text_rect = QRect(int(-rect.height() / 2), int(-rect.width() / 2 + text_y_offset), int(rect.height()), int(rect.width()))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided_title)
            painter.restore()

        # Draw hover cover if this book is hovered
        if is_hovered and self._hover_cover_pixmap is not None:
            self._draw_hover_cover(painter, rect)

        # Draw reading status indicator at bottom
        painter.save()
        painter.setOpacity(1.0)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            reading_status = self._get_reading_status(book_id, db, mi)

            if reading_status == 'finished':
                dot_color = QColor('#4CAF50')
            elif reading_status == 'reading':
                dot_color = QColor('#FFC107')
            else:
                dot_color = QColor('#F44336')

            dot_radius = 4
            dot_x = rect.x() + rect.width() // 2
            dot_y = rect.y() + rect.height() - dot_radius - 10

            painter.setBrush(QBrush(dot_color))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
            painter.drawEllipse(QPoint(dot_x, dot_y), dot_radius, dot_radius)

        except Exception as e:
            dot_color = QColor('#9C27B0')
            dot_radius = 4
            dot_x = rect.x() + rect.width() // 2
            dot_y = rect.y() + rect.height() - dot_radius - 10
            painter.setBrush(QBrush(dot_color))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
            painter.drawEllipse(QPoint(dot_x, dot_y), dot_radius, dot_radius)

        painter.restore()

    # Cover integration methods

    def _get_contrasting_text_color(self, background_color):
        '''
        Calculate text color based on background brightness for optimal contrast.

        :param background_color: QColor of the spine background
        :return: QColor for text
        '''
        if background_color is None or not background_color.isValid():
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
        else:
            if luminance > 0.5:
                return self.TEXT_COLOR_DARK
            else:
                return self.TEXT_COLOR

    def _get_spine_color(self, book_id, db):
        '''Get the spine color for a book from cache or by extraction.'''
        if book_id in self._cover_colors:
            cached_color = self._cover_colors[book_id]
            if cached_color is not None and cached_color.isValid():
                return cached_color
            self._cover_colors.pop(book_id, None)

        # Load color from cover
        try:
            color = get_cover_color(book_id, db)
            if color is None or not color.isValid():
                color = self.DEFAULT_SPINE_COLOR
            self._cover_colors[book_id] = color
            return color
        except Exception:
            color = self.DEFAULT_SPINE_COLOR
            self._cover_colors[book_id] = color
            return color

    def _get_spine_thumbnail(self, book_id, db):
        '''Get the spine thumbnail for a book from cache or by generation.'''
        if book_id in self._spine_thumbnails:
            thumb = self._spine_thumbnails[book_id]
            if thumb is not None and not thumb.isNull():
                return thumb
            self._spine_thumbnails.pop(book_id, None)

        try:
            thumbnail = get_spine_thumbnail(book_id, db, self.THUMBNAIL_HEIGHT)
            if thumbnail is not None and not thumbnail.isNull():
                self._spine_thumbnails[book_id] = thumbnail
                return thumbnail
        except Exception:
            pass

        try:
            cover_data = db.cover(book_id, as_image=True)
            if cover_data is not None and not cover_data.isNull():
                cover_width = cover_data.width()
                cover_height = cover_data.height()
                if cover_width > 0 and cover_height > 0:
                    aspect_ratio = cover_width / cover_height
                    thumb_width = int(self.THUMBNAIL_HEIGHT * aspect_ratio)
                    scaled = cover_data.scaled(
                        thumb_width, self.THUMBNAIL_HEIGHT,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    if not scaled.isNull():
                        thumbnail = QPixmap.fromImage(scaled)
                        self._spine_thumbnails[book_id] = thumbnail
                        return thumbnail
        except Exception:
            pass

        return None

    def _get_reading_status(self, book_id, db, mi=None):
        '''
        Determine reading status for a book based on:
        1. Tags containing 'read', 'reading', 'finished', etc.
        2. Custom column '#read' if it exists
        3. Last read position (if available)

        Returns: 'unread', 'reading', or 'finished'
        '''
        try:
            if mi is None:
                mi = db.get_metadata(book_id, index_is_id=True)

            # Method 1: Check tags for reading status (most common method)
            tags = getattr(mi, 'tags', []) or []
            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower in ('finished', 'read', 'completed'):
                    return 'finished'
                elif tag_lower in ('reading', 'in-progress', 'currently-reading', 'in progress'):
                    return 'reading'

            # Method 2: Check custom column '#read' (common convention)
            try:
                read_status = getattr(mi, '#read', None)
                if read_status:
                    status_lower = str(read_status).lower()
                    if 'finish' in status_lower or 'complete' in status_lower or status_lower == 'yes':
                        return 'finished'
                    elif 'progress' in status_lower or 'reading' in status_lower:
                        return 'reading'
            except (AttributeError, TypeError):
                pass

            # Method 3: Check last read position
            try:
                # Get all formats for this book
                formats = getattr(mi, 'formats', []) or []
                if formats:
                    # Check if any format has a last read position
                    for fmt in formats:
                        positions = db.get_last_read_positions(book_id, fmt, '_')
                        if positions:
                            # Has reading progress
                            for pos in positions:
                                pos_frac = pos.get('pos_frac', 0)
                                if pos_frac >= 0.95:  # 95% or more = finished
                                    return 'finished'
                                elif pos_frac > 0.01:  # More than 1% = reading
                                    return 'reading'
            except (AttributeError, TypeError, KeyError):
                pass

            return 'unread'
        except Exception:
            return 'unread'

    def _draw_texture_overlay(self, painter, book_id, db, rect):
        '''Draw cover texture overlay on spine.'''
        try:
            cover_data = db.cover(book_id, as_image=True)
            if cover_data is None or cover_data.isNull():
                return

            # Extract left edge for texture (10px wide)
            edge_width = min(10, rect.width())
            if cover_data.width() > 0:
                # Get left edge of cover
                edge_rect = QRect(0, 0, edge_width, cover_data.height())
                edge_image = cover_data.copy(edge_rect)

                # Scale to spine height
                scaled_edge = edge_image.scaled(
                    edge_width, rect.height(),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                # Draw with opacity
                painter.save()
                painter.setOpacity(0.3)  # 30% opacity
                painter.drawPixmap(rect.left(), rect.top(), QPixmap.fromImage(scaled_edge))
                painter.restore()
        except Exception:
            # Silently fail if texture overlay can't be drawn
            pass

    def _draw_hover_cover(self, painter, spine_rect):
        '''Draw the hover cover popup at the spine position (like JSX mock).

        The cover replaces the spine when hovered, appearing at the same position
        with full spine height (150px) and smooth fade-in animation.
        '''
        if self._hover_cover_pixmap is None or self._hover_cover_pixmap.isNull():
            return

        # Use the already-scaled pixmap dimensions (it was scaled in _load_hover_cover)
        cover_width = self._hover_cover_pixmap.width()
        cover_height = self._hover_cover_pixmap.height()

        # Position cover at spine position - left edge aligned with spine left edge
        # The cover replaces the spine, so left edge stays at original spine position
        popup_x = spine_rect.left()  # Left edge aligned with original spine
        popup_y = spine_rect.top()  # Same vertical position as spine

        # Draw shadow with blur effect (like JSX mock: 6px 6px 18px rgba(0,0,0,0.45))
        # Qt doesn't have native blur, so we'll use a darker shadow
        shadow_offset = 6
        shadow_blur = 3
        shadow_rect = QRect(
            popup_x + shadow_offset, 
            popup_y + shadow_offset, 
            cover_width, 
            cover_height
        )
        # Draw multiple shadow layers for blur effect
        for i in range(shadow_blur):
            alpha = int(115 * (1 - i / shadow_blur))  # 0.45 opacity = ~115 alpha
            shadow_color = QColor(0, 0, 0, alpha)
            shadow_layer = QRect(
                shadow_rect.x() + i,
                shadow_rect.y() + i,
                shadow_rect.width(),
                shadow_rect.height()
            )
            painter.fillRect(shadow_layer, shadow_color)

        # Draw cover with smooth fade-in (opacity transition)
        cover_rect = QRect(popup_x, popup_y, cover_width, cover_height)
        painter.save()
        painter.setOpacity(self._hover_cover_opacity)
        painter.drawPixmap(cover_rect, self._hover_cover_pixmap)
        painter.restore()

        # Add subtle gradient overlay (like JSX mock: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%))
        painter.save()
        overlay_gradient = QLinearGradient(
            QPointF(cover_rect.left(), cover_rect.top()),
            QPointF(cover_rect.right(), cover_rect.bottom())
        )
        overlay_gradient.setColorAt(0, QColor(255, 255, 255, 31))  # 0.12 opacity = ~31 alpha
        overlay_gradient.setColorAt(0.5, QColor(255, 255, 255, 0))
        overlay_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(cover_rect, QBrush(overlay_gradient))
        painter.restore()

    def _load_visible_covers(self):
        '''Load covers for visible books (lazy loading).'''
        if self._model is None:
            return

        scroll_y = self.verticalScrollBar().value()
        viewport_rect = self.viewport().rect()
        visible_rect = QRect(
            viewport_rect.x(),
            viewport_rect.y() + scroll_y,
            viewport_rect.width(),
            viewport_rect.height()
        )

        row_count = self._model.rowCount(QModelIndex())
        if row_count == 0:
            return

        db = self._model.db
        x_pos = 10  # Start position (no label area - dividers are inline)
        shelf_y = 10

        # Load covers for visible books
        # Use same layout logic as paintEvent (flattened items with grouping)
        all_rows = list(range(row_count))
        groups = group_books(all_rows, self._model, self._grouping_mode)

        # Flatten groups into a list of (row, group_name) tuples
        flattened_items = []
        for group_name, group_rows in groups:
            for row in group_rows:
                flattened_items.append((row, group_name))

        last_group_name = None
        for row, group_name in flattened_items:
            # Account for inline divider when group changes
            if self._grouping_mode != 'none' and group_name != last_group_name and last_group_name is not None:
                x_pos += 32  # DIVIDER_WIDTH (30) + gap (2)
            last_group_name = group_name
            try:
                index = self._model.index(row, 0)
                if not index.isValid():
                    continue

                book_id = self._model.id(index)
                mi = db.get_metadata(book_id, index_is_id=True)
                pages = self._get_page_count(book_id, db, mi)
                spine_width = self._calculate_spine_width(pages)
            except (AttributeError, IndexError, KeyError, TypeError):
                spine_width = 40

            spine_rect = QRect(x_pos, shelf_y, int(spine_width), self.SPINE_HEIGHT)

            # Check if spine is visible
            if spine_rect.bottom() >= visible_rect.top() and spine_rect.top() <= visible_rect.bottom():
                # Load color and thumbnail if not already cached
                if book_id not in self._cover_colors:
                    self._get_spine_color(book_id, db)
                # Always try to load thumbnail (will use cache if available)
                thumb = self._get_spine_thumbnail(book_id, db)
                # If thumbnail loaded, trigger repaint
                if thumb is not None and book_id not in self._spine_thumbnails:
                    self.viewport().update()

            x_pos += int(spine_width) + 2

            # Check if we need to move to next shelf
            if x_pos + spine_width > viewport_rect.width() - 10:
                x_pos = 10  # Reset to start position
                shelf_y += self.SHELF_SPACING
                # Early exit if we've scrolled past visible area
                if shelf_y > visible_rect.bottom() + self.SPINE_HEIGHT:
                    break

    def _calculate_shelf_y_for_row(self, row, scroll_y, viewport_width):
        '''Calculate which shelf y position a given row would be on.'''
        if self._model is None or row < 0:
            return 10 + scroll_y

        shelf_y = 10 + scroll_y
        x_pos = 10
        db = self._model.db

        for r in range(row + 1):  # Iterate up to and including the target row
            try:
                index = self._model.index(r, 0)
                if index.isValid():
                    book_id = self._model.id(index)
                    mi = db.get_metadata(book_id, index_is_id=True)
                    pages = self._get_page_count(book_id, db, mi)
                    spine_width = self._calculate_spine_width(pages)
                else:
                    spine_width = 40
            except (AttributeError, IndexError, KeyError, TypeError):
                spine_width = 40

            # Check if current book would overflow before adding it
            if x_pos + int(spine_width) > viewport_width - 10:
                # Move to next shelf
                x_pos = 10
                shelf_y += self.SHELF_SPACING

            # Add the current book's width
            x_pos += int(spine_width) + 2

        return shelf_y

    def _update_hover_fade(self):
        '''Update hover cover fade-in animation and shift progress.'''
        if self._hover_fade_start_time is None:
            self._hover_fade_timer.stop()
            return

        elapsed = (time() - self._hover_fade_start_time) * 1000  # Convert to ms
        duration = 200  # 200ms like JSX mock

        if elapsed >= duration:
            self._hover_cover_opacity = 1.0
            self._hover_shift_progress = 1.0
            self._hover_fade_timer.stop()
            self._hover_fade_start_time = None
        else:
            # Cubic ease-out curve (similar to JSX mock)
            # Ease-out cubic: 1 - (1 - t)^3
            # Interpolate from 0.3 to 1.0 for opacity
            t = elapsed / duration
            progress = 1.0 - (1.0 - t) ** 3
            # Interpolate opacity from 0.3 (start) to 1.0 (end)
            self._hover_cover_opacity = 0.3 + (1.0 - 0.3) * progress
            self._hover_shift_progress = progress

        self.viewport().update()

    def _load_hover_cover(self, book_id, db):
        '''Load full cover for hover popup with smooth fade-in animation.'''
        # Always load fresh cover - don't check if already loaded
        # This ensures we get the correct cover for the hovered book
        try:
            # Try multiple methods to get cover
            cover_data = None
            try:
                cover_data = db.cover(book_id, index_is_id=True, as_image=True)
            except (TypeError, AttributeError):
                try:
                    cover_data = db.cover(book_id, as_image=True)
                except Exception:
                    pass

            if cover_data is None or cover_data.isNull():
                self._hover_cover_pixmap = None
                self._hover_cover_row = -1
                self._hover_cover_opacity = 1.0
                return

            # Scale to hover size - use full spine height, calculate width from aspect ratio
            cover_height = self.SPINE_HEIGHT  # Use full spine height (150px)

            # Calculate proper aspect ratio to determine width
            if cover_data.width() > 0 and cover_data.height() > 0:
                cover_aspect = cover_data.width() / cover_data.height()
                # Calculate width to maintain aspect ratio with spine height
                cover_width = int(cover_height * cover_aspect)
                # But limit to reasonable max width (use HOVER_EXPANDED_WIDTH as max)
                cover_width = min(cover_width, self.HOVER_EXPANDED_WIDTH)
            else:
                # Fallback dimensions
                cover_width = self.HOVER_COVER_WIDTH
                cover_height = self.SPINE_HEIGHT

            self._hover_cover_pixmap = QPixmap.fromImage(cover_data).scaled(
                cover_width, cover_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._hover_cover_row = book_id

            # Start fade-in animation (like JSX mock: 0.2s ease transition)
            # Start with full opacity immediately for instant feedback
            self._hover_cover_opacity = 1.0
            self._hover_shift_progress = 1.0  # Start at full expansion for instant feedback
            # Still start timer for smooth animation if needed, but start at full
            self._hover_fade_start_time = time()
            if not self._hover_fade_timer.isActive():
                self._hover_fade_timer.start(16)  # ~60fps updates

            # Trigger immediate repaint to show the cover
            self.viewport().update()
        except Exception:
            self._hover_cover_pixmap = None
            self._hover_cover_row = -1
            self._hover_cover_opacity = 1.0

    # Sort interface methods (required for SortByAction integration)

    def sort_by_named_field(self, field, order, reset=True):
        '''Sort by a named field.'''
        if self._model is None:
            return
        if isinstance(order, Qt.SortOrder):
            order = order == Qt.SortOrder.AscendingOrder
        self._model.sort_by_named_field(field, order, reset)
        self.viewport().update()

    def reverse_sort(self):
        '''Reverse the current sort order.'''
        if self._model is None:
            return
        m = self.model()
        try:
            sort_col, order = m.sorted_on
        except (TypeError, AttributeError):
            sort_col, order = 'date', True
        self.sort_by_named_field(sort_col, not order)

    def resort(self):
        '''Re-apply the current sort.'''
        if self._model is None:
            return
        self._model.resort(reset=True)
        self.viewport().update()

    def intelligent_sort(self, field, ascending):
        '''Smart sort that toggles if already sorted on that field.'''
        if self._model is None:
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
        if self._model is None or len(fields) == 0:
            return

        # Delegate to model's multisort capability
        # This is a simplified version - full implementation would match BooksView
        for field, ascending in reversed(fields):
            if field in list(self._model.db.field_metadata.keys()):
                self.sort_by_named_field(field, ascending, reset=reset)
                reset = False  # Only reset on first sort

    # Selection methods (required for AlternateViews integration)

    def set_current_row(self, row):
        '''Set the current row.'''
        if self._model is None or self._selection_model is None:
            return
        if 0 <= row < self._model.rowCount(QModelIndex()):
            self._current_row = row
            index = self._model.index(row, 0)
            if index.isValid():
                self._selection_model.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.viewport().update()
            # Scroll to make row visible
            self._scroll_to_row(row)

    def select_rows(self, rows, using_ids=False):
        '''Select the specified rows.

        Args:
            rows: List of row indices or book IDs
            using_ids: If True, rows contains book IDs; if False, rows contains row indices
        '''
        if self._model is None or self._selection_model is None:
            return

        # Convert book IDs to row indices if needed
        if using_ids:
            row_indices = []
            for book_id in rows:
                try:
                    row = self._model.db.data.id_to_index(book_id)
                    if row >= 0:
                        row_indices.append(row)
                except (AttributeError, KeyError, ValueError, TypeError):
                    pass
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
        self.viewport().update()

    def _scroll_to_row(self, row):
        '''Scroll to make the specified row visible.'''
        # Simplified scrolling - will improve in Phase 2
        # For now, just update viewport
        self.viewport().update()

    # Database methods

    def set_database(self, db, stage=0):
        '''Set the database.'''
        self.dbref = lambda: db
        # Ensure connection to main view selection is established
        # (in case it wasn't ready when setModel was called)
        self._connect_to_main_view_selection()
        if stage == 0 and self._model is not None:
            # Model will be updated by AlternateViews
            # Clear caches when database changes
            self._cover_colors.clear()
            self._spine_thumbnails.clear()
            invalidate_caches()
            # Force repaint to reload colors
            self.viewport().update()

    def refresh_colors(self):
        '''Force refresh of all spine colors.'''
        self._cover_colors.clear()
        invalidate_caches()
        self.viewport().update()

    def shown(self):
        '''Called when this view becomes active.'''
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.viewport().update()

    def set_context_menu(self, menu):
        '''Set the context menu.'''
        self.context_menu = menu

    def contextMenuEvent(self, event):
        '''Handle context menu events.'''
        from calibre.constants import islinux
        from calibre.gui2.main_window import clone_menu
        from qt.core import QMenu

        # Create menu with grouping options
        m = QMenu(self)

        # Add grouping submenu
        grouping_menu = m.addMenu(_('Group by'))

        # Group by None
        none_action = grouping_menu.addAction(_('None'))
        none_action.setCheckable(True)
        none_action.setChecked(self._grouping_mode == 'none')
        none_action.triggered.connect(lambda: self._set_grouping_mode('none'))

        grouping_menu.addSeparator()

        # Group by Author
        author_action = grouping_menu.addAction(_('Author'))
        author_action.setCheckable(True)
        author_action.setChecked(self._grouping_mode == 'author')
        author_action.triggered.connect(lambda: self._set_grouping_mode('author'))

        # Group by Series
        series_action = grouping_menu.addAction(_('Series'))
        series_action.setCheckable(True)
        series_action.setChecked(self._grouping_mode == 'series')
        series_action.triggered.connect(lambda: self._set_grouping_mode('series'))

        # Group by Genre
        genre_action = grouping_menu.addAction(_('Genre'))
        genre_action.setCheckable(True)
        genre_action.setChecked(self._grouping_mode == 'genre')
        genre_action.triggered.connect(lambda: self._set_grouping_mode('genre'))

        # Group by Publisher
        publisher_action = grouping_menu.addAction(_('Publisher'))
        publisher_action.setCheckable(True)
        publisher_action.setChecked(self._grouping_mode == 'publisher')
        publisher_action.triggered.connect(lambda: self._set_grouping_mode('publisher'))

        # Group by Rating
        rating_action = grouping_menu.addAction(_('Rating'))
        rating_action.setCheckable(True)
        rating_action.setChecked(self._grouping_mode == 'rating')
        rating_action.triggered.connect(lambda: self._set_grouping_mode('rating'))

        # Group by Language
        language_action = grouping_menu.addAction(_('Language'))
        language_action.setCheckable(True)
        language_action.setChecked(self._grouping_mode == 'language')
        language_action.triggered.connect(lambda: self._set_grouping_mode('language'))

        # Group by Time Period
        time_action = grouping_menu.addAction(_('Time Period'))
        time_action.setCheckable(True)
        time_action.setChecked(self._grouping_mode == 'time_period')
        time_action.triggered.connect(lambda: self._set_grouping_mode('time_period'))

        # Add standard context menu items if available
        if self.context_menu is not None:
            m.addSeparator()
            # Clone actions to avoid issues with menu ownership
            for action in self.context_menu.actions():
                m.addAction(action)

        # Show menu
        if islinux:
            m = clone_menu(m)
        m.popup(event.globalPos())
        event.accept()

    def _set_grouping_mode(self, mode):
        '''Set the grouping mode and refresh display.'''
        self._grouping_mode = mode
        gprefs['bookshelf_grouping_mode'] = mode
        self._update_scrollbar_ranges()
        self.viewport().update()

    def get_selected_ids(self):
        '''Get selected book IDs.'''
        if self._model is None:
            return []
        return [self._model.id(self._model.index(row, 0)) for row in self._selected_rows]

    def current_book_state(self):
        '''Get current book state for restoration.'''
        if self._current_row >= 0 and self._model is not None:
            try:
                return self._model.id(self._model.index(self._current_row, 0))
            except (IndexError, ValueError, KeyError, TypeError, AttributeError):
                pass
        return None

    def restore_current_book_state(self, state):
        '''Restore current book state.'''
        if state is None or self._model is None:
            return
        book_id = state
        try:
            row = self._model.db.data.id_to_index(book_id)
            self.set_current_row(row)
            self.select_rows([row])
        except (IndexError, ValueError, KeyError, TypeError, AttributeError):
            pass

    def marked_changed(self, old_marked, current_marked):
        '''Handle marked books changes.'''
        # Refresh display if marked books changed
        self.viewport().update()

    def indices_for_merge(self, resolved=True):
        '''Get indices for merge operations.'''
        if self._model is None:
            return []
        return [self._model.index(row, 0) for row in self._selected_rows]

    # Mouse and keyboard events

    def viewportEvent(self, event):
        '''Handle viewport events - this is where mouse events on QAbstractScrollArea go.'''
        if event.type() == QEvent.Type.MouseButtonPress:
            handled = self._handle_mouse_press(event)
            if handled:
                return True
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            handled = self._handle_mouse_double_click(event)
            if handled:
                return True
        elif event.type() == QEvent.Type.MouseMove:
            # Handle hover detection
            self._handle_mouse_move(event)
        elif event.type() == QEvent.Type.Leave:
            # Clear hover when mouse leaves viewport
            if self._hovered_row >= 0:
                self._hovered_row = -1
                self._hover_cover_pixmap = None
                self._hover_cover_row = -1
                self._hover_cover_opacity = 1.0
                self._hover_shift_progress = 0.0
                self._hover_fade_timer.stop()
                self._hover_fade_start_time = None
                self.viewport().update()
        return super().viewportEvent(event)

    def _handle_mouse_move(self, ev):
        '''Handle mouse move events for hover detection.'''
        if self._model is None:
            return

        pos = ev.pos()
        row = self._book_at_position(pos.x(), pos.y())

        if row != self._hovered_row:
            # Hover changed - clear old cover first
            old_hovered = self._hovered_row
            self._hovered_row = row

            # Clear old hover cover when changing hover
            self._hover_cover_pixmap = None
            self._hover_cover_row = -1
            self._hover_cover_opacity = 1.0
            self._hover_shift_progress = 0.0
            self._hover_fade_timer.stop()
            self._hover_fade_start_time = None

            # Load hover cover if hovering over a book
            if row >= 0:
                try:
                    index = self._model.index(row, 0)
                    if index.isValid():
                        book_id = self._model.id(index)
                        db = self._model.db
                        self._load_hover_cover(book_id, db)
                except (AttributeError, IndexError, KeyError, TypeError):
                    pass

            # Update viewport to show/hide hover cover
            if old_hovered != row:
                self.viewport().update()

    def _handle_mouse_press(self, ev):
        '''Handle mouse press events on the viewport.'''
        if self._model is None:
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

            self.viewport().update()
            ev.accept()
            return True

        # No book was clicked
        return False

    def _handle_mouse_double_click(self, ev):
        '''Handle mouse double-click events on the viewport.'''
        if self._model is None:
            return False

        pos = ev.pos()
        row = self._book_at_position(pos.x(), pos.y())
        if row >= 0:
            # Set as current row first
            self._current_row = row
            # Open the book
            try:
                from calibre.gui2.ui import get_gui
                book_id = self._model.id(self._model.index(row, 0))
                gui = get_gui()
                if gui:
                    gui.iactions['View'].view_triggered(book_id)
                    return True
            except (IndexError, ValueError, KeyError, TypeError, AttributeError):
                pass
        return False

    def _connect_to_main_view_selection(self):
        '''Connect to the main library view's selection model to sync selection.'''
        if self.gui is None or not hasattr(self.gui, 'library_view'):
            return

        try:
            library_view = self.gui.library_view
            if library_view is None:
                return

            selection_model = library_view.selectionModel()
            if selection_model is not None:
                # Disconnect any existing connections to avoid duplicates
                try:
                    selection_model.currentChanged.disconnect(self._main_current_changed)
                except (TypeError, RuntimeError):
                    pass
                try:
                    selection_model.selectionChanged.disconnect(self._main_selection_changed)
                except (TypeError, RuntimeError):
                    pass

                # Connect to selection changes from main view
                selection_model.currentChanged.connect(self._main_current_changed)
                selection_model.selectionChanged.connect(self._main_selection_changed)
        except (AttributeError, TypeError):
            pass

    def _main_current_changed(self, current, previous):
        '''Handle current row change from main library view.'''
        if self._syncing_from_main or self._model is None:
            return

        try:
            if current.isValid():
                row = current.row()
                if 0 <= row < self._model.rowCount(QModelIndex()):
                    self._syncing_from_main = True
                    self.set_current_row(row)
                    self._syncing_from_main = False
            else:
                self._syncing_from_main = True
                self._current_row = -1
                self.viewport().update()
                self._syncing_from_main = False
        except (IndexError, ValueError, AttributeError, TypeError):
            self._syncing_from_main = False

    def _main_selection_changed(self, selected, deselected):
        '''Handle selection change from main library view.'''
        if self._syncing_from_main or self._model is None:
            return

        try:
            library_view = self.gui.library_view
            if library_view is None:
                return

            # Get selected rows from main view
            selected_indexes = library_view.selectionModel().selectedIndexes()
            rows = {idx.row() for idx in selected_indexes if idx.isValid()}

            self._syncing_from_main = True
            self.select_rows(list(rows), using_ids=False)
            self._syncing_from_main = False
        except (AttributeError, TypeError, ValueError):
            self._syncing_from_main = False

    def _sync_selection_to_main_view(self):
        '''Sync selection with the main library view.'''
        if self._syncing_from_main or self.gui is None or not hasattr(self.gui, 'library_view'):
            return
        try:
            library_view = self.gui.library_view
            if self._current_row >= 0 and self._model is not None:
                # Get book ID from current row
                book_id = self._model.id(self._model.index(self._current_row, 0))
                # Select in library view
                library_view.select_rows([book_id], using_ids=True)
        except (IndexError, ValueError, KeyError, TypeError, AttributeError):
            pass

    def mouseDoubleClickEvent(self, ev):
        '''Handle double-click to open book.'''
        # Double-click is handled in viewportEvent
        super().mouseDoubleClickEvent(ev)

    def _book_at_position(self, x, y):
        '''Find which book is at the given position. 
        x, y are in viewport coordinates.
        Returns row or -1.'''
        if self._model is None:
            return -1

        row_count = self._model.rowCount(QModelIndex())
        if row_count == 0:
            return -1

        # Convert viewport coordinates to content coordinates
        scroll_y = self.verticalScrollBar().value()
        content_y = y + scroll_y

        # Use same layout logic as paintEvent (flattened items with grouping)
        all_rows = list(range(row_count))
        groups = group_books(all_rows, self._model, self._grouping_mode)

        # Flatten groups into a list of (row, group_name) tuples
        flattened_items = []
        for group_name, group_rows in groups:
            for row in group_rows:
                flattened_items.append((row, group_name))

        # Use same shelf layout calculation as paintEvent
        shelf_layouts = self._calculate_shelf_layouts(flattened_items, self.viewport().width())

        # Pre-calculate hover shift amount (same as paintEvent)
        hover_shift_amount = 0
        hover_spine_width = 0
        if self._hovered_row >= 0:
            try:
                hover_index = self._model.index(self._hovered_row, 0)
                if hover_index.isValid():
                    hover_book_id = self._model.id(hover_index)
                    db = self._model.db
                    hover_mi = db.get_metadata(hover_book_id, index_is_id=True)
                    hover_pages = self._get_page_count(hover_book_id, db, hover_mi)
                    hover_spine_width = self._calculate_spine_width(hover_pages)
                    hover_shift_amount = max(0, self.HOVER_EXPANDED_WIDTH - hover_spine_width) * self._hover_shift_progress
            except (AttributeError, IndexError, KeyError, TypeError):
                pass

        shelf_y = 10

        for shelf_items in shelf_layouts:
            # Get starting x position for this shelf (centered)
            base_x_pos = shelf_items['start_x']
            shelf_start_row = shelf_items['start_row']
            last_group_name = None

            for row, group_name in shelf_items['items']:
                # Account for inline divider when group changes
                if self._grouping_mode != 'none' and group_name != last_group_name and last_group_name is not None:
                    base_x_pos += 32  # DIVIDER_WIDTH (30) + gap (2)
                last_group_name = group_name

                # Calculate spine width from page count
                try:
                    index = self._model.index(row, 0)
                    if index.isValid():
                        book_id = self._model.id(index)
                        db = self._model.db
                        mi = db.get_metadata(book_id, index_is_id=True)
                        pages = self._get_page_count(book_id, db, mi)
                        spine_width = self._calculate_spine_width(pages)
                    else:
                        spine_width = 40
                except (AttributeError, IndexError, KeyError, TypeError):
                    spine_width = 40

                # Check if this book is hovered
                is_hovered = row == self._hovered_row

                # Calculate display position and width (same as paintEvent with cumulative positioning)
                if is_hovered:
                    # Hovered book: use expanded width at base position
                    display_width = self.HOVER_EXPANDED_WIDTH
                    current_x = base_x_pos
                    width_to_add = self.HOVER_EXPANDED_WIDTH
                else:
                    # Non-hovered book: use spine width at base position
                    display_width = int(spine_width)
                    current_x = base_x_pos
                    width_to_add = spine_width

                spine_rect = QRect(int(current_x), shelf_y, display_width, self.SPINE_HEIGHT)

                # Check if point is within this spine
                if spine_rect.contains(x, content_y):
                    return row

                # Update base_x_pos for next book - use actual width (expanded for hovered, spine for others)
                base_x_pos += int(width_to_add) + 2

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
        if row >= 0 and self._model is not None:
            return self._model.index(row, 0)
        return QModelIndex()

    def currentIndex(self):
        '''Return the current model index (required for drag/drop).'''
        if self._current_row >= 0 and self._model is not None:
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
        from calibre.constants import islinux
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
# }}}
