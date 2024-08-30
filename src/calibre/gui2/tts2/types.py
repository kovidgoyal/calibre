#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
from contextlib import suppress
from enum import Enum, auto
from functools import lru_cache
from typing import Literal, NamedTuple

from qt.core import QLocale, QObject, QTextToSpeech, QVoice

from calibre.constants import islinux, ismacos, iswindows
from calibre.utils.config import JSONConfig
from calibre.utils.config_base import tweaks
from calibre.utils.localization import canonicalize_lang

CONFIG_NAME = 'tts'

@lru_cache(2)
def load_config():
    return JSONConfig(CONFIG_NAME)


class TrackingCapability(Enum):
    NoTracking: int = auto()
    WordByWord: int = auto()
    Sentence: int = auto()


class EngineMetadata(NamedTuple):
    name: Literal['winrt', 'darwin', 'sapi', 'flite', 'speechd']
    tracking_capability: TrackingCapability = TrackingCapability.NoTracking
    allows_choosing_audio_device: bool = True
    can_synthesize_audio_data: bool = True
    has_multiple_output_modules: bool = False
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
        voice = str(prefs.get('voice_map', {}).get(om, ''))
        return EngineSpecificSettings(
            voice_name=voice, output_module=om,
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
            ans['voice_map'] = { self.output_module: self.voice_name }
        if self.rate:
            ans['rate'] = self.rate
        if self.pitch:
            ans['pitch'] = self.pitch
        if self.volume is not None:
            ans['volume'] = self.volume
        if self.output_module:
            ans['output_module'] = self.output_module
        return ans

    def save_to_config(self):
        prefs = load_config()
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
            TrackingCapability.WordByWord if cap & int(QTextToSpeech.Capability.WordByWordProgress.value) else TrackingCapability.NoTracking,
            allows_choosing_audio_device, bool(cap & int(QTextToSpeech.Capability.Synthesize.value)))

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


def create_tts_backend(parent: QObject|None = None, force_engine: str | None = None):
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


def develop(engine_name=''):
    # {{{
    marked_text = [2, 'Demonstration', ' ', 16, 'of', ' ', 19, 'DOCX', ' ', 24, 'support', ' ', 32, 'in', ' ', 35, 'calibre', '\n\t', 44, 'This', ' ', 49, 'document', ' ', 58, 'demonstrates', ' ', 71, 'the', ' ', 75, 'ability', ' ', 83, 'of', ' ', 86, 'the', ' ', 90, 'calibre', ' ', 98, 'DOCX', ' ', 103, 'Input', ' ', 109, 'plugin', ' ', 116, 'to', ' ', 119, 'convert', ' ', 127, 'the', ' ', 131, 'various', ' ', 139, 'typographic', ' ', 151, 'features', ' ', 160, 'in', ' ', 163, 'a', ' ', 165, 'Microsoft', ' ', 175, 'Word', ' ', 180, '(2007', ' ', 186, 'and', ' ', 190, 'newer)', ' ', 197, 'document.', ' ', 207, 'Convert', ' ', 215, 'this', ' ', 220, 'document', ' ', 229, 'to', ' ', 232, 'a', ' ', 234, 'modern', ' ', 241, 'ebook', ' ', 247, 'format,', ' ', 255, 'such', ' ', 260, 'as', ' ', 263, 'AZW3', ' ', 268, 'for', ' ', 272, 'Kindles', ' ', 280, 'or', ' ', 283, 'EPUB', ' ', 288, 'for', ' ', 292, 'other', ' ', 298, 'ebook', ' ', 304, 'readers,', ' ', 313, 'to', ' ', 316, 'see', ' ', 320, 'it', ' ', 323, 'in', ' ', 326, 'action.', '\n\t', 335, 'There', ' ', 341, 'is', ' ', 344, 'support', ' ', 352, 'for', ' ', 356, 'images,', ' ', 364, 'tables,', ' ', 372, 'lists,', ' ', 379, 'footnotes,', ' ', 390, 'endnotes,', ' ', 400, 'links,', ' ', 407, 'dropcaps', ' ', 416, 'and', ' ', 420, 'various', ' ', 428, 'types', ' ', 434, 'of', ' ', 437, 'text', ' ', 442, 'and', ' ', 446, 'paragraph', ' ', 456, 'level', ' ', 462, 'formatting.', '\n\t', 475, 'To', ' ', 478, 'see', ' ', 482, 'the', ' ', 486, 'DOCX', ' ', 491, 'conversion', ' ', 502, 'in', ' ', 505, 'action,', ' ', 513, 'simply', ' ', 520, 'add', ' ', 524, 'this', ' ', 529, 'file', ' ', 534, 'to', ' ', 537, 'calibre', ' ', 545, 'using', ' ', 551, 'the', ' ', 555, '“Add', ' ', 560, 'Books”', ' ', 567, 'button', ' ', 574, 'and', ' ', 578, 'then', ' ', 583, 'click', ' ', 589, '“Convert”.', '  ', 601, 'Set', ' ', 605, 'the', ' ', 609, 'output', ' ', 616, 'format', ' ', 623, 'in', ' ', 626, 'the', ' ', 630, 'top', ' ', 634, 'right', ' ', 640, 'corner', ' ', 647, 'of', ' ', 650, 'the', ' ', 654, 'conversion', ' ', 665, 'dialog', ' ', 672, 'to', ' ', 675, 'EPUB', ' ', 680, 'or', ' ', 683, 'AZW3', ' ', 688, 'and', ' ', 692, 'click', ' ', 698, '“OK”.', '\n\t\xa0\n\t']  # noqa }}}

    from calibre.gui2 import Application
    app = Application([])
    app.shutdown_signal_received.connect(lambda: app.exit(1))
    tts = create_tts_backend(force_engine=engine_name)
    speech_started = False

    def print_saying(s, e):
        bits = []
        in_region = False
        for x in marked_text:
            if isinstance(x, int):
                if in_region:
                    if x >= e:
                        break
                else:
                    if x == s:
                        in_region = True
                    elif x > e:
                        break
            elif in_region:
                bits.append(x)
        print('Saying:', repr(''.join(bits)))

    import sys

    def state_changed(state):
        nonlocal speech_started
        print('State changed:', state)
        if state == QTextToSpeech.State.Speaking:
            speech_started = True
        elif state == QTextToSpeech.State.Error:
            print(tts.error_message(), file=sys.stderr)
            app.exit(1)
        elif state == QTextToSpeech.State.Ready:
            if speech_started:
                app.quit()
    tts.saying.connect(print_saying)
    tts.state_changed.connect(state_changed)
    tts.speak_marked_text(marked_text)
    app.exec()


if __name__ == '__main__':
    develop()
