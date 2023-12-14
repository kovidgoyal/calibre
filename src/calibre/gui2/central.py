#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from copy import copy
from enum import Enum, auto
from dataclasses import dataclass
from qt.core import (
    QDialog, QLabel, QPalette, QPointF, QSize, QSizePolicy, QStyle, QStyleOption,
    QStylePainter, Qt, QVBoxLayout, QWidget, pyqtSignal
)

from calibre.gui2 import Application, config
from calibre.gui2.cover_flow import MIN_SIZE


class Placeholder(QLabel):
    backgrounds = 'yellow', 'lightgreen', 'grey', 'cyan', 'magenta'
    bgcount = 0

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        bg = self.backgrounds[Placeholder.bgcount]
        Placeholder.bgcount = (Placeholder.bgcount + 1) % len(self.backgrounds)
        self.setStyleSheet(f'QLabel {{ background: {bg} }}')


class HandleState(Enum):
    both_visible = auto()
    only_main_visible = auto()
    only_side_visible = auto()


class SplitterHandle(QWidget):

    drag_started = pyqtSignal()
    drag_ended = pyqtSignal()
    dragged_to = pyqtSignal(QPointF)
    drag_start = None
    COLLAPSED_SIZE = 2  # pixels

    def __init__(self, parent: QWidget=None, orientation: Qt.Orientation = Qt.Orientation.Vertical):
        super().__init__(parent)
        self.orientation = orientation
        if orientation is Qt.Orientation.Vertical:
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.setCursor(Qt.CursorShape.SplitVCursor)

    @property
    def state(self) -> HandleState:
        p = self.parent()
        if p is not None:
            try:
                return p.handle_state(self)
            except AttributeError as err:
                raise Exception(str(err)) from err
        return HandleState.both_visible

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        if ev.button() is Qt.MouseButton.LeftButton:
            self.drag_start = ev.position()
            self.drag_started.emit()

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if ev.button() is Qt.MouseButton.LeftButton:
            self.drag_start = None
            self.drag_started.emit()

    def mouseMoveEvent(self, ev):
        super().mouseMoveEvent(ev)
        if self.drag_start is not None:
            pos = ev.position() - self.drag_start
            self.dragged_to.emit(self.mapToParent(pos))

    def paintEvent(self, ev):
        p = QStylePainter(self)
        opt = QStyleOption()
        opt.initFrom(self)
        if self.orientation is Qt.Orientation.Vertical:
            opt.state |= QStyle.StateFlag.State_Horizontal
        if min(opt.rect.width(), opt.rect.height()) == self.COLLAPSED_SIZE:
            p.fillRect(opt.rect, opt.palette.color(QPalette.ColorRole.Window))
        else:
            p.drawControl(QStyle.ControlElement.CE_Splitter, opt)
        p.end()


class Layout(Enum):

    wide = auto()
    narrow = auto()


@dataclass
class WideDesires:
    tag_browser_width: int = 0
    book_details_width: int = 0
    cover_browser_height: int = 0
    quick_view_height: int = 0


@dataclass
class NarrowDesires:
    book_details_height: int = 0
    quick_view_height: int = 0
    tag_browser_width: int = 0
    cover_browser_width: int = 0


@dataclass
class Visibility:
    tag_browser: bool = True
    book_details: bool = True
    book_list: bool = True
    cover_browser: bool = False
    quick_view: bool = False


class Central(QWidget):

    def __init__(self, parent=None, initial_layout=''):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.wide_desires = WideDesires()
        self.narrow_desires = NarrowDesires()
        self.is_visible = Visibility()
        self.layout = Layout.narrow if (initial_layout or config.get('gui_layout')) == 'narrow' else Layout.wide
        self.tag_browser = Placeholder('tag browser', self)
        self.book_list = Placeholder('book list', self)
        self.cover_browser = Placeholder('cover browser', self)
        self.cover_browser.setMinimumSize(MIN_SIZE)
        self.book_details = Placeholder('book details', self)
        self.quick_view = Placeholder('quick view', self)
        self.setMinimumSize(MIN_SIZE + QSize(200, 100))

        def h(orientation: Qt.Orientation = Qt.Orientation.Vertical):
            ans = SplitterHandle(self, orientation)
            ans.dragged_to.connect(self.splitter_handle_dragged)
            return ans

        self.left_handle = h()
        self.right_handle = h()
        self.top_handle = h(Qt.Orientation.Horizontal)
        self.bottom_handle = h(Qt.Orientation.Horizontal)

    def toggle_panel(self, which):
        was_visible = getattr(self.is_visible, which)
        setattr(self.is_visible, which, was_visible ^ True)
        if not was_visible:
            if self.layout is Layout.wide:
                self.size_panel_on_initial_show_wide(which)
            else:
                self.size_panel_on_initial_show_narrow(which)
        self.relayout()

    def toggle_tag_browser(self):
        self.toggle_panel('tag_browser')

    def toggle_book_details(self):
        self.toggle_panel('book_details')

    def toggle_cover_browser(self):
        self.toggle_panel('cover_browser')

    def toggle_quick_view(self):
        self.toggle_panel('quick_view')
        self.relayout()

    def handle_state(self, handle):
        if self.layout is Layout.wide:
            return self.wide_handle_state(handle)
        return self.narrow_handle_state(handle)

    def splitter_handle_dragged(self, pos):
        handle = self.sender()
        bv = copy(self.is_visible)
        if self.layout is Layout.wide:
            bd = copy(self.wide_desires)
            self.wide_move_splitter_handle_to(handle, pos)
            ad = self.wide_desires
        else:
            bd = copy(self.narrow_desires)
            self.narrow_move_splitter_handle_to(handle, pos)
            ad = self.narrow_desires
        if (bv, bd) != (self.is_visible, ad):
            self.relayout()

    def refresh_after_config_change(self):
        self.layout = Layout.narrow if config.get('gui_layout') == 'narrow' else Layout.wide
        self.relayout()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.relayout()

    def relayout(self):
        self.tag_browser.setVisible(self.is_visible.tag_browser)
        self.book_details.setVisible(self.is_visible.book_details)
        self.cover_browser.setVisible(self.is_visible.cover_browser)
        self.book_list.setVisible(self.is_visible.book_list)
        self.quick_view.setVisible(self.is_visible.quick_view)
        if self.layout is Layout.wide:
            self.do_wide_layout()
        else:
            self.do_narrow_layout()
        self.update()

    def toggle_layout(self):
        self.layout = Layout.narrow if self.layout is Layout.wide else Layout.wide
        self.relayout()

    # Wide {{{
    def wide_handle_state(self, handle):
        if handle is self.left_handle:
            return HandleState.both_visible if self.is_visible.tag_browser else HandleState.only_main_visible
        if handle is self.right_handle:
            return HandleState.both_visible if self.is_visible.book_details else HandleState.only_main_visible
        if handle is self.top_handle:
            if self.is_visible.cover_browser:
                return HandleState.both_visible if self.is_visible.book_list else HandleState.only_side_visible
            return HandleState.only_main_visible
        if handle is self.bottom_handle:
            return HandleState.both_visible if self.is_visible.quick_view else HandleState.only_main_visible

    def min_central_width_wide(self):
        return max(200, self.cover_browser.minimumWidth())

    def default_wide_side_panel_width(self):
        available_width = self.width() - 2 * int(self.style().pixelMetric(QStyle.PixelMetric.PM_SplitterWidth, widget=self))
        return min(300, (3 * available_width) // 10)

    def do_wide_layout(self):
        s = self.style()
        normal_handle_width = int(s.pixelMetric(QStyle.PixelMetric.PM_SplitterWidth, widget=self))
        available_width = self.width()
        for h in (self.left_handle, self.right_handle):
            width = h.COLLAPSED_SIZE
            hs = h.state
            if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
                width = normal_handle_width
            h.resize(width, self.height())
            available_width -= width
        default_width = self.default_wide_side_panel_width()
        tb = self.wide_desires.tag_browser_width or default_width
        if not self.is_visible.tag_browser:
            tb = 0
        bd = self.wide_desires.book_details_width or default_width
        if not self.is_visible.book_details:
            bd = 0
        min_central_width = self.min_central_width_wide()
        if tb + bd > available_width - min_central_width:
            width_to_share = max(0, available_width - min_central_width)
            tb = int(tb * width_to_share / (tb + bd))
            bd = max(0, width_to_share - tb)
        central_width = available_width - (tb + bd)
        if self.is_visible.tag_browser:
            self.tag_browser.setGeometry(0, 0, tb, self.height())
        self.left_handle.move(tb, 0)
        central_x = self.left_handle.x() + self.left_handle.width()
        self.right_handle.move(tb + central_width + self.left_handle.width(), 0)
        if self.is_visible.book_details:
            self.book_details.setGeometry(self.right_handle.x() + self.right_handle.width(), 0, bd, self.height())

        available_height = self.height()
        for h in (self.top_handle, self.bottom_handle):
            height = h.COLLAPSED_SIZE
            hs = h.state
            if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
                height = normal_handle_width
            if h is self.bottom_handle and hs is HandleState.only_main_visible:
                height = 0
            h.resize(central_width, height)
            available_height -= height

        cb = max(self.cover_browser.minimumHeight(), self.wide_desires.cover_browser_height or (2 * available_height // 5))
        if not self.is_visible.cover_browser:
            cb = 0
        qv = bl = 0
        if cb >= available_height:
            cb = available_height
        else:
            available_height -= cb
            min_bl_height = 50
            if available_height <= min_bl_height:
                bl = available_height
            elif self.is_visible.quick_view:
                qv = min(available_height - min_bl_height, self.wide_desires.quick_view_height or min(200, available_height // 2))
                bl = available_height - qv
            else:
                bl = available_height
        if self.is_visible.cover_browser:
            self.cover_browser.setGeometry(central_x, 0, central_width, cb)
        self.top_handle.move(central_x, cb)
        if self.is_visible.book_list:
            self.book_list.setGeometry(central_x, self.top_handle.y() + self.top_handle.height(), central_width, bl)
        self.bottom_handle.move(central_x, self.book_list.y() + self.book_list.height())
        if self.is_visible.quick_view:
            self.quick_view.setGeometry(central_x, self.bottom_handle.y() + self.bottom_handle.height(), central_width, qv)

    def wide_move_splitter_handle_to(self, handle: SplitterHandle, pos: QPointF):
        if handle is self.left_handle:
            x = int(pos.x())
            available_width = self.width() - self.left_handle.width() - self.right_handle.width() - self.min_central_width_wide()
            self.is_visible.tag_browser = True
            if x < 10:
                self.is_visible.tag_browser = False
                self.wide_desires.tag_browser_width = 10
            else:
                self.wide_desires.tag_browser_width = min(available_width, x)
        elif handle is self.right_handle:
            x = int(pos.x())
            available_width = self.width() - self.left_handle.width() - self.right_handle.width() - self.min_central_width_wide()
            self.is_visible.book_details = True
            w = self.width() - x - self.right_handle.width()
            if w < 10:
                self.is_visible.book_details = False
                self.wide_desires.book_details_width = 10
            else:
                self.wide_desires.book_details_width = min(available_width, w)
        elif handle is self.top_handle:
            y = int(pos.y())
            self.is_visible.cover_browser = True
            if y < max(self.cover_browser.minimumHeight(), 10):
                self.is_visible.cover_browser = False
                self.wide_desires.cover_browser_height = max(10, self.cover_browser.minimumHeight())
            else:
                self.wide_desires.cover_browser_height = max(y, self.cover_browser.minimumHeight())
        elif handle is self.bottom_handle:
            y = int(pos.y())
            h = self.height() - y - self.bottom_handle.height()
            if h < 10:
                self.is_visible.quick_view = False
                self.wide_desires.quick_view_height = 10
            else:
                available_height = max(0, self.height() - self.top_handle.height() - self.bottom_handle.height() - self.cover_browser.minimumHeight() - 50)
                self.wide_desires.quick_view_height = max(10, min(h, available_height))

    def size_panel_on_initial_show_wide(self, which):
        if which in ('tag_browser', 'book_details'):
            which += '_width'
            current = getattr(self.wide_desires, which)
            if current and current < 50:
                setattr(self.wide_desires, which, self.default_wide_side_panel_width())
        elif which == 'cover_browser':
            self.wide_desires.cover_browser_height = max(self.wide_desires.cover_browser_height, self.cover_browser.minimumHeight())
        else:
            self.wide_desires.quick_view_height = max(self.wide_desires.quick_view_height, 150)
    # }}}

    # Narrow {{{
    def narrow_handle_state(self, handle):
        if handle is self.left_handle:
            return HandleState.both_visible if self.is_visible.tag_browser else HandleState.only_main_visible
        if handle is self.right_handle:
            if self.is_visible.cover_browser:
                return HandleState.both_visible if self.is_visible.book_list else HandleState.only_side_visible
            return HandleState.only_main_visible
        if handle is self.top_handle:
            return HandleState.both_visible if self.is_visible.quick_view else HandleState.only_main_visible
        if handle is self.bottom_handle:
            return HandleState.both_visible if self.is_visible.book_details else HandleState.only_main_visible

    def min_central_width_narrow(self):
        return 200

    def min_central_height_narrow(self):
        return max(150, self.cover_browser.minimumHeight())

    def do_narrow_layout(self):
        s = self.style()
        normal_handle_width = int(s.pixelMetric(QStyle.PixelMetric.PM_SplitterWidth, widget=self))
        available_height = self.height()
        hs = self.bottom_handle.state
        height = self.bottom_handle.COLLAPSED_SIZE
        if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
            height = normal_handle_width
        self.bottom_handle.resize(self.width(), height)
        available_height -= height
        bd = self.narrow_desires.book_details_height or min(350, available_height // 3)
        if not self.is_visible.book_details:
            bd = 0
        central_height = max(self.min_central_height_narrow(), available_height - bd)
        bd = available_height - central_height
        self.bottom_handle.move(0, central_height)
        if self.is_visible.book_details:
            self.book_details.setGeometry(0, central_height + self.bottom_handle.height(), self.width(), bd)

        available_width = self.width()
        for h in (self.left_handle, self.right_handle):
            width = h.COLLAPSED_SIZE
            hs = h.state
            if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
                width = normal_handle_width
            h.resize(width, central_height)
            available_width -= width
        default_width = self.default_wide_side_panel_width()
        tb = self.narrow_desires.tag_browser_width or default_width
        if not self.is_visible.tag_browser:
            tb = 0
        cb = self.narrow_desires.cover_browser_width or default_width
        if self.is_visible.cover_browser:
            cb = max(self.cover_browser.minimumWidth(), cb)
        else:
            cb = 0
        min_central_width = self.min_central_width_narrow()
        if tb + cb > available_width - min_central_width:
            width_to_share = max(0, available_width - min_central_width)
            cb = int(cb * width_to_share / (tb + cb))
            cb = max(self.cover_browser.minimumWidth(), cb)
            if cb > width_to_share:
                cb = 0
            tb = max(0, width_to_share - cb)
        central_width = available_width - (tb + cb)
        if self.is_visible.tag_browser:
            self.tag_browser.setGeometry(0, 0, tb, self.height())
        self.left_handle.move(tb, 0)
        central_x = self.left_handle.x() + self.left_handle.width()
        self.right_handle.move(tb + central_width + self.left_handle.width(), 0)
        if self.is_visible.cover_browser:
            self.cover_browser.setGeometry(self.right_handle.x() + self.right_handle.width(), 0, cb, self.height())
        self.top_handle.resize(central_width, normal_handle_width if self.is_visible.quick_view else 0)
        central_height -= self.top_handle.height()
        qv = 0
        if self.is_visible.quick_view:
            qv = self.narrow_desires.quick_view_height or min(250, central_height // 2)
            qv = max(0, min(qv, central_height - 50))
        self.book_list.setGeometry(central_x, 0, central_width, max(0, central_height - qv))
        self.top_handle.move(central_x, self.book_list.y() + self.book_list.height())
        if self.is_visible.quick_view:
            self.quick_view.setGeometry(central_x, self.top_handle.y() + self.top_handle.height(), central_width, qv)

    def narrow_move_splitter_handle_to(self, handle: SplitterHandle, pos: QPointF):
        raise NotImplementedError('TODO: Implement me')

    def size_panel_on_initial_show_narrow(self, which):
        if which in ('tag_browser', 'cover_browser'):
            which += '_width'
            current = getattr(self.narrow_desires, which)
            if current and current < 50:
                setattr(self.narrow_desires, which, self.default_wide_side_panel_width())
        elif which == 'book_details':
            self.narrow_desires.book_details_height = max(self.narrow_desires.book_details_height, 350)
        else:
            self.narrow_desires.quick_view_height = max(self.narrow_desires.quick_view_height, 200)
    # }}}

    def sizeHint(self):
        return QSize(800, 600)


# develop {{{
def develop():
    app = Application([])
    class d(QDialog):
        def __init__(self):
            super().__init__()
            l = QVBoxLayout(self)
            l.setContentsMargins(0, 0, 0, 0)
            self.central = Central(self, initial_layout='narrow')
            l.addWidget(self.central)
            self.resize(self.sizeHint())
        def keyPressEvent(self, ev):
            if ev.key() == Qt.Key.Key_Q:
                self.central.toggle_quick_view()
            elif ev.key() == Qt.Key.Key_T:
                self.central.toggle_tag_browser()
            elif ev.key() == Qt.Key.Key_C:
                self.central.toggle_cover_browser()
            elif ev.key() == Qt.Key.Key_D:
                self.central.toggle_book_details()
            elif ev.key() == Qt.Key.Key_L:
                self.central.toggle_layout()
            elif ev.key() == Qt.Key.Key_Escape:
                self.reject()

    d = d()
    d.show()
    app.exec()


if __name__ == '__main__':
    develop()
# }}}
