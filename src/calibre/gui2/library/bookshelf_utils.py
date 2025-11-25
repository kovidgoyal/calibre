#!/usr/bin/env python

__license__ = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict
from io import BytesIO
from threading import Lock

from qt.core import (
    QColor,
    QImage,
    QPainter,
    QPixmap,
    QRect,
    Qt,
    qBlue,
    qGreen,
    qRed,
)

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


def extract_dominant_color(image_data, fallback_color='#8B4513'):
    '''
    Extract the dominant color from an image.

    :param image_data: Image data as bytes, QImage, QPixmap, or PIL Image
    :param fallback_color: Fallback color if extraction fails (default: brown)
    :return: QColor representing the dominant color
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

        # Get pixel data and use frequency-based extraction with saturation preference
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

        # Prefer more saturated colors if dominant is too gray
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

    # Resize to small size for performance (100x100 for better color accuracy)
    pil_image.thumbnail((100, 100), Image.Resampling.LANCZOS)

    # Convert to RGB if needed
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')

    # Extract dominant color using improved algorithm
    # Use less aggressive quantization to preserve color variety
    # Quantize to 32 levels per channel (better color preservation)
    color_counts = defaultdict(int)
    pixels = pil_image.getdata()
    
    for pixel in pixels:
        r, g, b = pixel
        # Quantize to 32 levels per channel (8 levels instead of 16)
        # This preserves more color variety while still grouping similar colors
        r_q = (r // 8) * 8
        g_q = (g // 8) * 8
        b_q = (b // 8) * 8
        color_counts[(r_q, g_q, b_q)] += 1

    if not color_counts:
        return QColor(fallback_color)

    # Find most common color, but prefer more saturated/vibrant colors
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
        # Prefer colors with higher frequency and reasonable saturation
        return (count, saturation * 100)

    # Get top colors by frequency
    sorted_colors = sorted(color_counts.items(), key=color_score, reverse=True)
    
    # Take the most frequent color, but if it's very desaturated (gray/brown),
    # try to find a more colorful alternative
    dominant_color = sorted_colors[0][0]
    
    # If the dominant color is too desaturated, look for a more vibrant alternative
    r, g, b = dominant_color
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    saturation = (max_val - min_val) / max_val if max_val > 0 else 0
    
    # If saturation is very low (< 0.2), try to find a more colorful color
    if saturation < 0.2 and len(sorted_colors) > 1:
        for (r2, g2, b2), count in sorted_colors[1:5]:  # Check top 5 alternatives
            max_val2 = max(r2, g2, b2)
            min_val2 = min(r2, g2, b2)
            sat2 = (max_val2 - min_val2) / max_val2 if max_val2 > 0 else 0
            # Use this color if it's more saturated and still reasonably frequent
            if sat2 > 0.3 and count > len(pixels) * 0.05:  # At least 5% of pixels
                dominant_color = (r2, g2, b2)
                break
    
    return QColor(dominant_color[0], dominant_color[1], dominant_color[2])


def get_cover_color(book_id, db, cache_key=None):
    '''
    Get the dominant color from a book's cover, with caching.

    :param book_id: Book ID
    :param db: Database reference (can be LibraryDatabase2 or Cache instance)
    :param cache_key: Optional cache key (book_id + timestamp for invalidation)
    :return: QColor representing the dominant color
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
    # Note: db can be LibraryDatabase2 (needs index_is_id=True) or Cache (direct book_id)
    # Also try new_api if available (like GridView does)
    color = None
    cover_data = None
    
    # Method 1: Try new_api.cover_or_cache (preferred method for LibraryDatabase2)
    try:
        if hasattr(db, 'new_api') and hasattr(db.new_api, 'cover_or_cache'):
            has_cover, cdata, timestamp = db.new_api.cover_or_cache(book_id, 0, as_what='pil_image')
            if has_cover and cdata is not None:
                # cdata is a PIL Image when as_what='pil_image'
                color = extract_dominant_color(cdata)
                if color is not None and color.isValid() and color != QColor('#8B4513'):
                    # Only use this color if it's valid and not the default fallback
                    pass  # color is already set
                else:
                    color = None  # Try other methods
    except Exception:
        pass
    
    # Method 2: Try as_image (QImage) - try with index_is_id first, then without
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
                from qt.core import QImage
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
                from qt.core import QImage
                qimg = QImage(cover_path)
                if not qimg.isNull():
                    color = extract_dominant_color(qimg)
        except Exception:
            pass
    
    # Final fallback - only use default if we truly couldn't extract a color
    # Don't cache the default color - let it retry next time
    if color is None or not color.isValid():
        return QColor('#8B4513')  # Default brown (not cached)

    # Only cache successfully extracted colors (not the default fallback)
    # This allows retrying if extraction failed temporarily
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
    Generate a small thumbnail for display on the spine.

    :param cover_data: Cover image as bytes, QImage, QPixmap, or PIL Image
    :param target_height: Target height in pixels (default: 20)
    :return: QPixmap thumbnail or None if generation fails
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

    # Scale to target height while maintaining aspect ratio
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
    Get a thumbnail for display on the spine, with caching.

    :param book_id: Book ID
    :param db: Database reference
    :param target_height: Target height in pixels (default: 20)
    :param cache_key: Optional cache key (book_id + timestamp for invalidation)
    :return: QPixmap thumbnail or None
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
    Extract the left edge of a cover image for use as a texture overlay.

    :param cover_data: Cover image as bytes, QImage, QPixmap, or PIL Image
    :param edge_width: Width of edge to extract in pixels (default: 10)
    :param opacity: Opacity for the texture (0.0 to 1.0, default: 0.3)
    :return: QPixmap of the edge texture or None
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
    Invalidate cached colors and thumbnails for specified books.

    :param book_ids: List of book IDs to invalidate, or None to clear all
    '''
    global _color_cache, _thumbnail_cache

    with _color_cache_lock:
        if book_ids is None:
            _color_cache.clear()
        else:
            # Remove entries matching any book_id (cache keys may be book_id or tuples)
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

