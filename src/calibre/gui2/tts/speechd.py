#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import atexit

from qt.core import QObject, Qt, QTextToSpeech, pyqtSignal
from speechd.client import CallbackType, DataMode, Priority, SpawnError, SSIPClient, SSIPCommunicationError

from calibre import prepare_string_for_xml
from calibre.gui2.tts.types import EngineSpecificSettings, TTSBackend, Voice
from calibre.spell.break_iterator import split_into_words_and_positions
from calibre.utils.localization import canonicalize_lang

MARK_TEMPLATE = '<mark name="{}"/>'


def mark_words(text: str, lang: str) -> str:
    ans = []
    pos = 0

    def a(x):
        ans.append(prepare_string_for_xml(x))

    for offset, sz in split_into_words_and_positions(text, lang):
        if offset > pos:
            a(text[pos:offset])
        ans.append(MARK_TEMPLATE.format(f'{offset}:{sz}'))
        a(text[offset:offset+sz])
        pos = offset + sz
    return ''.join(ans)


def wrap_in_ssml(text):
    return ('<?xml version="1.0"?>\n<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"><s>' +
            text + '</s></speak>')


class SpeechdTTSBackend(TTSBackend):

    saying = pyqtSignal(int, int)
    state_changed = pyqtSignal(QTextToSpeech.State)
    engine_name = 'speechd'

    _event_signal = pyqtSignal(object, object)

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)
        self._last_error = ''
        self._state = QTextToSpeech.State.Ready
        self._voices = None
        self._system_default_output_module = None
        self._status = {'synthesizing': False, 'paused': False}
        self._ssip_client: SSIPClient | None = None
        self._voice_lang = 'en'
        self._last_mark = self._last_text = ''
        self._next_cancel_is_for_pause = False
        self._event_signal.connect(self._update_status, type=Qt.ConnectionType.QueuedConnection)
        self._apply_settings(EngineSpecificSettings.create_from_config(self.engine_name))
        atexit.register(self.shutdown)

    @property
    def default_output_module(self) -> str:
        if self._ensure_state():
            return self._system_default_output_module
        return ''

    @property
    def available_voices(self) -> dict[str, tuple[Voice, ...]]:
       if self._voices is None:
            try:
                self._voices = self._get_all_voices_for_all_output_modules()
            except Exception as e:
                self._set_error(str(e))
       return self._voices or {}

    def stop(self) -> None:
        self._last_mark = self._last_text = ''
        if self._ssip_client is not None:
            if self._status['paused'] and self._status['synthesizing']:
                self._status = {'synthesizing': False, 'paused': False}
                self._set_state(QTextToSpeech.State.Ready)
            else:
                try:
                    self._ssip_client.stop()
                except Exception as e:
                    self._set_error(str(e))

    def say(self, text: str) -> None:
        self.stop()
        self._speak(mark_words(text, self._voice_lang))

    def error_message(self) -> str:
        return self._last_error

    def pause(self) -> None:
        if self._ssip_client is not None and self._status['synthesizing'] and not self._status['paused']:
            try:
                self._ssip_client.stop()
                self._next_cancel_is_for_pause = True
            except Exception as e:
                self._set_error(str(e))

    def resume(self) -> None:
        if self._ssip_client is not None and self._status['synthesizing'] and self._status['paused']:
            text = self._last_text
            idx = text.find(self._last_mark)
            if idx > -1:
                text = text[idx:]
            self._speak(text)

    def reload_after_configure(self) -> None:
        self._apply_settings(EngineSpecificSettings.create_from_config(self.engine_name))

    def shutdown(self):
        if self._ssip_client is not None:
            try:
                self._ssip_client.cancel()
            except Exception:
                pass
            try:
                self._ssip_client.close()
            except Exception:
                pass
            self._ssip_client = None

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
        try:
            om = settings.output_module or self._system_default_output_module
            self._ssip_client.set_output_module(om)
            if settings.voice_name:
                for v in self.available_voices[om]:
                    if v.name == settings.voice_name:
                        self._voice_lang = v.language_code
                        break
                self._ssip_client.set_synthesis_voice(settings.voice_name)
            else:
                self._voice_lang = self.available_voices[om][0].language_code
            self._ssip_client.set_pitch_range(int(max(-1, min(settings.pitch, 1)) * 100))
            self._ssip_client.set_rate(int(max(-1, min(settings.rate, 1)) * 100))
            if settings.volume is not None:
                self._ssip_client.set_volume(-100 + int(max(0, min(settings.volume, 1)) * 200))
            return True
        except Exception as e:
            self._set_error(str(e))
            return False

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
            pos, sep, length = index_mark.partition(':')
            self._last_mark = MARK_TEMPLATE.format(index_mark)
            self.saying.emit(int(pos), int(length))
        elif callback_type is CallbackType.BEGIN:
            self._status = {'synthesizing': True, 'paused': False}
            self._set_state(QTextToSpeech.State.Speaking)
        elif callback_type is CallbackType.END:
            self._status = {'synthesizing': False, 'paused': False}
            self._set_state(QTextToSpeech.State.Ready)
        elif callback_type is CallbackType.CANCEL:
            if self._next_cancel_is_for_pause:
                self._status = {'synthesizing': True, 'paused': True}
                self._set_state(QTextToSpeech.State.Paused)
                self._next_cancel_is_for_pause = False
            else:
                self._status = {'synthesizing': False, 'paused': False}
                self._set_state(QTextToSpeech.State.Ready)
        return event

    def _speak_callback(self, callback_type: CallbackType, index_mark=None):
        self._event_signal.emit(callback_type, index_mark)

    def _speak(self, text: str) -> None:
        if self._ensure_state():
            self._last_text = text
            self._last_mark = ''
            try:
                self._ssip_client.speak(wrap_in_ssml(text), self._speak_callback)
            except Exception as e:
                self._set_error(str(e))
