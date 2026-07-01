#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Calibre Contributors

'''
Audio player widget for playing audiobooks within Calibre.
Uses Qt's QMediaPlayer for playback with chapter navigation,
speed control, and position tracking.
'''

import os

from qt.core import (
    QAudioOutput, QHBoxLayout, QLabel, QMediaPlayer, QObject, QSlider,
    QSizePolicy, Qt, QTimer, QToolButton, QUrl, QVBoxLayout, QWidget,
    pyqtSignal,
)


def format_time(seconds):
    '''Format seconds as HH:MM:SS or MM:SS.'''
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m}:{s:02d}'


class ChapterList(QWidget):
    '''Clickable chapter list sidebar.'''

    chapter_selected = pyqtSignal(float)  # emits start time in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chapters = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self._buttons = []

    def set_chapters(self, chapters):
        '''Set chapters list. Each chapter: {id, start, end, title}.'''
        for btn in self._buttons:
            btn.deleteLater()
        self._buttons.clear()
        self.chapters = chapters or []

        for ch in self.chapters:
            btn = QToolButton(self)
            btn.setText(f'{ch["title"]}  ({format_time(ch["start"])})')
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            start = ch['start']
            btn.clicked.connect(lambda checked, s=start: self.chapter_selected.emit(s))
            self.layout.addWidget(btn)
            self._buttons.append(btn)
        self.layout.addStretch()

    def highlight_chapter(self, position_secs):
        '''Highlight the current chapter based on playback position.'''
        current_idx = -1
        for i, ch in enumerate(self.chapters):
            if ch['start'] <= position_secs < ch.get('end', float('inf')):
                current_idx = i
                break
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet('font-weight: bold;' if i == current_idx else '')


class AudioPlayer(QWidget):
    '''
    Main audio player widget with transport controls, position slider,
    chapter navigation, and speed control.
    '''

    position_changed = pyqtSignal(float)  # current position in seconds
    playback_finished = pyqtSignal()

    SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._chapters = []
        self._duration = 0
        self._current_speed_idx = 2  # 1.0x
        self._seeking = False

        self._setup_ui()
        self._connect_signals()

        self._update_timer = QTimer(self)
        self._update_timer.setInterval(500)
        self._update_timer.timeout.connect(self._on_timer)

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)

        # Title label
        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet('font-size: 14pt; font-weight: bold;')
        main.addWidget(self._title_label)

        # Chapter label
        self._chapter_label = QLabel()
        self._chapter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self._chapter_label)

        # Position slider
        slider_row = QHBoxLayout()
        self._time_label = QLabel('0:00')
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._duration_label = QLabel('0:00')
        slider_row.addWidget(self._time_label)
        slider_row.addWidget(self._slider, 1)
        slider_row.addWidget(self._duration_label)
        main.addLayout(slider_row)

        # Transport controls
        controls = QHBoxLayout()
        controls.addStretch()

        self._prev_chapter_btn = QToolButton()
        self._prev_chapter_btn.setText('⏮')
        self._prev_chapter_btn.setToolTip(_('Previous chapter'))
        controls.addWidget(self._prev_chapter_btn)

        self._rewind_btn = QToolButton()
        self._rewind_btn.setText('⏪ 30s')
        self._rewind_btn.setToolTip(_('Rewind 30 seconds'))
        controls.addWidget(self._rewind_btn)

        self._play_btn = QToolButton()
        self._play_btn.setText('▶')
        self._play_btn.setToolTip(_('Play / Pause'))
        self._play_btn.setStyleSheet('font-size: 18pt;')
        controls.addWidget(self._play_btn)

        self._forward_btn = QToolButton()
        self._forward_btn.setText('30s ⏩')
        self._forward_btn.setToolTip(_('Forward 30 seconds'))
        controls.addWidget(self._forward_btn)

        self._next_chapter_btn = QToolButton()
        self._next_chapter_btn.setText('⏭')
        self._next_chapter_btn.setToolTip(_('Next chapter'))
        controls.addWidget(self._next_chapter_btn)

        controls.addStretch()

        # Speed control
        self._speed_btn = QToolButton()
        self._speed_btn.setText('1.0×')
        self._speed_btn.setToolTip(_('Playback speed'))
        controls.addWidget(self._speed_btn)

        # Volume
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(100)
        self._volume_slider.setMaximumWidth(100)
        self._volume_slider.setToolTip(_('Volume'))
        controls.addWidget(QLabel('🔊'))
        controls.addWidget(self._volume_slider)

        main.addLayout(controls)

    def _connect_signals(self):
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status)

        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)

        self._play_btn.clicked.connect(self.toggle_play)
        self._rewind_btn.clicked.connect(lambda: self.seek_relative(-30))
        self._forward_btn.clicked.connect(lambda: self.seek_relative(30))
        self._prev_chapter_btn.clicked.connect(self.prev_chapter)
        self._next_chapter_btn.clicked.connect(self.next_chapter)
        self._speed_btn.clicked.connect(self.cycle_speed)
        self._volume_slider.valueChanged.connect(
            lambda v: self._audio_output.setVolume(v / 100.0)
        )

    def load(self, path, title='', chapters=None):
        '''Load an audio file for playback.'''
        self._chapters = chapters or []
        self._title_label.setText(title or os.path.basename(path))
        self._player.setSource(QUrl.fromLocalFile(path))
        self._update_chapter_label(0)

    def toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()
            self._update_timer.start()

    def seek_to(self, seconds):
        '''Seek to absolute position in seconds.'''
        self._player.setPosition(int(seconds * 1000))

    def seek_relative(self, delta_seconds):
        '''Seek relative to current position.'''
        current = self._player.position() / 1000.0
        self.seek_to(max(0, current + delta_seconds))

    def next_chapter(self):
        if not self._chapters:
            return self.seek_relative(30)
        current = self._player.position() / 1000.0
        for ch in self._chapters:
            if ch['start'] > current + 1:
                return self.seek_to(ch['start'])

    def prev_chapter(self):
        if not self._chapters:
            return self.seek_relative(-30)
        current = self._player.position() / 1000.0
        for ch in reversed(self._chapters):
            if ch['start'] < current - 2:
                return self.seek_to(ch['start'])
        if self._chapters:
            self.seek_to(self._chapters[0]['start'])

    def cycle_speed(self):
        self._current_speed_idx = (self._current_speed_idx + 1) % len(self.SPEED_OPTIONS)
        speed = self.SPEED_OPTIONS[self._current_speed_idx]
        self._player.setPlaybackRate(speed)
        self._speed_btn.setText(f'{speed}×')

    def current_position(self):
        '''Return current position in seconds.'''
        return self._player.position() / 1000.0

    def duration(self):
        '''Return total duration in seconds.'''
        return self._duration

    def stop(self):
        self._player.stop()
        self._update_timer.stop()

    def shutdown(self):
        self.stop()
        self._player.setSource(QUrl())

    # --- Private slots ---

    def _on_duration_changed(self, duration_ms):
        self._duration = duration_ms / 1000.0
        self._slider.setRange(0, duration_ms)
        self._duration_label.setText(format_time(self._duration))

    def _on_position_changed(self, position_ms):
        if not self._seeking:
            self._slider.setValue(position_ms)
        secs = position_ms / 1000.0
        self._time_label.setText(format_time(secs))
        self._update_chapter_label(secs)
        self.position_changed.emit(secs)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText('⏸')
            self._update_timer.start()
        else:
            self._play_btn.setText('▶')
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self._update_timer.stop()

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.playback_finished.emit()

    def _on_slider_pressed(self):
        self._seeking = True

    def _on_slider_released(self):
        self._seeking = False
        self._player.setPosition(self._slider.value())

    def _on_timer(self):
        # Periodic UI update
        pass

    def _update_chapter_label(self, position_secs):
        if not self._chapters:
            self._chapter_label.setText('')
            return
        for ch in reversed(self._chapters):
            if ch['start'] <= position_secs:
                self._chapter_label.setText(ch['title'])
                return
        self._chapter_label.setText(self._chapters[0]['title'] if self._chapters else '')
