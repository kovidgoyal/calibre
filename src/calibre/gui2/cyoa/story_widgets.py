#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import (
    QAction,
    QContextMenuEvent,
    QIcon,
    QKeyEvent,
    QLabel,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QPlainTextEdit,
    QPushButton,
    QRectF,
    QResizeEvent,
    QSize,
    QSizeF,
    Qt,
    QTextBrowser,
    QTextOption,
    QToolButton,
    QVBoxLayout,
    QWheelEvent,
    QWidget,
    pyqtSignal,
)

from calibre.gui2.cyoa.text_display import TextDisplayMixin
from calibre.gui2.momentum_scroll import MomentumScrollMixin
from calibre.utils.localization import _


class PromptEdit(QPlainTextEdit):
    # The box the player types their next action into. Ctrl+Enter submits.
    submit_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMaximumHeight(self.fontMetrics().lineSpacing() * 4)

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e is not None and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            e.accept()
            self.submit_requested.emit()
            return
        super().keyPressEvent(e)


class SceneImageDisplay(QWidget):
    # Shows an image scaled to fit while preserving aspect ratio, or a
    # placeholder message when there is no image. Double clicking the image
    # opens it in a popup and right clicking it shows a context menu, both
    # handled by the game widget. A discreet refresh button in the bottom
    # right corner of the image and, when there is no image because
    # generation failed or was never attempted for this scene, a retry or
    # generate button shown in place of the placeholder text all ask the
    # game widget to (re-)generate the picture via refresh_requested.
    popup_requested = pyqtSignal()
    context_menu_requested = pyqtSignal(object)  # the global position of the click as a QPoint
    refresh_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image_data = b''
        self.placeholder = ''
        self.failed = False
        self.busy = False
        self.can_generate = False
        self.pixmap = QPixmap()
        # Request a height matching the image so widgets placed below in a
        # layout sit directly under the image rather than under empty space.
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.refresh_button = rb = QToolButton(self)
        rb.setIcon(QIcon.ic('view-refresh.png'))
        rb.setAutoRaise(True)
        rb.setCursor(Qt.CursorShape.PointingHandCursor)
        rb.setToolTip('<p>' + _('Re-generate the picture of this scene'))
        rb.clicked.connect(self.refresh_requested)
        rb.hide()
        # Shown in place of the placeholder text when there is no picture of
        # this scene, offering to generate one, or to retry when generation
        # failed. Label and button texts are set in set_image().
        self.retry_panel = rp = QWidget(self)
        rl = QVBoxLayout(rp)
        self.retry_label = rla = QLabel(rp)
        rla.setWordWrap(True)
        rla.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.retry_button = tb = QPushButton(QIcon.ic('view-refresh.png'), '', rp)
        tb.clicked.connect(self.refresh_requested)
        rl.addStretch()
        rl.addWidget(rla)
        rl.addWidget(tb, alignment=Qt.AlignmentFlag.AlignHCenter)
        rl.addStretch()
        rp.hide()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, a0: int) -> int:
        if self.pixmap.isNull():
            return (a0 * 3) // 4  # the aspect ratio scene images are generated at
        sz = self.pixmap.deviceIndependentSize()
        return round(a0 * sz.height() / sz.width())

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton and not self.pixmap.isNull():
            a0.accept()
            self.popup_requested.emit()
            return
        super().mouseDoubleClickEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        if a0 is not None and not self.pixmap.isNull():
            a0.accept()
            self.context_menu_requested.emit(a0.globalPos())

    def set_image(
        self,
        image_data: bytes | None,
        placeholder: str,
        failed: bool = False,
        busy: bool = False,
        can_generate: bool = False,
    ) -> None:
        image_data = image_data or b''
        if (
            image_data == self.image_data
            and placeholder == self.placeholder
            and failed == self.failed
            and busy == self.busy
            and can_generate == self.can_generate
        ):
            return
        self.image_data, self.placeholder, self.failed, self.busy = image_data, placeholder, failed, busy
        self.can_generate = can_generate
        if failed:
            self.retry_label.setText(
                _(
                    'Failed to generate a picture of this scene. If retrying does not help,'
                    ' try changing the image generation AI model via the Settings button in the toolbar.'
                )
            )
            self.retry_button.setText(_('&Retry image generation'))
        else:
            self.retry_label.setText(_('No picture of this scene is available'))
            self.retry_button.setText(_('&Generate scene image'))
        pm = QPixmap()
        if image_data:
            pm.loadFromData(image_data)
            pm.setDevicePixelRatio(self.devicePixelRatioF())
        self.pixmap = pm
        self.position_overlays()
        self.updateGeometry()  # the height for width depends on the image aspect ratio
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(300, 400)

    def image_rect(self) -> QRectF:
        # Where the image is drawn: scaled to fit, centered horizontally and
        # aligned with the panel top.
        sz = QSizeF(self.pixmap.deviceIndependentSize())
        sz.scale(QSizeF(self.size()), Qt.AspectRatioMode.KeepAspectRatio)
        r = QRectF(0, 0, sz.width(), sz.height())
        r.moveCenter(QRectF(self.rect()).center())
        r.moveTop(0)
        return r

    def position_overlays(self) -> None:
        self.retry_panel.setGeometry(self.rect())
        self.retry_panel.setVisible((self.failed or self.can_generate) and self.pixmap.isNull() and not self.busy)
        if self.pixmap.isNull() or self.busy:
            self.refresh_button.hide()
            return
        margin = 4
        r = self.image_rect()
        s = self.refresh_button.sizeHint()
        self.refresh_button.move(round(r.right()) - s.width() - margin, round(r.bottom()) - s.height() - margin)
        self.refresh_button.show()
        self.refresh_button.raise_()

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self.position_overlays()  # the image rect the refresh button sits in depends on the widget size

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        p = QPainter(self)
        if self.pixmap.isNull():
            to = QTextOption(Qt.AlignmentFlag.AlignCenter)
            to.setWrapMode(QTextOption.WrapMode.WordWrap)
            p.drawText(QRectF(self.rect()), self.placeholder, to)
        else:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(self.image_rect(), self.pixmap, QRectF(self.pixmap.rect()))
        p.end()


class StoryView(TextDisplayMixin, MomentumScrollMixin, QTextBrowser):
    # The chapter text display: a text browser with momentum scrolling,
    # a line length limited to keep it comfortable to read and an extra
    # context menu action to copy the current turn.

    constrain_line_width = True
    extra_style_sheet = 'a { text-decoration: none }'  # quick action links are colored but not underlined

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.copy_turn_action: QAction | None = None
        self.setup_text_display()

    def wheelEvent(self, a0: QWheelEvent | None) -> None:
        if not self.zoom_wheel_event(a0):
            MomentumScrollMixin.wheelEvent(self, a0)

    def contextMenuEvent(self, e: QContextMenuEvent | None) -> None:
        if e is None:
            return
        m = self.createStandardContextMenu(e.pos())
        if m is None:
            return
        if self.copy_turn_action is not None:
            m.addSeparator()
            m.addAction(self.copy_turn_action)
        m.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        m.exec(e.globalPos())
