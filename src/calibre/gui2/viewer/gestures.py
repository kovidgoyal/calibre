#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import time, ctypes, sys
from functools import partial
from PyQt4.Qt import (
    QObject, QPointF, pyqtSignal, QEvent, QApplication, QMouseEvent, Qt,
    QContextMenuEvent)

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

HOLD_THRESHOLD = 1.0  # seconds
SWIPE_DISTANCE = 50  # manhattan pixels

Tap, TapAndHold, Pinch, Swipe, SwipeAndHold = 'Tap', 'TapAndHold', 'Pinch', 'Swipe', 'SwipeAndHold'
Left, Right, Up, Down = 'Left', 'Right', 'Up', 'Down'

class TouchPoint(object):

    def __init__(self, tp):
        self.creation_time = self.last_update_time = self.time_of_last_move = time.time()
        self.start_position = self.current_position = self.previous_position = QPointF(tp.pos())
        self.start_screen_position = self.current_screen_position = self.previous_screen_position = QPointF(tp.screenPos())
        self.time_since_last_update = -1
        self.total_movement = 0

    def update(self, tp):
        now = time.time()
        self.time_since_last_update = now - self.last_update_time
        self.last_update_time = now
        self.previous_position, self.previous_screen_position = self.current_position, self.current_screen_position
        self.current_position = QPointF(tp.pos())
        self.current_screen_position = QPointF(tp.screenPos())
        movement = (self.current_position - self.previous_position).manhattanLength()
        self.total_movement += movement
        if movement > 5:
            self.time_of_last_move = now

    @property
    def swipe_type(self):
        x_movement = self.current_position.x() - self.start_position.x()
        y_movement = self.current_position.y() - self.start_position.y()
        xabs, yabs = map(abs, (x_movement, y_movement))
        if max(xabs, yabs) < SWIPE_DISTANCE or min(xabs/max(yabs, 0.01), yabs/max(xabs, 0.01)) > 0.3:
            return
        d = x_movement if xabs > yabs else y_movement
        axis = (Left, Right) if xabs > yabs else (Up, Down)
        return axis[0 if d < 0 else 1]

class State(QObject):

    tapped = pyqtSignal(object)
    swiped = pyqtSignal(object)
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
                self.swipe_hold_updated.emit(tp)
        else:
            self.possible_gestures &= {TapAndHold, SwipeAndHold}
            if tp.total_movement > SWIPE_DISTANCE:
                st = tp.swipe_type
                if st is None:
                    self.possible_gestures.clear()
                else:
                    self.hold_started = True
                    self.possible_gestures = {SwipeAndHold}
                    self.hold_data = (now, st)
                    self.swipe_hold_started.emit(tp)
            else:
                self.possible_gestures = {TapAndHold}
                self.hold_started = True
                self.hold_data = now
                self.tap_hold_started.emit(tp)

    def finalize(self):
        if Tap in self.possible_gestures:
            tp = next(self.touch_points.itervalues())
            if tp.total_movement <= SWIPE_DISTANCE:
                self.tapped.emit(tp)
                return

        if Swipe in self.possible_gestures:
            tp = next(self.touch_points.itervalues())
            st = tp.swipe_type
            if st is not None:
                self.swiped.emit(st)
                return

        if Pinch in self.possible_gestures:
            pass  # TODO: Implement this

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
        self.state.swiped.connect(self.handle_swipe)
        self.state.tapped.connect(self.handle_tap)
        self.state.tap_hold_started.connect(partial(self.handle_tap_hold, 'start'))
        self.state.tap_hold_updated.connect(partial(self.handle_tap_hold, 'update'))
        self.state.tap_hold_finished.connect(partial(self.handle_tap_hold, 'end'))
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
        func = {Left:'next_page', Right: 'previous_page', Up:'goto_previous_section', Down:'goto_next_section'}[direction]
        getattr(view, func)()

    def handle_tap(self, tp):
        if self.close_open_menu():
            return
        view = self.parent()
        threshold = view.width() / 3.0
        attr = 'previous' if tp.start_position.x() <= threshold else 'next'
        getattr(view, '%s_page'%attr)()

    def handle_tap_hold(self, action, tp):
        etype = {'start':QEvent.MouseButtonPress, 'update':QEvent.MouseMove, 'end':QEvent.MouseButtonRelease}[action]
        ev = QMouseEvent(etype, tp.current_position.toPoint(), tp.current_screen_position.toPoint(), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(self.parent(), ev)
        if action == 'end':
            ev = QContextMenuEvent(QContextMenuEvent.Other, tp.current_position.toPoint(), tp.current_screen_position.toPoint())
            # We have to use post event otherwise the popup remains an alien widget and does not receive events
            QApplication.postEvent(self.parent(), ev)

