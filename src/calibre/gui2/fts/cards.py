#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


import weakref
from functools import lru_cache
from queue import Queue, ShutDown
from threading import Thread
from typing import NamedTuple

from qt.core import (
    QApplication,
    QFontMetricsF,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QRect,
    QScrollArea,
    QSizeF,
    Qt,
    QTextDocument,
    QTimer,
    QUrl,
    QVariant,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import prepare_string_for_xml
from calibre.db.cache import Cache
from calibre.ebooks.metadata import authors_to_string, fmt_sidx
from calibre.gui2 import config
from calibre.gui2.fts.utils import get_db, jump_shortcut
from calibre.gui2.widgets import BusyCursor
from calibre.utils.img import resize_to_fit


class Layout(NamedTuple):
    image_height: int = 128
    image_width: int = 96
    image_right_margin: int = 8
    image_bottom_margin: int = 4
    padding: int = 10
    border_radius: int = 12
    spacing: int = 14
    margin: int = 16
    min_card_width: int = -1


@lru_cache(maxsize=2)
def layout() -> Layout:
    app = QApplication.instance()
    fm = QFontMetricsF(app.font())
    return Layout(min_card_width=int(60 * fm.averageCharWidth()))


@lru_cache(maxsize=4)
def dummy_image(width, height):
    ans = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    ans.fill(Qt.GlobalColor.transparent)
    return ans


@lru_cache(maxsize=2)
def default_cover():
    ic = QIcon.ic('default_cover.png')
    return ic.pixmap(ic.availableSizes()[0]).toImage()


@lru_cache(maxsize=8)
def icon_resource_provider(qurl: QUrl) -> QVariant:
    if qurl.scheme() == 'calibre-icon':
        ic = QIcon.cached_icon(qurl.path().lstrip('/'))
        if ic.is_ok():
            dpr = QApplication.instance().devicePixelRatio()
            pmap = ic.pixmap(ic.availableSizes()[0])
            sz = QSizeF(16 * dpr, 16 * dpr).toSize()
            pmap = pmap.scaled(sz, transformMode=Qt.TransformationMode.SmoothTransformation)
            pmap.setDevicePixelRatio(dpr)
            return pmap
    return QVariant()


@lru_cache(maxsize=256)
def button_line(book_id: int, has_book: bool) -> str:
    template = (
        f'<a style="text-decoration: none" href="calibre://{{which}}/{book_id}" title="{{tt}}">'
        '<img valign="bottom" src="calibre-icon:///{icon}">\xa0{text}</a>\xa0\xa0\xa0'
    )
    if has_book:
        li = template.format(which='reindex', icon='view-refresh.png', text=_('Re-index'), tt=_(
            'Re-index this book. Useful if the book has been changed outside of calibre, and thus not automatically re-indexed.'))
    else:
        li = template.format(which='unindex', icon='trash.png', text=_('Un-index'), tt=_(
            'This book has been deleted from the library but is still present in the'
            ' full text search index. Remove it.'))
    return (
        template.format(which='jump', icon='lt.png', text=_('Select'), tt=_(
            'Scroll to this book in the calibre library book list and select it [{}]').format(jump_shortcut())) +
        template.format(which='mark', icon='marked.png', text=_('Mark'), tt=_(
            'Put a pin on this book in the calibre library, for future reference.\n'
            'You can search for marked books using the search term: {0}').format('marked:true')) +
        li)


class CardData:

    _height: int = -1
    width: int = -1
    # Cached layout results (filled by layout pass)
    row: int = -1            # which row this card lands in
    col: int = -1            # column index within the row
    x: int = 0               # final x position
    y: int = 0               # final y position
    doc: QTextDocument | None = None
    cover: QImage | None = None
    cover_requested: bool = False

    def __init__(self, results):
        self.results = results

    def result_updated(self):
        self.invalidate()

    def invalidate(self):
        self._height = -1
        self.doc = None

    def set_width(self, width):
        if width != self.width:
            self._height = -1
            self.width = width

    def set_cover(self, img: QImage) -> None:
        self.cover = img
        if self.doc is not None:
            self.doc.addResource(int(QTextDocument.ResourceType.ImageResource), QUrl('card://thumb'), self.cover)

    def ensure_renderable(self, dpr) -> QTextDocument:
        self.height
        return self.doc

    @property
    def height(self) -> int:
        if self._height < 0:
            self._compute_height()
        return self._height

    def _compute_height(self):
        if self.doc is None:
            self._load_doc()
        lc = layout()
        self.doc.setTextWidth(self.width - 2 * (lc.padding + 1))
        self._height = int(self.doc.size().height()) + 2 * lc.padding + 2

    def _load_doc(self):
        lc = layout()
        c = self.cover or dummy_image(lc.image_width + lc.image_right_margin, lc.image_height + lc.image_bottom_margin)
        sz = c.deviceIndependentSize().toSize()
        series = ''
        if s := self.results.series:
            sidx = fmt_sidx(self.results.series_index or 0, use_roman=config['use_roman_numerals_for_series_number'])
            series = _('{series_index} of {series}').format(series_index=sidx, series=s)
            series = f'{prepare_string_for_xml(series)}<br>'
        html = f'''
<img src="card://thumb" width="{sz.width()}" height="{sz.height()}" align="left" /><p style="text-indent: 0; margin: 0">
<big><b>{prepare_string_for_xml(self.results.title)}</b></big><br>
{prepare_string_for_xml(authors_to_string(self.results.authors))}<br>
{series}
{button_line(self.results.book_id, self.results.book_in_db)}
'''
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setResourceProvider(icon_resource_provider)
        doc.addResource(int(QTextDocument.ResourceType.ImageResource), QUrl('card://thumb'), c)
        doc.setHtml(html)
        self.doc = doc


class RowInfo(NamedTuple):
    '''Computed metadata for one row of cards.'''
    y: int = 0               # top Y of this row
    height: int = 0          # tallest card in this row
    first_index: int = 0     # index of first card in this row
    card_count: int = 0      # number of cards in this row


class CardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._card: CardData | None = None
        self.padding = 0

    def bind(self, card: CardData):
        '''Bind this widget to a CardData, rebuilding the document.'''
        self._card = card
        self.setFixedSize(card.width, card.height)
        self.update()

    def paintEvent(self, event):
        doc = self._card.ensure_renderable(self.devicePixelRatioF())
        with QPainter(self) as p:
            p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
            lc = layout()
            rect = self.rect().adjusted(1, 1, -1, -1)
            path = QPainterPath()
            path.addRoundedRect(
                float(rect.x()), float(rect.y()),
                float(rect.width()), float(rect.height()),
                lc.border_radius, lc.border_radius,
            )
            pal = self.palette()
            p.fillPath(path, pal.color(QPalette.ColorRole.Base))
            p.setPen(pal.color(QPalette.ColorRole.WindowText))
            p.drawPath(path)
            p.setClipPath(path)
            self.padding = lc.padding + 1
            p.translate(self.padding, self.padding)
            doc.drawContents(p)


class VirtualCardContainer(QWidget):

    cover_rendered = pyqtSignal(int, int, QImage)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.cover_render_queue: Queue[int] = Queue()
        self.model = model
        model.matches_found.connect(self.matches_found)
        model.result_with_context_found.connect(self.result_with_context_found)
        self._cards = ()
        self._cards_map = {}
        self._viewport_rect = QRect()
        # Layout results
        self._rows: list[RowInfo] = []
        self._total_height = 0
        self._cols_per_row = 1
        # Widget pool: map from card-data index → live widget
        self._live_widgets: dict[int, CardWidget] = {}
        # Recycling pool of unbound widgets
        self._pool: list[CardWidget] = []
        self.update_debounce_timer = t = QTimer(self)
        t.setInterval(50), t.setSingleShot(True)
        t.timeout.connect(self._full_relayout)
        self.preloaded = False
        self.generation = 0
        self.cover_rendered.connect(self.on_cover_rendered, type=Qt.ConnectionType.QueuedConnection)

    def preload(self):
        # We need all the metadata to calculate card height, so load it in one
        # fell swoop to avoid lock contention with the fts snippets thread
        if self.preloaded:
            return
        self.preloaded = True
        with BusyCursor():
            all_books = {c.results.book_id for c in self._cards}
            with (db := get_db()).safe_read_lock:
                titles = db._all_field_for('title', all_books, _('Unknown book'))
                authors = db._all_field_for('authors', all_books, [_('Unknown author')])
                series = db._all_field_for('series', all_books, '')
                series_indices = db._all_field_for('series_index', all_books, 1)
                abids = db._all_book_ids(lambda x: x)
                in_db = {bid: bid in abids for bid in all_books}
            for card in self._cards:
                card.results.preload(titles, authors, series, series_indices, in_db)

    def matches_found(self, num):
        self._cards = tuple(CardData(r) for r in self.model.results) if num > 0 else ()
        self._cards_map = {id(c.results): c for c in self._cards}
        self.preloaded = False
        self.cover_render_queue.shutdown(True)
        self.cover_render_queue = Queue()
        self.generation += 1
        Thread(daemon=True, name='FTSCoverRender', target=self.render_covers, args=(
            self.cover_render_queue, self.devicePixelRatioF(), layout(), default_cover,
            weakref.ref(get_db()), self.generation)).start()
        if self.isVisible():
            self._full_relayout()

    def render_covers(self, queue: Queue[int], dpr: float, lc: Layout, default_cover: QImage, db_ref: weakref.ref[Cache], generation: int):
        while True:
            try:
                book_id, idx = queue.get()
            except ShutDown:
                break
            if (db := db_ref()) is None:
                break
            try:
                img = db.cover(book_id, as_image=True)
            except Exception:
                import traceback
                traceback.print_exc()
                continue
            if not img or img.isNull():
                img = default_cover
            sz = QSizeF(lc.image_width * dpr, lc.image_height * dpr).toSize()
            img = resize_to_fit(img, sz.width(), sz.height())[1]
            csz = QSizeF(lc.image_width + lc.image_right_margin, lc.image_height + lc.image_bottom_margin) * dpr
            canvas = QImage(csz.toSize(), QImage.Format.Format_ARGB32_Premultiplied)
            canvas.setDevicePixelRatio(dpr)
            img.setDevicePixelRatio(dpr)
            canvas.fill(Qt.GlobalColor.transparent)
            with QPainter(canvas) as p:
                sz = img.deviceIndependentSize().toSize()
                left = (lc.image_width - sz.width()) // 2
                top = (lc.image_height - sz.height()) // 2
                p.drawImage(left, top, img)
            try:
                self.cover_rendered.emit(generation, idx, canvas)
            except RuntimeError:
                break

    def on_cover_rendered(self, generation, idx, img):
        if generation == self.generation and idx < len(self._cards):
            card = self._cards[idx]
            card.set_cover(img)
            self.update()

    def result_with_context_found(self, results, index: int):
        card = self._cards_map[id(results)]
        card.result_updated()
        if self.isVisible():
            self.update_debounce_timer.start()

    def set_viewport(self, viewport_rect: QRect):
        '''Called by the scroll area whenever scroll position or size changes.'''
        self._viewport_rect = viewport_rect
        self._update_visible_widgets()

    def _full_relayout(self):
        self.preload()
        viewport_width = self._viewport_rect.width()
        lc = layout()
        usable = viewport_width - 2 * lc.margin
        max_cols = max(1, (usable + lc.spacing) // (lc.min_card_width + lc.spacing))
        if max_cols < 2:
            self._cols_per_row = 1
            card_width = usable
        else:
            self._cols_per_row = max_cols
            card_width = (usable + lc.spacing - max_cols * lc.spacing) // max_cols

        for card in self._cards:
            card.set_width(card_width)

        # Assign cards to rows
        self._rows.clear()
        row_idx = 0
        i = 0
        y = lc.margin
        while i < len(self._cards):
            row_cards = self._cards[i : i + self._cols_per_row]
            row_height = max(c.height for c in row_cards)
            ri = RowInfo(y=y, height=row_height, first_index=i, card_count=len(row_cards))
            self._rows.append(ri)
            for col, card in enumerate(row_cards):
                card.row = row_idx
                card.col = col
                card.x = lc.margin + col * (card_width + lc.spacing)
                card.y = y
            y += row_height + lc.spacing
            i += len(row_cards)
            row_idx += 1

        self._total_height = y - lc.spacing + lc.margin if self._rows else 0
        self.setFixedHeight(self._total_height)
        self._update_visible_widgets()

    # -- visibility determination (binary search on rows) --------------------
    def _visible_row_range(self) -> tuple[int, int]:
        '''Return [first_visible_row, last_visible_row) using binary search.'''
        if not self._rows:
            return (0, 0)
        OVERSCAN = 20
        top = self._viewport_rect.top() - OVERSCAN
        bottom = self._viewport_rect.bottom() + OVERSCAN

        # Binary search for first row whose bottom edge >= top
        lo, hi = 0, len(self._rows)
        while lo < hi:
            mid = (lo + hi) // 2
            row = self._rows[mid]
            if row.y + row.height < top:
                lo = mid + 1
            else:
                hi = mid
        first = lo

        # Binary search for first row whose top edge > bottom
        lo, hi = first, len(self._rows)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._rows[mid].y > bottom:
                hi = mid
            else:
                lo = mid + 1
        last = lo

        return (first, last)

    # -- widget lifecycle (create / recycle / hide) --------------------------
    def _update_visible_widgets(self):
        first_row, last_row = self._visible_row_range()

        # Determine which card indices should be visible
        needed: set[int] = set()
        for r in range(first_row, last_row):
            ri = self._rows[r]
            for idx in range(ri.first_index, ri.first_index + ri.card_count):
                needed.add(idx)

        # Recycle widgets that are no longer needed
        to_remove = [idx for idx in self._live_widgets if idx not in needed]
        for idx in to_remove:
            w = self._live_widgets.pop(idx)
            w.hide()
            self._pool.append(w)

        # Create/reuse widgets for newly visible cards
        for idx in needed:
            if idx in self._live_widgets:
                # Already alive — update size and position
                card = self._cards[idx]
                w = self._live_widgets[idx]
                w.setFixedSize(card.width, card.height)
                w.setGeometry(card.x, card.y, card.width, card.height)
                continue

            card = self._cards[idx]
            if self._pool:
                w = self._pool.pop()
            else:
                w = self._create_card_widget()
            if not card.cover_requested:
                self.cover_render_queue.put((card.results.book_id, idx))
                card.cover_requested = True
            w.bind(card)
            w.setGeometry(card.x, card.y, card.width, card.height)
            w.show()
            self._live_widgets[idx] = w

    def _create_card_widget(self):
        return CardWidget(self)


class CardView(QScrollArea):

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._container = VirtualCardContainer(model, self)
        self.setWidget(self._container)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        # Debounce resize relayout
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(50)
        self._resize_timer.timeout.connect(self._do_relayout)

    def _viewport_rect(self) -> QRect:
        vp = self.viewport()
        return QRect(0, self.verticalScrollBar().value(), vp.width(), vp.height())

    def _on_scroll(self):
        self._container.set_viewport(self._viewport_rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Set container width to match viewport width so row count updates
        self._container.setFixedWidth(self.viewport().width())
        self._resize_timer.start()

    def _do_relayout(self):
        self._container.set_viewport(self._viewport_rect())
        self._container._full_relayout()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._container.setFixedWidth(self.viewport().width())
        self._do_relayout()

    def shutdown(self):
        self._container.cover_render_queue.shutdown(True)


class CardsView(QWidget):

    def __init__(self, model, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.view = cv = CardView(model, self)
        l.addWidget(cv)

    def shutdown(self):
        self.view.shutdown()

    def current_result(self):
        return None, None
