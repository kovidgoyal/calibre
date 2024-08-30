#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from typing import NamedTuple

from qt.core import QMediaDevices, QObject, QTextToSpeech, pyqtSignal

from calibre.gui2.tts2.types import EngineSpecificSettings, Voice, qvoice_to_voice


class Pos(NamedTuple):
    mark: int
    offset_in_text: int


class Tracker:

    def reset(self) -> None:
        self.positions: list[Pos] = []
        self.last_pos: int = 0

    def parse_marked_text(self, marked_text: list[str | int]) -> str:
        self.reset()
        text: list[str] = []
        text_len: int = 0
        for x in marked_text:
            if isinstance(x, int):
                self.positions.append(Pos(x, text_len))
            else:
                text_len += len(x)
                text.append(x)
        return ''.join(text)

    def mark_word(self, start: int, length: int) -> tuple[int, int] | None:
        end = start + length
        matches: list[Pos] = []
        while True:
            if self.last_pos >= len(self.positions):
                break
            pos = self.positions[self.last_pos]
            if start <= pos.offset_in_text < end:
                matches.append(pos)
            elif pos.offset_in_text >= end:
                break
            self.last_pos += 1
        if matches:
            return matches[0].mark, matches[-1].mark
        return None


class QtTTSBackend(QObject):

    saying = pyqtSignal(int, int)
    state_changed = pyqtSignal(QTextToSpeech.State)

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)
        self.tracker = Tracker()
        self._voices = None
        self._create_engine(engine_name)

    @property
    def available_voices(self) -> dict[str, tuple[Voice, ...]]:
        if self._voices is None:
            self._voices = tuple(map(qvoice_to_voice, self.tts.availableVoices()))
        return {'': self._voices}

    @property
    def engine_name(self) -> str:
        return self.tts.engine()

    def change_rate(self, steps: int = 1) -> bool:
        current = self.tts.rate()
        new_rate = max(-1, min(current + 0.2 * steps, 1))
        if current == new_rate:
            return False
        self.tts.setRate(new_rate)
        self._current_settings = self._current_settings._replace(rate=new_rate)
        self._current_settings.save_to_config()
        return True

    def shutdown(self) -> None:
        self.tts.stop(QTextToSpeech.BoundaryHint.Immediate)

    def speak_simple_text(self, text: str) -> None:
        self.tts.say(text)

    def pause(self) -> None:
        self.tts.pause()

    def resume(self) -> None:
        self.tts.resume()

    def stop(self) -> None:
        self.tts.stop()

    def resume_after_configure(self) -> None:
        raise NotImplementedError('TODO: Implement me')

    def speak_marked_text(self, marked_text: list[str | int]) -> None:
        self.tts.say(self.tracker.parse_marked_text(marked_text))

    def error_message(self) -> str:
        return self.tts.errorString()

    def _create_engine(self, engine_name: str) -> None:
        s = {}
        if engine_name:
            settings = EngineSpecificSettings.create_from_config(engine_name)
            if settings.audio_device_id:
                for x in QMediaDevices.audioOutputs():
                    if bytes(x.id) == settings.audio_device_id.id:
                        s['audioDevice'] = x
                        break
            self.tts = QTextToSpeech(engine_name, s, self)
        else:
            self.tts = QTextToSpeech(self)
            engine_name = self.tts.engine()
            settings = EngineSpecificSettings.create_from_config(engine_name)
            if settings.audio_device_id:
                for x in QMediaDevices.audioOutputs():
                    if bytes(x.id) == settings.audio_device_id.id:
                        s['audioDevice'] = x
                        self.tts = QTextToSpeech(engine_name, s, self)
                        break

        self.tts.setRate(max(-1, min(float(settings.rate), 1)))
        self.tts.setPitch(max(-1, min(float(settings.pitch), 1)))
        if settings.volume is not None:
            self.tts.setVolume(max(0, min(float(settings.volume), 1)))
        if settings.voice_name:
            for v in self.availableVoices():
                if v.name() == settings.voice_name:
                    self.setVoice(v)
                    break
        self.tts.sayingWord.connect(self._saying_word)
        self.tts.stateChanged.connect(self.state_changed.emit)
        self._current_settings = settings

    def _saying_word(self, word: str, utterance_id: int, start: int, length: int) -> None:
        x = self.tracker.mark_word(start, length)
        if x is not None:
            self.saying.emit(x[0], x[1])
