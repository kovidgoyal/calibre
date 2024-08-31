#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
from contextlib import suppress
from enum import Enum, auto
from functools import lru_cache
from typing import Literal, NamedTuple

from qt.core import QLocale, QObject, QTextToSpeech, QVoice, pyqtSignal

from calibre.constants import islinux, ismacos, iswindows
from calibre.utils.config import JSONConfig
from calibre.utils.config_base import tweaks
from calibre.utils.localization import canonicalize_lang

CONFIG_NAME = 'tts'

@lru_cache(2)
def load_config() -> JSONConfig:
    return JSONConfig(CONFIG_NAME)


class TrackingCapability(Enum):
    NoTracking: int = auto()
    WordByWord: int = auto()
    Sentence: int = auto()


class EngineMetadata(NamedTuple):
    name: Literal['winrt', 'darwin', 'sapi', 'flite', 'speechd']
    tracking_capability: TrackingCapability = TrackingCapability.NoTracking
    allows_choosing_audio_device: bool = True
    has_multiple_output_modules: bool = False
    can_synthesize_audio_data: bool = True
    can_change_pitch: bool = True
    can_change_volume: bool = True
    voices_have_quality_metadata: bool = False


class Quality(Enum):
    High: int = auto()
    Medium: int = auto()
    Low: int = auto()


class Voice(NamedTuple):
    name: str = ''
    language_code: str = ''

    country_code: str = ''
    human_name: str = ''
    notes: str = ''  # variant from speechd voices, or notes from piper voices
    gender: QVoice.Gender = QVoice.Gender.Unknown
    age: QVoice.Age = QVoice.Age.Other
    quality: Quality = Quality.High

    @property
    def short_text(self) -> str:
        return self.human_name or self.name or _('System default voice')

    def sort_key(self) -> tuple[Quality, str]:
        return (self.quality, self.short_text.lower())


def qvoice_to_voice(v: QVoice) -> QVoice:
    lang = canonicalize_lang(QLocale.languageToCode(v.language())) or 'und'
    country = QLocale.territoryToString(v.locale().territory())
    return Voice(v.name(), lang, country, gender=v.gender(), age=v.age())


class AudioDeviceId(NamedTuple):
    id: bytes
    description: str


class EngineSpecificSettings(NamedTuple):
    audio_device_id: AudioDeviceId | None = None
    voice_name: str = ''
    rate: float = 0  # -1 to 1 0 is normal speech
    pitch: float = 0  # -1 to 1 0 is normal speech
    volume: float | None = None  # 0 to 1, None is platform default volume
    output_module: str = ''
    engine_name: str = ''

    @classmethod
    def create_from_prefs(cls, engine_name: str, prefs: dict[str, object]) -> 'EngineSpecificSettings':
        adev = prefs.get('audio_device_id')
        audio_device_id = None
        if adev:
            with suppress(Exception):
                aid = bytes.fromhex(adev['id'])
                description = adev['description']
                audio_device_id = AudioDeviceId(aid, description)
        rate = 0
        with suppress(Exception):
            rate = max(-1, min(float(prefs.get('rate')), 1))
        pitch = 0
        with suppress(Exception):
            pitch = max(-1, min(float(prefs.get('pitch')), 1))
        volume = None
        with suppress(Exception):
            volume = max(0, min(float(prefs.get('volume')), 1))
        om = str(prefs.get('output_module', ''))
        return EngineSpecificSettings(
            voice_name=str(prefs.get('voice', '')), output_module=om,
            audio_device_id=audio_device_id, rate=rate, pitch=pitch, volume=volume, engine_name=engine_name)

    @classmethod
    def create_from_config(cls, engine_name: str) -> 'EngineSpecificSettings':
        prefs = load_config().get('engines', {}).get(engine_name, {})
        return cls.create_from_prefs(engine_name, prefs)

    @property
    def as_dict(self) -> dict[str, object]:
        ans = {}
        if self.audio_device_id:
            ans['audio_device_id'] = {'id': self.audio_device_id.id.hex(), 'description': self.audio_device_id.description}
        if self.voice_name:
            ans['voice'] = self.voice_name
        if self.rate:
            ans['rate'] = self.rate
        if self.pitch:
            ans['pitch'] = self.pitch
        if self.volume is not None:
            ans['volume'] = self.volume
        if self.output_module:
            ans['output_module'] = self.output_module
        return ans

    def save_to_config(self, prefs:JSONConfig | None = None):
        prefs = prefs or load_config()
        val = self.as_dict
        engines = prefs.get('engines', {})
        if not val:
            engines.pop(self.engine_name, None)
        else:
            engines[self.engine_name] = val
        prefs['engines'] = engines


@lru_cache(2)
def available_engines() -> dict[str, EngineMetadata]:
    ans = {}
    e = QTextToSpeech()

    def qt_engine_metadata(name: str, allows_choosing_audio_device: bool = False) -> EngineMetadata:
        e.setEngine(name)
        cap = int(e.engineCapabilities().value)
        return EngineMetadata(name,
            tracking_capability=TrackingCapability.WordByWord if cap & int(
                QTextToSpeech.Capability.WordByWordProgress.value) else TrackingCapability.NoTracking,
            allows_choosing_audio_device=allows_choosing_audio_device,
            can_synthesize_audio_data=bool(cap & int(QTextToSpeech.Capability.Synthesize.value)))

    for x in QTextToSpeech.availableEngines():
        if x == 'winrt':
            ans[x] = qt_engine_metadata(x, True)
        elif x == 'darwin':
            ans[x] = qt_engine_metadata(x)
        elif x == 'sapi':
            ans[x] = qt_engine_metadata(x)
        elif x == 'macos':
            # this is slated for removal in Qt 6.8 so skip it
            continue
        elif x == 'flite':
            ans[x] = qt_engine_metadata(x, True)
        elif x == 'speechd':
            continue
    if islinux:
        from speechd.paths import SPD_SPAWN_CMD
        cmd = os.getenv("SPEECHD_CMD", SPD_SPAWN_CMD)
        if cmd and os.access(cmd, os.X_OK) and os.path.isfile(cmd):
            ans['speechd'] = EngineMetadata('speechd', TrackingCapability.WordByWord, allows_choosing_audio_device=False, has_multiple_output_modules=True)
    return ans


def default_engine_name() -> str:
    if iswindows:
        return 'sapi' if tweaks.get('prefer_winsapi') else 'winrt'
    if ismacos:
        return 'darwin'
    return 'speechd'


class TTSBackend(QObject):
    saying = pyqtSignal(int, int)  # offset, length
    state_changed = pyqtSignal(QTextToSpeech.State)
    available_voices: dict[str, tuple[Voice, ...]] = {}
    engine_name: str = ''
    default_output_module: str = ''

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)

    def pause(self) -> None:
        raise NotImplementedError()

    def resume(self) -> None:
        raise NotImplementedError()

    def stop(self) -> None:
        raise NotImplementedError()

    def say(self, text: str) -> None:
        raise NotImplementedError()

    def error_message(self) -> str:
        raise NotImplementedError()


def create_tts_backend(parent: QObject|None = None, force_engine: str | None = None) -> TTSBackend:
    prefs = load_config()
    engine_name = prefs.get('engine', '') if force_engine is None else force_engine
    engine_name = engine_name or default_engine_name()
    if engine_name not in available_engines():
        engine_name = default_engine_name()

    if engine_name == 'speechd':
        from calibre.gui2.tts2.speechd import SpeechdTTSBackend
        ans = SpeechdTTSBackend(engine_name, parent)
    else:
        if engine_name not in available_engines():
            engine_name = ''  # let Qt pick the engine
        from calibre.gui2.tts2.qt import QtTTSBackend
        ans = QtTTSBackend(engine_name, parent)
    return ans


if __name__ == '__main__':
    develop()
