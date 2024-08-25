#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QObject, QTextToSpeech, pyqtSignal
from speechd.client import DataMode, Priority, SpawnError, SSIPClient, SSIPCommunicationError

from calibre.gui2.tts2.types import EngineSpecificSettings, Voice
from calibre.utils.localization import canonicalize_lang


class SpeechdTTSBackend(QObject):

    saying = pyqtSignal(int, int)
    state_changed = pyqtSignal(QTextToSpeech.State)

    def __init__(self, engine_name: str = '', settings: EngineSpecificSettings = EngineSpecificSettings(), parent: QObject|None = None):
        super().__init__(parent)
        self._last_error = ''
        self._state = QTextToSpeech.State.Ready
        self._voices = None
        self._system_default_output_module = None
        self.ssip_client: SSIPClient | None = None
        self.apply_settings(engine_name, settings)

    @property
    def available_voices(self) -> dict[str, tuple[Voice, ...]]:
        if self._voices is None:
            def v(x) -> Voice:
                name, langcode, variant = x
                return Voice(name, canonicalize_lang(langcode) or 'und', human_name=name, notes=variant)

            if self._ensure_state():
                ans = {}
                try:
                    om = self.ssip_client.get_output_module()
                    for omq in self.ssip_client.list_output_modules():
                        self.ssip_client.set_output_module(omq)
                        ans[omq] = tuple(map(v, self.ssip_client.list_synthesis_voices()))
                    self.ssip_client.set_output_module(om)
                    self._voices = ans
                except Exception as e:
                    self._set_error(str(e))
        return self._voices or {}

    def apply_settings(self, engine_name: str, settings: EngineSpecificSettings) -> None:
        try:
            self._apply_settings(settings)
        except Exception as err:
            self._set_error(str(err))

    def _set_error(self, msg: str) -> None:
        self._last_error = msg
        self._set_state(QTextToSpeech.Error)

    def _create_ssip_client(self) -> bool:
        try:
            self.ssip_client = SSIPClient('calibre')
            self.ssip_client.set_priority(Priority.TEXT)
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
        if self.ssip_client is None:
            if not self.create_ssip_client():
                return False
        if self._system_default_output_module is None:
            self._system_default_output_module = self.ssip_client.get_output_module()
            if self._system_default_output_module == '(null)':
                mods = self.ssip_client.list_output_modules()
                if not mods:
                    self._last_error = _('Speech dispatcher on this system is not configured with any available voices. Install some voices first.')
                    return False
                self._system_default_output_module = mods[0]
        self._set_use_ssml(True)

    def _set_use_ssml(self, on: bool) -> bool:
        mode = DataMode.SSML if on else DataMode.TEXT
        try:
            self.ssip_client.set_data_mode(mode)
            return True
        except SSIPCommunicationError:
            self.ssip_client.close()
            self.ssip_client = None
            self._set_error(_('Failed to set support for SSML to: {}').format(on))

    def _apply_settings(self, settings: EngineSpecificSettings) -> bool:
        if not self._ensure_state():
            return False
        self.ssip_client.set_pitch_range(int(max(-1, min(settings.pitch, 1)) * 100))
        self.ssip_client.set_rate(int(max(-1, min(settings.rate, 1)) * 100))
        if settings.volume is not None:
            self.ssip_client.set_volume(-100 + int(max(0, min(settings.volume, 1)) * 200))
        om = settings.output_module or self._system_default_output_module
        self.ssip_client.set_output_module(om)
        if settings.voice_name:
            self.ssip_client.set_synthesis_voice(settings.voice_name)
        return True
