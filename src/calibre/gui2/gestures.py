#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import os
from functools import lru_cache
from qt.core import (
    QApplication, QEvent, QInputDevice, QMouseEvent, QObject, QPointF, QScroller, Qt,
    pyqtSignal
)

from calibre.utils.monotonic import monotonic
from polyglot.builtins import itervalues

HOLD_THRESHOLD = 1.0  # seconds
TAP_THRESHOLD  = 50   # manhattan pixels

Tap, TapAndHold, Flick = 'Tap', 'TapAndHold', 'Flick'
Left, Right, Up, Down = 'Left', 'Right', 'Up', 'Down'


@lru_cache(maxsize=2)
def touch_supported():
    if 'CALIBRE_NO_TOUCH' in os.environ:
        return False
    for dev in QInputDevice.devices():
        if dev.type() == QInputDevice.DeviceType.TouchScreen:
            return True
    return False


class TouchPoint:

    def __init__(self, tp):
        self.creation_time = self.last_update_time = self.time_of_last_move = monotonic()
        self.start_screen_position = self.current_screen_position = self.previous_screen_position = QPointF(tp.globalPosition())
        self.time_since_last_update = -1
        self.total_movement = 0
        self.start_position = self.current_position = tp.position()
        self.extra_data = None

    def update(self, tp):
        self.current_position = tp.position()
        now = monotonic()
        self.time_since_last_update = now - self.last_update_time
        self.last_update_time = now
        self.previous_screen_position, self.current_screen_position = self.current_screen_position, QPointF(tp.globalPosition())
        movement = (self.current_screen_position - self.previous_screen_position).manhattanLength()
        self.total_movement += movement
        if movement > 5:
            self.time_of_last_move = now


class State(QObject):

    tapped = pyqtSignal(object)
    flicking = pyqtSignal(object, object)
    tap_hold_started = pyqtSignal(object)
    tap_hold_updated = pyqtSignal(object)
    tap_hold_finished = pyqtSignal(object)

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
        self.possible_gestures = {Tap, TapAndHold, Flick}

    def update(self, ev, boundary='update'):
        if boundary == 'cancel':
            self.clear()
            return
        if boundary == 'start':
            self.start()

        for tp in ev.points():
            tpid = tp.id()
            if tpid not in self.touch_points:
                self.touch_points[tpid] = TouchPoint(tp)
            else:
                self.touch_points[tpid].update(tp)

        if len(self.touch_points) > 1:
            self.possible_gestures.clear()

        if boundary == 'end':
            self.check_for_holds()
            self.finalize()
            self.clear()
        else:
            self.check_for_holds()
            if Flick in self.possible_gestures:
                tp = next(itervalues(self.touch_points))
                self.flicking.emit(tp, False)

    def check_for_holds(self):
        if not {TapAndHold} & self.possible_gestures:
            return
        now = monotonic()
        tp = next(itervalues(self.touch_points))
        if now - tp.time_of_last_move < HOLD_THRESHOLD:
            return
        if self.hold_started:
            if TapAndHold in self.possible_gestures:
                self.tap_hold_updated.emit(tp)
        else:
            self.possible_gestures &= {TapAndHold}
            if tp.total_movement > TAP_THRESHOLD:
                self.possible_gestures.clear()
            else:
                self.possible_gestures = {TapAndHold}
                self.hold_started = True
                self.hold_data = now
                self.tap_hold_started.emit(tp)

    def finalize(self):
        if Tap in self.possible_gestures:
            tp = next(itervalues(self.touch_points))
            if tp.total_movement <= TAP_THRESHOLD:
                self.tapped.emit(tp)
                return

        if Flick in self.possible_gestures:
            tp = next(itervalues(self.touch_points))
            self.flicking.emit(tp, True)

        if not self.hold_started:
            return

        if TapAndHold in self.possible_gestures:
            tp = next(itervalues(self.touch_points))
            self.tap_hold_finished.emit(tp)
            return


def send_click(view, pos, button=Qt.MouseButton.LeftButton, double_click=False):
    mods = QApplication.keyboardModifiers()
    if double_click:
        ev = QMouseEvent(QEvent.Type.MouseButtonDblClick, pos, button, button, mods)
        QApplication.postEvent(view.viewport(), ev)
        return
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, pos, button, button, mods)
    QApplication.postEvent(view.viewport(), ev)
    ev = QMouseEvent(QEvent.Type.MouseButtonRelease, pos, button, button, mods)
    QApplication.postEvent(view.viewport(), ev)


class GestureManager(QObject):

    def __init__(self, view):
        QObject.__init__(self, view)
        if touch_supported():
            view.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.state = State()
        self.last_touch_event_device_id = None
        self.state.tapped.connect(
            self.handle_tap,
            type=Qt.ConnectionType.QueuedConnection)  # has to be queued otherwise QApplication.keyboardModifiers() does not work
        self.state.flicking.connect(self.handle_flicking)
        connect_lambda(self.state.tap_hold_started, self, lambda self, tp: self.handle_tap_hold('start', tp))
        connect_lambda(self.state.tap_hold_updated, self, lambda self, tp: self.handle_tap_hold('update', tp))
        connect_lambda(self.state.tap_hold_finished, self, lambda self, tp: self.handle_tap_hold('end', tp))
        self.evmap = {QEvent.Type.TouchBegin: 'start', QEvent.Type.TouchUpdate: 'update', QEvent.Type.TouchEnd: 'end', QEvent.Type.TouchCancel: 'cancel'}
        self.last_tap_at = 0
        if touch_supported():
            self.scroller = QScroller.scroller(view.viewport())

    def handle_event(self, ev):
        if not touch_supported():
            return
        etype = ev.type()
        if etype in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            if self.last_touch_event_device_id is not None and self.last_touch_event_device_id == ev.pointingDevice().uniqueId():
                # swallow fake mouse events generated by the same device as the last touch event
                ev.ignore()
                return False
            self.scroller.stop()
            return
        if etype == QEvent.Type.Wheel and self.scroller.state() != QScroller.State.Inactive:
            ev.ignore()
            return False
        boundary = self.evmap.get(etype)
        if boundary is None or ev.deviceType() != QInputDevice.DeviceType.TouchScreen:
            return
        self.last_touch_event_device_id = ev.pointingDevice().uniqueId()
        self.state.update(ev, boundary=boundary)
        ev.accept()
        return True

    def close_open_menu(self):
        m = getattr(self.parent(), 'context_menu', None)
        if m is not None and hasattr(m, 'isVisible') and m.isVisible():
            m.close()
            return True

    def handle_flicking(self, touch_point, is_end):
        if is_end:
            it = QScroller.Input.InputRelease
        else:
            it = QScroller.Input.InputPress if touch_point.extra_data is None else QScroller.Input.InputMove
        touch_point.extra_data = True
        self.scroller.handleInput(it, touch_point.current_position, int(touch_point.last_update_time * 1000))

    def handle_tap(self, tp):
        self.scroller.stop()
        last_tap_at, self.last_tap_at = self.last_tap_at, monotonic()
        if self.close_open_menu():
            return
        interval = QApplication.instance().doubleClickInterval() / 1000
        double_tap = self.last_tap_at - last_tap_at < interval
        send_click(self.parent(), tp.start_position, double_click=double_tap)

    def handle_tap_hold(self, action, tp):
        self.scroller.stop()
        if action == 'end':
            send_click(self.parent(), tp.start_position, button=Qt.MouseButton.RightButton)
