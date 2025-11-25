#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import (
    QAbstractScrollArea,
    QApplication,
    QBrush,
    QColor,
    QEvent,
    QFont,
    QFontMetrics,
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
)

from calibre.gui2 import gprefs
from calibre.gui2.library.alternate_views import setup_dnd_interface
from calibre.gui2.library.bookshelf_utils import (
    get_cover_color,
    get_spine_thumbnail,
    invalidate_caches,
)
from calibre.utils.localization import _
from time import time


@setup_dnd_interface
class BookshelfView(QAbstractScrollArea):

    '''
    Enhanced bookshelf view displaying books as spines on shelves.

    This view provides an immersive browsing experience with sorting
    and grouping capabilities.
    '''

    files_dropped = pyqtSignal(object)
    books_dropped = pyqtSignal(object)

    # Spine dimensions
    SPINE_HEIGHT = 150
    SPINE_MIN_WIDTH = 35  # Increased from 25
    SPINE_MAX_WIDTH = 70  # Increased from 55
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

        # Viewport setup - set background color directly on viewport
        viewport = self.viewport()
        viewport.setAutoFillBackground(True)
        palette = viewport.palette()
        palette.setColor(QPalette.ColorRole.Base, self.BACKGROUND_COLOR)
        viewport.setPalette(palette)

        # Initialize drag and drop interface (sets drag_allowed, drag_start_pos, etc.)
        # Note: QAbstractScrollArea doesn't have setDragEnabled/setDragDropMode,
        # so we set the attributes manually
        self.drag_allowed = True
        self.drag_start_pos = None

        # Phase 2: Cover loading and caching
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
        # When hovered, book expands to this width (like JSX mock: 105px)
        self.HOVER_EXPANDED_WIDTH = 105

        # Timer for lazy loading covers
        self._load_covers_timer = QTimer(self)
        self._load_covers_timer.setSingleShot(True)
        self._load_covers_timer.timeout.connect(self._load_visible_covers)

    def setModel(self, model):
        '''Set the model for this view.'''
        if self._model is not None:
            # Disconnect old model signals if needed
            pass
        self._model = model
        if model is not None:
            # Create selection model for AlternateViews integration
            self._selection_model = QItemSelectionModel(model, self)
            model.dataChanged.connect(self._model_data_changed)
            model.rowsInserted.connect(self._model_rows_changed)
            model.rowsRemoved.connect(self._model_rows_changed)
            model.modelReset.connect(self._model_reset)
        else:
            self._selection_model = None
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
        # Phase 2: Invalidate caches for removed books if needed
        # (This is a simplified version - full implementation would track removed book IDs)
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

        # Calculate total height needed (Phase 2: calculate based on actual layout)
        viewport_width = self.viewport().width()
        x_pos = 10
        shelf_y = 10
        db = self._model.db

        for row in range(row_count):
            try:
                index = self._model.index(row, 0)
                if index.isValid():
                    book_id = self._model.id(index)
                    mi = db.get_metadata(book_id, index_is_id=True)
                    pages = getattr(mi, 'pages', 0) or 0
                    spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, pages / 8))
                else:
                    spine_width = 40
            except (AttributeError, IndexError, KeyError, TypeError):
                spine_width = 40

            x_pos += int(spine_width) + 2

            # If we've filled the shelf, move to next shelf
            if x_pos + spine_width > viewport_width - 10:
                x_pos = 10
                shelf_y += self.SHELF_SPACING

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

        # Draw book spines and shelves
        row_count = self._model.rowCount(QModelIndex())
        if row_count > 0:
            x_pos = 10  # Start position
            shelf_y = 10 + scroll_y
            db = self._model.db
            shelf_started = False
            shelf_start_row = 0  # Track which row starts each shelf
            
            # Track hovered book info for shift calculation
            hover_spine_width = 0
            hover_on_current_shelf = False
            if self._hovered_row >= 0:
                try:
                    hover_index = self._model.index(self._hovered_row, 0)
                    if hover_index.isValid():
                        hover_book_id = self._model.id(hover_index)
                        hover_mi = db.get_metadata(hover_book_id, index_is_id=True)
                        hover_pages = getattr(hover_mi, 'pages', 0) or 0
                        hover_spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, hover_pages / 8))
                except (AttributeError, IndexError, KeyError, TypeError):
                    pass

            for row in range(row_count):
                if row >= row_count:
                    break

                # Calculate spine width from page count (Phase 2)
                try:
                    index = self._model.index(row, 0)
                    if index.isValid():
                        book_id = self._model.id(index)
                        mi = db.get_metadata(book_id, index_is_id=True)
                        pages = getattr(mi, 'pages', 0) or 0
                        spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, pages / 8))
                    else:
                        spine_width = 40
                except (AttributeError, IndexError, KeyError, TypeError):
                    spine_width = 40

                # Check if this book is hovered
                is_hovered = row == self._hovered_row
                
                # Check if hovered book is on current shelf (by checking if it's between shelf_start_row and current row)
                # Reset for each iteration
                hover_on_current_shelf = False
                if self._hovered_row >= 0:
                    hover_on_current_shelf = (shelf_start_row <= self._hovered_row <= row)
                
                # Calculate shift for books to the right of hovered book on same shelf
                shift_amount = 0
                if hover_on_current_shelf and self._hovered_row < row:
                    # This book is to the right of hovered book on the same shelf - shift it
                    # Shift by exactly the difference: (cover_width - original_spine_width)
                    # Get actual cover width if available, otherwise use expanded width
                    if self._hover_cover_pixmap is not None and not self._hover_cover_pixmap.isNull():
                        actual_cover_width = self._hover_cover_pixmap.width()
                    else:
                        actual_cover_width = self.HOVER_EXPANDED_WIDTH
                    full_shift = max(0, actual_cover_width - hover_spine_width)
                    shift_amount = full_shift * self._hover_shift_progress

                # Apply shift for books to the right of hovered book
                if is_hovered:
                    # Cover replaces spine - use actual cover width from loaded pixmap
                    # Get the actual cover width (accounting for aspect ratio)
                    if self._hover_cover_pixmap is not None and not self._hover_cover_pixmap.isNull():
                        cover_display_width = self._hover_cover_pixmap.width()
                    else:
                        # Fallback to expanded width if cover not loaded yet
                        cover_display_width = self.HOVER_EXPANDED_WIDTH
                    # Keep left edge at original spine position
                    current_x = x_pos
                    display_width = int(cover_display_width)
                else:
                    # Shift books to the right of hovered book
                    current_x = x_pos + shift_amount
                    display_width = int(spine_width)

                # Draw shelf before first book on each row
                if not shelf_started or x_pos == 10:
                    if shelf_y + self.SPINE_HEIGHT >= visible_rect.top() and shelf_y <= visible_rect.bottom():
                        self._draw_shelf(painter, shelf_y, visible_rect)
                    shelf_started = True

                # Check if spine is visible
                # Ensure first book doesn't get cut off - clamp to viewport left edge
                clamped_x = max(visible_rect.left(), int(current_x))
                if clamped_x != int(current_x):
                    # Adjust width if we clamped the x position
                    display_width = max(1, display_width - (clamped_x - int(current_x)))
                
                spine_rect = QRect(clamped_x, shelf_y, display_width, self.SPINE_HEIGHT)
                
                if spine_rect.bottom() >= visible_rect.top() and spine_rect.top() <= visible_rect.bottom():
                    # Pre-load color if not cached (ensure colors are loaded)
                    if book_id not in self._cover_colors:
                        self._get_spine_color(book_id, db)
                    self._draw_spine(painter, row, spine_rect)

                # Update x_pos for next book
                # Always use original spine_width for layout calculation
                # The shift_amount already accounts for the expansion
                x_pos += int(spine_width) + 2  # Small gap between spines

                # If we've filled the shelf, move to next shelf
                if x_pos + spine_width > viewport_rect.width() - 10:
                    x_pos = 10
                    shelf_y += self.SHELF_SPACING
                    shelf_started = False
                    shelf_start_row = row + 1  # Next shelf starts at next row

        # Trigger lazy loading of visible covers (Phase 2)
        if not self._load_covers_timer.isActive():
            self._load_covers_timer.start(100)  # Delay 100ms to avoid loading during scroll

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
            pages = getattr(mi, 'pages', 0) or 0
            spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, pages / 8))
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

            # Truncate title to fit
            fm = QFontMetrics(font)
            max_width = rect.height() - 10
            elided_title = fm.elidedText(title, Qt.TextElideMode.ElideRight, max_width)
            text_rect = QRect(int(-rect.height() / 2), int(-rect.width() / 2), int(rect.height()), int(rect.width()))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided_title)
            painter.restore()

        # Draw hover cover popup (Phase 2) - shown when hovered
        # Check if this is the hovered book and we have a cover loaded
        if is_hovered and self._hover_cover_pixmap is not None:
            # Draw the hover cover - it will replace the transparent spine
            self._draw_hover_cover(painter, rect)

    # Phase 2: Cover integration methods

    def _get_contrasting_text_color(self, background_color):
        '''
        Calculate the appropriate text color (light or dark) based on background brightness.
        Uses relative luminance formula to determine contrast.
        
        :param background_color: QColor of the spine background
        :return: QColor for text (light for dark backgrounds, dark for light backgrounds)
        '''
        if background_color is None or not background_color.isValid():
            return self.TEXT_COLOR
        
        # Get RGB values (0-255)
        r = background_color.red()
        g = background_color.green()
        b = background_color.blue()
        
        # Calculate relative luminance using standard formula
        # Normalize RGB to 0-1 range
        def normalize(value):
            val = value / 255.0
            # Apply gamma correction
            if val <= 0.03928:
                return val / 12.92
            else:
                return ((val + 0.055) / 1.055) ** 2.4
        
        r_norm = normalize(r)
        g_norm = normalize(g)
        b_norm = normalize(b)
        
        # Relative luminance formula (WCAG standard)
        luminance = 0.2126 * r_norm + 0.7152 * g_norm + 0.0722 * b_norm
        
        # Use dark text for light backgrounds (luminance > 0.5)
        # Use light text for dark backgrounds (luminance <= 0.5)
        if luminance > 0.5:
            return self.TEXT_COLOR_DARK
        else:
            return self.TEXT_COLOR

    def _get_spine_color(self, book_id, db):
        '''Get the spine color for a book, using cache if available.'''
        if book_id in self._cover_colors:
            cached_color = self._cover_colors[book_id]
            # Validate cached color
            if cached_color is not None and cached_color.isValid():
                return cached_color
            # Remove invalid color from cache
            self._cover_colors.pop(book_id, None)
        
        # Load color from cover
        try:
            color = get_cover_color(book_id, db)
            # Ensure color is valid
            if color is None or not color.isValid():
                color = self.DEFAULT_SPINE_COLOR
            self._cover_colors[book_id] = color
            return color
        except Exception:
            # On error, use default color
            color = self.DEFAULT_SPINE_COLOR
            self._cover_colors[book_id] = color
            return color

    def _get_spine_thumbnail(self, book_id, db):
        '''Get the spine thumbnail for a book, using cache if available.'''
        if book_id in self._spine_thumbnails:
            thumb = self._spine_thumbnails[book_id]
            if thumb is not None and not thumb.isNull():
                return thumb
            # Remove invalid thumbnail from cache
            self._spine_thumbnails.pop(book_id, None)

        # Try to load thumbnail
        try:
            thumbnail = get_spine_thumbnail(book_id, db, self.THUMBNAIL_HEIGHT)
            if thumbnail is not None and not thumbnail.isNull():
                self._spine_thumbnails[book_id] = thumbnail
                return thumbnail
        except Exception:
            pass

        # If loading failed, try direct cover loading as fallback
        try:
            cover_data = db.cover(book_id, as_image=True)
            if cover_data is not None and not cover_data.isNull():
                # Generate thumbnail directly
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
        x_pos = 10
        shelf_y = 10

        # Load covers for visible books
        for row in range(row_count):
            try:
                index = self._model.index(row, 0)
                if not index.isValid():
                    continue

                book_id = self._model.id(index)
                mi = db.get_metadata(book_id, index_is_id=True)
                pages = getattr(mi, 'pages', 0) or 0
                spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, pages / 8))
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
                x_pos = 10
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
                    pages = getattr(mi, 'pages', 0) or 0
                    spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, pages / 8))
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

    def select_rows(self, rows):
        '''Select the specified rows.'''
        if self._model is None or self._selection_model is None:
            return
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
        if stage == 0 and self._model is not None:
            # Model will be updated by AlternateViews
            # Phase 2: Clear caches when database changes
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
        if self.context_menu is None:
            return
        from calibre.constants import islinux
        from calibre.gui2.main_window import clone_menu
        m = clone_menu(self.context_menu) if islinux else self.context_menu
        m.popup(event.globalPos())
        event.accept()

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
            # Phase 2: Handle hover detection
            self._handle_mouse_move(event)
        elif event.type() == QEvent.Type.Leave:
            # Phase 2: Clear hover when mouse leaves viewport
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

    def _sync_selection_to_main_view(self):
        '''Sync selection with the main library view.'''
        if self.gui is None or not hasattr(self.gui, 'library_view'):
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

        x_pos = 10
        shelf_y = 10
        shelf_start_row = 0

        for row in range(row_count):
            # Calculate spine width from page count
            try:
                index = self._model.index(row, 0)
                if index.isValid():
                    book_id = self._model.id(index)
                    db = self._model.db
                    mi = db.get_metadata(book_id, index_is_id=True)
                    pages = getattr(mi, 'pages', 0) or 0
                    spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, pages / 8))
                else:
                    spine_width = 40
            except (AttributeError, IndexError, KeyError, TypeError):
                spine_width = 40

            # Account for hover expansion - if this book is hovered, use expanded width
            is_hovered = row == self._hovered_row
            if is_hovered:
                # Use expanded width for hit testing
                display_width = self.HOVER_EXPANDED_WIDTH
            else:
                display_width = int(spine_width)
            
            # Account for shift if a book to the left is hovered on same shelf
            current_x = x_pos
            if self._hovered_row >= 0 and shelf_start_row <= self._hovered_row < row:
                # This book is to the right of hovered book on same shelf - account for shift
                try:
                    hover_index = self._model.index(self._hovered_row, 0)
                    if hover_index.isValid():
                        hover_book_id = self._model.id(hover_index)
                        hover_mi = db.get_metadata(hover_book_id, index_is_id=True)
                        hover_pages = getattr(hover_mi, 'pages', 0) or 0
                        hover_spine_width = max(self.SPINE_MIN_WIDTH, min(self.SPINE_MAX_WIDTH, hover_pages / 8))
                        shift_amount = max(0, self.HOVER_EXPANDED_WIDTH - hover_spine_width)
                        current_x = x_pos + shift_amount
                except (AttributeError, IndexError, KeyError, TypeError):
                    pass

            spine_rect = QRect(int(current_x), shelf_y, display_width, self.SPINE_HEIGHT)

            # Check if point is within this spine (accounting for expansion and shift)
            if spine_rect.contains(x, content_y):
                return row

            # Update x_pos for next book (use original position for layout)
            x_pos += int(spine_width) + 2

            # Check if we need to move to next shelf
            if x_pos + spine_width > self.viewport().width() - 10:
                x_pos = 10
                shelf_y += self.SHELF_SPACING
                shelf_start_row = row + 1
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

