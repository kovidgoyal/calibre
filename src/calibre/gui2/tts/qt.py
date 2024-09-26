#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QMediaDevices, QObject, QTextToSpeech

from calibre.gui2.tts.types import EngineSpecificSettings, TTSBackend, Voice, qvoice_to_voice


class QtTTSBackend(TTSBackend):

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)
        self.speaking_text = ''
        self.last_word_offset = 0
        self.last_spoken_word = None
        self.ignore_tracking_until_state_changes_to_speaking = False
        self._qt_reload_after_configure(engine_name)

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
        if self.tts.engine() == 'sapi' and self.tts.state() is QTextToSpeech.State.Speaking:
            # prevent an occasional crash on stop by re-creating the engine rather than stopping it
            self.tts.sayingWord.disconnect()
            self.tts.stateChanged.disconnect()
            self.tts.pause()
            self.tts.deleteLater()
            del self.tts
            self._qt_reload_after_configure('sapi')
            self._state_changed(QTextToSpeech.State.Ready)
        else:
            self.tts.stop()

    def say(self, text: str) -> None:
        self.last_word_offset = 0
        self.last_spoken_word = None
        self.speaking_text = text
        if self.tts.engine() == 'sapi':
            self.ignore_tracking_until_state_changes_to_speaking = True
        self.tts.say(text)

    def error_message(self) -> str:
        return self.tts.errorString()

    def reload_after_configure(self) -> None:
        self._qt_reload_after_configure(self.engine_name)

    def _qt_reload_after_configure(self, engine_name: str) -> None:
        # Bad things happen with more than one QTextToSpeech instance
        s = {}
        self._voices = None
        new_backend = not hasattr(self, 'tts')
        if engine_name:
            settings = EngineSpecificSettings.create_from_config(engine_name)
            if settings.audio_device_id:
                for x in QMediaDevices.audioOutputs():
                    if bytes(x.id()) == settings.audio_device_id.id:
                        s['audioDevice'] = x
                        break
            if new_backend:
                self.tts = QTextToSpeech(engine_name, s, self)
            else:
                self.tts.setEngine(engine_name, s)
        else:
            if new_backend:
                self.tts = QTextToSpeech(self)
            else:
                self.tts.setEngine('')
            engine_name = self.tts.engine()
            settings = EngineSpecificSettings.create_from_config(engine_name)
            if settings.audio_device_id:
                for x in QMediaDevices.audioOutputs():
                    if bytes(x.id) == settings.audio_device_id.id:
                        s['audioDevice'] = x
                        self.tts = QTextToSpeech(engine_name, s, self)
                        break
        if new_backend:
            self.tts.sayingWord.connect(self._saying_word)
            self.tts.stateChanged.connect(self._state_changed)

        self.tts.setRate(max(-1, min(float(settings.rate), 1)))
        self.tts.setPitch(max(-1, min(float(settings.pitch), 1)))
        if settings.volume is not None:
            self.tts.setVolume(max(0, min(float(settings.volume), 1)))
        if settings.voice_name:
            for v in self.tts.availableVoices():
                if v.name() == settings.voice_name:
                    self.tts.setVoice(v)
                    break
        self._current_settings = settings

    def _saying_word(self, word: str, utterance_id: int, start: int, length: int) -> None:
        # print(f'{repr(word)=} {start=} {length=}, {repr(self.speaking_text[start:start+length])=} {self.ignore_tracking_until_state_changes_to_speaking=}')
        if self.ignore_tracking_until_state_changes_to_speaking:
            return
        # Qt's word tracking is broken with non-BMP unicode chars, the
        # start and length values are totally wrong, so track manually
        key = word, start, length
        # Qt sometimes repeats words with windows modern engine at least, for a test case see https://bugs.launchpad.net/calibre/+bug/2080708
        if self.last_spoken_word == key:
            return
        self.last_spoken_word = key
        idx = self.speaking_text.find(word, self.last_word_offset)
        # print(f'{self.last_word_offset=} {idx=}')
        if idx > -1:
            self.saying.emit(idx, len(word))
            self.last_word_offset = idx + len(word)

    def _state_changed(self, state: QTextToSpeech.State) -> None:
        if self.ignore_tracking_until_state_changes_to_speaking and state is QTextToSpeech.State.Speaking:
            self.ignore_tracking_until_state_changes_to_speaking = False
        self.state_changed.emit(state)
