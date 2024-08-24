#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from enum import Enum, auto
from functools import lru_cache
from typing import Literal, NamedTuple

from qt.core import QLocale, QTextToSpeech, QVoice

from calibre.utils.localization import canonicalize_lang


class TrackingCapability(Enum):
    NoTracking: int = auto()
    WordByWord: int = auto()
    Sentence: int = auto()


class EngineMetadata(NamedTuple):
    name: Literal['winrt', 'darwin', 'sapi', 'flite', 'speechd']
    tracking_capability: TrackingCapability = TrackingCapability.NoTracking
    allows_choosing_audio_device: bool = True
    can_synthesize_audio_data: bool = True


class Quality(Enum):
    High: int = auto()
    Medium: int = auto()
    Low: int = auto()


class Voice(NamedTuple):
    name: str
    language_code: str
    country_code: str

    human_name: str = ''
    notes: str = ''
    gender: QVoice.Gender = QVoice.Gender.Unknown
    age: QVoice.Age = QVoice.Age.Other
    quality: Quality = Quality.High


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



@lru_cache(2)
def available_engines() -> dict[str, EngineMetadata]:
    ans = {}
    e = QTextToSpeech()

    def qt_engine_metadata(name: str, allows_choosing_audio_device: bool = False) -> EngineMetadata:
        e.setEngine(name)
        cap = e.engineCapabilities()
        return EngineMetadata(
            name, TrackingCapability.WordByWord if cap & QTextToSpeech.Capability.WordByWordProgress else TrackingCapability.NoTracking,
            allows_choosing_audio_device, cap & QTextToSpeech.Capability.Synthesize)

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
            # TODO: Replace this with our own speechd client that supports word tracking
            ans[x] = qt_engine_metadata(x)
    return ans
