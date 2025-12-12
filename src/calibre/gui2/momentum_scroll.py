#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from collections import deque
from typing import NamedTuple

from qt.core import (
    QAbstractScrollArea,
    QElapsedTimer,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QMainWindow,
    QSlider,
    QStringListModel,
    Qt,
    QTimer,
    QVBoxLayout,
    QWheelEvent,
    QWidget,
)

from calibre.gui2 import Application


def same_sign(a: float, b: float) -> bool:
    if a == 0 or b == 0:
        return True
    return (a > 0) == (b > 0)


class ScrollSample(NamedTuple):
    '''Store a scroll sample with timestamp for velocity calculation.'''
    delta_x: float
    delta_y: float
    timestamp: int


class MomentumSettings(NamedTuple):
    # Deceleration factor (0-1, higher = longer coast)
    friction: float = 0.95
    min_velocity: float = 0.5  # Minimum velocity before stopping
    max_velocity: float = 100   # maximum velocity to prevent runaway scrolling
    boost_factor: float = 2  # how much of new swipe velocity to add
    velocity_scale: float = 0.8  # Scale factor for initial velocity
    timer_interval_ms: int = int(1000/120)  # 120 FPS update rate
    # Time to wait after ScrollEnd to see if system momentum arrives
    momentum_detection_delay_ms: int  = 50
    # Whether to enable momentum in the specified axis, defers to Qt handling
    # of wheelevents when false
    enable_x: bool = True
    enable_y: bool = True
    # How much to scale scroll amounts by
    x_multiplier: float = 1
    y_multiplier: float = 1


class MomentumScroller:
    '''
    Handles momentum/kinetic scrolling for Qt scroll areas.

    Behavior by platform/device:
    - macOS trackpad: Uses system-provided momentum (ScrollMomentum phase)
    - Linux trackpad: Has phases but sometimes no momentum, so we synthesize it when needed
    - Mouse wheel (all platforms): No phases, we synthesize momentum
    '''

    def __init__(self, scroll_area: QAbstractScrollArea, settings: MomentumSettings = MomentumSettings()):
        self.settings = settings
        self.scroll_area = scroll_area
        self.seen_momentum_event = False
        self.synthetic_momentum_already_used = False

        # Velocity tracking
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        # Accumulated sub-pixel scroll amounts
        self.accumulated_x = 0.0
        self.accumulated_y = 0.0

        # Sample history for calculating velocity
        self.samples:  deque[ScrollSample] = deque(maxlen=20)

        # Timing
        self.elapsed_timer = QElapsedTimer()
        self.elapsed_timer.start()

        # Animation timer for synthetic momentum
        self.momentum_timer = QTimer()
        self.momentum_timer.timeout.connect(self._update_momentum)

        # Timer to detect if system momentum is coming
        self.momentum_detection_timer = QTimer()
        self.momentum_detection_timer.setSingleShot(True)
        self.momentum_detection_timer.timeout.connect(self._start_synthetic_momentum)

        # State tracking
        self._in_scroll_gesture = False
        self._last_scroll_end_time = 0

    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        '''
        Process a wheel event, respecting system momentum phases when available.

        Returns True if the event was handled.
        '''
        dx, dy = self._get_delta(event)
        current_time = self.elapsed_timer.elapsed()

        match event.phase():
            case Qt.ScrollPhase.NoScrollPhase:
                # Record sample
                self.samples.append(ScrollSample(dx, dy, current_time))

                # Trim old samples
                self._trim_old_samples(current_time)

                # Calculate current velocity
                self._accumulate_velocity_from_samples(current_time)

                # Apply immediate scroll
                self._do_scroll(dx, dy)

                # Reset momentum timer - will start coasting after input stops
                self.momentum_timer.stop()
                self.momentum_timer.start(self.settings.timer_interval_ms)

            case Qt.ScrollPhase.ScrollBegin:
                # User started a new scroll gesture
                self._in_scroll_gesture = True
                self.accumulated_x = 0
                self.accumulated_y = 0
                self.samples.clear()

                # Stop any ongoing synthetic momentum
                self.momentum_timer.stop()
                self.momentum_detection_timer.stop()

            case Qt.ScrollPhase.ScrollUpdate:
                # Active scrolling - record sample and apply delta
                self.samples.append(ScrollSample(dx, dy, current_time))
                self._do_scroll(dx, dy)

            case Qt.ScrollPhase.ScrollEnd:
                # User lifted fingers
                self._in_scroll_gesture = False
                self._last_scroll_end_time = current_time

                # Calculate new gesture velocity and combine with existing
                self._accumulate_velocity_from_samples(current_time)

                if not self.seen_momentum_event:
                    if max(abs(self.velocity_x), abs(self.velocity_y)) > self.settings.min_velocity:
                        if self.synthetic_momentum_already_used:
                            self.start_momentum_timer()
                        else:
                            # Wait briefly to see if system momentum events arrive
                            # If they do, we'll use those; if not, we synthesize
                            self.momentum_detection_timer.start(self.settings.momentum_detection_delay_ms)

            case Qt.ScrollPhase.ScrollMomentum:
                # System-provided momentum (macOS)
                self.seen_momentum_event = True
                self.momentum_detection_timer.stop()
                self.momentum_timer.stop()
                self._do_scroll(dx, dy)

        return True

    def _start_synthetic_momentum(self):
        '''
        Called after ScrollEnd if no system momentum arrived.
        Start our own momentum animation.
        '''
        if not self.seen_momentum_event:
            self.synthetic_momentum_already_used = True
            self.start_momentum_timer()

    def start_momentum_timer(self):
        if max(abs(self.velocity_x), abs(self.velocity_y)) > self.settings.min_velocity:
            self.momentum_timer.start(self.settings.timer_interval_ms)

    def _get_delta(self, event: QWheelEvent) -> tuple[float, float]:
        '''Extract scroll delta from wheel event.'''
        pixel_delta = event.pixelDelta()
        angle_delta = event.angleDelta()

        # Prefer pixel delta (from trackpads), fall back to angle delta
        if not pixel_delta.isNull():
            return float(pixel_delta.x()), float(pixel_delta.y())
        # Convert angle delta to pixels (120 units = 1 step)
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        return angle_delta.x() / 120.0 * (h_bar.singleStep() if h_bar else 1), angle_delta.y() / 120.0 * (v_bar.singleStep() if v_bar else 1)

    def _trim_old_samples(self, current_time: int, window_ms: int = 150):
        '''Remove samples older than the window.'''
        cutoff = current_time - window_ms
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def _calculate_gesture_velocity(self) -> tuple[float, float]:
        '''Calculate velocity from the current gesture samples.'''
        if len(self.samples) < 2:
            if self.samples:
                s = self.samples[0]
                return s.delta_x * self.settings.velocity_scale, s.delta_y * self.settings.velocity_scale
            return 0.0, 0.0

        # Use weighted average - more recent samples have higher weight
        total_dx = 0.0
        total_dy = 0.0
        total_weight = 0.0

        first_time = self.samples[0].timestamp
        last_time = self.samples[-1].timestamp
        time_span = max(last_time - first_time, 1)

        for sample in self.samples:
            weight = 1.0 + (sample.timestamp - first_time) / time_span
            total_dx += sample.delta_x * weight
            total_dy += sample.delta_y * weight
            total_weight += weight

        if total_weight > 0:
            avg_dx = total_dx / total_weight
            avg_dy = total_dy / total_weight
            return avg_dx * self.settings.velocity_scale, avg_dy * self.settings.velocity_scale

        return 0.0, 0.0

    def _clamp_velocity(self, velocity:  float) -> float:
        m = self.settings.max_velocity
        return max(-m, min(velocity, m))

    def _accumulate_velocity_from_samples(self, current_time:  int):
        '''
        Calculate velocity from recent scroll samples and add to existing velocity.

        This creates the cumulative effect where repeated swipes increase speed.
        '''
        self._trim_old_samples(current_time)

        if not self.samples:
            return

        # Calculate new gesture velocity
        new_vx, new_vy = self._calculate_gesture_velocity()

        # Check direction compatibility and accumulate
        # Same direction: add velocities
        # Opposite direction: new velocity takes over
        if same_sign(self.velocity_x, new_vx):
            self.velocity_x = self._clamp_velocity(self.velocity_x + new_vx * self.settings.boost_factor)
        else:
            self.velocity_x = new_vx

        if same_sign(self.velocity_y, new_vy):
            self.velocity_y = self._clamp_velocity(self.velocity_y + new_vy * self.settings.boost_factor)
        else:
            self.velocity_y = new_vy

    def _update_momentum(self):
        '''Called by timer to apply synthetic momentum scrolling.'''
        # For discrete events, check if we're still receiving input
        if self.samples:
            time_since_last = self.elapsed_timer.elapsed() - self.samples[-1].timestamp
            if time_since_last < self.settings.timer_interval_ms * 2:
                # Still receiving wheel events, don't apply momentum yet
                return

        # Apply friction
        self.velocity_x *= self.settings.friction
        self.velocity_y *= self.settings.friction

        # Check if we should stop
        if max(abs(self.velocity_x), abs(self.velocity_y)) < self.settings.min_velocity:
            self._stop_momentum()
            return

        # Apply the scroll
        self._do_scroll(self.velocity_x, self.velocity_y)

    def _do_scroll(self, dx: float, dy: float):
        '''Apply scroll delta to the scroll area.'''
        # Accumulate sub-pixel amounts
        self.accumulated_x += dx
        self.accumulated_y += dy

        # Extract integer pixels to scroll
        scroll_x = self.accumulated_x
        scroll_y = self.accumulated_y

        # Keep the fractional remainder
        self.accumulated_x -= int(scroll_x)
        self.accumulated_y -= int(scroll_y)

        # Apply to scrollbars
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()

        if scroll_x != 0 and h_bar:
            h_bar.setValue(h_bar.value() - int(scroll_x * self.settings.x_multiplier))

        if scroll_y != 0 and v_bar:
            v_bar.setValue(v_bar.value() - int(scroll_y * self.settings.y_multiplier))

    def _stop_momentum(self):
        '''Stop momentum and reset state.'''
        self.velocity_x = 0
        self.velocity_y = 0
        self.accumulated_x = 0
        self.accumulated_y = 0
        self.samples.clear()
        self.momentum_timer.stop()

    def stop(self):
        '''Public method to stop any ongoing momentum scrolling.'''
        self.momentum_detection_timer.stop()
        self._stop_momentum()
        self._in_scroll_gesture = False


class MomentumScrollMixin:
    '''
    Mixin class to add momentum scrolling to any QAbstractScrollArea subclass.

    Automatically uses system momentum on macOS, synthesizes on Linux/Windows.

    Usage:
        class MyListView(MomentumScrollMixin, QListView):
            pass
    '''

    _momentum_scroller:  MomentumScroller | None = None
    _momentum_settings: MomentumSettings | None = None

    def _ensure_momentum_scroller(self):
        if self._momentum_scroller is None:
            self._momentum_scroller = MomentumScroller(self, self._momentum_settings or MomentumSettings())

    def wheelEvent(self, event: QWheelEvent):
        self._ensure_momentum_scroller()
        if (not self._momentum_scroller.settings.enable_x and event.angleDelta().x() != 0) or (
                not self._momentum_scroller.settings.enable_y and event.angleDelta().y() != 0):
            return super().wheelEvent(event)
        self._momentum_scroller.handle_wheel_event(event)
        event.accept()

    def stopMomentumScroll(self):
        '''Stop any ongoing momentum scrolling.'''
        if self._momentum_scroller:
            self._momentum_scroller.stop()

    def update_momentum_scroll_settings(self, **kw) -> None:
        self._ensure_momentum_scroller()
        self._momentum_scroller.settings = self._momentum_scroller.settings._replace(**kw)


# Demo {{{
if __name__ == '__main__':
    import sys

    class MomentumListView(QListView, MomentumScrollMixin):
        '''QListView with momentum scrolling enabled.'''
        pass

    class DemoWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('Momentum Scrolling Demo')
            self.setMinimumSize(400, 600)

            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)

            # Info box
            info_box = QGroupBox('Scroll Behavior')
            info_layout = QVBoxLayout(info_box)
            info_layout.addWidget(QLabel(
                '• <b>macOS trackpad</b>: Native system momentum\n'
                '• <b>Linux trackpad</b>: Synthetic momentum (phases, no system momentum)\n'
                '• <b>Mouse wheel</b>:  Synthetic momentum (no phases)'
            ))
            layout.addWidget(info_box)

            # Create list view with momentum scrolling
            self.list_view = MomentumListView()
            items = [f'Item {i} - Scroll me!' for i in range(1, 501)]
            model = QStringListModel(items)
            self.list_view.setModel(model)
            layout.addWidget(self.list_view, 1)

            # Tuning controls
            tuning_box = QGroupBox('Synthetic Momentum Tuning')
            tuning_layout = QVBoxLayout(tuning_box)

            # Friction slider
            friction_row = QHBoxLayout()
            friction_row.addWidget(QLabel('Friction:'))
            self.friction_slider = QSlider(Qt.Orientation.Horizontal)
            self.friction_slider.setRange(80, 99)
            self.friction_slider.setValue(92)
            self.friction_slider.valueChanged.connect(self._update_friction)
            friction_row.addWidget(self.friction_slider)
            self.friction_label = QLabel('0.92')
            self.friction_label.setMinimumWidth(35)
            friction_row.addWidget(self.friction_label)
            tuning_layout.addLayout(friction_row)

            # Velocity scale slider
            velocity_row = QHBoxLayout()
            velocity_row.addWidget(QLabel('Velocity: '))
            self.velocity_slider = QSlider(Qt.Orientation.Horizontal)
            self.velocity_slider.setRange(20, 200)
            self.velocity_slider.setValue(80)
            self.velocity_slider.valueChanged.connect(self._update_velocity)
            velocity_row.addWidget(self.velocity_slider)
            self.velocity_label = QLabel('0.80')
            self.velocity_label.setMinimumWidth(35)
            velocity_row.addWidget(self.velocity_label)
            tuning_layout.addLayout(velocity_row)

            layout.addWidget(tuning_box)

        def _update_friction(self, value):
            friction = value / 100.0
            self.friction_label.setText(f'{friction:.2f}')
            if self.list_view._momentum_scroller:
                self.list_view._momentum_scroller.settings = self.list_view._momentum_scroller.settings._replace(friction=friction)

        def _update_velocity(self, value):
            velocity = value / 100.0
            self.velocity_label.setText(f'{velocity:.2f}')
            if self.list_view._momentum_scroller:
                self.list_view._momentum_scroller.settings = self.list_view._momentum_scroller.settings._replace(velocity_scale=velocity)

    app = Application([])
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())
# }}}
