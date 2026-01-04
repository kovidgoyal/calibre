#!/usr/bin/env python
# License: GPLv3
# Copyright: Andy C <achuongdev@gmail.com>, un_pogaz <un.pogaz@gmail.com>, Kovid Goyal <kovid@kovidgoyal.net>

# TODO:
# Remove py_dominant_color after beta release

# Imports {{{
import bisect
import math
import random
import struct
import weakref
from collections.abc import Iterable, Iterator
from contextlib import suppress
from functools import lru_cache, partial
from operator import attrgetter
from queue import LifoQueue, ShutDown
from threading import Event, RLock, Thread, current_thread
from typing import NamedTuple

from qt.core import (
    QAbstractItemView,
    QAbstractScrollArea,
    QBrush,
    QBuffer,
    QColor,
    QContextMenuEvent,
    QEasingCurve,
    QEvent,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QItemSelection,
    QItemSelectionModel,
    QKeyEvent,
    QKeySequence,
    QLinearGradient,
    QLocale,
    QMenu,
    QModelIndex,
    QMouseEvent,
    QObject,
    QPainter,
    QPaintEvent,
    QPalette,
    QParallelAnimationGroup,
    QPen,
    QPixmap,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QResizeEvent,
    QSize,
    QSizeF,
    QStyle,
    Qt,
    QTimer,
    QWidget,
    pyqtProperty,
    pyqtSignal,
)
from xxhash import xxh3_64_intdigest

from calibre import fit_image
from calibre.db.cache import Cache
from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2 import config, gprefs, is_dark_theme
from calibre.gui2.library.alternate_views import ClickStartData, handle_selection_click, handle_selection_drag, selection_for_rows, setup_dnd_interface
from calibre.gui2.library.caches import CoverThumbnailCache, Thumbnailer
from calibre.gui2.library.models import BooksModel
from calibre.gui2.momentum_scroll import MomentumScrollMixin
from calibre.gui2.palette import dark_palette, light_palette
from calibre.utils.icu import numeric_sort_key
from calibre.utils.img import resize_to_fit
from calibre.utils.iso8601 import UNDEFINED_DATE
from calibre.utils.localization import lang_map
from calibre_extensions.imageops import dominant_color

# }}}


TEMPLATE_ERROR_COLOR = QColor('#9C27B0')
TEMPLATE_ERROR = _('TEMPLATE ERROR')


# Utility functions {{{

def random_from_id(book_id: int, limit: int = 21) -> int:
    ' Return a pseudo random integer in [0, limit) that is fully determined by book_id '
    return xxh3_64_intdigest(b'', seed=book_id) % limit


def normalised_size(size_bytes: int) -> float:
    '''Estimate page count from file size.'''
    # Average ebook: ~1-2KB per page, so estimate pages from size
    if size_bytes and size_bytes > 0:
        # Estimate: ~1500 bytes per page (conservative)
        estimated_pages = size_bytes // 1500
        # Normalise the value
        return min(estimated_pages / 2000, 1)
    return 0.

# }}}


# Cover functions {{{

class WoodTheme(NamedTuple):
    background: QColor
    # Main wood body gradient colors (top to bottom)
    wood_top: QColor
    wood_mid_light: QColor
    wood_mid_dark: QColor
    wood_bottom: QColor

    # Wood grain color
    grain_color: QColor
    grain_alpha_range: tuple[int, int]

    # Knot colors
    knot_color: QColor

    # Highlight and shadow
    highlight_color: QColor
    shadow_color: QColor

    # Edge colors
    edge_color: QColor
    end_grain_dark: QColor
    end_grain_light: QColor

    # Bevel colors
    bevel_light: QColor
    bevel_dark: QColor

    # Bookcase colors
    back_panel_base: QColor
    back_panel_dark: QColor
    side_panel_base: QColor
    side_panel_dark: QColor
    inner_shadow_color: QColor
    cavity_color: QColor

    @classmethod
    def light_theme(cls) -> 'WoodTheme':
        # Light oak/pine colors for light mode
        return WoodTheme(
            background=QColor(245, 245, 245),

            wood_top=QColor(210, 170, 125),
            wood_mid_light=QColor(190, 150, 105),
            wood_mid_dark=QColor(170, 130, 90),
            wood_bottom=QColor(150, 115, 75),

            grain_color=QColor(120, 80, 50),
            grain_alpha_range=(15, 40),

            knot_color=QColor(100, 65, 40, 50),

            highlight_color=QColor(255, 255, 255, 80),
            shadow_color=QColor(0, 0, 0, 30),

            edge_color=QColor(120, 85, 55),
            end_grain_dark=QColor(130, 95, 65),
            end_grain_light=QColor(170, 130, 95),

            bevel_light=QColor(230, 195, 160, 100),
            bevel_dark=QColor(100, 70, 45, 80),

            back_panel_base=QColor(160, 120, 80),
            back_panel_dark=QColor(130, 95, 60),
            side_panel_base=QColor(175, 135, 95),
            side_panel_dark=QColor(145, 105, 70),
            inner_shadow_color=QColor(60, 40, 25, 20),
            cavity_color=QColor(90, 60, 40),
        )

    @classmethod
    def dark_theme(cls) -> 'WoodTheme':
        # Dark walnut/mahogany colors for dark mode
        return WoodTheme(
            background=QColor(30, 30, 35),

            wood_top=QColor(85, 55, 40),
            wood_mid_light=QColor(70, 45, 32),
            wood_mid_dark=QColor(55, 35, 25),
            wood_bottom=QColor(42, 28, 20),

            grain_color=QColor(30, 18, 12),
            grain_alpha_range=(20, 50),

            knot_color=QColor(25, 15, 10, 60),

            highlight_color=QColor(255, 220, 180, 35),
            shadow_color=QColor(0, 0, 0, 50),

            edge_color=QColor(35, 22, 15),
            end_grain_dark=QColor(30, 20, 14),
            end_grain_light=QColor(65, 42, 30),

            bevel_light=QColor(120, 85, 60, 70),
            bevel_dark=QColor(20, 12, 8, 90),

            back_panel_base=QColor(45, 30, 22),
            back_panel_dark=QColor(30, 20, 14),
            side_panel_base=QColor(55, 38, 28),
            side_panel_dark=QColor(38, 25, 18),
            inner_shadow_color=QColor(0, 0, 0, 30),
            cavity_color=QColor(20, 14, 10),
        )


def color_with_alpha(c: QColor, a: int) -> QColor:
    ans = QColor(c)
    ans.setAlpha(a)
    return ans


class RenderCase:

    dark_theme: WoodTheme
    light_theme: WoodTheme
    theme: WoodTheme

    def __init__(self):
        self.last_rendered_shelf_at = QRect(0, 0, 0, 0), False
        self.last_rendered_background_at = QRect(0, 0, 0, 0), False
        self.last_rendered_background = QPixmap()
        self.shelf_cache: dict[int, QPixmap] = {}
        self.back_panel_grain = tuple(self.generate_grain_lines(count=80, seed=42))

    def generate_grain_lines(self, seed: int = 42, count: int = 60) -> Iterator[tuple[float, float, float, float, float]]:
        r = random.Random(seed)
        for i in range(count):
            y_offset = r.uniform(-0.3, 0.3)
            thickness = r.uniform(0.5, 2.0)
            alpha = r.uniform(0, 1)
            wave_amplitude = r.uniform(0, 2)
            wave_frequency = r.uniform(0.01, 0.03)
            yield y_offset, thickness, alpha, wave_amplitude, wave_frequency

    def ensure_theme(self, is_dark: bool) -> None:
        attr = 'dark_theme' if is_dark else 'light_theme'
        if not hasattr(self, attr):
            setattr(self, attr, WoodTheme.dark_theme() if is_dark else WoodTheme.light_theme())
        self.theme = self.dark_theme if is_dark else self.light_theme

    def background_as_pixmap(self, width: int, height: int) -> QPixmap:
        rect = QRect(0, 0, width, height)
        is_dark = is_dark_theme()
        q = rect, is_dark
        if self.last_rendered_shelf_at == q:
            return self.last_rendered_background
        self.ensure_theme(is_dark)
        ans = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(ans)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.draw_back_panel(painter, rect)
        # Add vertical grain for back panel (typical plywood back)
        self.draw_back_panel_grain(painter, rect)
        self.draw_cavity_shadows(painter, rect)
        painter.end()
        self.last_rendered_background = QPixmap.fromImage(ans)
        return self.last_rendered_background

    def draw_back_panel(self, painter: QPainter, interior_rect: QRect) -> None:
        # Base gradient for back panel (slightly recessed look)
        back_gradient = QLinearGradient(interior_rect.left(), 0, interior_rect.right(), 0)
        back_gradient.setColorAt(0.0, self.theme.back_panel_dark)
        back_gradient.setColorAt(0.15, self.theme.back_panel_base)
        back_gradient.setColorAt(0.85, self.theme.back_panel_base)
        back_gradient.setColorAt(1.0, self.theme.back_panel_dark)
        painter.fillRect(interior_rect, back_gradient)

    def draw_back_panel_grain(self, painter: QPainter, rect: QRect) -> None:
        painter.save()
        painter.setClipRect(rect)

        r = random.Random(555)
        min_alpha, max_alpha = self.theme.grain_alpha_range

        # Vertical grain lines
        for i in range(50):
            x = rect.left() + r.randint(0, rect.width())
            alpha = r.randint(min_alpha // 2, max_alpha // 2)

            grain_color = color_with_alpha(self.theme.grain_color, alpha)
            pen = QPen(grain_color)
            pen.setWidthF(r.uniform(0.5, 1.5))
            painter.setPen(pen)

            # Slightly wavy vertical line
            y1 = rect.top()
            y2 = rect.bottom()
            wave = r.uniform(-3, 3)
            painter.drawLine(int(x), y1, int(x + wave), y2)

        painter.restore()

    def draw_cavity_shadows(self, painter: QPainter, cavity_rect: QRect) -> None:
        side_shadow_width = 20
        # Left side shadow
        left_shadow_gradient = QLinearGradient(cavity_rect.left(), 0, cavity_rect.left() + side_shadow_width, 0)
        left_shadow_gradient.setColorAt(0.0, self.theme.inner_shadow_color)
        left_shadow_gradient.setColorAt(1.0, color_with_alpha(self.theme.inner_shadow_color, 0))
        painter.fillRect(cavity_rect.x(), cavity_rect.y(), side_shadow_width, cavity_rect.height(), left_shadow_gradient)
        # Right side shadow
        right_shadow_gradient = QLinearGradient(cavity_rect. right() - side_shadow_width, 0, cavity_rect.right(), 0)
        right_shadow_gradient.setColorAt(0.0, color_with_alpha(self.theme.inner_shadow_color, 0))
        right_shadow_gradient.setColorAt(1.0, self.theme.inner_shadow_color)
        painter.fillRect(
            cavity_rect.right() - side_shadow_width, cavity_rect.y(), side_shadow_width, cavity_rect.height(), right_shadow_gradient)

    def shelf_as_pixmap(self, width: int, height: int, instance: int) -> QPixmap:
        rect = QRect(0, 0, width, height)
        is_dark = is_dark_theme()
        q = rect, is_dark
        if self.last_rendered_shelf_at != q:
            self.shelf_cache.clear()
        self.last_rendered_shelf_at = q
        if ans := self.shelf_cache.get(instance):
            return ans
        self.ensure_theme(is_dark)
        ans = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(ans)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.draw_shelf_body(painter, rect)
        self.draw_wood_grain(painter, rect, tuple(self.generate_grain_lines(102 + instance)))
        self.draw_knots(painter, rect, seed=123 + instance)
        self.draw_top_highlight(painter, rect)
        self.draw_bottom_edge(painter, rect)
        self.draw_front_bevel(painter, rect)
        self.draw_edges(painter, rect)
        painter.end()
        self.shelf_cache[instance] = p = QPixmap.fromImage(ans)
        return p

    def draw_shelf_body(self, painter, rect):
        # Base wood gradient
        wood_gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        wood_gradient.setColorAt(0.0, self.theme.wood_top)         # Lighter top
        wood_gradient.setColorAt(0.3, self.theme.wood_mid_light)   # Mid tone
        wood_gradient.setColorAt(0.7, self.theme.wood_mid_dark)    # Darker
        wood_gradient.setColorAt(1.0, self.theme.wood_bottom)      # Darkest bottom

        painter.fillRect(rect, wood_gradient)

    def draw_wood_grain(self, painter, rect, grain_lines, alpha_multiplier: float = 1.0):
        painter.save()
        painter.setClipRect(rect)

        spacing = rect.height() / len(grain_lines)
        min_alpha, max_alpha = self.theme.grain_alpha_range
        for i, (y_offset, thickness, alpha_factor, wave_amp, wave_freq) in enumerate(grain_lines):
            alpha = int((min_alpha + alpha_factor * (max_alpha - min_alpha)) * alpha_multiplier)
            # Vary the grain color
            grain_color = QColor(self.theme.grain_color)
            grain_color.setAlpha(alpha)
            pen = QPen(grain_color)
            pen.setWidthF(thickness)
            painter. setPen(pen)

            # Calculate y position with offset
            base_y = rect. top() + i * spacing + y_offset * spacing

            # Draw wavy grain line
            points = []
            for x in range(rect. left(), rect.right(), 5):
                import math
                wave = wave_amp * math. sin(x * wave_freq + i)
                points.append((x, base_y + wave))

            for j in range(len(points) - 1):
                painter.drawLine(
                    int(points[j][0]), int(points[j][1]),
                    int(points[j + 1][0]), int(points[j + 1][1])
                )
        painter.restore()

    def draw_knots(self, painter: QPainter, rect: QRect, count: int = 3, seed: int = 123):
        painter.save()
        painter.setClipRect(rect)
        r = random.Random(seed)
        for _ in range(count):
            knot_x = r.randint(rect.left() + 20, rect.right() - 20)
            knot_y = r.randint(rect.top() + 5, rect.bottom() - 5)
            knot_size = r.randint(3, 6)

            knot_gradient = QLinearGradient(knot_x - knot_size, knot_y, knot_x + knot_size, knot_y)
            knot_color_transparent = color_with_alpha(self.theme.knot_color, 0)
            knot_gradient.setColorAt(0.0, knot_color_transparent)
            knot_gradient.setColorAt(0.5, self.theme.knot_color)
            knot_gradient.setColorAt(1.0, knot_color_transparent)

            painter.setBrush(QBrush(knot_gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(knot_x - knot_size, knot_y - knot_size // 2, knot_size * 2, knot_size)
        painter.restore()

    def draw_top_highlight(self, painter, rect):
        highlight_gradient = QLinearGradient(0, rect.top(), 0, rect.top() + 8)
        highlight_gradient.setColorAt(0.0, self.theme.highlight_color)
        highlight_gradient.setColorAt(0.5, color_with_alpha(self.theme.highlight_color, self.theme.highlight_color.alpha() // 3))
        highlight_gradient.setColorAt(1.0, color_with_alpha(self.theme.highlight_color, 0))
        highlight_rect = QRect(rect.x(), rect.y(), rect.width(), 8)
        painter.fillRect(highlight_rect, highlight_gradient)

    def draw_bottom_edge(self, painter, rect):
        shadow_gradient = QLinearGradient(0, rect.bottom() - 6, 0, rect.bottom())
        shadow_gradient.setColorAt(0.0, color_with_alpha(self.theme.shadow_color, 0))
        shadow_gradient.setColorAt(0.7, self.theme.shadow_color)
        shadow_gradient.setColorAt(1.0, color_with_alpha(self.theme.shadow_color, self.theme.shadow_color.alpha() * 2))
        shadow_rect = QRect(rect.x(), rect.bottom() - 6, rect. width(), 6)
        painter.fillRect(shadow_rect, shadow_gradient)

    def draw_front_bevel(self, painter, rect):
        # Top chamfer line
        chamfer_pen = QPen(self.theme.bevel_light)
        chamfer_pen.setWidth(1)
        painter.setPen(chamfer_pen)
        painter.drawLine(rect.left(), rect.top() + 2, rect.right(), rect.top() + 2)

        # Bottom chamfer (darker)
        chamfer_pen. setColor(self.theme.bevel_dark)
        painter.setPen(chamfer_pen)
        painter.drawLine(rect.left(), rect.bottom() - 2, rect. right(), rect.bottom() - 2)

    def draw_edges(self, painter, rect):
        # Darker edge outline
        edge_pen = QPen(self.theme.edge_color)
        edge_pen.setWidth(1)
        painter.setPen(edge_pen)
        painter.setBrush(Qt. BrushStyle. NoBrush)
        painter.drawRect(rect)

        # Left end grain (slightly different tone)
        end_grain_width = 4
        left_end = QRect(rect.x(), rect.y(), end_grain_width, rect.height())
        end_gradient = QLinearGradient(left_end.left(), 0, left_end.right(), 0)
        end_gradient.setColorAt(0.0, self.theme.end_grain_dark)
        end_gradient.setColorAt(1.0, color_with_alpha(self.theme.end_grain_light, 0))
        painter.fillRect(left_end, end_gradient)

        # Right end grain
        right_end = QRect(rect. right() - end_grain_width, rect.y(), end_grain_width, rect.height())
        end_gradient = QLinearGradient(right_end.left(), 0, right_end.right(), 0)
        end_gradient.setColorAt(0.0, color_with_alpha(self.theme.end_grain_light, 0))
        end_gradient.setColorAt(1.0, self.theme.end_grain_dark)
        painter.fillRect(right_end, end_gradient)


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
    i = QImage(I('default_cover.png'))
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


def draw_pixmap_with_shadow(
    pixmap: QPixmap, opacity: float = 1.0, has_shadow: bool = True,
    shadow_color: QColor = QColor(0, 0, 0, 100), fill_color: QColor = QColor(Qt.GlobalColor.transparent),
) -> tuple[QPixmap, int]:
    ''' Draw a QPixmap with a nice drop shadow effect. '''
    # Create a larger image to accommodate the shadow
    shadow_blur = 10 if has_shadow else 0
    margin = shadow_blur * 2
    total_width, total_height = pixmap.width(), pixmap.height()
    if margin > 0:
        shadow_offset_x = shadow_offset_y = shadow_blur // 2
        total_width += margin * 2 + abs(shadow_offset_x)
        total_height += margin * 2 + abs(shadow_offset_y)

    # Create shadow image
    shadow_image = QImage(total_width, total_height, QImage.Format_ARGB32_Premultiplied)
    shadow_image.fill(Qt.GlobalColor.transparent)

    shadow_painter = QPainter(shadow_image)
    shadow_painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    shadow_painter.setPen(Qt.PenStyle.NoPen)

    if margin:
        # Draw the shadow shape (rounded rect or simple rect based on preference)
        shadow_rect = QRectF(
            margin + shadow_offset_x,
            margin + shadow_offset_y,
            pixmap.width(),
            pixmap.height()
        )

        # Draw multiple layers with decreasing opacity for blur effect
        for i in range(shadow_blur, 0, -1):
            alpha = int(shadow_color.alpha() * (1 - i / shadow_blur) * 0.5)
            blur_color = QColor(shadow_color.red(), shadow_color.green(),
                            shadow_color.blue(), alpha)
            shadow_painter.setBrush(blur_color)

            blur_rect = shadow_rect.adjusted(-i, -i, i, i)
            shadow_painter.drawRoundedRect(blur_rect, 3, 3)

    shadow_painter.fillRect(QRect(margin, margin, pixmap.width(), pixmap.height()), fill_color)
    shadow_painter.setOpacity(opacity)
    shadow_painter.drawPixmap(margin, margin, pixmap)
    shadow_painter.end()
    return QPixmap.fromImage(shadow_image), margin


class CachedCoverRenderer:

    def __init__(self, p: PixmapWithDominantColor) -> None:
        self.pixmap = p
        self.last_rendered_size = QSize()
        self.last_rendered_opacity = -1
        self.last_rendered_pixmap = QPixmap()
        self.last_rendered_margin = 0
    set_pixmap = __init__

    def as_pixmap(self, size: QSize, opacity: float, parent: QWidget) -> tuple[QPixmap, int]:
        if size == self.last_rendered_size and opacity == self.last_rendered_opacity:
            return self.last_rendered_pixmap, self.last_rendered_margin
        dpr = parent.devicePixelRatioF()
        ss = (QSizeF(size) * dpr).toSize()
        pmap = self.pixmap.scaled(ss, transformMode=Qt.TransformationMode.SmoothTransformation)
        self.last_rendered_pixmap, self.last_rendered_margin = draw_pixmap_with_shadow(
                pmap, has_shadow=gprefs['bookshelf_shadow'], fill_color=self.pixmap.dominant_color, opacity=opacity)
        self.last_rendered_pixmap.setDevicePixelRatio(dpr)
        self.last_rendered_margin = int(self.last_rendered_margin / dpr)
        self.last_rendered_opacity = opacity
        self.last_rendered_size = size
        return self.last_rendered_pixmap, self.last_rendered_margin
# }}}


# Layout {{{
@lru_cache(maxsize=2)
def all_groupings() -> dict[str, str]:
    return {
        'authors': '',
        'series': _('No series'),
        'tags': _('Untagged'),
        'publisher': _('No publisher'),
        'pubdate': _('Unpublished'),
        'timestamp': _('Unknown'),
        'rating': _('Unrated'),
        'languages': _('No language'),
    }


class LayoutConstraints(NamedTuple):
    min_spine_width: int = 15
    max_spine_width: int = 60
    default_spine_width: int = 40
    spine_height: int = 200
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
    return random_from_id(book_id) if gprefs['bookshelf_variable_height'] else 0


class ShelfItem(NamedTuple):
    start_x: int
    case_start_y: int
    width: int
    idx: int
    case_idx: int
    reduce_height_by: int = 0
    book_id: int = 0
    group_name: str = ''
    is_hover_expanded: bool = False

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

    def contains(self, x: int, gap: int = 0) -> bool:
        return self.start_x <= x < self.start_x + self.width + gap

    def overlap_length(self, X: 'ShelfItem') -> int:
        xs, xl = X.start_x, X.width
        ys, yl = self.start_x, self.width
        xe = xs + xl
        ye = ys + yl
        return max(0, min(xe, ye) - max(xs, ys))


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

    def book_or_divider_at_xpos(self, x: int, lc: LayoutConstraints) -> ShelfItem | None:
        if self.items:
            idx = bisect.bisect_right(self.items, x, key=attrgetter('start_x'))
            if idx > 0:
                candidate = self.items[idx-1]
                if candidate.contains(x, lc.horizontal_gap):
                    if candidate.is_hover_expanded:
                        return candidate
                    if candidate.idx and (prev := self.items[candidate.idx-1]).is_hover_expanded and prev.contains(x):
                        return prev
                    if idx < len(self.items) and (n := self.items[idx]).is_hover_expanded and n.contains(x):
                        return n
                    return candidate
        return None

    def book_or_divider_at_region(self, region: ShelfItem, lc: LayoutConstraints) -> ShelfItem | None:
        if self.items:
            idx = bisect.bisect_right(self.items, region.start_x, key=attrgetter('start_x'))
            if idx > 0:
                candidate = self.items[idx-1]
                if candidate.contains(region.start_x, lc.horizontal_gap):
                    if idx < len(self.items):
                        nc = self.items[idx]
                        a, b = region.overlap_length(candidate), region.overlap_length(nc)
                        return candidate if a >= b else nc
                    return candidate
        return None

    def closest_book_to(self, idx: int) -> ShelfItem | None:
        q = self.items[idx]
        if not q.is_divider:
            return q
        for delta in range(1, len(self.items)):
            for i in (idx + delta, idx - delta):
                if 0 <= i < len(self.items) and not (ans := self.items[i]).is_divider:
                    return ans
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
        s = ShelfItem(start_x=x, group_name=group_name, width=lc.divider_width, case_start_y=self.start_y,
                      idx=len(self.items), case_idx=self.idx)
        self.items.append(s)
        self.width = s.start_x + s.width
        return True

    def add_book(self, book_id: int, width: int, group_name: str, lc: LayoutConstraints) -> bool:
        if (x := self._get_x_for_item(width, lc)) is None:
            return False
        s = ShelfItem(
            start_x=x, book_id=book_id, reduce_height_by=height_reduction_for_book_id(book_id),
            width=width, group_name=group_name, case_start_y=self.start_y, idx=len(self.items), case_idx=self.idx)
        self.items.append(s)
        self.width = s.start_x + s.width
        return True

    @property
    def is_shelf(self) -> bool:
        return self.items is None

    def shift_for_expanded_cover(self, shelf_item: ShelfItem, lc: LayoutConstraints, width: int) -> 'CaseItem':
        if (extra := width - shelf_item.width) <= 0:
            return self
        ans = CaseItem(y=self.start_y, height=self.height, idx=self.idx)
        space_at_right_edge = max(0, lc.width - self.width)
        left_shift = 0
        right_shift = min(space_at_right_edge, extra)
        extra -= right_shift
        if extra > 0:
            shift_left = shelf_item.idx > 2
            shift_right = shelf_item.idx < len(self.items) - 3
            if shift_left:
                if shift_right:
                    left_shift += extra // 2
                    right_shift += extra - left_shift
                else:
                    left_shift += extra
            else:
                right_shift += extra
        if gprefs['bookshelf_hover'] == 'shift':
            for i, item in enumerate(self.items):
                if i < shelf_item.idx:
                    if left_shift:
                        item = item._replace(start_x=item.start_x - left_shift)
                elif i == shelf_item.idx:
                    item = item._replace(start_x=item.start_x - left_shift, width=width, is_hover_expanded=True)
                elif right_shift:
                    item = item._replace(start_x=item.start_x + right_shift)
                ans.items.append(item)
                ans.width = item.start_x + item.width
        else:
            ans.items = self.items[:]
            item = ans.items[shelf_item.idx]
            ans.items[shelf_item.idx] = item._replace(start_x=item.start_x - left_shift, width=width, is_hover_expanded=True)
        return ans


def get_grouped_iterator(db: Cache, book_ids_iter: Iterable[int], field_name: str = '') -> Iterator[tuple[str, Iterable[int]]]:
    formatter = lambda x: x  # noqa: E731
    fm = db.field_metadata
    sort_key = numeric_sort_key
    get_books_in_group = lambda group: db.books_for_field(field_name, group)  # noqa: E731
    get_field_id_map = lambda: db.get_id_map(field_name)  # noqa: E731
    sort_map = {book_id: i for i, book_id in enumerate(book_ids_iter)}
    all_book_ids = frozenset(sort_map)
    ungrouped_name = all_groupings().get(field_name, _('Unknown'))
    dt = fm.get(field_name, {}).get('datatype')

    match field_name:
        case '':
            yield '', 0
            yield '', book_ids_iter
            return
        case 'authors':
            def get_authors_field_id_map() -> dict[int, str]:
                field_id_map = db.get_id_map('authors')
                author_sort_map = db.author_data(field_id_map)
                def gas(aid: int, au: str) -> str:
                    try:
                        return author_sort_map[aid]['sort']
                    except Exception:
                        return au
                return {aid: gas(aid, au) for aid, au in field_id_map.items()}
            get_field_id_map = get_authors_field_id_map
        case 'languages':
            lm = lang_map()
            formatter = lambda x: lm.get(x, x)  # noqa: E731
            sort_key = lambda x: numeric_sort_key(formatter(x))  # noqa: E731
        case field_name if dt == 'rating':
            formatter = rating_to_stars
            sort_key = lambda x: -x  # noqa: E731
            ungrouped_name = _('Unrated')
        case field_name if dt == 'datetime':
            df = fm[field_name].get('display', {}).get('date_format') or 'dd MMM yyyy'
            if 'd' in df:
                lsys = QLocale.system().monthName
                month_map = db.books_by_month(field=field_name, restrict_to_books=all_book_ids)
                get_books_in_group = month_map.__getitem__
                get_field_id_map = lambda: {x: x for x in month_map}  # noqa: E731
                sort_key = lambda x: (-x[0], -x[1])  # noqa: E731
                formatter = lambda x: (f'{lsys(x[1], QLocale.FormatType.ShortFormat)} {x[0]}' if x[0] > UNDEFINED_DATE.year else ungrouped_name)  # noqa: E731
            else:
                year_map = db.books_by_year(field=field_name, restrict_to_books=all_book_ids)
                get_books_in_group = year_map.__getitem__
                get_field_id_map = lambda: {x: x for x in year_map}  # noqa: E731
                sort_key = lambda x: -x  # noqa: E731
                formatter = lambda x: str(x) if x > UNDEFINED_DATE.year else ungrouped_name  # noqa: E731

    field_id_map = get_field_id_map()
    yield '', len(field_id_map)
    seen = set()
    for group in sorted(field_id_map, key=lambda fid: sort_key(field_id_map[fid])):
        books_in_group = (get_books_in_group(group) & all_book_ids) - seen
        if books_in_group:
            seen |= books_in_group
            yield formatter(field_id_map[group]), sorted(books_in_group,  key=sort_map.__getitem__)
    if ungrouped_name and (leftover := all_book_ids - seen):
        yield ungrouped_name, sorted(leftover,  key=sort_map.__getitem__)


def base_log(f: float, b: float = 10) -> float:
    return math.log(1+max(0, min(f, 1))*b, b+1)


def width_from_pages(pages: int, num_of_pages_for_max_width: int = 1500) -> float:
    return base_log(pages/num_of_pages_for_max_width)


def width_from_size(sz: int) -> float:
    return base_log(normalised_size(sz))


def get_spine_width(
    book_id: int, db: Cache, spine_size_template: str, template_cache: dict[str, str],
    lc: LayoutConstraints, cache: dict[int, int]
) -> int:
    if (ans := cache.get(book_id)) is not None:
        return ans

    def linear(f: float):
        return lc.min_spine_width + int(max(0, min(f, 1)) * (lc.max_spine_width - lc.min_spine_width))

    ans = -1
    match spine_size_template:
        case '{pages}' | 'pages':
            pages = db.field_for('pages', book_id, 0)
            if pages > 0:
                ans = linear(width_from_pages(pages))
            else:
                ans = linear(width_from_size(db.field_for('size', book_id, 0)))
        case '{size}' | 'size':
            ans = linear(width_from_size(db.field_for('size', book_id, 0)))
        case '{random}' | 'random':
            # range: 0.25-0.75
            ans = linear((25+(random_from_id(book_id, limit=51)))/100)
        case '':
            ans = lc.default_spine_width
        case _:
            with suppress(Exception):
                if 0 <= (x := float(spine_size_template)) <= 1:
                    ans = linear(x)
            if ans < 0:
                with suppress(Exception):
                    mi = db.get_proxy_metadata(book_id)
                    rslt = mi.formatter.safe_format(spine_size_template, mi, TEMPLATE_ERROR, mi, template_cache=template_cache)
                    ans = linear(float(rslt))
    if ans <= 0:
        ans = lc.default_spine_width
    cache[book_id] = ans
    return ans


class LayoutPayload(NamedTuple):
    invalidate_event: Event
    layout_constraints: LayoutConstraints
    group_field_name: str
    row_to_book_id: tuple[int, ...]
    book_id_to_item_map: dict[int, ShelfItem]
    book_id_visual_order_map: dict[int, int]
    book_ids_in_visual_order: list[int]


class BookCase(QObject):
    items: list[CaseItem]
    layout_finished: bool = False
    height: int = 0

    shelf_added = pyqtSignal(object, object)
    num_of_groups_changed = pyqtSignal()

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.worker: Thread | None = None
        self.row_to_book_id: tuple[int, ...] = ()
        self._book_id_to_row_map: dict[int, int] = {}
        self.book_id_visual_order_map: dict[int, int] = {}
        self.book_ids_in_visual_order: list[int] = []
        self.num_of_books_that_need_pages_counted = 0
        self.using_page_counts = False
        self.queue: LifoQueue[LayoutPayload] = LifoQueue()
        self.lock = RLock()
        self.current_invalidate_event = Event()
        self.spine_width_cache: dict[int, int] = {}
        self.num_of_groups = 0
        self.payload: LayoutPayload | None = None
        self.invalidate()

    def shutdown(self):
        self.current_invalidate_event.set()
        self.current_invalidate_event = Event()
        with suppress(TypeError):
            self.num_of_groups_changed.disconnect()
        with suppress(TypeError):
            self.shelf_added.disconnect()
        if self.worker is not None:
            self.queue.shutdown(immediate=True)
            w, self.worker = self.worker, None
            if current_thread().is_alive() and w.is_alive():
                w.join()

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
            self.group_field_name = group_field_name
            self.items = []
            self.height = 0
            self.using_page_counts = False
            self.num_of_books_that_need_pages_counted = 0
            self.layout_constraints = layout_constraints
            self.book_id_visual_order_map: dict[int, int] = {}
            self.book_ids_in_visual_order = []
            self.book_id_to_item_map: dict[int, ShelfItem] = {}
            self.num_of_groups = 0
            if model is not None and (db := model.db) is not None:
                # implies set of books to display has changed
                self.row_to_book_id = db.data.index_to_id_map()
                self._book_id_to_row_map = {}
                self.dbref = weakref.ref(db)
            self.layout_finished = not bool(self.row_to_book_id)
            self.payload = LayoutPayload(
                self.current_invalidate_event, self.layout_constraints, self.group_field_name, self.row_to_book_id,
                self.book_id_to_item_map, self.book_id_visual_order_map, self.book_ids_in_visual_order)

    def ensure_layouting_is_current(self) -> None:
        if db := self.dbref():
            db.new_api.queue_pages_scan()
        with self.lock:
            if self.layout_constraints.width > 0 and self.payload is not None:
                if self.worker is None:
                    self.worker = Thread(target=self.layout_thread, name='BookCaseLayout', daemon=True)
                    self.worker.start()
                p, self.payload = self.payload, None
                self.queue.put(p)

    @property
    def book_id_to_row_map(self) -> dict[int, int]:
        if self.row_to_book_id and not self._book_id_to_row_map:
            self._book_id_to_row_map = {bid: r for r, bid in enumerate(self.row_to_book_id)}
        return self._book_id_to_row_map

    def layout_thread(self) -> None:
        while True:
            try:
                x = self.queue.get()
            except ShutDown:
                break
            self.do_layout_in_worker(*x)

    def do_layout_in_worker(
        self, invalidate: Event, lc: LayoutConstraints, group_field_name: str, row_to_book_id: tuple[int, ...],
        book_id_to_item_map: dict[int, ShelfItem], book_id_visual_order_map: dict[int, int],
        book_ids_in_visual_order: list[int],
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
        if mdb is None or invalidate.is_set():
            return
        db = mdb.new_api
        spine_size_template = db.pref('bookshelf_spine_size_template') or db.backend.prefs.defaults['bookshelf_spine_size_template']
        template_cache = {}
        group_iter = get_grouped_iterator(db, row_to_book_id, group_field_name)
        _, num_of_groups = next(group_iter)
        with self.lock:
            if invalidate.is_set():
                return
            self.num_of_groups = num_of_groups
        self.num_of_groups_changed.emit()
        num_of_books_that_need_pages_counted = db.num_of_books_that_need_pages_counted()
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
                try:
                    spine_width = get_spine_width(
                        book_id, db, spine_size_template, template_cache, lc, self.spine_width_cache)
                except Exception:
                    spine_width = lc.default_spine_width
                if not current_case_item.add_book(book_id, spine_width, group_name, lc):
                    y = commit_case_item(current_case_item)
                    current_case_item = CaseItem(y=y, height=lc.spine_height, idx=len(self.items))
                    current_case_item.add_book(book_id, spine_width, group_name, lc)
                book_id_to_item_map[book_id] = current_case_item.items[-1]
                book_id_visual_order_map[book_id] = len(book_id_visual_order_map)
                book_ids_in_visual_order.append(book_id)
        if current_case_item.items:
            commit_case_item(current_case_item)
        with self.lock:
            if invalidate.is_set():
                return
            self.layout_finished = True
            self.num_of_books_that_need_pages_counted = num_of_books_that_need_pages_counted
            self.using_page_counts = spine_size_template in ('{pages}', 'pages')
            if len(self.items) > 1:
                self.shelf_added.emit(self.items[-2], self.items[-1])

    def visual_row_cmp(self, a: int, b: int) -> int:
        ' Compares if a or b (book_row numbers) is visually before the other in left-to-right top-to-bottom order'
        try:
            a = self.row_to_book_id[a]
            b = self.row_to_book_id[b]
        except IndexError:
            return a - b
        return self.book_id_visual_order_map[a] - self.book_id_visual_order_map[b]

    def visual_selection_between(self, a: int, b: int) -> Iterator[int]:
        ' Return all book_rows visually from a to b in left to right top-to-bottom order '
        a = self.row_to_book_id[a]
        b = self.row_to_book_id[b]
        aidx = self.book_ids_in_visual_order.index(a)
        bidx = self.book_ids_in_visual_order.index(b)
        s, e = min(aidx, bidx), max(aidx, bidx)
        yield from map(self.book_id_to_row_map.__getitem__, self.book_ids_in_visual_order[s:e+1])

    def visual_neighboring_book(self, book_id: int, delta: int = 1, allow_wrap: bool = False) -> int:
        idx = self.book_id_visual_order_map[book_id]
        nidx = idx + delta
        if allow_wrap:
            nidx = (nidx + len(self.book_ids_in_visual_order)) % len(self.book_ids_in_visual_order)
        if 0 <= nidx < len(self.book_ids_in_visual_order):
            return self.book_ids_in_visual_order[nidx]
        return 0

    def shelf_of_book(self, book_id: int) -> CaseItem | None:
        if si := self.book_id_to_item_map.get(book_id):
            return self.items[si.case_idx]
        return None

    def end_book_on_shelf_of(self, book_id: int, first: bool = False) -> int:
        if ci := self.shelf_of_book(book_id):
            return ci.items[0 if first else -1].book_id
        return 0

    def book_in_column_of(self, book_id: int, delta: int = 1, allow_wrap: bool = False) -> int:
        if not (si := self.book_id_to_item_map.get(book_id)):
            return
        if not (ci := self.shelf_of_book(book_id)):
            return 0
        shelf_idx = ci.idx // 2 + delta
        num_shelves = len(self.items) // 2
        if allow_wrap:
            shelf_idx = (shelf_idx + num_shelves) % num_shelves
        if shelf_idx < 0 or shelf_idx >= num_shelves:
            return 0
        target_shelf = self.items[shelf_idx * 2]
        if not (target_si := target_shelf.book_or_divider_at_region(si, self.layout_constraints)):
            return 0
        return ans.book_id if (ans := target_shelf.closest_book_to(target_si.idx)) else 0
# }}}


class ExpandedCover(QObject):

    updated = pyqtSignal()

    def __init__(self, parent: 'BookshelfView'):
        super().__init__(parent)
        self._opacity = 0
        self._size = QSize()
        self.is_showing_cover = False
        self.shelf_item: ShelfItem | None = None
        self.case_item: CaseItem | None = None
        self.modified_case_item: CaseItem | None = None
        self.cover_renderer: CachedCoverRenderer = CachedCoverRenderer(PixmapWithDominantColor())
        self.opacity_animation = a = QPropertyAnimation(self, b'opacity')
        a.setEasingCurve(QEasingCurve.Type.InOutCubic)
        a.setStartValue(0.3)
        a.setEndValue(1)
        self.size_animation = a = QPropertyAnimation(self, b'size')
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation = a = QParallelAnimationGroup(self)
        a.addAnimation(self.opacity_animation)
        a.addAnimation(self.size_animation)
        self.debounce_timer = t = QTimer(self)
        t.setInterval(120)
        t.timeout.connect(self.start)
        t.setSingleShot(True)

    @property
    def layout_constraints(self) -> LayoutConstraints:
        return self.parent().layout_constraints

    def shelf_item_hovered(self, case_item: CaseItem | None = None, shelf_item: ShelfItem | None = None) -> None:
        self.pending_shelf_item, self.pending_case_item = shelf_item, case_item
        self.debounce_timer.start()

    def start(self) -> None:
        if getattr(self.pending_shelf_item, 'book_id', -1) == getattr(self.shelf_item, 'book_id', -1):
            self.pending_case_item = self.pending_shelf_item = None
            return
        self.invalidate()
        self.shelf_item, self.case_item = self.pending_shelf_item, self.pending_case_item
        self.pending_case_item = self.pending_shelf_item = None
        if self.shelf_item is not None:
            duration = 0 if config['disable_animations'] else gprefs['bookshelf_fade_time']
            if duration > 0:
                self.opacity_animation.setDuration(duration)
                self.size_animation.setDuration(duration)
            lc = self.layout_constraints
            sz = QSize(self.shelf_item.width, lc.spine_height - self.shelf_item.reduce_height_by)
            self.modified_case_item = self.case_item
            pixmap, final_sz = self.parent().load_hover_cover(self.shelf_item)
            self.cover_renderer.set_pixmap(pixmap)
            self.size_animation.setStartValue(sz)
            self.size_animation.setEndValue(final_sz)
            self.is_showing_cover = True
            if duration > 0:
                self.animation.start()
            else:
                self._opacity = 1
                self._size = final_sz
                self.shift_items()
        self.updated.emit()

    def invalidate(self) -> None:
        self.shelf_item = self.case_item = self.modified_case_item = None
        self.animation.stop()
        self.debounce_timer.stop()
        self.is_showing_cover = False

    @pyqtProperty(float)
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, val: float) -> None:
        self._opacity = val

    @pyqtProperty(QSize)
    def size(self) -> QSize:
        return self._size

    @size.setter
    def size(self, val: QSize) -> None:
        self._size = val
        self.shift_items()
        self.updated.emit()

    def shift_items(self) -> None:
        self.modified_case_item = self.case_item.shift_for_expanded_cover(
                self.shelf_item, self.layout_constraints, self.size.width())

    @property
    def expanded_cover_should_be_displayed(self) -> bool:
        return self.shelf_item is not None and self.modified_case_item is not None and self.is_showing_cover

    def modify_shelf_layout(self, case_item: CaseItem) -> CaseItem:
        if self.expanded_cover_should_be_displayed and case_item is self.case_item:
            case_item = self.modified_case_item
        return case_item

    def is_expanded(self, book_id: int) -> bool:
        return self.expanded_cover_should_be_displayed and self.shelf_item.book_id == book_id

    def draw_expanded_cover(
        self, painter: QPainter, scroll_y: int, lc: LayoutConstraints, is_selected: bool, is_current: bool,
        selection_highlight_color: QColor
    ) -> None:
        shelf_item = self.modified_case_item.items[self.shelf_item.idx]
        cover_rect = shelf_item.rect(lc)
        cover_rect.translate(0, -scroll_y)
        pmap, margin = self.cover_renderer.as_pixmap(cover_rect.size(), self.opacity, self.parent())
        painter.drawPixmap(cover_rect.topLeft() - QPoint(margin, margin), pmap)
        if selection_highlight_color.isValid():
            pen = QPen(selection_highlight_color)
            pen.setWidth(2)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setOpacity(1.0)
            painter.drawRect(cover_rect)


class SavedState(NamedTuple):
    current_book_id: int
    selected_book_ids: set[int]


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
    DIVIDER_TEXT_COLOR = QColor('#b0b5c0')
    DIVIDER_LINE_COLOR = QColor('#4a4a6a')
    DIVIDER_GRADIENT_LINE_1 = DIVIDER_LINE_COLOR.toRgb()
    DIVIDER_GRADIENT_LINE_2 = DIVIDER_LINE_COLOR.toRgb()
    DIVIDER_GRADIENT_LINE_1.setAlphaF(0.0)  # Transparent at top/bottom
    DIVIDER_GRADIENT_LINE_2.setAlphaF(0.75)  # Visible in middle

    def __init__(self, gui):
        super().__init__(gui)
        self.text_color_for_dark_background = dark_palette().color(QPalette.ColorRole.WindowText)
        self.text_color_for_light_background = light_palette().color(QPalette.ColorRole.WindowText)
        self.gui = gui
        self._model: BooksModel | None = None
        self.context_menu: QMenu | None = None
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.resize_debounce_timer = t = QTimer(self)
        t.timeout.connect(self.resize_debounced)
        t.setSingleShot(True), t.setInterval(200)
        self.pages_count_update_check_timer = t = QTimer(self)
        t.timeout.connect(self.check_pages_count_update)
        t.setSingleShot(True), t.setInterval(2000)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Ensure viewport receives mouse events
        self.viewport().setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_MouseTracking, True)

        # Initialize drag and drop
        # so we set the attributes manually
        self.drag_allowed = True
        self.drag_start_pos = None
        self.bookcase = BookCase(self)
        self.bookcase.shelf_added.connect(self.on_shelf_layout_done, type=Qt.ConnectionType.QueuedConnection)
        self.bookcase.num_of_groups_changed.connect(self.update_scrollbar_ranges, type=Qt.ConnectionType.QueuedConnection)

        # Selection tracking
        self._selection_model: QItemSelectionModel = QItemSelectionModel(None, self)
        self.selectionModel().selectionChanged.connect(self.update_viewport)
        self.click_start_data: ClickStartData | None = None

        # Cover loading and caching
        self.expanded_cover = ExpandedCover(self)
        self.expanded_cover.updated.connect(self.update_viewport)

        self.layout_constraints = LayoutConstraints()
        self.layout_constraints = self.layout_constraints._replace(width=self.get_available_width())
        self.grouping_mode = ''
        self.refresh_settings()
        self.cover_cache = CoverThumbnailCache(
            name='bookshelf-thumbnail-cache', ram_limit=800,
            max_size=gprefs['bookshelf_disk_cache_size'], thumbnailer=ThumbnailerWithDominantColor(),
            thumbnail_size=self.thumbnail_size(), parent=self, version=2,
        )
        self.cover_cache.rendered.connect(self.update_viewport, type=Qt.ConnectionType.QueuedConnection)

        # Cover template caching
        self.template_inited = False
        self.template_cache = {}
        self.template_title = ''
        self.template_title_is_empty = True

    def calculate_shelf_geometry(self) -> None:
        lc = self.layout_constraints
        if (h := gprefs['bookshelf_height']) < 120 or h > 1200:
            screen_height = self.screen().availableSize().height()
            h = max(100 + lc.shelf_height, screen_height // 3)
        lc = lc._replace(spine_height=h - lc.shelf_height, width=self.get_available_width())
        # Keep aspect ratio of spines
        default = LayoutConstraints()
        hr = lc.spine_height / default.spine_height
        lc = lc._replace(
            min_spine_width=int(default.min_spine_width * hr),
            max_spine_width=int(default.max_spine_width * hr),
            default_spine_width=int(default.default_spine_width * hr)
        )
        self.layout_constraints = lc

    def thumbnail_size(self) -> tuple[int, int]:
        lc = self.layout_constraints
        dpr = self.devicePixelRatioF()
        sz = QSizeF(lc.max_spine_width * dpr, lc.spine_height * dpr).toSize()
        return sz.width(), sz.height()

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
        self.template_title = db_pref('bookshelf_title_template') or ''
        self.template_title_is_title = self.template_title == '{title}'
        self.template_title_is_empty = not self.template_title.strip()
        self.template_inited = True

    def render_template_title(self, book_id: int) -> str:
        '''Return the title generate for this book.'''
        self.init_template(self.dbref())
        if self.template_title_is_empty:
            return ''
        if self.template_title_is_title:
            return self.dbref().new_api.field_for('title', book_id)
        mi = self.dbref().get_proxy_metadata(book_id)
        rslt = mi.formatter.safe_format(
            self.template_title, mi, TEMPLATE_ERROR, mi, column_name='title', template_cache=self.template_cache)
        return rslt or _('Unknown')

    # Miscellaneous methods

    def refresh_settings(self):
        '''Refresh the gui and render settings.'''
        self.calculate_shelf_geometry()
        if hasattr(self, 'cover_cache'):
            self.cover_cache.set_thumbnail_size(*self.thumbnail_size())
            self.cover_cache.set_disk_cache_max_size(gprefs['bookshelf_disk_cache_size'])
            self.update_ram_cache_size()
        self.bookcase.clear_spine_width_cache()
        self.invalidate()

    def view_is_visible(self) -> bool:
        '''Return if the bookshelf view is visible.'''
        with suppress(AttributeError):
            return self.gui.bookshelf_view_button.is_visible
        return False

    def shutdown(self):
        self.resize_debounce_timer.stop()
        self.pages_count_update_check_timer.stop()
        self.cover_cache.shutdown()
        self.bookcase.shutdown()
        self.expanded_cover.invalidate()

    def setModel(self, model: BooksModel | None) -> None:
        '''Set the model for this view.'''
        signals = {
            'dataChanged': 'model_data_changed', 'rowsInserted': 'model_rows_changed',
            'rowsRemoved': 'model_rows_changed', 'modelReset': 'model_reset',
        }
        if self._model is not None:
            for s, tgt in signals.items():
                getattr(self._model, s).disconnect(getattr(self, tgt))
        self._model = model
        self.selectionModel().setModel(model)
        if model is not None:
            # Create selection model for sync
            for s, tgt in signals.items():
                getattr(self._model, s).connect(getattr(self, tgt))
        self.invalidate(set_of_books_changed=True)

    def model(self) -> BooksModel | None:
        '''Return the model.'''
        return self._model

    def selectionModel(self) -> QItemSelectionModel:
        '''Return the selection model (required for AlternateViews integration).'''
        return self._selection_model

    def model_data_changed(self, top_left, bottom_right, roles):
        '''Handle model data changes.'''
        self.update_viewport()

    def model_rows_changed(self, parent, first, last):
        '''Handle model row changes.'''
        self.invalidate(set_of_books_changed=True)

    def model_reset(self):
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

    @property
    def has_transient_scrollbar(self) -> bool:
        return self.style().styleHint(QStyle.StyleHint.SH_ScrollBar_Transient, widget=self) != 0

    def resizeEvent(self, ev: QResizeEvent) -> None:
        self.resize_debounce_timer.start()
        return super().resizeEvent(ev)

    def resize_debounced(self) -> None:
        if self.layout_constraints.width != (new_width := self.get_available_width()) and new_width > 20:
            self.layout_constraints = self.layout_constraints._replace(width=new_width)
            self.invalidate()

    def update_scrollbar_ranges(self):
        '''Update scrollbar ranges based on the current shelf layouts.'''
        total_height = self.bookcase.max_possible_height
        viewport_height = self.viewport().height()
        self.verticalScrollBar().setRange(0, max(0, total_height - viewport_height))
        self.verticalScrollBar().setPageStep(viewport_height)
        self.verticalScrollBar().setSingleStep(self.layout_constraints.step_height)
        self.update_ram_cache_size()

    def get_available_width(self) -> int:
        # We always layout assuming scrollbar takes up space unless it is a
        # transient scrollbar. This means when all books fit in the viewport there
        # will be some extra space on the right. This is an acceptable
        # compromise since, layouting is expensive and we cannot know if the
        # scrollbar is needed till we do layouting once.
        sw = 0 if self.has_transient_scrollbar else self.verticalScrollBar().width()
        return self.width() - (2 * self.layout_constraints.side_margin) - sw

    def invalidate(self, set_of_books_changed=True):
        self.bookcase.invalidate(
            self.layout_constraints, model=self.model() if set_of_books_changed else None,
            group_field_name=self.grouping_mode)
        if set_of_books_changed:
            self.expanded_cover.invalidate()
        self.update_scrollbar_ranges()
        self.update_viewport()

    def check_for_pages_update(self):
        # If there are a lot of books with pages yet to be counted, re-layout
        # once all have been counted
        if self.bookcase.num_of_books_that_need_pages_counted > 10 and self.bookcase.using_page_counts:
            self.pages_count_update_check_timer.start()

    def check_pages_count_update(self):
        if (db := self.dbref()):
            num_of_books_that_need_pages_counted = db.new_api.num_of_books_that_need_pages_counted()
            if num_of_books_that_need_pages_counted:
                self.pages_count_update_check_timer.start()
            else:
                self.invalidate()

    def on_shelf_layout_done(self, books: CaseItem, shelf: CaseItem) -> None:
        if self.view_is_visible():
            if self.bookcase.layout_finished:
                self.update_scrollbar_ranges()
                self.check_for_pages_update()
            y = books.start_y
            height = books.height + shelf.height
            r = self.viewport().rect()
            r.moveTop(self.verticalScrollBar().value())
            if self.bookcase.layout_finished or r.intersects(QRect(r.left(), y, r.width(), height)):
                self.update_viewport()

    @property
    def shelves_per_screen(self) -> int:
        viewport_height = self.viewport().height()
        lc = self.layout_constraints
        return max(1, math.ceil(viewport_height / lc.step_height))

    def update_ram_cache_size(self):
        if hasattr(self, 'cover_cache'):
            lc = self.layout_constraints
            books_per_shelf = self.get_available_width() / lc.min_spine_width
            lm = gprefs['bookshelf_cache_size_multiple'] * books_per_shelf * self.shelves_per_screen
            self.cover_cache.set_ram_limit(max(0, int(lm)))

    # Paint and Drawing methods

    def shown(self):
        '''Called when this view becomes active.'''
        self.bookcase.ensure_layouting_is_current()

    def update_viewport(self):
        '''Update viewport only if the bookshelf view is visible.'''
        if not self.view_is_visible():
            return
        self.viewport().update()

    def draw_emblems(self, painter: QPainter, item: ShelfItem, scroll_y: int) -> None:
        book_id = item.book_id
        above, below = [], []
        if m := self.model():
            from calibre.gui2.ui import get_gui
            db = m.db
            marked = db.data.get_marked(book_id)
            if marked:
                below.append(m.marked_icon if marked == 'true' else m.marked_text_icon_for(marked))
            db = db.new_api
            device_connected = get_gui().device_connected is not None
            on_device = device_connected and db.field_for('ondevice', book_id)
            if on_device:
                if getattr(self, 'on_device_icon', None) is None:
                    self.on_device_icon = QIcon.ic('ok.png')
                which = above if below else below
                which.append(self.on_device_icon)

        def draw_horizontal(emblems: list[QIcon], above: bool = True) -> None:
            if not emblems:
                return
            gap = 2
            max_width = (item.width - gap) // len(emblems)
            lc = self.layout_constraints
            max_height = lc.shelf_gap if above else lc.shelf_height
            sz = min(max_width, max_height)
            width = sz
            if len(emblems) > 1:
                width += gap + sz
            x = max(0, (item.width - width) // 2) + item.start_x + lc.side_margin
            y = item.case_start_y - scroll_y
            if above:
                y += lc.shelf_gap + item.reduce_height_by - sz
            else:
                y += lc.spine_height
            for ic in emblems:
                p = ic.pixmap(sz, sz)
                painter.drawPixmap(QPoint(x, y), p)
                x += sz + gap
        draw_horizontal(above)
        draw_horizontal(below, False)

    def paintEvent(self, ev: QPaintEvent):
        '''Paint the bookshelf view.'''
        if not self.view_is_visible():
            return
        self.bookcase.ensure_layouting_is_current()

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        # Get visible area
        scroll_y = self.verticalScrollBar().value()
        viewport_rect = self.viewport().rect()
        visible_rect = viewport_rect.translated(0, scroll_y)
        hovered_item: ShelfItem | None = None
        sm = self.selectionModel()
        current_row = sm.currentIndex().row()
        shelf_bases, shelves = [], []

        for shelf in self.bookcase.iter_shelves_from_ypos(scroll_y):
            if shelf.start_y > visible_rect.bottom():
                break
            if shelf.is_shelf:
                shelf_bases.append(shelf)
                continue
            nshelf = self.expanded_cover.modify_shelf_layout(shelf)
            shelves.append((nshelf, shelf is not nshelf))
        if not hasattr(self, 'case_renderer'):
            self.case_renderer = RenderCase()
        painter.drawPixmap(
            QPoint(0, 0), self.case_renderer.background_as_pixmap(viewport_rect.width(), viewport_rect.height()))
        n = self.shelves_per_screen
        for base in shelf_bases:
            self.draw_shelf_base(painter, base, scroll_y, self.width(), base.idx % n)
        for shelf, has_expanded in shelves:
            # Draw books and inline dividers on it
            for item in shelf.items:
                if item.is_divider:
                    self.draw_inline_divider(painter, item, scroll_y)
                    continue
                if has_expanded and self.expanded_cover.is_expanded(item.book_id):
                    hovered_item = item
                else:
                    # Draw a book spine at this position
                    row = self.bookcase.book_id_to_row_map[item.book_id]
                    self.draw_spine(painter, item, scroll_y, sm.isRowSelected(row), row == current_row)
                self.draw_emblems(painter, item, scroll_y)
        if hovered_item is not None:
            row = self.bookcase.book_id_to_row_map[hovered_item.book_id]
            is_selected, is_current = sm.isRowSelected(row), row == current_row
            self.expanded_cover.draw_expanded_cover(
                painter, scroll_y, self.layout_constraints, is_selected, is_current,
                self.selection_highlight_color(is_selected, is_current))

    def draw_shelf_base(self, painter: QPainter, shelf: ShelfItem, scroll_y: int, width: int, instance: int):
        p = self.case_renderer.shelf_as_pixmap(width, self.layout_constraints.shelf_height, instance)
        shelf_rect = QRect(0, shelf.start_y, width, self.layout_constraints.shelf_height)
        shelf_rect.translate(0, -scroll_y)
        painter.drawPixmap(QPoint(0, shelf.start_y - scroll_y), p)

    def draw_selection_highlight(self, painter: QPainter, spine_rect: QRect, color: QColor):
        painter.save()
        pen = QPen(color)
        gap = min(4, self.layout_constraints.horizontal_gap // 2)
        pen.setWidth(2 * gap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(1.0)
        painter.drawRect(spine_rect.adjusted(gap, gap, -gap, -gap))
        painter.restore()

    @lru_cache(maxsize=4096)
    def get_sized_text(self, text: str, max_width: int, start: float, stop: float) -> tuple[str, QFont, QRect]:
        '''Return a text, a QFont and a QRect that fit into the max_width.'''
        font = QFont(self.font())
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

    def draw_inline_divider(self, painter: QPainter, divider: ShelfItem, scroll_y: int):
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
        elided_text, font, sized_rect = self.get_sized_text(divider.group_name, text_rect.width(), 12, 8)
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
        if gprefs['bookshelf_up_to_down']:
            painter.rotate(180)
            text_rect.adjust(max(0, line_rect.width() - 6), 0, 0, 0)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)
        painter.restore()

    def default_cover_pixmap(self) -> PixmapWithDominantColor:
        lc = self.layout_constraints
        sz = (QSizeF(lc.hover_expanded_width, lc.spine_height) * self.devicePixelRatioF()).toSize()
        return default_cover_pixmap(sz.width(), sz.height())

    def draw_spine(self, painter: QPainter, spine: ShelfItem, scroll_y: int, is_selected: bool, is_current: bool):
        '''Draw a book spine.'''
        lc = self.layout_constraints
        spine_rect = spine.rect(lc).translated(0, -scroll_y)
        thumbnail = self.cover_cache.thumbnail_as_pixmap(spine.book_id)
        if thumbnail is None:  # not yet rendered
            self.case_renderer.ensure_theme(is_dark_theme())
            spine_color = self.case_renderer.theme.background
        else:
            if thumbnail.isNull():
                thumbnail = self.default_cover_pixmap()
            spine_color = thumbnail.dominant_color
            if not spine_color.isValid():
                spine_color = self.default_cover_pixmap().dominant_color

            if is_selected or is_current:
                spine_color = spine_color.lighter(120)

            # Draw spine background with gradient (darker edges, lighter center)
            self.draw_spine_background(painter, spine_rect, spine_color)

            # Draw cover thumbnail overlay
            self.draw_spine_cover(painter, spine_rect, thumbnail)

        # Draw title (rotated vertically)
        title = self.render_template_title(spine.book_id)
        self.draw_spine_title(painter, spine_rect, spine_color, title)

        # Draw selection highlight around the spine
        color = self.selection_highlight_color(is_selected, is_current)
        if color.isValid():
            self.draw_selection_highlight(painter, spine_rect, color)

    def selection_highlight_color(self, is_selected: bool, is_current: bool) -> QColor:
        if is_current:
            return self.palette().color(QPalette.ColorRole.LinkVisited)
        if is_selected:
            return self.palette().color(QPalette.ColorRole.Highlight)
        return QColor()

    def draw_spine_background(self, painter: QPainter, rect: QRect, spine_color: QColor):
        '''Draw spine background with gradient (darker edges, lighter center).'''
        painter.save()
        painter.setOpacity(1.0)
        gradient = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.topRight()))
        gradient.setColorAt(0, spine_color.darker(115))
        gradient.setColorAt(0.5, spine_color)
        gradient.setColorAt(1, spine_color.darker(115))
        painter.fillRect(rect, QBrush(gradient))

        # Add subtle vertical gradient for depth
        vertical_gradient = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomLeft()))
        vertical_gradient.setColorAt(0, QColor(255, 255, 255, 20))  # Slight highlight at top
        vertical_gradient.setColorAt(1, QColor(0, 0, 0, 30))  # Slight shadow at bottom
        painter.fillRect(rect, QBrush(vertical_gradient))
        painter.restore()

    def draw_spine_title(self, painter: QPainter, rect: QRect, spine_color: QColor, title: str):
        '''Draw vertically the title on the spine.'''
        if not title:
            return
        painter.save()
        painter.translate(rect.left() + rect.width() // 2, rect.top() + rect.height() // 2)
        painter.rotate(90 if gprefs['bookshelf_up_to_down'] else -90)

        # Determine text color based on spine background brightness
        text_color = self.get_contrasting_text_color(spine_color)
        painter.setPen(text_color)

        text_rect = QRect(
            -rect.height() // 2,
            -rect.width() // 2,
            rect.height(),
            rect.width(),
        )
        # leave space for margin with top of the spine
        text_rect.adjust(6, 0, -6, 0)
        elided_text, font, _rect = self.get_sized_text(title, text_rect.width(), 12, 8)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided_text)
        painter.restore()

    def draw_spine_cover(self, painter: QPainter, rect: QRect, thumbnail: PixmapWithDominantColor) -> None:
        match gprefs['bookshelf_thumbnail']:
            case 'none':
                return
            # Adjust size
            case 'crops':
                thumbnail = thumbnail.copy(0, 0, rect.width(), thumbnail.height())
            case 'edge':
                width = round(max(10, rect.width() * 0.2))
                thumbnail = thumbnail.copy(0, 0, width, thumbnail.height())
                rect = QRect(rect.x(), rect.y(), width, rect.height())
        # Draw with opacity
        painter.save()
        painter.setOpacity(0.3)  # 30% opacity
        dpr = thumbnail.devicePixelRatioF()
        thumbnail.setDevicePixelRatio(self.devicePixelRatioF())
        painter.drawPixmap(rect, thumbnail)
        thumbnail.setDevicePixelRatio(dpr)
        painter.restore()

    # Cover integration methods

    def load_hover_cover(self, si: ShelfItem) -> tuple[PixmapWithDominantColor, QSize]:
        lc = self.layout_constraints
        cover_img = self.dbref().cover(si.book_id, as_image=True)
        dpr = self.devicePixelRatioF()
        final_sz = QSize(lc.hover_expanded_width, lc.spine_height - si.reduce_height_by)
        sz = (QSizeF(final_sz) * dpr).toSize()
        if cover_img is None or cover_img.isNull():
            cover_pixmap = self.default_cover_pixmap()
            resize_needed, nw, nh = fit_image(cover_pixmap.width(), cover_pixmap.height(), sz.width(), sz.height())
            if resize_needed:
                cover_pixmap = PixmapWithDominantColor(
                    cover_pixmap.scaled(int(nw), int(nh), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            _, cover_img = resize_to_fit(cover_img, sz.width(), sz.height())
            cover_pixmap = PixmapWithDominantColor.fromImage(cover_img)
        final_sz = (QSizeF(cover_pixmap.size()) / dpr).toSize()
        return cover_pixmap, final_sz

    def get_contrasting_text_color(self, background_color: QColor) -> QColor:
        if not background_color or not background_color.isValid():
            return self.text_color_for_light_background
        is_yellow_gold = background_color.red() > 180 and background_color.yellow() > 150 and background_color.blue() < 150
        threshold = 0.35 if is_yellow_gold else 0.5
        return self.text_color_for_light_background if background_color.lightnessF() > threshold else self.text_color_for_dark_background

    # Selection methods (required for AlternateViews integration)

    def select_rows(self, rows: Iterable[int], using_ids: bool = False) -> None:
        if not (m := self.model()):
            return
        if using_ids:
            row_indices = []
            for book_id in rows:
                if (row := self.row_from_book_id(book_id)) is not None:
                    row_indices.append(row)
            rows = row_indices

        sel = selection_for_rows(m, rows)
        sm = self.selectionModel()
        sm.select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

    def selectAll(self):
        m = self.model()
        sm = self.selectionModel()
        sel = QItemSelection(m.index(0, 0), m.index(m.rowCount(QModelIndex())-1, 0))
        sm.select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

    def set_current_row(self, row):
        sm = self.selectionModel()
        sm.setCurrentIndex(self.model().index(row, 0), QItemSelectionModel.SelectionFlag.NoUpdate)

    def set_database(self, newdb, stage=0):
        if stage == 0:
            self.grouping_mode = newdb.new_api.pref('bookshelf_grouping_mode', '')

            # Clear caches when database changes
            self.template_inited = False
            self.cover_cache.set_database(newdb)
            self.bookcase.clear_spine_width_cache()
            self.invalidate(set_of_books_changed=True)

    def set_context_menu(self, menu: QMenu):
        self.context_menu = menu

    def contextMenuEvent(self, ev: QContextMenuEvent):
        # Create menu with grouping options
        menu = QMenu(self)

        # Add grouping submenu
        grouping_menu = menu.addMenu(QIcon.ic('bookshelf.png'), _('Group by'))
        fm = self.gui.current_db.new_api.field_metadata

        def add(field: str, name: str) -> None:
            action = grouping_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(self.grouping_mode == field)
            action.triggered.connect(partial(self.set_grouping_mode, field))
        add('', _('Ungrouped'))
        grouping_menu.addSeparator()
        cf = {}
        for field, m in fm.custom_field_metadata(include_composites=False).items():
            if m['is_category'] or m['datatype'] == 'datetime':
                cf[field] = numeric_sort_key(m['name'])
        for k in all_groupings():
            cf[k] = numeric_sort_key(fm[k])
        for k in sorted(cf, key=cf.get):
            add(k, fm[k]['name'])
        # Add standard context menu items if available
        if cm := self.context_menu:
            menu.addSeparator()
            for action in cm.actions():
                menu.addAction(action)

        menu.popup(ev.globalPos())
        ev.accept()

    def set_grouping_mode(self, mode: str):
        '''Set the grouping mode and refresh display.'''
        if mode != self.grouping_mode:
            self.grouping_mode = mode
            self.dbref().set_pref('bookshelf_grouping_mode', mode)
            self.invalidate()

    def get_selected_ids(self) -> list[int]:
        return [self.book_id_from_row(index.row()) for index in self.selectionModel().selectedRows() if index.isValid()]

    def current_book_state(self) -> SavedState:
        '''Get current book state for restoration.'''
        sm = self.selectionModel()
        r = sm.currentIndex().row()
        current_book_id = 0
        if r > -1:
            with suppress(Exception):
                current_book_id = self.bookcase.row_to_book_id[r]
        selected_rows = (index.row() for index in sm.selectedRows())
        selected_book_ids = set()
        with suppress(Exception):
            selected_book_ids = {self.bookcase.row_to_book_id[r] for r in selected_rows}
        return SavedState(current_book_id, selected_book_ids)

    def restore_current_book_state(self, state: SavedState) -> None:
        m = self.model()
        if not state or not m:
            return
        with suppress(Exception):
            selected_rows = set(map(m.db.id_to_index, state.selected_book_ids))
            self.select_rows(selected_rows)
        with suppress(Exception):
            self.set_current_row(m.db.id_to_index(state.current_book_id))

    def marked_changed(self, old_marked: set[int], current_marked: set[int]):
        # Refresh display if marked books changed
        self.update_viewport()

    def indices_for_merge(self, resolved=True):
        return self.selectionModel().selectedRows()

    # Mouse and keyboard events {{{

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if ev.matches(QKeySequence.StandardKey.SelectAll):
            self.selectAll()
            ev.accept()
            return
        if (key := ev.key()) not in (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageDown,
            Qt.Key.Key_PageUp, Qt.Key.Key_Home, Qt.Key.Key_End
        ):
            return super().keyPressEvent(ev)
        if not self.bookcase.book_ids_in_visual_order or not (m := self.model()):
            return
        ev.accept()
        target_book_id = 0
        current_row = self.selectionModel().currentIndex().row()
        try:
            current_book_id = self.bookcase.row_to_book_id[current_row]
        except Exception:
            current_book_id = self.bookcase.book_ids_in_visual_order[0]
        has_ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
        has_shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        match key:
            case Qt.Key.Key_Left:
                target_book_id = self.bookcase.visual_neighboring_book(current_book_id, delta=-1)
            case Qt.Key.Key_Right:
                target_book_id = self.bookcase.visual_neighboring_book(current_book_id, delta=1)
            case Qt.Key.Key_Up:
                target_book_id = self.bookcase.book_in_column_of(current_book_id, delta=-1)
            case Qt.Key.Key_Down:
                target_book_id = self.bookcase.book_in_column_of(current_book_id, delta=1)
            case Qt.Key.Key_PageUp:
                target_book_id = self.bookcase.book_in_column_of(current_book_id, delta=-self.shelves_per_screen)
            case Qt.Key.Key_PageDown:
                target_book_id = self.bookcase.book_in_column_of(current_book_id, delta=self.shelves_per_screen)
            case Qt.Key.Key_Home:
                if has_ctrl:
                    target_book_id = self.bookcase.book_ids_in_visual_order[0]
                    has_ctrl = False
                else:
                    target_book_id = self.bookcase.end_book_on_shelf_of(current_book_id, first=True)
            case Qt.Key.Key_End:
                if has_ctrl:
                    target_book_id = self.bookcase.book_ids_in_visual_order[-1]
                    has_ctrl = False
                else:
                    target_book_id = self.bookcase.end_book_on_shelf_of(current_book_id, first=False)
        if target_book_id <= 0:
            return
        target_index = m.index(self.bookcase.book_id_to_row_map[target_book_id], 0)
        sm = self.selectionModel()
        if has_shift:
            handle_selection_click(self, target_index, self.bookcase.visual_row_cmp, self.selection_between)
        elif has_ctrl:
            sm.setCurrentIndex(target_index, QItemSelectionModel.SelectionFlag.Rows | QItemSelectionModel.SelectionFlag.Toggle)
        else:
            sm.setCurrentIndex(target_index, QItemSelectionModel.SelectionFlag.Rows | QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.scrollTo(target_index)
        self.update_viewport()

    def scrollTo(self, index: QModelIndex, hint: QAbstractItemView.ScrollHint = QAbstractItemView.ScrollHint.EnsureVisible) -> None:
        si = self.bookcase.book_id_to_item_map.get(self.book_id_from_row(index.row()))
        if si is None:
            return
        viewport_height = self.viewport().height()
        shelf_height = self.layout_constraints.step_height
        match hint:
            case QAbstractItemView.ScrollHint.PositionAtTop:
                y = 0
            case QAbstractItemView.ScrollHint.PositionAtBottom:
                y = max(0, viewport_height - shelf_height)
            case QAbstractItemView.ScrollHint.PositionAtCenter:
                y = max(0, (viewport_height - shelf_height)//2)
            case QAbstractItemView.ScrollHint.EnsureVisible:
                top = si.case_start_y - self.verticalScrollBar().value()
                if top >= 0 and top + shelf_height <= viewport_height:
                    return
                y = 0 if top < 0 else max(0, viewport_height - shelf_height)
        self.verticalScrollBar().setValue(si.case_start_y - y)
        self.update_viewport()

    def selection_between(self, a: QModelIndex, b: QModelIndex) -> QItemSelection:
        if m := self.model():
            return selection_for_rows(m, self.bookcase.visual_selection_between(a.row(), b.row()))
        return QItemSelection()

    def handle_mouse_move_event(self, ev: QMouseEvent):
        ev.accept()
        if ev.buttons() & Qt.MouseButton.LeftButton:
            handle_selection_drag(self, self.indexAt(ev.pos()), self.click_start_data, self.bookcase.visual_row_cmp, self.selection_between)
            return
        if gprefs['bookshelf_hover'] == 'none':
            return
        pos = ev.pos()
        case_item, _, shelf_item = self.item_at_position(pos.x(), pos.y())
        if shelf_item is not None and not shelf_item.is_divider:
            self.expanded_cover.shelf_item_hovered(case_item, shelf_item)
        else:
            self.expanded_cover.shelf_item_hovered()

    def currentIndex(self):
        return self.selectionModel().currentIndex()

    def handle_mouse_press_event(self, ev: QMouseEvent) -> None:
        if ev.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton) or not (index := self.indexAt(ev.pos())).isValid():
            return
        sm = self.selectionModel()
        flags = QItemSelectionModel.SelectionFlag.Rows
        modifiers = ev.modifiers()
        if ev.button() == Qt.MouseButton.RightButton:
            modifiers = Qt.KeyboardModifier.NoModifier  # no extended selection with right button
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Toggle selection
            sm.setCurrentIndex(index, flags | QItemSelectionModel.SelectionFlag.Toggle)
        else:
            if not modifiers & Qt.KeyboardModifier.ShiftModifier:
                sm.setCurrentIndex(index, flags | QItemSelectionModel.SelectionFlag.ClearAndSelect)
            self.click_start_data = handle_selection_click(self, index, self.bookcase.visual_row_cmp, self.selection_between)
        ev.accept()

    def handle_mouse_release_event(self, ev: QMouseEvent) -> None:
        self.click_start_data = None

    def mouseDoubleClickEvent(self, ev: QMouseEvent) -> bool:
        '''Handle mouse double-click events on the viewport.'''
        index = self.indexAt(ev.pos())
        self.click_start_data = None
        if index.isValid() and (row := index.row()) >= 0:
            # Set as current row first
            self.set_current_row(row)
            # Open the book
            self.gui.iactions['View'].view_triggered(row)
            ev.accept()

    def viewportEvent(self, ev: QEvent) -> None:
        if ev.type() == QEvent.Type.Leave:
            # Clear hover when mouse leaves viewport
            self.expanded_cover.invalidate()
            self.update_viewport()
            ev.accept()
            return True
        return super().viewportEvent(ev)
    # }}}

    def item_at_position(self, x: int, y: int) -> tuple[CaseItem|None, CaseItem|None, ShelfItem|None]:
        scroll_y = self.verticalScrollBar().value()
        content_y = y + scroll_y
        lc = self.layout_constraints
        x -= lc.side_margin
        if (shelf := self.bookcase.shelf_with_ypos(content_y)) is not None:
            modshelf = self.expanded_cover.modify_shelf_layout(shelf)
            if (item := modshelf.book_or_divider_at_xpos(x, lc)) is not None:
                return shelf, modshelf, item
        return None, None, None

    def book_id_at_position(self, x: int, y: int) -> int:
        _, _, shelf_item = self.item_at_position(x, y)
        if shelf_item is not None and not shelf_item.is_divider:
            return shelf_item.book_id
        return -1

    def book_row_at_position(self, x: int, y: int) -> int:
        ' Find which book is at the given position. x, y are in viewport coordinates '
        book_id = self.book_id_at_position(x, y)
        if book_id > 0:
            if (row := self.row_from_book_id(book_id)) is not None:
                return row
        return -1

    def indexAt(self, pos: QPoint) -> QModelIndex:
        if (m := self.model()):
            row = self.book_row_at_position(pos.x(), pos.y())
            if row >= 0 and (ans := m.index(row, 0)).isValid():
                return ans
        return QModelIndex()
