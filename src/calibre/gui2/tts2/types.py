#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from enum import Enum, auto
from functools import lru_cache
from typing import Literal, NamedTuple

from qt.core import QLocale, QObject, QTextToSpeech, QVoice

from calibre.constants import islinux
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
    has_multiple_output_modules: bool = False
    can_change_rate: bool = True
    can_change_pitch: bool = True
    can_change_volume: bool = True


class Quality(Enum):
    High: int = auto()
    Medium: int = auto()
    Low: int = auto()


class Voice(NamedTuple):
    name: str
    language_code: str

    country_code: str = ''
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
    output_module: str = ''



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
            ans[x] = EngineMetadata(x, TrackingCapability.WordByWord, allows_choosing_audio_device=False, has_multiple_output_modules=True)
    return ans


def create_tts_backend(engine_name: str = '', settings: EngineSpecificSettings = EngineSpecificSettings(), parent: QObject|None = None):
    if engine_name == '' and islinux:
        engine_name = 'speechd'
    if engine_name not in available_engines():
        engine_name = ''
    if engine_name == 'speechd':
        from calibre.gui2.tts2.speechd import SpeechdTTSBackend
        return SpeechdTTSBackend(engine_name, settings, parent)
    from calibre.gui2.tts2.qt import QtTTSBackend
    return QtTTSBackend(engine_name, settings, parent)


def develop(engine_name=''):
    # {{{
    marked_text = [2, 'Demonstration', ' ', 16, 'of', ' ', 19, 'DOCX', ' ', 24, 'support', ' ', 32, 'in', ' ', 35, 'calibre', '\n\t', 44, 'This', ' ', 49, 'document', ' ', 58, 'demonstrates', ' ', 71, 'the', ' ', 75, 'ability', ' ', 83, 'of', ' ', 86, 'the', ' ', 90, 'calibre', ' ', 98, 'DOCX', ' ', 103, 'Input', ' ', 109, 'plugin', ' ', 116, 'to', ' ', 119, 'convert', ' ', 127, 'the', ' ', 131, 'various', ' ', 139, 'typographic', ' ', 151, 'features', ' ', 160, 'in', ' ', 163, 'a', ' ', 165, 'Microsoft', ' ', 175, 'Word', ' ', 180, '(2007', ' ', 186, 'and', ' ', 190, 'newer)', ' ', 197, 'document.', ' ', 207, 'Convert', ' ', 215, 'this', ' ', 220, 'document', ' ', 229, 'to', ' ', 232, 'a', ' ', 234, 'modern', ' ', 241, 'ebook', ' ', 247, 'format,', ' ', 255, 'such', ' ', 260, 'as', ' ', 263, 'AZW3', ' ', 268, 'for', ' ', 272, 'Kindles', ' ', 280, 'or', ' ', 283, 'EPUB', ' ', 288, 'for', ' ', 292, 'other', ' ', 298, 'ebook', ' ', 304, 'readers,', ' ', 313, 'to', ' ', 316, 'see', ' ', 320, 'it', ' ', 323, 'in', ' ', 326, 'action.', '\n\t', 335, 'There', ' ', 341, 'is', ' ', 344, 'support', ' ', 352, 'for', ' ', 356, 'images,', ' ', 364, 'tables,', ' ', 372, 'lists,', ' ', 379, 'footnotes,', ' ', 390, 'endnotes,', ' ', 400, 'links,', ' ', 407, 'dropcaps', ' ', 416, 'and', ' ', 420, 'various', ' ', 428, 'types', ' ', 434, 'of', ' ', 437, 'text', ' ', 442, 'and', ' ', 446, 'paragraph', ' ', 456, 'level', ' ', 462, 'formatting.', '\n\t', 475, 'To', ' ', 478, 'see', ' ', 482, 'the', ' ', 486, 'DOCX', ' ', 491, 'conversion', ' ', 502, 'in', ' ', 505, 'action,', ' ', 513, 'simply', ' ', 520, 'add', ' ', 524, 'this', ' ', 529, 'file', ' ', 534, 'to', ' ', 537, 'calibre', ' ', 545, 'using', ' ', 551, 'the', ' ', 555, '“Add', ' ', 560, 'Books”', ' ', 567, 'button', ' ', 574, 'and', ' ', 578, 'then', ' ', 583, 'click', ' ', 589, '“Convert”.', '  ', 601, 'Set', ' ', 605, 'the', ' ', 609, 'output', ' ', 616, 'format', ' ', 623, 'in', ' ', 626, 'the', ' ', 630, 'top', ' ', 634, 'right', ' ', 640, 'corner', ' ', 647, 'of', ' ', 650, 'the', ' ', 654, 'conversion', ' ', 665, 'dialog', ' ', 672, 'to', ' ', 675, 'EPUB', ' ', 680, 'or', ' ', 683, 'AZW3', ' ', 688, 'and', ' ', 692, 'click', ' ', 698, '“OK”.', '\n\t\xa0\n\t']  # noqa }}}

    from calibre.gui2 import Application
    app = Application([])
    app.shutdown_signal_received.connect(lambda: app.exit(1))
    tts = create_tts_backend(engine_name=engine_name)
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
