#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from contextlib import suppress
from copy import copy
from dataclasses import asdict, dataclass, fields
from enum import Enum, auto
from qt.core import (
    QAction, QDialog, QHBoxLayout, QIcon, QKeySequence, QLabel, QMainWindow, QPalette,
    QPointF, QSize, QSizePolicy, QStyle, QStyleOption, QStylePainter, Qt, QToolButton,
    QVBoxLayout, QWidget, pyqtSignal,
)

from calibre.gui2 import Application, config, gprefs
from calibre.gui2.cover_flow import MIN_SIZE

HIDE_THRESHOLD = 10
SHOW_THRESHOLD = 50


def migrate_settings(width=-1, height=-1):
    if width < 100:
        width = 1200
    if height < 100:
        height = 600
    wd, nd = WideDesires(), NarrowDesires()
    ans = {
        'layout': config['gui_layout'],
        'wide_visibility': Visibility().serialize(),
        'narrow_visibility': Visibility().serialize(),
        'wide_desires': wd.serialize(),
        'narrow_desires': nd.serialize(),
    }
    sizes = {
        'wide': {
            'tag_browser': int(width * wd.tag_browser_width),
            'book_details': int(width * wd.book_details_width),
            'cover_browser': int(height * wd.cover_browser_height),
            'quick_view': int(height * wd.quick_view_height),
        },
        'narrow': {
            'tag_browser': int(width * nd.tag_browser_width),
            'book_details': int(height * nd.book_details_height),
            'cover_browser': int(width * nd.cover_browser_width),
            'quick_view': int(height * nd.quick_view_height),
        }
    }
    for which, hor_is_wide in {
        'tag_browser': True,
        'book_details': True,
        'cover_browser': False,
    }.items():
        key = 'wide' if hor_is_wide else 'narrow'
        val = gprefs.get(f'{which}_splitter_horizontal_state')
        if val:
            with suppress(Exception):
                ans[f'{key}_visibility'][which] = bool(val[0])
                sizes[key][which] = val[1]
        key = 'narrow' if hor_is_wide else 'wide'
        val = gprefs.get(f'{which}_splitter_vertical_state')
        if val:
            with suppress(Exception):
                ans[f'{key}_visibility'][which] = bool(val[0])
                sizes[key][which] = val[1]
    if gprefs.get('quickview visible'):
        ans['wide_visibility']['quick_view'] = ans['narrow_visibility']['quick_view'] = True
    qdh = gprefs.get('quickview_dialog_heights') or (int(2*height/3), int(height/3))

    # Migrate wide sizes
    s, a = sizes['wide'], ans['wide_desires']
    a['tag_browser_width'] = min(0.45, s['tag_browser'] / width)
    a['book_details_width'] = min(0.45, s['book_details'] / width)
    theight = s['cover_browser'] + qdh[0] + qdh[1]
    if theight == s['cover_browser']:
        theight *= 3
    a['cover_browser_height'] = s['cover_browser'] / theight
    a['quick_view_height'] = qdh[1] / theight

    # Migrate narrow sizes
    s, a = sizes['narrow'], ans['narrow_desires']
    a['tag_browser_width'] = min(0.45, s['tag_browser'] / width)
    a['cover_browser_width'] = min(0.45, s['cover_browser'] / width)
    theight = s['book_details'] + qdh[0] + qdh[1]
    if theight == s['book_details']:
        theight *= 3
    a['book_details_height'] = s['book_details'] / theight
    a['quick_view_height'] = qdh[1] / theight
    return ans


class Placeholder(QLabel):
    backgrounds = 'yellow', 'lightgreen', 'grey', 'cyan', 'magenta'
    bgcount = 0

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        bg = self.backgrounds[Placeholder.bgcount]
        Placeholder.bgcount = (Placeholder.bgcount + 1) % len(self.backgrounds)
        self.setStyleSheet(f'QLabel {{ background: {bg};\nborder: 1px solid red; }}')


class LayoutButton(QToolButton):

    on_action_trigger = pyqtSignal(bool)

    def __init__(self, name: str, icon: str, label: str, central: 'CentralContainer', shortcut=None):
        super().__init__(central)
        self.central = central
        self.label = label
        self.name = name
        self.shortcut = shortcut
        self.setIcon(QIcon.ic(icon))
        self.setCheckable(True)
        self.setChecked(self.is_visible)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if isinstance(central, CentralContainer):
            self.toggled.connect(central.layout_button_toggled)

    def initialize_with_gui(self, gui):
        if self.shortcut is not None:
            self.action_toggle = QAction(self.icon(), _('Toggle') + ' ' + self.label, self)
            self.action_toggle.changed.connect(self.update_shortcut)
            self.action_toggle.triggered.connect(self.toggle)
            gui.addAction(self.action_toggle)
            gui.keyboard.register_shortcut(
                f'toggle_central_panel_{self.name}', self.action_toggle.text(), group=_('Main window layout'),
                default_keys=(self.shortcut,), action=self.action_toggle)

    @property
    def is_visible(self):
        return getattr(self.central.is_visible, self.name)

    def update_shortcut(self, action_toggle=None):
        if not isinstance(action_toggle, QAction):
            action_toggle = getattr(self, 'action_toggle', None)
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
        self.set_orientation(orientation)

    def set_orientation(self, orientation):
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


class CentralContainer(QWidget):

    layout: Layout = Layout.wide

    def __init__(self, parent=None, prefs_name='main_window_central_widget_state', separate_cover_browser=None, for_develop=False):
        self.separate_cover_browser = config['separate_cover_flow'] if separate_cover_browser is None else separate_cover_browser
        self.prefs_name = prefs_name
        self.wide_desires = WideDesires()
        self.narrow_desires = NarrowDesires()
        self.wide_is_visible = Visibility()
        self.narrow_is_visible = Visibility()
        self._last_cb_position = self.gui = None
        super().__init__(parent)
        self.action_toggle_layout = QAction(self)
        self.action_toggle_layout.triggered.connect(self.toggle_layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if for_develop:
            self.tag_browser = Placeholder('tag browser', self)
            self.book_list = Placeholder('book list', self)
            self.cover_browser = Placeholder('cover browser', self)
            self.book_details = Placeholder('book details', self)
            self.quick_view = Placeholder('quick view', self)
        else:
            self.tag_browser = QWidget(self)
            self.book_list = QWidget(self)
            self.cover_browser = QWidget(self)
            self.book_details = QWidget(self)
            self.quick_view = QWidget(self)
        self.cover_browser.setMinimumSize(MIN_SIZE)
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

    @property
    def narrow_cb_on_top(self):
        p = self._last_cb_position = gprefs['cover_browser_narrow_view_position']
        if p == 'automatic':
            gui = self.gui or self
            ratio = gui.width() / gui.height()
            return ratio <= 1.4
        return p == 'on_top'

    @property
    def cb_on_top_changed(self):
        return (self._last_cb_position is None or
                gprefs['cover_browser_narrow_view_position'] != self._last_cb_position)

    @property
    def is_visible(self):
        return self.wide_is_visible if self.layout is Layout.wide else self.narrow_is_visible

    def set_widget(self, which, w):
        existing = getattr(self, which)
        existing.setVisible(False)
        existing.setParent(None)
        setattr(self, which, w)
        w.setParent(self)

    def initialize_with_gui(self, gui, book_list_widget):
        self.gui = gui
        self.tag_browser_button.initialize_with_gui(gui)
        self.book_details_button.initialize_with_gui(gui)
        self.cover_browser_button.initialize_with_gui(gui)
        self.quick_view_button.initialize_with_gui(gui)
        self.set_widget('book_details', gui.book_details)
        self.set_widget('tag_browser', gui.tb_widget)
        self.set_widget('book_list', book_list_widget)
        gui.keyboard.register_shortcut(
            'toggle_layout_type', _('Toggle layout between wide and narrow'), group=_('Main window layout'),
            default_keys=('Alt+Shift+L',), action=self.action_toggle_layout)
        gui.addAction(self.action_toggle_layout)
        # cover browser is set in CoverFlowMixin
        # Quickview is set in quickview.py code

    @property
    def is_wide(self):
        return self.layout is Layout.wide

    def change_layout(self, gui, is_wide):
        layout = Layout.wide if is_wide else Layout.narrow
        if layout is self.layout and not self.cb_on_top_changed:
            return False
        ss = self.serialized_settings()
        before = ss[self.layout.name + '_visibility']
        after = ss[layout.name + '_visibility']
        gui.book_details.change_layout(is_wide)
        self.layout = layout
        self.write_settings()
        # apply visibility changes by clicking buttons to ensure button
        # state is correct and also deals with the case of the QV widget not
        # being initialised
        changes = set()
        if before != after:
            for k in before:
                if before[k] != after[k]:
                    changes.add(k)
                    setattr(self.is_visible, k, before[k])
        if changes:
            for k in changes:
                button = getattr(self, k + '_button')
                button.click()
        else:
            self.relayout()
        return True

    def serialized_settings(self):
        return {
            'layout': self.layout.name,
            'wide_visibility': self.wide_is_visible.serialize(),
            'narrow_visibility': self.narrow_is_visible.serialize(),
            'wide_desires': self.wide_desires.serialize(),
            'narrow_desires': self.narrow_desires.serialize()
        }

    def layout_button_toggled(self):
        if not self.ignore_button_toggles:
            b = self.sender()
            if b.name == 'quick_view':
                return
            self.set_visibility_of(b.name, b.isChecked())
            self.relayout()

    def unserialize_settings(self, s):
        l = s.get('layout')
        self.layout = Layout.narrow if l == 'narrow' else Layout.wide
        self.wide_is_visible.unserialize(s.get('wide_visibility') or {})
        self.narrow_is_visible.unserialize(s.get('narrow_visibility') or {})
        self.wide_desires.unserialize(s.get('wide_desires') or {})
        self.narrow_desires.unserialize(s.get('narrow_desires') or {})

    def write_settings(self):
        gprefs.set(self.prefs_name, self.serialized_settings())

    def read_settings(self):
        before = self.serialized_settings()
        # sadly self.size() doesnt always return sensible values so look at
        # the size of the main window which works perfectly for width, not so
        # perfectly for height
        sz = self.size()
        p = self.parent()
        while p is not None and not isinstance(p, QMainWindow):
            p = p.parent()
        if p is not None:
            psz = p.size()
            sz = QSize(max(sz.width(), psz.width()), max(sz.height(), psz.height() - 50))
        settings = gprefs.get(self.prefs_name) or migrate_settings(sz.width(), sz.height())
        self.unserialize_settings(settings)
        if self.serialized_settings() != before:
            self.update_button_states_from_visibility()
            self.relayout()
            return True
        return False

    def reset_to_defaults(self):
        before = self.serialized_settings()
        self.layout = Layout.wide
        self.is_visible.reset_to_defaults()
        self.wide_desires.reset_to_defaults()
        self.narrow_desires.reset_to_defaults()
        if self.serialized_settings() != before:
            self.update_button_states_from_visibility()
            self.relayout()

    def toggle_panel(self, which):
        was_visible = getattr(self.is_visible, which)
        self.set_visibility_of(which, was_visible ^ True)
        self.relayout()

    def set_visibility_of(self, which, visible):
        was_visible = getattr(self.is_visible, which)
        setattr(self.is_visible, which, visible)
        if not was_visible:
            if self.layout is Layout.wide:
                self.size_panel_on_initial_show_wide(which)
            else:
                self.size_panel_on_initial_show_narrow(which)
        self.update_button_states_from_visibility()

    def show_panel(self, which):
        if not getattr(self.is_visible, which):
            self.set_visibility_of(which, True)
            self.relayout()

    def hide_panel(self, which):
        if getattr(self.is_visible, which):
            self.set_visibility_of(which, False)
            self.relayout()

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
        self.cover_browser.setVisible(self.is_visible.cover_browser and not self.separate_cover_browser)
        self.book_list.setVisible(self.is_visible.book_list)
        self.quick_view.setVisible(self.is_visible.quick_view)
        if self.layout is Layout.wide:
            self.right_handle.set_orientation(Qt.Orientation.Vertical)
            self.do_wide_layout()
        else:
            self.right_handle.set_orientation(Qt.Orientation.Horizontal if self.narrow_cb_on_top else Qt.Orientation.Vertical)
            self.do_narrow_layout()
        self.update()

    def toggle_layout(self):
        if self.gui:
            self.change_layout(self.gui, self.layout is Layout.narrow)
        else:
            self.layout = Layout.narrow if self.layout is Layout.wide else Layout.wide
            self.relayout()

    def button_for(self, which):
        return getattr(self, which + '_button')

    def sizeHint(self):
        return QSize(800, 600)

    # Wide {{{
    def wide_handle_state(self, handle):
        if handle is self.left_handle:
            return HandleState.both_visible if self.is_visible.tag_browser else HandleState.only_main_visible
        if handle is self.right_handle:
            return HandleState.both_visible if self.is_visible.book_details else HandleState.only_main_visible
        if handle is self.top_handle:
            if self.is_visible.cover_browser and not self.separate_cover_browser:
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
            if hs is HandleState.only_main_visible and h is self.bottom_handle or (h is self.top_handle and self.separate_cover_browser):
                height = 0
            h.resize(int(central_width), int(height))
            available_height -= height

        cb = max(self.cover_browser.minimumHeight(), int(self.wide_desires.cover_browser_height * self.height()))
        if not self.is_visible.cover_browser or self.separate_cover_browser:
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
        if self.is_visible.cover_browser and not self.separate_cover_browser:
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
            if self.is_visible.cover_browser and not self.separate_cover_browser:
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

    def do_narrow_layout_with_cb_on_top(self):
        s = self.style()
        normal_handle_width = int(s.pixelMetric(QStyle.PixelMetric.PM_SplitterWidth, widget=self))
        available_height = self.height()
        for handle in (self.bottom_handle, self.right_handle):
            hs = handle.state
            height = self.bottom_handle.COLLAPSED_SIZE
            if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
                height = normal_handle_width
            handle.resize(self.width(), height)
            available_height -= height
        bd = int(self.narrow_desires.book_details_height * self.height()) if self.is_visible.book_details else 0
        bd = max(0, min(bd, max(0, available_height - self.min_central_height_narrow() - 40)))
        central_height = available_height - bd + self.right_handle.height()
        self.bottom_handle.move(0, central_height - self.bottom_handle.height())
        if self.is_visible.book_details:
            self.book_details.setGeometry(0, self.bottom_handle.y() + self.bottom_handle.height(), self.width(), bd)
        available_width = self.width()
        hs = self.left_handle.state
        width = self.left_handle.COLLAPSED_SIZE
        if hs is HandleState.both_visible or hs is HandleState.only_side_visible:
            width = normal_handle_width
        self.left_handle.resize(width, central_height)
        available_width -= width
        tb = int(self.narrow_desires.tag_browser_width * self.width()) if self.is_visible.tag_browser else 0
        self.left_handle.move(tb, 0)
        if self.is_visible.tag_browser:
            self.tag_browser.setGeometry(0, 0, tb, central_height)
        central_x = self.left_handle.x() + self.left_handle.width()
        central_width = self.width() - central_x
        central_height -= self.right_handle.height()
        cb = min(max(0, central_height - 80), int(self.height() * self.narrow_desires.cover_browser_width)) if self.is_visible.cover_browser else 0
        if cb and cb < self.cover_browser.minimumHeight():
            cb = min(self.cover_browser.minimumHeight(), central_height)
        if self.is_visible.cover_browser:
            self.cover_browser.setGeometry(central_x, 0, central_width, cb)
        self.right_handle.resize(central_width, self.right_handle.height())
        self.right_handle.move(central_x, cb)
        central_top = self.right_handle.y() + self.right_handle.height()
        central_height = self.bottom_handle.y() - central_top
        self.top_handle.resize(central_width, normal_handle_width if self.is_visible.quick_view else 0)
        available_height = central_height - self.top_handle.height()
        qv = int(self.height() * self.narrow_desires.quick_view_height) if self.is_visible.quick_view else 0
        qv = min(qv, max(0, available_height - 80))
        bl = max(0, available_height - qv)
        self.book_list.setGeometry(central_x, central_top, central_width, bl)
        self.top_handle.move(central_x, self.book_list.y() + self.book_list.height())
        if self.is_visible.quick_view:
            self.quick_view.setGeometry(central_x, self.top_handle.y() + self.top_handle.height(), central_width, qv)

    def do_narrow_layout(self):
        if self.narrow_cb_on_top:
            return self.do_narrow_layout_with_cb_on_top()
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
            if h is self.right_handle and self.separate_cover_browser:
                width = 0
            h.resize(int(width), int(central_height))
            available_width -= width
        tb = int(self.narrow_desires.tag_browser_width * self.width()) if self.is_visible.tag_browser else 0
        cb = max(self.cover_browser.minimumWidth(),
                 int(self.narrow_desires.cover_browser_width * self.width())) if self.is_visible.cover_browser and not self.separate_cover_browser else 0
        min_central_width = self.min_central_width_narrow()
        if tb + cb > max(0, available_width - min_central_width):
            width_to_share = max(0, available_width - min_central_width)
            cb = int(cb * width_to_share / (tb + cb))
            cb = max(self.cover_browser.minimumWidth(), cb)
            if cb > width_to_share:
                cb = 0
            tb = max(0, width_to_share - cb)
        central_width = available_width - (tb + cb)
        if self.is_visible.tag_browser:
            self.tag_browser.setGeometry(0, 0, int(tb), int(central_height))
        self.left_handle.move(tb, 0)
        central_x = self.left_handle.x() + self.left_handle.width()
        self.right_handle.move(tb + central_width + self.left_handle.width(), 0)
        if self.is_visible.cover_browser and not self.separate_cover_browser:
            self.cover_browser.setGeometry(int(self.right_handle.x() + self.right_handle.width()), 0, int(cb), int(central_height))
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
            if self.narrow_cb_on_top:
                available_width += self.right_handle.width()
            self.is_visible.tag_browser = True
            if x < HIDE_THRESHOLD:
                self.is_visible.tag_browser = False
                self.narrow_desires.tag_browser_width = 0
            else:
                self.narrow_desires.tag_browser_width = min(available_width, x) / self.width()
        elif handle is self.right_handle:
            if self.narrow_cb_on_top:
                y = int(pos.y())
                self.is_visible.cover_browser = True
                if y < max(self.cover_browser.minimumHeight(), HIDE_THRESHOLD):
                    self.is_visible.cover_browser = False
                    self.narrow_desires.cover_browser_width = 0
                else:
                    self.narrow_desires.cover_browser_width = max(y, self.cover_browser.minimumHeight()) / self.height()
            else:
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
        if which == 'tag_browser':
            current = self.narrow_desires.tag_browser_width * self.width()
            if current < SHOW_THRESHOLD:
                self.narrow_desires.tag_browser_width = NarrowDesires.tag_browser_width
        elif which == 'cover_browser':
            d = self.height() if self.narrow_cb_on_top else self.width()
            current = self.narrow_desires.cover_browser_width * d
            if current < SHOW_THRESHOLD:
                self.narrow_desires.cover_browser_width = NarrowDesires.cover_browser_width
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
            self.central = CentralContainer(self, for_develop=True, prefs_name='develop_central_layout_widget_state', separate_cover_browser=False)
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
