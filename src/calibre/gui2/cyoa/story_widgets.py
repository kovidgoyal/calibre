#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Container, Mapping
from html import escape

from qt.core import (
    QAction,
    QContextMenuEvent,
    QIcon,
    QImage,
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
    QTextBlockFormat,
    QTextBrowser,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextOption,
    QToolButton,
    QUrl,
    QVBoxLayout,
    QWheelEvent,
    QWidget,
    pyqtSignal,
)

from calibre.ai.cyoa import GameState
from calibre.ai.utils import ContentType, response_to_html
from calibre.gui2.cyoa.text_display import TextDisplayMixin
from calibre.gui2.momentum_scroll import MomentumScrollMixin
from calibre.utils.localization import _
from calibre.utils.resources import get_image_path

# The ornamental divider drawn between the turns of a chapter, rendered from
# imgsrc/scene-divider.svg at twice its display width so it stays crisp on
# high DPI screens.
SCENE_DIVIDER_URL = 'cyoa://scene-divider'
SCENE_DIVIDER_WIDTH = 300  # display width in a story view in device independent pixels
# The pictures of the scenes of individual turns, shown in the read the story
# dialog. Every picture is both a document resource, named by the one based
# number of the turn it belongs to, and a link with the same number, so that
# clicking it can show the picture full size.
SCENE_IMAGE_URL_PREFIX = 'cyoa://scene/'
SCENE_IMAGE_SCHEME = 'cyoa-scene'


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

    def wheelEvent(self, a0: QWheelEvent | None) -> None:  # ty: ignore[invalid-method-override]
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


# Rendering the story into a text document {{{


def scene_divider_image(width: int, device_pixel_ratio: float) -> QImage:
    # The divider scaled for the screen it is displayed on. It must be
    # registered on the document of every view that shows it, see
    # add_scene_divider_resource().
    img = QImage(get_image_path('scene-divider.png')).scaledToWidth(round(width * device_pixel_ratio), Qt.TransformationMode.SmoothTransformation)
    img.setDevicePixelRatio(device_pixel_ratio)
    return img


def add_scene_divider_resource(view: QTextBrowser, divider: QImage) -> None:
    if (doc := view.document()) is not None:
        doc.addResource(int(QTextDocument.ResourceType.ImageResource), QUrl(SCENE_DIVIDER_URL), divider)


def scene_image_url(turn_number: int) -> str:
    return f'{SCENE_IMAGE_URL_PREFIX}{turn_number}'


def add_scene_image_resources(view: QTextBrowser, images: Mapping[int, bytes], width: int) -> frozenset[int]:
    # Register the pictures of the scenes of turns, keyed by one based turn
    # number, as resources of the document of view, scaled to width device
    # independent pixels but never enlarged beyond their natural size, and
    # return the numbers of the turns whose picture can actually be shown.
    # The scaling is done here rather than by the text layout as the layout
    # neither smooths the images it scales nor accounts for the device pixel
    # ratio of the screen. The resources must be registered before the
    # images are inserted, as the layout resolves their size as they are
    # inserted, again after every clear(), which discards them, and again
    # whenever the width available for them changes.
    ans: set[int] = set()
    doc = view.document()
    if doc is None or width <= 0:
        return frozenset(ans)
    dpr = view.devicePixelRatioF()
    target = round(width * dpr)
    for turn_number, raw in images.items():
        img = QImage()
        if not raw or not img.loadFromData(raw):
            continue
        if 0 < target < img.width():
            img = img.scaledToWidth(target, Qt.TransformationMode.SmoothTransformation)
        img.setDevicePixelRatio(dpr)
        doc.addResource(int(QTextDocument.ResourceType.ImageResource), QUrl(scene_image_url(turn_number)), img)
        ans.add(turn_number)
    return frozenset(ans)


def story_text_width(view: QTextBrowser) -> int:
    # The width in device independent pixels of the column the text of the
    # story is laid out in, which is narrower than the view when the length
    # of a line is limited, see TextDisplayMixin.apply_max_line_width().
    doc, vp = view.document(), view.viewport()
    if doc is None or vp is None:
        return 0
    margin = doc.documentMargin()
    left = right = margin
    if (frame := doc.rootFrame()) is not None:
        fmt = frame.frameFormat()
        left, right = max(margin, fmt.leftMargin()), max(margin, fmt.rightMargin())
    ans = vp.width() - left - right
    if (vsb := view.verticalScrollBar()) is not None and not vsb.isVisible():
        # A chapter is almost always long enough to need a vertical
        # scrollbar, which narrows the viewport as soon as it appears, so
        # leave room for it. Without this an image scaled to the full width
        # of the column overflows it the moment the text is inserted.
        ans -= vsb.sizeHint().width()
    return max(0, round(ans))


def insert_scene_image(c: QTextCursor, turn_number: int) -> None:
    # The picture of the scene of a turn, centered in a block of its own and
    # wrapped in a link, so that clicking it can show it full size. Its
    # resource must already be registered on the document, see
    # add_scene_image_resources().
    bf = QTextBlockFormat()
    bf.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    bf.setTopMargin(12), bf.setBottomMargin(12)
    c.insertBlock(bf, QTextCharFormat())
    c.insertHtml(f'<a href="{SCENE_IMAGE_SCHEME}:{turn_number}"><img src="{scene_image_url(turn_number)}"></a>')


def insert_scene_divider(c: QTextCursor) -> None:
    # The divider needs its own insertion helper as insertHtml() merges the
    # fragment's first block into the current block, losing the center
    # alignment, see insert_html_block().
    bf = QTextBlockFormat()
    bf.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    bf.setTopMargin(12), bf.setBottomMargin(12)
    c.insertBlock(bf, QTextCharFormat())
    c.insertHtml(f'<img src="{SCENE_DIVIDER_URL}">')


def insert_html_block(c: QTextCursor, html: str) -> None:
    # QTextCursor.insertHtml() merges the first block of the fragment into
    # the current block, which inherits its block format. Sequential calls
    # thus run text into the preceding heading and attach the ruler of a
    # preceding <hr> to the following paragraph, so start every fragment in
    # a fresh block with default formatting.
    if c.position():
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
    c.insertHtml(html)


def render_chapter(c: QTextCursor, state: GameState, chapter: int, image_turns: Container[int] = ()) -> list[tuple[int, int]]:
    # Insert the title and the prose of one zero based chapter of the story
    # at the cursor, as the player read it while playing: the action taken
    # before each turn followed by the passage the AI wrote for it, with a
    # divider between turns. The picture of the scene of a turn, if its one
    # based number is in image_turns, follows the prose it illustrates, as
    # the illustrations of a book do. Returns the (document position, one
    # based turn number) of every turn inserted, which maps a position in
    # the document back to the turn at it, see
    # GameWidget.visible_turn_number().
    ans: list[tuple[int, int]] = []
    titles = state.chapter_titles
    if not 0 <= chapter < len(titles):
        return ans
    insert_html_block(c, f'<h2>{escape(titles[chapter])}</h2>')
    for i, t in enumerate(state.turns):
        if t.chapter != chapter:
            continue
        if ans:
            insert_scene_divider(c)
        ans.append((c.position(), i + 1))
        if t.player_input:
            insert_html_block(c, f'<p><i>➤ {escape(t.player_input)}</i></p>')
        insert_html_block(c, response_to_html(t.turn.narrative, ContentType.markdown))
        if i + 1 in image_turns:
            insert_scene_image(c, i + 1)
    return ans


# }}}
