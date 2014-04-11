#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import time, ctypes, sys
from functools import partial
from PyQt5.Qt import (
    QObject, QPointF, pyqtSignal, QEvent, QApplication, QMouseEvent, Qt,
    QContextMenuEvent, QDialog, QDialogButtonBox, QLabel, QVBoxLayout)

from calibre.constants import iswindows

touch_supported = False
if iswindows and sys.getwindowsversion()[:2] >= (6, 2):  # At least windows 7
    from ctypes import wintypes
    try:
        RegisterTouchWindow = ctypes.windll.user32.RegisterTouchWindow
        RegisterTouchWindow.argtypes = (wintypes.HWND, wintypes.ULONG)
        RegisterTouchWindow.restype = wintypes.BOOL
        touch_supported = True
    except Exception:
        pass

SWIPE_HOLD_INTERVAL = 0.5  # seconds
HOLD_THRESHOLD = 1.0  # seconds
TAP_THRESHOLD  = 50   # manhattan pixels
SWIPE_DISTANCE = 100  # manhattan pixels
PINCH_CENTER_THRESHOLD = 150  # manhattan pixels
PINCH_SQUEEZE_FACTOR = 2.5  # smaller length must be less that larger length / squeeze factor

Tap, TapAndHold, Pinch, Swipe, SwipeAndHold = 'Tap', 'TapAndHold', 'Pinch', 'Swipe', 'SwipeAndHold'
Left, Right, Up, Down = 'Left', 'Right', 'Up', 'Down'
In, Out = 'In', 'Out'

class Help(QDialog):  # {{{

    def __init__(self, parent=None):
        QDialog.__init__(self, parent=parent)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.la = la = QLabel(
        '''
            <style>
            h2 { text-align: center }
            dt { font-weight: bold }
            dd { margin-bottom: 1.5em }
            </style>

        ''' + _(
            '''
            <h2>The list of available gestures</h2>
            <dl>
            <dt>Single tap</dt>
            <dd>A single tap on the right two thirds of the page will turn to the next page
            and on the left one-third of the page will turn to the previous page. Single tapping
            on a link will activate the link.</dd>

            <dt>Swipe</dt>
            <dd>Swipe to the left to go to the next page and to the right to go to the previous page.
            This mimics turning pages in a paper book. When the viewer is not in paged mode, swiping
            scrolls the text line by line instead of page by page.</dd>

            <dt>Pinch</dt>
            <dd>Pinch in or out to decrease or increase the font size</dd>

            <dt>Swipe and hold</dt>
            <dd>If you swipe and the hold your finger down instead of lifting it, pages will be turned
            rapidly allowing for quickly scanning through large numbers of pages.</dd>

            <dt>Tap and hold</dt>
            <dd>Bring up the context (right-click) menu</dd>
            </dl>
            '''
        ))
        la.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        la.setWordWrap(True)
        l.addWidget(la, Qt.AlignTop|Qt.AlignLeft)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)
        self.resize(600, 500)
# }}}

class TouchPoint(object):

    def __init__(self, tp):
        self.creation_time = self.last_update_time = self.time_of_last_move = time.time()
        self.start_screen_position = self.current_screen_position = self.previous_screen_position = QPointF(tp.screenPos())
        self.time_since_last_update = -1
        self.total_movement = 0

    def update(self, tp):
        now = time.time()
        self.time_since_last_update = now - self.last_update_time
        self.last_update_time = now
        self.previous_screen_position, self.current_screen_position = self.current_screen_position, QPointF(tp.screenPos())
        movement = (self.current_screen_position - self.previous_screen_position).manhattanLength()
        self.total_movement += movement
        if movement > 5:
            self.time_of_last_move = now

    @property
    def swipe_type(self):
        x_movement = self.current_screen_position.x() - self.start_screen_position.x()
        y_movement = self.current_screen_position.y() - self.start_screen_position.y()
        xabs, yabs = map(abs, (x_movement, y_movement))
        if max(xabs, yabs) < SWIPE_DISTANCE or min(xabs/max(yabs, 0.01), yabs/max(xabs, 0.01)) > 0.3:
            return
        d = x_movement if xabs > yabs else y_movement
        axis = (Left, Right) if xabs > yabs else (Up, Down)
        return axis[0 if d < 0 else 1]

    @property
    def swipe_live(self):
        x_movement = self.current_screen_position.x() - self.previous_screen_position.x()
        y_movement = self.current_screen_position.y() - self.previous_screen_position.y()
        return (x_movement, y_movement)

def get_pinch(p1, p2):
    starts = [p1.start_screen_position, p2.start_screen_position]
    ends = [p1.current_screen_position, p2.current_screen_position]
    start_center = (starts[0] + starts[1]) / 2.0
    end_center = (ends[0] + ends[1]) / 2.0
    if (start_center - end_center).manhattanLength() > PINCH_CENTER_THRESHOLD:
        return None
    start_length = (starts[0] - starts[1]).manhattanLength()
    end_length = (ends[0] - ends[1]).manhattanLength()
    if min(start_length, end_length) > max(start_length, end_length) / PINCH_SQUEEZE_FACTOR:
        return None
    return In if start_length > end_length else Out

class State(QObject):

    tapped = pyqtSignal(object)
    swiped = pyqtSignal(object)
    swiping = pyqtSignal(object, object)
    pinched = pyqtSignal(object)
    tap_hold_started = pyqtSignal(object)
    tap_hold_updated = pyqtSignal(object)
    swipe_hold_started = pyqtSignal(object)
    swipe_hold_updated = pyqtSignal(object)
    tap_hold_finished = pyqtSignal(object)
    swipe_hold_finished = pyqtSignal(object)

    def __init__(self):
        QObject.__init__(self)
        self.clear()

    def clear(self):
        self.possible_gestures = set()
        self.touch_points = {}
        self.hold_started = False
        self.hold_data = None

    def start(self):
        self.clear()
        self.possible_gestures = {Tap, TapAndHold, Swipe, Pinch, SwipeAndHold}

    def update(self, ev, boundary='update'):
        if boundary == 'start':
            self.start()

        for tp in ev.touchPoints():
            tpid = tp.id()
            if tpid not in self.touch_points:
                self.touch_points[tpid] = TouchPoint(tp)
            else:
                self.touch_points[tpid].update(tp)

        if len(self.touch_points) > 2:
            self.possible_gestures.clear()
        elif len(self.touch_points) > 1:
            self.possible_gestures &= {Pinch}

        if boundary == 'end':
            self.finalize()
            self.clear()
        else:
            self.check_for_holds()
            if {Swipe, SwipeAndHold} & self.possible_gestures:
                tp = next(self.touch_points.itervalues())
                self.swiping.emit(*tp.swipe_live)

    def check_for_holds(self):
        if not {SwipeAndHold, TapAndHold} & self.possible_gestures:
            return
        now = time.time()
        tp = next(self.touch_points.itervalues())
        if now - tp.time_of_last_move < HOLD_THRESHOLD:
            return
        if self.hold_started:
            if TapAndHold in self.possible_gestures:
                self.tap_hold_updated.emit(tp)
            if SwipeAndHold in self.possible_gestures:
                self.swipe_hold_updated.emit(self.hold_data[1])
        else:
            self.possible_gestures &= {TapAndHold, SwipeAndHold}
            if tp.total_movement > TAP_THRESHOLD:
                st = tp.swipe_type
                if st is None:
                    self.possible_gestures.clear()
                else:
                    self.hold_started = True
                    self.possible_gestures = {SwipeAndHold}
                    self.hold_data = (now, st)
                    self.swipe_hold_started.emit(st)
            else:
                self.possible_gestures = {TapAndHold}
                self.hold_started = True
                self.hold_data = now
                self.tap_hold_started.emit(tp)

    def finalize(self):
        if Tap in self.possible_gestures:
            tp = next(self.touch_points.itervalues())
            if tp.total_movement <= TAP_THRESHOLD:
                self.tapped.emit(tp)
                return

        if Swipe in self.possible_gestures:
            tp = next(self.touch_points.itervalues())
            st = tp.swipe_type
            if st is not None:
                self.swiped.emit(st)
                return

        if Pinch in self.possible_gestures:
            points = tuple(self.touch_points.itervalues())
            if len(points) == 2:
                pinch_dir = get_pinch(*points)
                if pinch_dir is not None:
                    self.pinched.emit(pinch_dir)

        if not self.hold_started:
            return

        if TapAndHold in self.possible_gestures:
            tp = next(self.touch_points.itervalues())
            self.tap_hold_finished.emit(tp)
            return

        if SwipeAndHold in self.possible_gestures:
            self.swipe_hold_finished.emit(self.hold_data[1])
            return


class GestureHandler(QObject):

    def __init__(self, view):
        QObject.__init__(self, view)
        self.state = State()
        self.last_swipe_hold_update = None
        self.state.swiped.connect(self.handle_swipe)
        self.state.tapped.connect(self.handle_tap)
        self.state.swiping.connect(self.handle_swiping)
        self.state.tap_hold_started.connect(partial(self.handle_tap_hold, 'start'))
        self.state.tap_hold_updated.connect(partial(self.handle_tap_hold, 'update'))
        self.state.tap_hold_finished.connect(partial(self.handle_tap_hold, 'end'))
        self.state.swipe_hold_started.connect(partial(self.handle_swipe_hold, 'start'))
        self.state.swipe_hold_updated.connect(partial(self.handle_swipe_hold, 'update'))
        self.state.swipe_hold_finished.connect(partial(self.handle_swipe_hold, 'end'))
        self.state.pinched.connect(self.handle_pinch)
        self.evmap = {QEvent.TouchBegin: 'start', QEvent.TouchUpdate: 'update', QEvent.TouchEnd: 'end'}

        # Ignore fake mouse events generated by the window system from touch
        # events. At least on windows, we know how to identify these fake
        # events. See http://msdn.microsoft.com/en-us/library/windows/desktop/ms703320(v=vs.85).aspx
        self.is_fake_mouse_event = lambda : False
        if touch_supported and iswindows:
            MI_WP_SIGNATURE = 0xFF515700
            SIGNATURE_MASK = 0xFFFFFF00
            try:
                f = ctypes.windll.user32.GetMessageExtraInfo
                f.restype = wintypes.LPARAM
                def is_fake_mouse_event():
                    val = f()
                    ans = (val & SIGNATURE_MASK) == MI_WP_SIGNATURE
                    return ans
                self.is_fake_mouse_event = is_fake_mouse_event
                QApplication.instance().focusChanged.connect(self.register_for_wm_touch)
            except Exception:
                import traceback
                traceback.print_exc()

    def register_for_wm_touch(self, *args):
        if touch_supported and iswindows:
            # For some reason performing certain actions like toggling the ToC
            # view causes windows to stop sending WM_TOUCH events. This works
            # around that bug.
            # This might need to be changed for Qt 5 and effectivewinid returns
            # a different kind of object.
            hwnd = int(self.parent().effectiveWinId())
            RegisterTouchWindow(hwnd, 0)

    def __call__(self, ev):
        if not touch_supported:
            return False
        etype = ev.type()
        if etype in (
                QEvent.MouseMove, QEvent.MouseButtonPress,
                QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick,
                QEvent.ContextMenu) and self.is_fake_mouse_event():
            # swallow fake mouse events that the windowing system generates from touch events
            ev.accept()
            return True
        boundary = self.evmap.get(etype, None)
        if boundary is None:
            return False
        self.state.update(ev, boundary=boundary)
        ev.accept()
        return True

    def close_open_menu(self):
        m = getattr(self.parent(), 'context_menu', None)
        if m is not None and m.isVisible():
            m.close()
            return True

    def handle_swipe(self, direction):
        if self.close_open_menu():
            return
        view = self.parent()
        if not view.document.in_paged_mode:
            return
        func = {Left:'next_page', Right: 'previous_page', Up:'goto_previous_section', Down:'goto_next_section'}[direction]
        getattr(view, func)()

    def handle_swiping(self, x, y):
        if max(abs(x), abs(y)) < 1:
            return
        view = self.parent()
        if view.document.in_paged_mode:
            return
        ydirection = Up if y < 0 else Down
        if view.manager is not None and abs(y) > 0:
            if ydirection is Up and view.document.at_bottom:
                view.manager.next_document()
                return
            elif ydirection is Down and view.document.at_top:
                view.manager.previous_document()
                return
        view.scroll_by(x=-x, y=-y)
        if view.manager is not None:
            view.manager.scrolled(view.scroll_fraction)

    def current_position(self, tp):
        return self.parent().mapFromGlobal(tp.current_screen_position.toPoint())

    def handle_tap(self, tp):
        if self.close_open_menu():
            return
        view = self.parent()
        mf = view.document.mainFrame()
        r = mf.hitTestContent(self.current_position(tp))
        if r.linkElement().isNull():
            threshold = view.width() / 3.0
            attr = 'previous' if self.current_position(tp).x() <= threshold else 'next'
            getattr(view, '%s_page'%attr)()
        else:
            for etype in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
                ev = QMouseEvent(etype, self.current_position(tp), tp.current_screen_position.toPoint(), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
                QApplication.sendEvent(view, ev)

    def handle_tap_hold(self, action, tp):
        etype = {'start':QEvent.MouseButtonPress, 'update':QEvent.MouseMove, 'end':QEvent.MouseButtonRelease}[action]
        ev = QMouseEvent(etype, self.current_position(tp), tp.current_screen_position.toPoint(), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(self.parent(), ev)
        if action == 'end':
            ev = QContextMenuEvent(QContextMenuEvent.Other, self.current_position(tp), tp.current_screen_position.toPoint())
            # We have to use post event otherwise the popup remains an alien widget and does not receive events
            QApplication.postEvent(self.parent(), ev)

    def handle_swipe_hold(self, action, direction):
        view = self.parent()
        if not view.document.in_paged_mode:
            return
        if action == 'start':
            self.last_swipe_hold_update = time.time()
            try:
                self.handle_swipe(direction)
            finally:
                view.is_auto_repeat_event = False
        elif action == 'update' and self.last_swipe_hold_update is not None and time.time() - self.last_swipe_hold_update > SWIPE_HOLD_INTERVAL:
            view.is_auto_repeat_event = True
            self.last_swipe_hold_update = time.time()
            try:
                self.handle_swipe(direction)
            finally:
                view.is_auto_repeat_event = False
        elif action == 'end':
            self.last_swipe_hold_update = None

    def handle_pinch(self, direction):
        attr = 'magnify' if direction is Out else 'shrink'
        getattr(self.parent(), '%s_fonts' % attr)()

    def show_help(self):
        Help(self.parent()).exec_()

if __name__ == '__main__':
    app = QApplication([])
    Help().exec_()
