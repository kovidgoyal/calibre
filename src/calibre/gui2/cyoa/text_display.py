#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The look of the widgets that display the text of the "Create Your Own
# Adventure" game: the font, the colors and, for the main story view, the
# maximum length of a line. All of them come from a single set of
# preferences shared by every such widget, see data.TextDisplaySettings, so
# that zooming in one of them, with Ctrl+wheel or the zoom keyboard
# shortcuts, zooms all of them. Widgets created from TextDisplayMixin
# register themselves here, so that a change made in the settings dialog is
# applied to all of them at once, including those that are not visible.

import weakref
from collections.abc import Callable, Iterator
from functools import partial
from typing import TYPE_CHECKING

from qt.core import (
    QApplication,
    QColor,
    QEvent,
    QFont,
    QFontMetricsF,
    QKeySequence,
    QPalette,
    QShortcut,
    Qt,
    QTextBrowser,
    QTextEdit,
    QWheelEvent,
    QWidget,
    sip,
)

from calibre.gui2.cyoa import data
from calibre.gui2.palette import dark_link_color, light_link_color

# One wheel click is 120 in angle delta units and changes the font size by
# this many points.
WHEEL_STEP = 120
ZOOM_STEP = 1
# Set on the window the zoom shortcuts have been installed on, so that they
# are installed only once per window, see install_zoom_shortcuts().
ZOOM_SHORTCUTS_PROPERTY = 'cyoa-zoom-shortcuts-installed'

_registry: list[weakref.ref[TextDisplayMixin]] = []


def register(w: TextDisplayMixin) -> None:
    _registry[:] = [r for r in _registry if r() is not None]
    _registry.append(weakref.ref(w))


def text_displays() -> Iterator[TextDisplayMixin]:
    # The text display widgets that are still alive. Their Python wrappers
    # can outlive the underlying C++ objects, so deleted ones are skipped.
    for ref in tuple(_registry):
        w = ref()
        if w is not None and not sip.isdeleted(w):
            yield w


def apply_text_display_settings() -> None:
    for w in text_displays():
        w.apply_text_display_settings()


def default_font_size() -> int:
    f = QApplication.font()
    ans = f.pointSize()
    if ans <= 0:  # a font specified in pixels rather than points
        ans = round(f.pointSizeF())
    return ans if ans > 0 else 12


def text_display_font() -> QFont:
    s = data.text_display_settings()
    ans = QFont(QApplication.font())
    if s.font_family:
        ans.setFamily(s.font_family)
    ans.setPointSize(s.font_size or default_font_size())
    return ans


def change_font_size(delta: int) -> None:
    s = data.text_display_settings()
    current = s.font_size or default_font_size()
    data.set_text_display_font_size(max(data.MIN_FONT_SIZE, min(current + delta, data.MAX_FONT_SIZE)))
    apply_text_display_settings()


def reset_font_size() -> None:
    data.set_text_display_font_size(0)
    apply_text_display_settings()


def install_zoom_shortcuts(widget: QWidget) -> None:
    # The zoom shortcuts are installed on the window rather than on every
    # text display widget, both so that they work whichever widget of the
    # window has keyboard focus and so that two text displays in the same
    # window do not make them ambiguous.
    win = widget.window()
    if win is None or win.property(ZOOM_SHORTCUTS_PROPERTY):
        return
    win.setProperty(ZOOM_SHORTCUTS_PROPERTY, True)
    specs: tuple[tuple[QKeySequence.StandardKey | None, tuple[str, ...], Callable[[], None]], ...] = (
        # Ctrl++ needs a shifted key on many keyboards, so accept Ctrl+= too
        (QKeySequence.StandardKey.ZoomIn, ('Ctrl+=',), partial(change_font_size, ZOOM_STEP)),
        (QKeySequence.StandardKey.ZoomOut, (), partial(change_font_size, -ZOOM_STEP)),
        (None, ('Ctrl+0',), reset_font_size),
    )
    for standard_key, extra, func in specs:
        seqs = list(QKeySequence.keyBindings(standard_key)) if standard_key is not None else []
        for text in extra:
            ks = QKeySequence(text, QKeySequence.SequenceFormat.PortableText)
            if ks not in seqs:
                seqs.append(ks)
        for ks in seqs:
            sc = QShortcut(ks, win)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(func)


class TextDisplayMixin(QTextEdit if TYPE_CHECKING else object):
    """
    Mixin that makes a QTextEdit based widget follow the game's text display
    settings, adding Ctrl+wheel and Ctrl+plus/minus/zero zooming.

    Usage:
        class MyView(TextDisplayMixin, QTextBrowser):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setup_text_display()
    """

    # Set on the main story view: the text in it is limited to
    # data.text_display_settings().max_line_width characters per line.
    constrain_line_width = False
    # CSS a subclass wants applied to the HTML it displays, on top of the
    # rules needed by the text display settings, see document_style_sheet().
    extra_style_sheet = ''
    # Guards against re-entering apply_max_line_width() from the viewport
    # resize the changed margins can themselves cause.
    _applying_line_width = False
    _wheel_zoom_delta = 0

    def setup_text_display(self) -> None:
        register(self)
        install_zoom_shortcuts(self)
        self.apply_text_display_settings()

    def apply_text_display_settings(self) -> None:
        s = data.text_display_settings()
        f = text_display_font()
        self.setFont(f)
        if (doc := self.document()) is not None:
            doc.setDefaultFont(f)
        # Roles left unset in the palette are inherited, so an empty color
        # means: follow the standard colors. The text is drawn using the
        # palette of the widget but the background is filled using the
        # palette of the viewport, which does not inherit from the widget,
        # so both need to be set.
        pal = QPalette()
        if s.foreground and (col := QColor(s.foreground)).isValid():
            pal.setColor(QPalette.ColorRole.Text, col)
        if s.background and (col := QColor(s.background)).isValid():
            pal.setColor(QPalette.ColorRole.Base, col)
        self.setPalette(pal)
        if (vp := self.viewport()) is not None:
            vp.setPalette(pal)
        if doc is not None:
            doc.setDefaultStyleSheet(self.document_style_sheet(s))
        self.apply_max_line_width()

    def document_style_sheet(self, s: data.TextDisplaySettings) -> str:
        # The HTML parser colors links a fixed blue, which can be illegible
        # on a background color chosen by the player, so link colors are set
        # to match it. Note that the style sheet is applied when HTML is
        # parsed, so the widget has to be re-populated for a change to it to
        # become visible.
        css = self.extra_style_sheet
        if s.background and (col := QColor(s.background)).isValid():
            link = dark_link_color if col.lightness() < 128 else light_link_color
            css += f'\na {{ color: {link.name()} }}'
        return css

    def apply_max_line_width(self) -> None:
        # Rather than narrowing the widget itself, which would move the
        # splitter and the widgets below it, the text is kept to at most
        # max_line_width characters by widening the side margins of the
        # document, which also centers it in the available space.
        if not self.constrain_line_width or self._applying_line_width:
            return
        doc, vp = self.document(), self.viewport()
        if doc is None or vp is None or (frame := doc.rootFrame()) is None:
            return
        margin = doc.documentMargin()
        if num_chars := data.text_display_settings().max_line_width:
            desired = num_chars * QFontMetricsF(doc.defaultFont()).averageCharWidth()
            margin = max(margin, (vp.width() - desired) / 2)
        fmt = frame.frameFormat()
        if abs(fmt.leftMargin() - margin) < 1 and abs(fmt.rightMargin() - margin) < 1:
            return  # sub-pixel changes are not worth a re-layout
        fmt.setLeftMargin(margin), fmt.setRightMargin(margin)
        self._applying_line_width = True
        try:
            frame.setFrameFormat(fmt)
        finally:
            self._applying_line_width = False

    def zoom_wheel_event(self, ev: QWheelEvent | None) -> bool:
        # Ctrl+wheel zooms every text display widget. Returns True when the
        # event was such a zoom and has been handled, so that subclasses can
        # call this from their wheelEvent() and scroll otherwise. They have
        # to do so themselves rather than this class overriding wheelEvent()
        # because the mixins it is combined with override it as well.
        if ev is None or ev.modifiers() != Qt.KeyboardModifier.ControlModifier:
            self._wheel_zoom_delta = 0
            return False
        # High resolution wheels and touchpads send many small deltas, so
        # accumulate them into whole clicks.
        self._wheel_zoom_delta += ev.angleDelta().y()
        steps = int(self._wheel_zoom_delta / WHEEL_STEP)
        if steps:
            self._wheel_zoom_delta -= steps * WHEEL_STEP
            change_font_size(steps * ZOOM_STEP)
        ev.accept()
        return True

    def viewportEvent(self, a0: QEvent | None) -> bool:
        ans = super().viewportEvent(a0)
        if a0 is not None and a0.type() == QEvent.Type.Resize:
            # The width available for the text changes not just when the
            # widget is resized but also when the scrollbar appears
            self.apply_max_line_width()
        return ans


class TextDisplay(TextDisplayMixin, QTextBrowser):
    # A read-only display of story text that follows the game's text display
    # settings.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup_text_display()

    def wheelEvent(self, e: QWheelEvent | None) -> None:
        if not self.zoom_wheel_event(e):
            super().wheelEvent(e)
