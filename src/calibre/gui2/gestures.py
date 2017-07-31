#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import sys
from functools import partial

from PyQt5.Qt import (
    QApplication, QEvent, QMouseEvent, QObject, QPointF, QScroller, Qt, QTouchDevice,
    pyqtSignal
)

from calibre.constants import iswindows
from calibre.utils.monotonic import monotonic

touch_supported = False
if iswindows and sys.getwindowsversion()[:2] >= (6, 2):  # At least windows 7
    touch_supported = True

HOLD_THRESHOLD = 1.0  # seconds
TAP_THRESHOLD  = 50   # manhattan pixels

Tap, TapAndHold, Flick = 'Tap', 'TapAndHold', 'Flick'
Left, Right, Up, Down = 'Left', 'Right', 'Up', 'Down'


class TouchPoint(object):

    def __init__(self, tp):
        self.creation_time = self.last_update_time = self.time_of_last_move = monotonic()
        self.start_screen_position = self.current_screen_position = self.previous_screen_position = QPointF(tp.screenPos())
        self.time_since_last_update = -1
        self.total_movement = 0
        self.start_position = self.current_position = tp.pos()
        self.extra_data = None

    def update(self, tp):
        self.current_position = tp.pos()
        now = monotonic()
        self.time_since_last_update = now - self.last_update_time
        self.last_update_time = now
        self.previous_screen_position, self.current_screen_position = self.current_screen_position, QPointF(tp.screenPos())
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
        if boundary == 'start':
            self.start()

        for tp in ev.touchPoints():
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
                tp = next(self.touch_points.itervalues())
                self.flicking.emit(tp, False)

    def check_for_holds(self):
        if not {TapAndHold} & self.possible_gestures:
            return
        now = monotonic()
        tp = next(self.touch_points.itervalues())
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
            tp = next(self.touch_points.itervalues())
            if tp.total_movement <= TAP_THRESHOLD:
                self.tapped.emit(tp)
                return

        if Flick in self.possible_gestures:
            tp = next(self.touch_points.itervalues())
            self.flicking.emit(tp, True)

        if not self.hold_started:
            return

        if TapAndHold in self.possible_gestures:
            tp = next(self.touch_points.itervalues())
            self.tap_hold_finished.emit(tp)
            return


def send_click(view, pos, button=Qt.LeftButton, double_click=False):
    if double_click:
        ev = QMouseEvent(QEvent.MouseButtonDblClick, pos, button, button, QApplication.keyboardModifiers())
        QApplication.postEvent(view.viewport(), ev)
        return
    ev = QMouseEvent(QEvent.MouseButtonPress, pos, button, button, QApplication.keyboardModifiers())
    QApplication.postEvent(view.viewport(), ev)
    ev = QMouseEvent(QEvent.MouseButtonRelease, pos, button, button, QApplication.keyboardModifiers())
    QApplication.postEvent(view.viewport(), ev)


class GestureManager(QObject):

    def __init__(self, view):
        QObject.__init__(self, view)
        if touch_supported:
            view.viewport().setAttribute(Qt.WA_AcceptTouchEvents)
        self.state = State()
        self.state.tapped.connect(self.handle_tap)
        self.state.flicking.connect(self.handle_flicking)
        self.state.tap_hold_started.connect(partial(self.handle_tap_hold, 'start'))
        self.state.tap_hold_updated.connect(partial(self.handle_tap_hold, 'update'))
        self.state.tap_hold_finished.connect(partial(self.handle_tap_hold, 'end'))
        self.evmap = {QEvent.TouchBegin: 'start', QEvent.TouchUpdate: 'update', QEvent.TouchEnd: 'end'}
        self.last_tap_at = 0
        if touch_supported:
            self.scroller = QScroller.scroller(view.viewport())

    def handle_event(self, ev):
        if not touch_supported:
            return
        etype = ev.type()
        if etype in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
            if ev.source() in (Qt.MouseEventSynthesizedBySystem, Qt.MouseEventSynthesizedByQt):
                # swallow fake mouse events generated from touch events
                ev.ignore()
                return False
            self.scroller.stop()
            return
        if etype == QEvent.Wheel and self.scroller.state() != QScroller.Inactive:
            ev.ignore()
            return False
        boundary = self.evmap.get(etype, None)
        if boundary is None or ev.device().type() != QTouchDevice.TouchScreen:
            return
        self.state.update(ev, boundary=boundary)
        ev.accept()
        return True

    def close_open_menu(self):
        m = getattr(self.parent(), 'context_menu', None)
        if m is not None and m.isVisible():
            m.close()
            return True

    def handle_flicking(self, touch_point, is_end):
        if is_end:
            it = QScroller.InputRelease
        else:
            it = QScroller.InputPress if touch_point.extra_data is None else QScroller.InputMove
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
            send_click(self.parent(), tp.start_position, button=Qt.RightButton)
