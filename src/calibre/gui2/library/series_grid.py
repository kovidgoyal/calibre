#!/usr/bin/env python
# License: GPLv3

from random import Random, choice, uniform
from time import monotonic
from typing import NamedTuple

from qt.core import (
    QAbstractProxyModel,
    QColor,
    QItemSelectionModel,
    QListView,
    QModelIndex,
    QPainter,
    QPixmap,
    QPoint,
    QRect,
    QSize,
    QStyleOptionViewItem,
    Qt,
    QTimer,
    QVariantAnimation,
)

from calibre.ebooks.metadata import fmt_sidx
from calibre.gui2 import config, gprefs
from calibre.gui2.library.alternate_views import CoverDelegate, GridView, double_click_action
from calibre.gui2.library.caches import CoverThumbnailCache, ThumbnailRenderer
from calibre.gui2.library.series_grid_animations import paint_page_curl, paint_slide
from calibre.utils.icu import sort_key
from calibre.utils.localization import _, ngettext

MAX_STACK_SIZE = 10


def stack_size():
    return max(1, min(MAX_STACK_SIZE, int(gprefs['series_grid_stack_size'])))


def cover_pose(book_id, front=False):
    mode = gprefs['series_grid_stack_rendering']
    if mode == 'neat' or (mode == 'hybrid' and front):
        return 0.0, 0.0, 0.0
    # Seed per book, independently of its position in the stack or repaint.
    rng = Random(book_id)
    return rng.uniform(-6, 6), rng.uniform(-3, 3), rng.uniform(-3, 3)


class CoverTransition(NamedTuple):
    row: int
    old_book_id: int
    direction: int


class SeriesModel(QAbstractProxyModel):
    """One stable row per group, mapped to its currently displayed book.

    Only books in the current search/virtual library are grouped. Group order
    follows the alphabetical group name. Series follow series_index;
    author and tag stacks retain the source sort and can share books.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.view = parent
        self.groups = []
        self.positions = {}
        self.reset_positions = False
        self.book_to_group = {}
        self.book_to_groups = {}
        self.book_to_source = {}
        self.rebuild_timer = QTimer(self)
        self.rebuild_timer.setSingleShot(True)
        self.rebuild_timer.timeout.connect(self.rebuild)

    @property
    def db(self):
        source = self.sourceModel()
        return source.db if source is not None else None

    def __getattr__(self, name):
        # Formatting caches used by CoverDelegate have no row coordinates.
        source = self.sourceModel()
        if source is None:
            raise AttributeError(name)
        return getattr(source, name)

    def setSourceModel(self, source):
        previous = self.sourceModel()
        if previous is not None:
            for signal in (previous.modelReset, previous.layoutChanged, previous.rowsInserted, previous.rowsRemoved, previous.dataChanged):
                signal.disconnect(self.schedule_rebuild)
        super().setSourceModel(source)
        if source is not None:
            for signal in (source.modelReset, source.layoutChanged, source.rowsInserted, source.rowsRemoved, source.dataChanged):
                signal.connect(self.schedule_rebuild)
        self.rebuild()

    def schedule_rebuild(self, *args):
        self.rebuild_timer.start(0)

    def rebuild(self):
        source = self.sourceModel()
        groups = {}
        source_rows = {}
        group_by = gprefs['series_grid_group_by']
        if source is not None and source.db is not None:
            api = source.db.new_api
            for row in range(source.rowCount()):
                book_id = source.id(row)
                if group_by == 'series':
                    series = api.field_for('series', book_id)
                    keys = [('series', series)] if series else [('book', book_id)] if gprefs['series_grid_show_standalone'] else []
                else:
                    keys = [(group_by, value) for value in dict.fromkeys(api.field_for(group_by, book_id) or ())]
                for key in keys:
                    groups.setdefault(key, []).append(book_id)
                source_rows[book_id] = row
            if group_by == 'series':
                for books in groups.values():
                    books.sort(key=lambda bid: (api.field_for('series_index', bid) or 0, bid))
        new_groups = sorted(groups.items(), key=lambda item: sort_key(
            api.field_for('title', item[1][0]) if item[0][0] == 'book' else item[0][1]))
        changed = self.groups != new_groups
        av = getattr(getattr(getattr(self.view, 'gui', None), 'library_view', None), 'alternate_views', None)
        was_link_broken = av.break_link if av is not None else False
        if av is not None:
            av.break_link = True
        if changed:
            self.beginResetModel()
        self.groups = new_groups
        self.book_to_source = source_rows
        self.book_to_groups = {}
        for row, (_key, books) in enumerate(self.groups):
            for bid in books:
                self.book_to_groups.setdefault(bid, []).append(row)
        self.book_to_group = {bid: rows[0] for bid, rows in self.book_to_groups.items()}
        previous_positions = {} if self.reset_positions else self.positions
        self.reset_positions = False
        self.positions = {
            series: previous_positions.get(series, books[0]) if previous_positions.get(series) in books else books[0] for series, books in self.groups
        }
        if changed:
            self.endResetModel()
        elif self.groups:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.groups) - 1, self.columnCount() - 1))
        if av is not None:
            av.break_link = was_link_broken
            if changed and av.current_view is self.view and not was_link_broken:
                av.main_current_changed(av.main_view.currentIndex())
                av.main_selection_changed()
                self.view.sync_book_details()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.groups)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.sourceModel() is None else self.sourceModel().columnCount()

    def index(self, row, column=0, parent=QModelIndex()):
        if not parent.isValid() and 0 <= row < len(self.groups) and 0 <= column < self.columnCount():
            return self.createIndex(row, column)
        return QModelIndex()

    def parent(self, index):
        return QModelIndex()

    def book_id(self, row):
        series, books = self.groups[row]
        return self.positions[series]

    def id(self, index):
        return self.book_id(index.row() if hasattr(index, 'row') else index)

    def cover(self, row):
        return self.sourceModel().cover(self.source_row(row))

    def source_row(self, row):
        return self.book_to_source[self.book_id(row)] if 0 <= row < len(self.groups) else -1

    def mapToSource(self, index):
        if index.isValid() and 0 <= index.row() < len(self.groups):
            return self.sourceModel().index(self.source_row(index.row()), index.column())
        return QModelIndex()

    def mapFromSource(self, index):
        if index.isValid():
            row = self.group_for_book(self.sourceModel().id(index))
            if row is not None:
                return self.index(row, index.column())
        return QModelIndex()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        source = self.mapToSource(index)
        return self.sourceModel().data(source, role) if source.isValid() else None

    def flags(self, index):
        return self.sourceModel().flags(self.mapToSource(index))

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        return self.sourceModel().setData(self.mapToSource(index), value, role)

    def group_for_book(self, book_id):
        rows = self.book_to_groups.get(book_id, ())
        current = self.view.currentIndex().row() if self.view is not None else -1
        return current if current in rows else rows[0] if rows else None

    def show_book(self, book_id, row=None):
        if row is None:
            row = self.group_for_book(book_id)
        if row is not None:
            series, _books = self.groups[row]
            if self.positions[series] != book_id:
                self.positions[series] = book_id
                self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1))
        return row

    def step(self, row, delta):
        series, books = self.groups[row]
        position = books.index(self.positions[series])
        target = (position + delta) % len(books)
        if target == position:
            return False
        self.show_book(books[target], row)
        return True

    def nearby_books(self, row):
        series, books = self.groups[row]
        position = books.index(self.positions[series])
        return tuple(dict.fromkeys(books[(position + offset) % len(books)] for offset in (0, -1, *range(1, max(4, stack_size())))))


class SeriesThumbnailRenderer(ThumbnailRenderer):
    """Disk I/O and image decoding happen exclusively in the render worker."""

    def __init__(self, *args):
        self.pending = set()
        self.wanted_ids = frozenset()
        super().__init__(*args)

    def peek(self, book_id):
        try:
            return self.ram_cache[book_id]
        except KeyError:
            return None

    def cached_or_none(self, book_id):
        cached = self.peek(book_id)
        if cached is not None:
            return cached
        if self.dbref() is not None and not self.shutting_down:
            self.wanted_ids = self.wanted_ids | {book_id}
            self.request_render(book_id)
        return None

    def request_render(self, book_id):
        key = (self.current_library_id, book_id, *self.disk_cache.thumbnail_size)
        if key not in self.pending:
            self.pending.add(key)
            super().request_render(book_id)

    def fetch_cover_from_cache(self, book_id, width, height):
        if book_id not in self.wanted_ids:
            return None
        return super().fetch_cover_from_cache(book_id, width, height)

    def on_cover_rendered(self, library_id, book_id, width, height, img):
        self.pending.discard((library_id, book_id, width, height))
        if img is not None and book_id in self.wanted_ids:
            super().on_cover_rendered(library_id, book_id, width, height, img)

    def set_database(self, db):
        super().set_database(db)
        self.pending.clear()
        self.wanted_ids = frozenset()

    def set_thumbnail_size(self, width, height):
        if (width, height) != self.disk_cache.thumbnail_size:
            super().set_thumbnail_size(width, height)
            self.pending.clear()


class SeriesThumbnailCache(CoverThumbnailCache):
    renderer_class = SeriesThumbnailRenderer

    def peek(self, book_id):
        return self.renderer.peek(book_id)


class SeriesCoverDelegate(CoverDelegate):
    cache_class = SeriesThumbnailCache

    def __init__(self, parent):
        super().__init__(parent)
        self.transition = None
        self.transition_mode = 'vertical'
        self.transition_textures = None
        self.cover_rects = {}
        self.transition_animation = QVariantAnimation(self)
        self.transition_animation.setDuration(140)
        self.transition_animation.setStartValue(0.0)
        self.transition_animation.setEndValue(1.0)
        self.transition_animation.valueChanged.connect(self.update_transition)
        self.transition_animation.finished.connect(self.finish_transition)
        self.wrap_row = None
        self.wrap_timer = QTimer(self)
        self.wrap_timer.setSingleShot(True)
        self.wrap_timer.setInterval(650)
        self.wrap_timer.timeout.connect(self.clear_wrap)

    def clear_wrap(self):
        row, self.wrap_row = self.wrap_row, None
        if row is not None:
            self.parent().update(self.parent().model().index(row, 0))

    def update_transition(self, value):
        if self.transition is not None:
            self.parent().repaint_cover(self.transition.row)

    def finish_transition(self):
        transition, self.transition = self.transition, None
        self.transition_textures = None
        if transition is not None:
            self.parent().repaint_cover(transition.row)

    def start_transition(self, row, old_book, direction, wrapped):
        self.transition_animation.stop()
        mode = gprefs['series_grid_animation']
        # Compatibility with the former mixed random mode.
        self.transition_mode = choice(('vertical', 'horizontal')) if mode in ('random', 'slide_random') else mode
        self.transition_textures = None
        if self.transition_mode == 'curl_random':
            self.transition_mode = choice(('curl', 'curl_horizontal'))
        self.transition_skew = choice((-1, 1)) * uniform(0.18, 0.36) if self.transition_mode.startswith('curl') else 0.0
        self.transition_animation.setDuration(240 if self.transition_mode.startswith('curl') else 140)
        if wrapped and mode != 'none' and not config['disable_animations']:
            self.wrap_row = row
            self.wrap_timer.start()
        self.transition = CoverTransition(row, old_book, direction)
        self.parent().prefetch_timer.start()
        if mode == 'none' or config['disable_animations']:
            self.wrap_timer.stop()
            self.clear_wrap()
            self.finish_transition()
        else:
            self.transition_animation.start()

    def set_dimensions(self):
        super().set_dimensions()
        if not self.title_height:
            self.title_height = 30
            self.item_size += QSize(0, self.title_height)
        extra = max(48, self.title_height * 2) - self.title_height
        self.title_height += extra
        self.item_size += QSize(0, extra)
        self.stack_extent = (stack_size() - 1) * 6 if gprefs['series_grid_stack_rendering'] == 'neat' else 0
        self.stack_margin = int(max(self.cover_size.width(), self.cover_size.height()) * 0.06) + 4 if gprefs['series_grid_stack_rendering'] != 'neat' else 0
        padding = self.stack_extent + 2 * self.stack_margin
        self.item_size += QSize(padding, padding)
        self.title_height += self.stack_extent + self.stack_margin

    def paint(self, painter, option, index):
        self.parent().visible_rows.add(index.row())
        self.painting_index = index
        local_option = QStyleOptionViewItem(option)
        margin, extent = self.stack_margin, self.stack_extent
        local_option.rect = option.rect.adjusted(margin, margin, -margin - extent, 0)
        try:
            super().paint(painter, local_option, index)
        finally:
            self.painting_index = QModelIndex()

    def paint_posed_cover(self, painter, rect, pixmap, book_id, front=False):
        angle, dx, dy = cover_pose(book_id, front)
        painter.save()
        painter.translate(rect.center().x() + dx, rect.center().y() + dy)
        painter.rotate(angle)
        painter.translate(-rect.center())
        if pixmap is None or pixmap.isNull():
            painter.fillRect(rect, QColor(100, 100, 110))
        else:
            target = QRect(rect)
            target.setSize(pixmap.size().scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio))
            target.moveCenter(rect.center())
            super().paint_cover(painter, target, pixmap)
            rect = target
        painter.setPen(self.highlight_color)
        painter.drawRect(rect)
        painter.restore()

    def posed_texture(self, rect, pixmap, book_id):
        margin = self.stack_margin
        dpr = self.parent().device_pixel_ratio
        texture = QPixmap(int((rect.width() + 2 * margin) * dpr), int((rect.height() + 2 * margin) * dpr))
        texture.setDevicePixelRatio(dpr)
        texture.fill(Qt.GlobalColor.transparent)
        painter = QPainter(texture)
        self.paint_posed_cover(painter, QRect(margin, margin, rect.width(), rect.height()), pixmap, book_id, front=True)
        painter.end()
        return texture

    def paint_cover(self, painter, rect, pixmap):
        model = self.painting_index.model()
        series, books = model.groups[self.painting_index.row()]
        mode = gprefs['series_grid_stack_rendering']
        if mode != 'neat':
            # All books share a fixed canvas, even when their aspect ratios
            # differ. A book's pose must not depend on stack depth or front.
            center = rect.center()
            rect = QRect(0, 0, self.cover_size.width(), self.cover_size.height())
            rect.moveCenter(center)
        margin = self.stack_margin
        self.cover_rects[self.painting_index.row()] = (
            QRect(self.parent().visualRect(self.painting_index)),
            rect.adjusted(-margin, -margin, margin, margin),
        )
        painter.save()
        try:
            for offset in range(min(stack_size(), len(books)) - 1, 0, -1):
                rear = QRect(rect).translated(offset * 6, offset * 6) if mode == 'neat' else QRect(rect)
                bid = books[(books.index(model.positions[series]) + offset) % len(books)]
                cover = self.cover_cache.peek(bid) if self.parent().rear_covers_enabled else None
                if (cover is None or cover.isNull()) and pixmap is not None and not pixmap.isNull():
                    # Until decoded, assume the rear book has the front book's
                    # proportions instead of filling the entire cover canvas.
                    center = rear.center()
                    rear.setSize(pixmap.size().scaled(rear.size(), Qt.AspectRatioMode.KeepAspectRatio))
                    rear.moveCenter(center)
                self.paint_posed_cover(painter, rear, cover, bid)
            transition = self.transition
            if transition is not None and transition.row == self.painting_index.row():
                old_book, direction = transition.old_book_id, transition.direction
                old_cover = self.cover_cache.peek(old_book)
                if old_cover is not None and not old_cover.isNull():
                    painter.save()
                    animation_rect = rect
                    if self.stack_margin:
                        key = (old_book, model.id(self.painting_index), rect.size(), gprefs['series_grid_stack_rendering'])
                        if self.transition_textures is None or self.transition_textures[0] != key:
                            self.transition_textures = (
                                key,
                                self.posed_texture(rect, old_cover, old_book),
                                self.posed_texture(rect, pixmap, model.id(self.painting_index)),
                            )
                        old_cover, pixmap = self.transition_textures[1:]
                        animation_rect = rect.adjusted(-self.stack_margin, -self.stack_margin, self.stack_margin, self.stack_margin)
                    painter.setClipRect(animation_rect)
                    progress = float(self.transition_animation.currentValue() or 0)
                    if self.transition_mode.startswith('curl'):
                        paint_page_curl(
                            painter,
                            animation_rect,
                            old_cover,
                            pixmap,
                            progress,
                            direction,
                            horizontal=self.transition_mode != 'curl',
                            skew=self.transition_skew,
                        )
                    else:
                        paint_slide(painter, animation_rect, old_cover, pixmap, progress, direction, horizontal=self.transition_mode == 'horizontal')
                    painter.restore()
                else:
                    self.paint_posed_cover(painter, rect, pixmap, model.id(self.painting_index), front=True)
            else:
                self.paint_posed_cover(painter, rect, pixmap, model.id(self.painting_index), front=True)
            if self.wrap_row == self.painting_index.row():
                badge = rect.adjusted(0, 0, 0, -rect.height() + 26)
                painter.fillRect(badge, QColor(30, 30, 30, 210))
                painter.setPen(QColor('white'))
                painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, _('↻ Wrap'))
        finally:
            painter.restore()

    def render_field(self, db, book_id):
        model = self.parent().model()
        row = self.painting_index.row()
        if row is None:
            return '', False
        series, books = model.groups[row]
        if series[0] == 'book':
            return db.field_for('title', book_id), False
        number = fmt_sidx(db.field_for('series_index', book_id))
        count = ngettext('%d book', '%d books', len(books)) % len(books)
        if series[0] != 'series':
            position = books.index(book_id) + 1
            return f'{series[1]}\n{position} / {len(books)}', False
        return _('%(series)s\nVolume %(number)s · %(count)s') % {'series': series[1], 'number': number, 'count': count}, False

    def paint_title(self, painter, rect, db, book_id, align_top=False):
        text, _is_stars = self.render_field(db, book_id)
        rect = QRect(rect).adjusted(0, self.stack_extent + self.stack_margin, 0, 0)
        painter.save()
        try:
            painter.setPen(self.highlight_color)
            metrics = painter.fontMetrics()
            lines = text.split('\n')
            height = metrics.height()
            top = rect.top() if align_top else rect.top() + max(0, (rect.height() - height * len(lines)) // 2)
            for number, line in enumerate(lines):
                line_rect = QRect(rect.left(), top + number * height, rect.width(), height)
                painter.drawText(line_rect, Qt.AlignmentFlag.AlignCenter, metrics.elidedText(line, Qt.TextElideMode.ElideRight, rect.width()))
        finally:
            painter.restore()


class SeriesGridView(GridView):
    delegate_class = SeriesCoverDelegate

    def __init__(self, parent):
        self.visible_rows = set()
        self.rear_covers_enabled = False
        self.last_scroll_at = 0
        super().__init__(parent)
        self.series_model = SeriesModel(self)
        self.wheel_row = None
        self.wheel_delta = 0
        self.prefetch_timer = QTimer(self)
        self.prefetch_timer.setInterval(60)
        self.prefetch_timer.setSingleShot(True)
        self.prefetch_timer.timeout.connect(self.prefetch_neighbors)

    def repaint_cover(self, row):
        index = self.model().index(row, 0)
        if not index.isValid():
            return
        tile = self.visualRect(index)
        previous = self.delegate.cover_rects.get(row)
        region = previous[1] if previous is not None and previous[0] == tile else tile
        self.viewport().update(region)

    def paintEvent(self, e):
        model = self.model()
        transition = self.delegate.transition
        if transition is not None and model is not None and 0 <= transition.row < model.rowCount():
            previous = self.delegate.cover_rects.get(transition.row)
            if (
                previous is not None
                and previous[0] == self.visualRect(model.index(transition.row, 0))
                and previous[1].contains(e.rect())
                and self.rear_covers_enabled
                and monotonic() - self.last_scroll_at >= 0.15
                and self.delegate.cover_cache.peek(transition.old_book_id) is not None
                and self.delegate.cover_cache.peek(model.book_id(transition.row)) is not None
            ):
                # A cached animation frame changes only this cover. Scrolling,
                # layout changes and broader repaints use the normal path below.
                return super().paintEvent(e)
        if model is not None:
            self.visible_rows = self.rows_in_viewport()
        previous_rear_state = self.rear_covers_enabled
        self.rear_covers_enabled = self.ready_for_rear_covers()
        super().paintEvent(e)
        if model is None:
            return
        if not model.rowCount():
            painter = QPainter(self.viewport())
            painter.setPen(self.delegate.highlight_color)
            message = _('No books to display in Series Grid view.')
            if gprefs['series_grid_group_by'] == 'series' and not gprefs['series_grid_show_standalone']:
                message += '\n\n' + _(
                    'To include books without a series, enable "Show books without a series" in Preferences > Look & feel > Cover grid > Series Grid view.'
                )
            painter.drawText(self.viewport().rect().adjusted(24, 24, -24, -24), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, message)
            painter.end()
        viewport = self.viewport().rect()
        self.visible_rows = {row for row in self.visible_rows if 0 <= row < model.rowCount() and self.visualRect(model.index(row, 0)).intersects(viewport)}
        self.delegate.cover_rects = {row: rects for row, rects in self.delegate.cover_rects.items() if row in self.visible_rows}
        wanted = {model.book_id(row) for row in self.visible_rows}
        if monotonic() - self.last_scroll_at >= 0.15:
            wanted.update(book_id for row in self.visible_rows for book_id in model.nearby_books(row))
        if self.delegate.transition is not None:
            wanted.add(self.delegate.transition.old_book_id)
        self.delegate.cover_cache.renderer.wanted_ids = frozenset(wanted)
        if previous_rear_state != self.rear_covers_enabled:
            self.viewport().update()
        if not self.prefetch_timer.isActive():
            self.prefetch_timer.start()

    def rows_in_viewport(self):
        # Sampling within uniform tiles finds all visible items without walking
        # every series in the library, including partially visible edge tiles.
        size = self.delegate.item_size
        viewport = self.viewport().rect()
        rows = set()
        for y in (*range(0, viewport.height(), max(1, size.height() // 2)), viewport.bottom()):
            for x in (*range(0, viewport.width(), max(1, size.width() // 2)), viewport.right()):
                index = self.indexAt(QPoint(x, y))
                if index.isValid():
                    rows.add(index.row())
        for point in (viewport.bottomRight(), viewport.topRight(), viewport.bottomLeft()):
            index = self.indexAt(point)
            if index.isValid():
                rows.add(index.row())
        return rows

    def ready_for_rear_covers(self):
        model = self.model()
        return (
            bool(self.visible_rows)
            and monotonic() - self.last_scroll_at >= 0.15
            and all(self.delegate.cover_cache.peek(model.book_id(row)) is not None for row in self.visible_rows)
        )

    def prefetch_neighbors(self):
        model = self.model()
        if model is None or not self.isVisible():
            return
        remaining = 0.15 - (monotonic() - self.last_scroll_at)
        if remaining > 0:
            self.prefetch_timer.start(max(1, int(remaining * 1000) + 1))
            return
        rows = sorted(row for row in self.visible_rows if row < model.rowCount())
        cache = self.delegate.cover_cache
        # All visible front covers take priority over rear/neighbor covers.
        missing_fronts = [model.book_id(row) for row in rows if cache.peek(model.book_id(row)) is None]
        if missing_fronts:
            for book_id in missing_fronts:
                cache.thumbnail_as_pixmap(book_id)
            self.prefetch_timer.start()
            return
        cache.renderer.wanted_ids = frozenset(book_id for row in rows for book_id in model.nearby_books(row))
        if not self.rear_covers_enabled:
            self.viewport().update()
        missing = list(dict.fromkeys(book_id for row in rows for book_id in model.nearby_books(row) if cache.peek(book_id) is None))
        for book_id in missing[:2]:
            cache.thumbnail_as_pixmap(book_id)
        if missing:
            self.prefetch_timer.start()

    def shutdown(self):
        self.prefetch_timer.stop()
        super().shutdown()

    def scrollContentsBy(self, dx, dy):
        self.last_scroll_at = monotonic()
        super().scrollContentsBy(dx, dy)
        if hasattr(self, 'prefetch_timer'):
            self.prefetch_timer.start(150)

    def setModel(self, source):
        self.series_model.setSourceModel(source)
        QListView.setModel(self, self.series_model)

    def set_database(self, newdb, stage=0):
        if stage == 0:
            self.visible_rows.clear()
            self.delegate.cover_rects.clear()
            self.prefetch_timer.stop()
            self.series_model.reset_positions = True
            self.delegate.transition_animation.stop()
            self.delegate.finish_transition()
            self.delegate.wrap_timer.stop()
            self.delegate.clear_wrap()
        super().set_database(newdb, stage=stage)
        if stage == 1:
            self.series_model.rebuild_timer.stop()
            self.series_model.rebuild()

    def update_memory_cover_cache_size(self):
        size = self.delegate.item_size
        spacing = 2 * self.spacing()
        columns = self.viewport().width() // max(1, size.width() + spacing) + 1
        rows = self.viewport().height() // max(1, size.height() + spacing) + 2
        self.delegate.cover_cache.set_ram_limit(max(20, columns * rows * max(5, stack_size() + 1)))

    def refresh_settings(self):
        self.delegate.transition_animation.stop()
        self.delegate.finish_transition()
        self.delegate.wrap_timer.stop()
        self.delegate.clear_wrap()
        super().refresh_settings()
        self.delegate.set_dimensions()
        self.setSpacing(self.delegate.spacing)
        self.update_memory_cover_cache_size()
        self.doItemsLayout()
        self.viewport().update()

    def sync_book_details(self):
        av = getattr(self.gui.library_view, 'alternate_views', None)
        details = getattr(self.gui, 'book_details', None)
        if av is not None and av.current_view is self and details is not None:
            index = self.series_model.mapToSource(self.currentIndex())
            if index.isValid():
                self.series_model.sourceModel().current_changed(index, None)
            else:
                details.show_data(None)

    def shown(self):
        super().shown()
        self.sync_book_details()

    def source_row(self, row):
        return self.series_model.source_row(row)

    def set_current_row(self, row):
        source = self.series_model.sourceModel()
        if row < 0 or row >= source.rowCount():
            GridView.set_current_row(self, -1)
            return
        group = self.series_model.show_book(source.id(row))
        if group is not None:
            GridView.set_current_row(self, group)
        else:
            GridView.set_current_row(self, -1)

    def select_rows(self, rows):
        source = self.series_model.sourceModel()
        groups = {
            self.series_model.group_for_book(source.id(row))
            for row in rows
            if 0 <= row < source.rowCount() and source.id(row) in self.series_model.book_to_group
        }
        GridView.select_rows(self, groups)

    def get_selected_ids(self):
        return list(dict.fromkeys(self.series_model.id(index) for index in self.selectionModel().selectedIndexes()))

    @property
    def current_book(self):
        index = self.currentIndex()
        return self.series_model.id(index) if index.isValid() else None

    def restore_current_book_state(self, state):
        book_id = state
        row = self.series_model.book_to_source.get(book_id)
        if row is not None:
            self.set_current_row(row)
            self.select_rows((row,))
            self.scrollTo(self.currentIndex())

    def re_render(self, book_id, thumb):
        for row in self.series_model.book_to_groups.get(book_id, ()):
            self.update(self.series_model.index(row, 0))

    def marked_changed(self, old_marked, current_marked):
        for book_id in old_marked | current_marked:
            self.re_render(book_id, None)

    def double_clicked(self, index):
        if gprefs['series_grid_animation'] != 'none':
            self.start_view_animation(index)
        double_click_action(self.series_model.mapToSource(index))

    def action_index(self, index):
        return self.series_model.mapToSource(index)

    def rows_for_merge(self, resolved=True):
        return list(dict.fromkeys(self.source_row(index.row()) for index in self.selectionModel().selectedIndexes()))

    def wheelEvent(self, a0):
        event = a0
        index = self.indexAt(event.position().toPoint())
        if not index.isValid() or event.modifiers() or len(self.series_model.groups[index.row()][1]) < 2:
            self.wheel_row = None
            self.wheel_delta = 0
            return super().wheelEvent(event)
        if self.wheel_row != index.row():
            self.wheel_row = index.row()
            self.wheel_delta = 0
        delta = event.angleDelta().y()
        if not delta:
            return super().wheelEvent(event)
        self.wheel_delta += delta
        steps = int(self.wheel_delta / 120)
        self.wheel_delta -= steps * 120
        old_book = self.series_model.book_id(index.row())
        _series, books = self.series_model.groups[index.row()]
        old_position = books.index(old_book)
        wrapped = steps and not 0 <= old_position - steps < len(books)
        if steps and self.series_model.step(index.row(), -steps):
            self.delegate.start_transition(index.row(), old_book, -steps, wrapped)
            self.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            av = self.gui.library_view.alternate_views
            av.slave_current_changed(index)
            av.slave_selection_changed()
        event.accept()
