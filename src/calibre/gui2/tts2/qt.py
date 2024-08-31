#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QMediaDevices, QObject, QTextToSpeech

from calibre.gui2.tts2.types import EngineSpecificSettings, TTSBackend, Voice, qvoice_to_voice


class QtTTSBackend(TTSBackend):

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)
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

    @property
    def default_output_module(self) -> str:
        return ''

    def pause(self) -> None:
        self.tts.pause()

    def resume(self) -> None:
        self.tts.resume()

    def stop(self) -> None:
        self.tts.stop()

    def say(self, text: str) -> None:
        self.tts.say(text)

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
            for v in self.tts.availableVoices():
                if v.name() == settings.voice_name:
                    self.tts.setVoice(v)
                    break
        self.tts.sayingWord.connect(self._saying_word)
        self.tts.stateChanged.connect(self.state_changed.emit)
        self._current_settings = settings

    def _saying_word(self, word: str, utterance_id: int, start: int, length: int) -> None:
        self.saying.emit(start, length)
