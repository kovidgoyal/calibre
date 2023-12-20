#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from copy import copy
from dataclasses import asdict, dataclass, fields
from enum import Enum, auto
from qt.core import (
    QDialog, QHBoxLayout, QIcon, QKeySequence, QLabel, QPalette, QPointF, QSize,
    QSizePolicy, QStyle, QStyleOption, QStylePainter, Qt, QToolButton, QVBoxLayout,
    QWidget, pyqtSignal,
)

from calibre.gui2 import Application, gprefs
from calibre.gui2.cover_flow import MIN_SIZE

HIDE_THRESHOLD = 10
SHOW_THRESHOLD = 50


class Placeholder(QLabel):
    backgrounds = 'yellow', 'lightgreen', 'grey', 'cyan', 'magenta'
    bgcount = 0

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        bg = self.backgrounds[Placeholder.bgcount]
        Placeholder.bgcount = (Placeholder.bgcount + 1) % len(self.backgrounds)
        self.setStyleSheet(f'QLabel {{ background: {bg} }}')


class LayoutButton(QToolButton):

    def __init__(self, name: str, icon: str, label: str, central: 'Central', shortcut=None):
        super().__init__(central)
        self.central = central
        self.label = label
        self.name = name
        self.shortcut = shortcut
        self.setIcon(QIcon.ic(icon))
        self.setCheckable(True)
        self.setChecked(self.is_visible)
        self.toggled.connect(central.layout_button_toggled)

    @property
    def is_visible(self):
        return getattr(self.central.is_visible, self.name)

    def update_shortcut(self, action_toggle=None):
        action_toggle = action_toggle or getattr(self, 'action_toggle', None)
        if action_toggle:
            sc = ', '.join(sc.toString(QKeySequence.SequenceFormat.NativeText)
                                for sc in action_toggle.shortcuts())
            self.shortcut = sc or ''
            self.update_text()

    def update_text(self):
        t = _('Hide {}') if self.isChecked() else _('Show {}')
        t = t.format(self.label)
        if self.shortcut:
            t += f' [{self.shortcut}]'
        self.setText(t), self.setToolTip(t), self.setStatusTip(t)

    def set_state_to_show(self, *args):
        self.setChecked(False)
        self.update_text()

    def set_state_to_hide(self, *args):
        self.setChecked(True)
        self.update_text()

    def update_state(self, *args):
        self.set_state_to_show() if self.is_visible else self.set_state_to_hide()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            if self.name == 'search':
                gui.iactions['Preferences'].do_config(initial_plugin=('Interface', 'Search'), close_after_initial=True)
                ev.accept()
                return
            tab_name = {'book_details':'book_details', 'cover_grid':'cover_grid', 'cover_browser':'cover_browser',
                        'tag_browser':'tag_browser', 'quick_view':'quickview'}.get(self.name)
            if tab_name:
                if gui is not None:
                    gui.iactions['Preferences'].do_config(initial_plugin=('Interface', 'Look & Feel', tab_name+'_tab'), close_after_initial=True)
                    ev.accept()
                    return
        return QToolButton.mouseReleaseEvent(self, ev)


class HandleState(Enum):
    both_visible = auto()
    only_main_visible = auto()
    only_side_visible = auto()


class SplitterHandle(QWidget):

    dragged_to = pyqtSignal(QPointF)
    toggle_requested = pyqtSignal()

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

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if ev.button() is Qt.MouseButton.LeftButton:
            self.drag_start = None

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.toggle_requested.emit()
            ev.accept()
            return
        return super().mouseDoubleClickEvent(ev)

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
    tag_browser_width: float = 0.3
    book_details_width: float = 0.3
    cover_browser_height: float = 0.4
    quick_view_height: float = 0.2

    def serialize(self):
        return {k: v for k, v in asdict(self).items() if v > 0}

    def unserialize(self, x):
        for field in fields(self):
            v = x.get(field.name, 0)
            if isinstance(v, (int, float)) and 0 < v <= 1:
                setattr(self, field.name, v)

    def reset_to_defaults(self):
        c = type(self)
        for f in fields(self):
            setattr(self, f.name, getattr(c, f.name))


@dataclass
class NarrowDesires:
    book_details_height: int = 0.3
    quick_view_height: int = 0.2
    tag_browser_width: int = 0.25
    cover_browser_width: int = 0.35

    def serialize(self):
        return {k: v for k, v in asdict(self).items() if v > 0}

    def unserialize(self, x):
        for field in fields(self):
            v = x.get(field.name, 0)
            if isinstance(v, (int, float)) and 0 < v <= 1:
                setattr(self, field.name, v)

    def reset_to_defaults(self):
        c = type(self)
        for f in fields(self):
            setattr(self, f.name, getattr(c, f.name))


@dataclass
class Visibility:
    tag_browser: bool = True
    book_details: bool = True
    book_list: bool = True
    cover_browser: bool = False
    quick_view: bool = False

    def serialize(self):
        return asdict(self)

    def unserialize(self, x):
        for f in fields(self):
            v = x.get(f.name)
            if isinstance(v, bool):
                setattr(self, f.name, v)

    def reset_to_defaults(self):
        c = type(self)
        for f in fields(self):
            setattr(self, f.name, getattr(c, f.name))


class Central(QWidget):

    layout: Layout = Layout.wide

    def __init__(self, parent=None, prefs_name='main_window_central_widget_state'):
        self.prefs_name = prefs_name
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.wide_desires = WideDesires()
        self.narrow_desires = NarrowDesires()
        self.is_visible = Visibility()
        self.tag_browser = Placeholder('tag browser', self)
        self.book_list = Placeholder('book list', self)
        self.cover_browser = Placeholder('cover browser', self)
        self.cover_browser.setMinimumSize(MIN_SIZE)
        self.book_details = Placeholder('book details', self)
        self.quick_view = Placeholder('quick view', self)
        self.ignore_button_toggles = False
        self.tag_browser_button = LayoutButton('tag_browser', 'tags.png', _('Tag browser'), self, 'Shift+Alt+T')
        self.book_details_button = LayoutButton('book_details', 'book.png', _('Book details'), self, 'Shift+Alt+D')
        self.cover_browser_button = LayoutButton('cover_browser', 'cover_flow.png', _('Cover browser'), self, 'Shift+Alt+B')
        self.quick_view_button = LayoutButton('quick_view', 'quickview.png', _('Quickview'), self)
        self.setMinimumSize(MIN_SIZE + QSize(200, 100))

        def h(orientation: Qt.Orientation = Qt.Orientation.Vertical):
            ans = SplitterHandle(self, orientation)
            ans.dragged_to.connect(self.splitter_handle_dragged)
            ans.toggle_requested.connect(self.toggle_handle)
            return ans

        self.left_handle = h()
        self.right_handle = h()
        self.top_handle = h(Qt.Orientation.Horizontal)
        self.bottom_handle = h(Qt.Orientation.Horizontal)

    def serialized_settings(self):
        return {
            'layout': self.layout.name,
            'visibility': self.is_visible.serialize(),
            'wide_desires': self.wide_desires.serialize(),
            'narrow_desires': self.narrow_desires.serialize()
        }

    def layout_button_toggled(self):
        if not self.ignore_button_toggles:
            b = self.sender()
            self.set_visibility_of(b.name, b.isChecked())
            self.relayout()

    def unserialize_settings(self, s):
        l = s.get('layout')
        if l == 'wide':
            self.layout = Layout.wide
        elif l == 'narrow':
            self.layout = Layout.narrow
        self.is_visible.unserialize(s.get('visibility') or {})
        self.wide_desires.unserialize(s.get('wide_desires') or {})
        self.narrow_desires.unserialize(s.get('narrow_desires') or {})

    def write_settings(self):
        gprefs.set(self.prefs_name, self.serialized_settings())

    def read_settings(self):
        before = self.serialized_settings()
        self.unserialize_settings(gprefs.get(self.prefs_name) or {})
        if self.serialized_settings() != before:
            self.relayout()

    def reset_to_defaults(self):
        before = self.serialized_settings()
        self.layout = Layout.wide
        self.is_visible.reset_to_defaults()
        self.wide_desires.reset_to_defaults()
        self.narrow_desires.reset_to_defaults()
        if self.serialized_settings() != before:
            self.relayout()

    def toggle_panel(self, which):
        was_visible = getattr(self.is_visible, which)
        setattr(self.is_visible, which, was_visible ^ True)
        if not was_visible:
            if self.layout is Layout.wide:
                self.size_panel_on_initial_show_wide(which)
            else:
                self.size_panel_on_initial_show_narrow(which)
        self.update_button_states_from_visibility()
        self.relayout()

    def set_visibility_of(self, which, visible):
        setattr(self.is_visible, which, visible)
        self.update_button_states_from_visibility()

    def panel_name_for_handle(self, handle):
        return self.panel_name_for_handle_wide(handle) if self.layout is Layout.wide else self.panel_name_for_handle_narrow(handle)

    def toggle_handle(self):
        panel = self.panel_name_for_handle(self.sender())
        self.set_visibility_of(panel, getattr(self.is_visible, panel) ^ True)
        self.relayout()

    def update_button_states_from_visibility(self):
        orig = self.ignore_button_toggles
        self.ignore_button_toggles = True
        try:
            self.tag_browser_button.setChecked(self.is_visible.tag_browser)
            self.book_details_button.setChecked(self.is_visible.book_details)
            self.cover_browser_button.setChecked(self.is_visible.cover_browser)
            self.quick_view_button.setChecked(self.is_visible.quick_view)
        finally:
            self.ignore_button_toggles = orig

    def toggle_tag_browser(self):
        self.toggle_panel('tag_browser')

    def toggle_book_details(self):
        self.toggle_panel('book_details')

    def toggle_cover_browser(self):
        self.toggle_panel('cover_browser')

    def toggle_quick_view(self):
        self.toggle_panel('quick_view')

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
            if bv != self.is_visible:
                self.update_button_states_from_visibility()
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

    def do_wide_layout(self):
        s = self.style()
        normal_handle_width = int(s.pixelMetric(QStyle.PixelMetric.PM_SplitterWidth, widget=self))
        available_width = self.width()
        for h in (self.left_handle, self.right_handle):
            width = h.COLLAPSED_SIZE
            hs = h.state
            if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
                width = normal_handle_width
            h.resize(int(width), int(self.height()))
            available_width -= width
        tb = int(self.width() * self.wide_desires.tag_browser_width) if self.is_visible.tag_browser else 0
        bd = int(self.width() * self.wide_desires.book_details_width) if self.is_visible.book_details else 0
        min_central_width = self.min_central_width_wide()
        if tb + bd > available_width - min_central_width:
            width_to_share = max(0, available_width - min_central_width)
            tb = int(tb * width_to_share / (tb + bd))
            bd = max(0, width_to_share - tb)
        central_width = available_width - (tb + bd)
        if self.is_visible.tag_browser:
            self.tag_browser.setGeometry(0, 0, int(tb), int(self.height()))
        self.left_handle.move(tb, 0)
        central_x = self.left_handle.x() + self.left_handle.width()
        self.right_handle.move(tb + central_width + self.left_handle.width(), 0)
        if self.is_visible.book_details:
            self.book_details.setGeometry(int(self.right_handle.x() + self.right_handle.width()), 0, int(bd), int(self.height()))

        available_height = self.height()
        for h in (self.top_handle, self.bottom_handle):
            height = h.COLLAPSED_SIZE
            hs = h.state
            if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
                height = normal_handle_width
            if h is self.bottom_handle and hs is HandleState.only_main_visible:
                height = 0
            h.resize(int(central_width), int(height))
            available_height -= height

        cb = max(self.cover_browser.minimumHeight(), int(self.wide_desires.cover_browser_height * self.height()))
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
                qv = min(available_height - min_bl_height, int(self.wide_desires.quick_view_height * self.height()))
                if qv < HIDE_THRESHOLD:
                    qv = 0
                bl = available_height - qv
            else:
                bl = available_height
        if self.is_visible.cover_browser:
            self.cover_browser.setGeometry(int(central_x), 0, int(central_width), int(cb))
        self.top_handle.move(central_x, cb)
        if self.is_visible.book_list:
            self.book_list.setGeometry(int(central_x), int(self.top_handle.y() + self.top_handle.height()), int(central_width), int(bl))
        self.bottom_handle.move(central_x, self.book_list.y() + self.book_list.height())
        if self.is_visible.quick_view:
            self.quick_view.setGeometry(int(central_x), int(self.bottom_handle.y() + self.bottom_handle.height()), int(central_width), int(qv))

    def wide_move_splitter_handle_to(self, handle: SplitterHandle, pos: QPointF):
        if handle is self.left_handle:
            x = int(pos.x())
            self.is_visible.tag_browser = True
            if x < HIDE_THRESHOLD:
                self.is_visible.tag_browser = False
                self.wide_desires.tag_browser_width = 0
            else:
                self.wide_desires.tag_browser_width = x / self.width()
        elif handle is self.right_handle:
            x = int(pos.x())
            self.is_visible.book_details = True
            w = self.width() - x
            if w < HIDE_THRESHOLD:
                self.is_visible.book_details = False
                self.wide_desires.book_details_width = 0
            else:
                self.wide_desires.book_details_width = w / self.width()
        elif handle is self.top_handle:
            y = int(pos.y())
            self.is_visible.cover_browser = True
            if y < max(self.cover_browser.minimumHeight(), HIDE_THRESHOLD):
                self.is_visible.cover_browser = False
                self.wide_desires.cover_browser_height = 0
            else:
                self.wide_desires.cover_browser_height = max(y, self.cover_browser.minimumHeight()) / self.height()
        elif handle is self.bottom_handle:
            y = int(pos.y())
            h = self.height() - y - self.bottom_handle.height()
            if h < HIDE_THRESHOLD:
                self.is_visible.quick_view = False
                self.wide_desires.quick_view_height = 0
            else:
                available_height = max(0, self.height() - self.top_handle.height() - self.bottom_handle.height() - self.cover_browser.minimumHeight() - 50)
                self.wide_desires.quick_view_height = max(HIDE_THRESHOLD, min(h, available_height)) / self.height()

    def size_panel_on_initial_show_wide(self, which):
        if which in ('tag_browser', 'book_details'):
            which += '_width'
            current = int(getattr(self.wide_desires, which) * self.width())
            if current < SHOW_THRESHOLD:
                setattr(self.wide_desires, which, getattr(WideDesires, which))
        elif which == 'cover_browser':
            self.wide_desires.cover_browser_height = max(int(self.height() * self.wide_desires.cover_browser_height),
                                                         self.cover_browser.minimumHeight()) / self.height()
        else:
            self.wide_desires.quick_view_height = max(int(self.height() * self.wide_desires.quick_view_height), 150) / self.height()

    def panel_name_for_handle_wide(self, handle):
        return {self.left_handle: 'tag_browser', self.right_handle: 'book_details', self.top_handle: 'cover_browser', self.bottom_handle: 'quick_view'}[handle]
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
        self.bottom_handle.resize(int(self.width()), int(height))
        available_height -= height
        bd = int(self.narrow_desires.book_details_height * self.height()) if self.is_visible.book_details else 0
        central_height = max(self.min_central_height_narrow(), available_height - bd)
        bd = available_height - central_height
        self.bottom_handle.move(0, central_height)
        if self.is_visible.book_details:
            self.book_details.setGeometry(0, int(central_height + self.bottom_handle.height()), int(self.width()), int(bd))

        available_width = self.width()
        for h in (self.left_handle, self.right_handle):
            width = h.COLLAPSED_SIZE
            hs = h.state
            if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
                width = normal_handle_width
            h.resize(int(width), int(central_height))
            available_width -= width
        tb = int(self.narrow_desires.tag_browser_width * self.width()) if self.is_visible.tag_browser else 0
        cb = max(self.cover_browser.minimumWidth(), int(self.narrow_desires.cover_browser_width * self.width())) if self.is_visible.cover_browser else 0
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
            self.tag_browser.setGeometry(0, 0, int(tb), int(self.height()))
        self.left_handle.move(tb, 0)
        central_x = self.left_handle.x() + self.left_handle.width()
        self.right_handle.move(tb + central_width + self.left_handle.width(), 0)
        if self.is_visible.cover_browser:
            self.cover_browser.setGeometry(int(self.right_handle.x() + self.right_handle.width()), 0, int(cb), int(self.height()))
        self.top_handle.resize(int(central_width), int(normal_handle_width if self.is_visible.quick_view else 0))
        central_height -= self.top_handle.height()
        qv = 0
        if self.is_visible.quick_view:
            qv = int(self.narrow_desires.quick_view_height * self.height())
            qv = max(0, min(qv, central_height - 50))
        self.book_list.setGeometry(int(central_x), 0, int(central_width), int(max(0, central_height - qv)))
        self.top_handle.move(central_x, self.book_list.y() + self.book_list.height())
        if self.is_visible.quick_view:
            self.quick_view.setGeometry(int(central_x), int(self.top_handle.y() + self.top_handle.height()), int(central_width), int(qv))

    def narrow_move_splitter_handle_to(self, handle: SplitterHandle, pos: QPointF):
        if handle is self.left_handle:
            x = int(pos.x())
            available_width = self.width() - self.left_handle.width() - self.right_handle.width() - self.min_central_width_narrow()
            self.is_visible.tag_browser = True
            if x < HIDE_THRESHOLD:
                self.is_visible.tag_browser = False
                self.narrow_desires.tag_browser_width = 0
            else:
                self.narrow_desires.tag_browser_width = min(available_width, x) / self.width()
        elif handle is self.right_handle:
            x = int(pos.x())
            available_width = self.width() - self.left_handle.width() - self.right_handle.width() - self.min_central_width_narrow()
            self.is_visible.cover_browser = True
            w = min(available_width, self.width() - x - self.right_handle.width())
            if w < HIDE_THRESHOLD:
                self.is_visible.cover_browser = False
                self.narrow_desires.book_details_width = 0
            else:
                self.narrow_desires.cover_browser_width = max(self.cover_browser.minimumWidth(), w) / self.width()
        elif handle is self.bottom_handle:
            y = int(pos.y())
            h = self.height() - y - self.bottom_handle.height()
            if h < HIDE_THRESHOLD:
                self.is_visible.book_details = False
                self.narrow_desires.book_details_height = 0
            else:
                self.is_visible.book_details = True
                available_height = max(0, self.height() - self.bottom_handle.height() - self.min_central_height_narrow())
                self.narrow_desires.book_details_height = max(HIDE_THRESHOLD, min(h, available_height)) / self.height()
        elif handle is self.top_handle:
            y = int(pos.y())
            available_height = self.bottom_handle.y() if self.is_visible.book_details else self.height()
            available_height -= self.top_handle.height()
            h = available_height - y
            if h < HIDE_THRESHOLD or available_height < 5:
                self.is_visible.quick_view = False
                self.narrow_desires.quick_view_height = 0
            else:
                self.is_visible.quick_view = True
                self.narrow_desires.quick_view_height = max(0, available_height - y) / self.height()

    def size_panel_on_initial_show_narrow(self, which):
        if which in ('tag_browser', 'cover_browser'):
            which += '_width'
            current = getattr(self.narrow_desires, which) * self.width()
            if current < SHOW_THRESHOLD:
                setattr(self.narrow_desires, which, getattr(NarrowDesires, which))
        elif which == 'book_details':
            current = self.height() * self.narrow_desires.book_details_height
            if current < SHOW_THRESHOLD:
                self.narrow_desires.book_details_height = NarrowDesires.book_details_height
        else:
            current = self.height() * self.narrow_desires.quick_view_height
            if current < SHOW_THRESHOLD:
                self.narrow_desires.quick_view_height = NarrowDesires.quick_view_height

    def panel_name_for_handle_narrow(self, handle):
        return {self.left_handle: 'tag_browser', self.right_handle: 'cover_browser', self.top_handle: 'quick_view', self.bottom_handle: 'book_details'}[handle]
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
            h = QHBoxLayout()
            l.addLayout(h)
            self.central = Central(self, prefs_name='develop_central_layout_widget_state')
            h.addWidget(self.central.tag_browser_button)
            h.addWidget(self.central.book_details_button)
            h.addWidget(self.central.cover_browser_button)
            h.addWidget(self.central.quick_view_button)
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
            elif ev.key() == Qt.Key.Key_R:
                self.central.reset_to_defaults()
            elif ev.key() == Qt.Key.Key_Escape:
                self.reject()

    d = d()
    d.central.read_settings()
    d.show()
    app.exec()
    d.central.write_settings()


if __name__ == '__main__':
    develop()
# }}}
