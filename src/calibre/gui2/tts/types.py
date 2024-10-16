#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
from contextlib import suppress
from enum import Enum, auto
from functools import lru_cache
from typing import Literal, NamedTuple

from qt.core import QApplication, QLocale, QObject, QTextToSpeech, QVoice, QWidget, pyqtSignal

from calibre.constants import islinux, ismacos, iswindows, piper_cmdline
from calibre.utils.config import JSONConfig
from calibre.utils.config_base import tweaks
from calibre.utils.localization import canonicalize_lang

CONFIG_NAME = 'tts'
TTS_EMBEDED_CONFIG = 'tts-embedded'
# lru_cache doesn't work for this because it returns different results for
# load_config() and load_config(CONFIG_NAME)
conf_cache = {}


def load_config(config_name=CONFIG_NAME) -> JSONConfig:
    if (ans := conf_cache.get(config_name)) is None:
        ans = conf_cache[config_name] = JSONConfig(config_name)
    return ans


class TrackingCapability(Enum):
    NoTracking: int = auto()
    WordByWord: int = auto()
    Sentence: int = auto()


class EngineMetadata(NamedTuple):
    name: Literal['winrt', 'darwin', 'sapi', 'flite', 'speechd', 'piper']
    human_name: str
    description: str
    tracking_capability: TrackingCapability = TrackingCapability.NoTracking
    allows_choosing_audio_device: bool = True
    has_multiple_output_modules: bool = False
    can_synthesize_audio_data: bool = True
    can_change_pitch: bool = True
    can_change_volume: bool = True
    voices_have_quality_metadata: bool = False
    has_managed_voices: bool = False
    has_sentence_delay: bool = False


class Quality(Enum):
    High: int = auto()
    Medium: int = auto()
    Low: int = auto()
    ExtraLow: int = auto()

    @classmethod
    def from_piper_quality(self, x: str) -> 'Quality':
        return {'x_low': Quality.ExtraLow, 'low': Quality.Low, 'medium': Quality.Medium, 'high': Quality.High}[x]

    @property
    def localized_name(self) -> str:
        if self is Quality.Medium:
            return _('Medium quality')
        if self is Quality.Low:
            return _('Low quality')
        if self is Quality.ExtraLow:
            return _('Extra low quality')
        return _('High quality')


class Voice(NamedTuple):
    name: str = ''
    language_code: str = ''

    country_code: str = ''
    human_name: str = ''
    notes: str = ''  # variant from speechd voices
    gender: QVoice.Gender = QVoice.Gender.Unknown
    age: QVoice.Age = QVoice.Age.Other
    quality: Quality = Quality.High

    engine_data: dict[str, str] | None = None

    @property
    def basic_name(self) -> str:
        return self.human_name or self.name or _('System default voice')

    def short_text(self, m: EngineMetadata) -> str:
        ans = self.basic_name
        if self.country_code:
            territory = QLocale.codeToTerritory(self.country_code)
            ans += f' ({QLocale.territoryToString(territory)})'
        if m.voices_have_quality_metadata:
            ans += f' [{self.quality.localized_name}]'
        return ans

    def tooltip(self, m: EngineMetadata) -> str:
        ans = []
        if self.notes:
            ans.append(self.notes)
        if self.age is not QVoice.Age.Other:
            ans.append(_('Age: {}').format(QVoice.ageName(self.age)))
        if self.gender is not QVoice.Gender.Unknown:
            ans.append(_('Gender: {}').format(QVoice.genderName(self.gender)))
        return '\n'.join(ans)

    def sort_key(self) -> tuple[Quality, str]:
        return (self.quality.value, self.basic_name.lower())



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
    sentence_delay: float = 0  # seconds >= 0
    preferred_voices: dict[str, str] | None = None

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
        sentence_delay = 0.
        with suppress(Exception):
            sentence_delay = max(0, float(prefs.get('sentence_delay')))
        with suppress(Exception):
            preferred_voices = prefs.get('preferred_voices')
        return EngineSpecificSettings(
            voice_name=str(prefs.get('voice', '')), output_module=om, sentence_delay=sentence_delay, preferred_voices=preferred_voices,
            audio_device_id=audio_device_id, rate=rate, pitch=pitch, volume=volume, engine_name=engine_name)

    @classmethod
    def create_from_config(cls, engine_name: str, config_name: str = CONFIG_NAME) -> 'EngineSpecificSettings':
        prefs = load_config(config_name)
        val = prefs.get('engines', {}).get(engine_name, {})
        return cls.create_from_prefs(engine_name, val)

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
        if self.sentence_delay:
            ans['sentence_delay'] = self.sentence_delay
        if self.preferred_voices:
            ans['preferred_voices'] = self.preferred_voices
        return ans

    def save_to_config(self, prefs:JSONConfig | None = None, config_name: str = CONFIG_NAME):
        prefs = load_config(config_name) if prefs is None else prefs
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

    def qt_engine_metadata(name: str, human_name: str, desc: str, allows_choosing_audio_device: bool = False) -> EngineMetadata:
        e.setEngine(name)
        cap = int(e.engineCapabilities().value)
        return EngineMetadata(name, human_name, desc,
            tracking_capability=TrackingCapability.WordByWord if cap & int(
                QTextToSpeech.Capability.WordByWordProgress.value) else TrackingCapability.NoTracking,
            allows_choosing_audio_device=allows_choosing_audio_device,
            can_synthesize_audio_data=bool(cap & int(QTextToSpeech.Capability.Synthesize.value)))

    for x in QTextToSpeech.availableEngines():
        if x == 'winrt':
            ans[x] = qt_engine_metadata(x, _('Modern Windows Engine'), _(
                'The "winrt" engine can track the currently spoken word on screen. Additional voices for it are available from Microsoft.'
                ), True)
        elif x == 'darwin':
            ans[x] = qt_engine_metadata(x, _('macOS Engine'), _(
                'The "darwin" engine can track the currently spoken word on screen. Additional voices for it are available from Apple.'
            ))
        elif x == 'sapi':
            ans[x] = qt_engine_metadata(x, _('Legacy Windows Engine'), _(
                'The "sapi" engine can track the currently spoken word on screen. It is no longer supported by Microsoft.'
            ))
        elif x == 'macos':
            # this is slated for removal in Qt 6.8 so skip it
            continue
        elif x == 'flite':
            ans[x] = qt_engine_metadata(x, _('The "flite" Engine'), _(
                'The "flite" engine can track the currently spoken word on screen.'
            ), True)
        elif x == 'speechd':
            continue
    if piper_cmdline():
        ans['piper'] = EngineMetadata('piper', _('The Piper Neural Engine'), _(
            'The "piper" engine can track the currently spoken sentence on screen. It uses a neural network '
            'for natural sounding voices. The neural network is run locally on your computer, it is fairly resource intensive to run.'
        ), TrackingCapability.Sentence, can_change_pitch=False, voices_have_quality_metadata=True, has_managed_voices=True,
        has_sentence_delay=True)
    if islinux:
        try:
            from speechd.paths import SPD_SPAWN_CMD
        except ImportError:
            pass
        else:
            cmd = os.getenv("SPEECHD_CMD", SPD_SPAWN_CMD)
            if cmd and os.access(cmd, os.X_OK) and os.path.isfile(cmd):
                ans['speechd'] = EngineMetadata('speechd', _('The Speech Dispatcher Engine'), _(
                    'The "speechd" engine can usually track the currently spoken word on screen, however, it depends on the'
                    ' underlying output module. The default espeak output module does support it.'
                ), TrackingCapability.WordByWord, allows_choosing_audio_device=False, has_multiple_output_modules=True)

    return ans


def default_engine_name() -> str:
    if 'piper' in available_engines():
        return 'piper'
    if iswindows:
        return 'sapi' if tweaks.get('prefer_winsapi') else 'winrt'
    if ismacos:
        return 'darwin'
    if 'speechd' in available_engines():
        return 'speechd'
    return 'flite'


def widget_parent(p: QObject) -> QWidget | None:
    while p is not None and not isinstance(p, QWidget):
        p = p.parent()
    return p


class TTSBackend(QObject):
    saying = pyqtSignal(int, int)  # offset, length
    state_changed = pyqtSignal(QTextToSpeech.State)
    available_voices: dict[str, tuple[Voice, ...]] = {}
    engine_name: str = ''
    default_output_module: str = ''
    filler_char: str = ' '

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

    def reload_after_configure(self) -> None:
        raise NotImplementedError()

    def validate_settings(self, s: EngineSpecificSettings, parent: QWidget | None) -> bool:
        return True

    def is_voice_downloaded(self, v: Voice) -> bool:
        return True

    def delete_voice(self, v: Voice) -> None:
        pass

    def download_voice(self, v: Voice) -> None:
        pass


engine_instances: dict[str, TTSBackend] = {}


def create_tts_backend(force_engine: str | None = None, config_name: str = CONFIG_NAME) -> TTSBackend:
    if not available_engines():
        raise OSError('There are no available TTS engines. Install a TTS engine before trying to use Read Aloud, such as flite or speech-dispatcher')
    prefs = load_config(config_name)
    engine_name = prefs.get('engine', '') if force_engine is None else force_engine
    engine_name = engine_name or default_engine_name()
    if engine_name not in available_engines():
        engine_name = default_engine_name()
    if engine_name == 'piper':
        if engine_name not in engine_instances:
            from calibre.gui2.tts.piper import Piper
            engine_instances[engine_name] = Piper(engine_name, QApplication.instance())
        ans = engine_instances[engine_name]
    elif engine_name == 'speechd':
        if engine_name not in engine_instances:
            from calibre.gui2.tts.speechd import SpeechdTTSBackend
            engine_instances[engine_name] = SpeechdTTSBackend(engine_name, QApplication.instance())
        ans = engine_instances[engine_name]
    else:
        if 'qt' not in engine_instances:
            # Bad things happen with more than one QTextToSpeech instance
            from calibre.gui2.tts.qt import QtTTSBackend
            engine_instances['qt'] = QtTTSBackend(engine_name if engine_name in available_engines() else '', QApplication.instance())
        ans = engine_instances['qt']
        if ans.engine_name != engine_name:
            ans._qt_reload_after_configure(engine_name if engine_name in available_engines() else '')
    return ans
