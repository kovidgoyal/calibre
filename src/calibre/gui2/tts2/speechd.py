#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from contextlib import suppress

from qt.core import QObject, Qt, QTextToSpeech, pyqtSignal
from speechd.client import CallbackType, DataMode, Priority, SpawnError, SSIPClient, SSIPCommunicationError

from calibre import prepare_string_for_xml
from calibre.gui2.tts2.types import EngineSpecificSettings, Voice
from calibre.utils.localization import canonicalize_lang

MARK_TEMPLATE = '<mark name="{}"/>'

def add_markup(text_parts, mark_template=MARK_TEMPLATE, escape_marked_text=prepare_string_for_xml, chunk_size=0):
    buf = []
    size = 0
    for x in text_parts:
        if isinstance(x, int):
            item = mark_template.format(x)
        else:
            item = escape_marked_text(x)
        sz = len(item)
        if chunk_size and size + sz > chunk_size:
            yield ''.join(buf).strip()
            size = 0
            buf = []
        size += sz
        buf.append(item)
    if size:
        yield ''.join(buf).strip()


def wrap_in_ssml(text):
    return ('<?xml version="1.0"?>\n<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"><s>' +
            text + '</s></speak>')


class SpeechdTTSBackend(QObject):

    saying = pyqtSignal(int, int)
    state_changed = pyqtSignal(QTextToSpeech.State)

    _event_signal = pyqtSignal(object, object)

    def __init__(self, engine_name: str = '', settings: EngineSpecificSettings = EngineSpecificSettings(), parent: QObject|None = None):
        super().__init__(parent)
        self._last_error = ''
        self._state = QTextToSpeech.State.Ready
        self._voices = None
        self._system_default_output_module = None
        self._current_settings = EngineSpecificSettings()
        self._status = {'synthesizing': False, 'paused': False}
        self._next_begin_is_for_resume = False
        self._ssip_client: SSIPClient | None = None
        self._event_signal.connect(self._update_status, type=Qt.ConnectionType.QueuedConnection)
        self._current_marked_text = self._last_mark = None
        self.apply_settings(engine_name, settings)

    @property
    def available_voices(self) -> dict[str, tuple[Voice, ...]]:
       if self._voices is None:
            try:
                self._voices = self._get_all_voices_for_all_output_modules()
            except Exception as e:
                self._set_error(str(e))
       return self._voices or {}

    def apply_settings(self, engine_name: str, settings: EngineSpecificSettings) -> None:
        try:
            self._apply_settings(settings)
        except Exception as err:
            self._set_error(str(err))

    def change_rate(self, steps: int = 1) -> bool:
        current = self._current_settings.rate
        new_rate = max(-1, min(current + 0.2 * steps, 1))
        if current == new_rate:
            return False
        try:
            self._ssip_client.set_rate(int(max(-1, min(new_rate, 1)) * 100))
        except Exception as e:
            self._set_error(str(e))
            return False
        self._current_settings = self._current_settings._replace(rate=new_rate)
        return True

    def stop(self) -> None:
        self._current_marked_text = self._last_mark = None
        self._next_cancel_is_for_pause = self._next_begin_is_for_resume = False
        if self._ssip_client is not None:
            try:
                self._ssip_client.stop()
            except Exception as e:
                self._set_error(str(e))

    def speak_simple_text(self, text: str) -> None:
        self.stop()
        self._current_marked_text = self._last_mark = None
        self._speak(prepare_string_for_xml(text))

    def speak_marked_text(self, marked_text: list[str | int]) -> None:
        self.stop()
        text = ''.join(add_markup(marked_text))
        self._current_marked_text = text
        self._last_mark = None
        self._speak(text)

    def __del__(self):
        if self._ssip_client is not None:
            with suppress(Exception):
                self._ssip_client.cancel()
            self._ssip_client.close()
            self._ssip_client = None
    shutdown = __del__

    def _set_state(self, s: QTextToSpeech.State) -> None:
        self._state = s
        self.state_changed.emit(s)

    def _set_error(self, msg: str) -> None:
        self._last_error = msg
        self._set_state(QTextToSpeech.State.Error)

    def _create_ssip_client(self) -> bool:
        try:
            self._ssip_client = SSIPClient('calibre')
            self._ssip_client.set_priority(Priority.TEXT)
            return True
        except SSIPCommunicationError as err:
            ex = err.additional_exception()
            if isinstance(ex, SpawnError):
                self._set_error(_('Could not find speech-dispatcher on your system. Please install it.'))
            else:
                self._set_error(str(err))
        except SpawnError:
            self._set_error(_('Could not find speech-dispatcher on your system. Please install it.'))
        except Exception as err:
            self._set_error(str(err))
        return False

    def _ensure_state(self) -> bool:
        if self._ssip_client is None:
            if not self._create_ssip_client():
                return False
        if self._system_default_output_module is None:
            self._system_default_output_module = self._ssip_client.get_output_module()
            if self._system_default_output_module == '(null)':
                mods = self._ssip_client.list_output_modules()
                if not mods:
                    self._set_error(_(
                        'Speech dispatcher on this system is not configured with any available output modules. Install some output modules first.'))
                    return False
                self._system_default_output_module = mods[0]
        return self._set_use_ssml(True)

    def _set_use_ssml(self, on: bool) -> bool:
        mode = DataMode.SSML if on else DataMode.TEXT
        try:
            self._ssip_client.set_data_mode(mode)
            return True
        except SSIPCommunicationError:
            self._ssip_client.close()
            self._ssip_client = None
            self._set_error(_('Failed to set support for SSML to: {}').format(on))
        return False

    def _apply_settings(self, settings: EngineSpecificSettings) -> bool:
        if not self._ensure_state():
            return False
        self._ssip_client.set_pitch_range(int(max(-1, min(settings.pitch, 1)) * 100))
        self._ssip_client.set_rate(int(max(-1, min(settings.rate, 1)) * 100))
        if settings.volume is not None:
            self._ssip_client.set_volume(-100 + int(max(0, min(settings.volume, 1)) * 200))
        om = settings.output_module or self._system_default_output_module
        self._ssip_client.set_output_module(om)
        if settings.voice_name:
            self._ssip_client.set_synthesis_voice(settings.voice_name)
        self._current_settings = settings
        return True

    def _get_all_voices_for_all_output_modules(self) -> dict[str, Voice]:
        ans = {}
        def v(x) -> Voice:
            name, langcode, variant = x
            return Voice(name, canonicalize_lang(langcode) or 'und', human_name=name, notes=variant)

        if self._ensure_state():
            om = self._ssip_client.get_output_module()
            for omq in self._ssip_client.list_output_modules():
                self._ssip_client.set_output_module(omq)
                ans[omq] = tuple(map(v, self._ssip_client.list_synthesis_voices()))
            self._ssip_client.set_output_module(om)
        return ans

    def _update_status(self, callback_type, index_mark=None):
        event = None
        if callback_type is CallbackType.INDEX_MARK:
            mark = int(index_mark)
            self._last_mark = mark
            self.saying.emit(mark, mark)
        elif callback_type is CallbackType.BEGIN:
            self._status = {'synthesizing': True, 'paused': False}
            self._set_state(QTextToSpeech.State.Speaking)
            self._next_begin_is_for_resume = False
        elif callback_type is CallbackType.END:
            self._status = {'synthesizing': False, 'paused': False}
            self._set_state(QTextToSpeech.State.Ready)
        elif callback_type is CallbackType.CANCEL:
            if self._next_cancel_is_for_pause:
                self._status = {'synthesizing': True, 'paused': True}
                self._set_state(QTextToSpeech.State.Paused)
            else:
                self._status = {'synthesizing': False, 'paused': False}
                self._set_state(QTextToSpeech.State.Ready)
            self._next_cancel_is_for_pause = False
        return event

    def _speak_callback(self, callback_type: CallbackType, index_mark=None):
        self._event_signal.emit(callback_type, index_mark)

    def _speak(self, text: str) -> None:
        if self._ensure_state():
            self._ssip_client.speak(wrap_in_ssml(text), self._speak_callback)
