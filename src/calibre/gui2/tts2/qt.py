#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from typing import NamedTuple

from qt.core import QMediaDevices, QObject, QTextToSpeech, pyqtSignal

from calibre.constants import islinux
from calibre.gui2.tts2.types import EngineSpecificSettings


class Pos(NamedTuple):
    mark: int
    offset_in_text: int


class Tracker:

    def reset(self) -> None:
        self.positions: list[Pos] = []
        self.last_pos: int = 0

    def parse_marked_text(self, marked_text: list[str | int]) -> str:
        self.reset()
        text: list[str] = []
        text_len: int = 0
        for x in marked_text:
            if isinstance(x, int):
                self.positions.append(Pos(x, text_len))
            else:
                text_len += len(x)
                text.append(x)
        return ''.join(text)

    def mark_word(self, start: int, length: int) -> tuple[int, int] | None:
        end = start + length
        matches: list[Pos] = []
        while True:
            if self.last_pos >= len(self.positions):
                break
            pos = self.positions[self.last_pos]
            if start <= pos.offset_in_text < end:
                matches.append(pos)
            elif pos.offset_in_text >= end:
                break
            self.last_pos += 1
        if matches:
            return matches[0].mark, matches[-1].mark
        return None


class QtTTSBackend(QObject):

    saying = pyqtSignal(int, int)
    state_changed = pyqtSignal(QTextToSpeech.State)

    def __init__(self, engine_name: str = '', settings: EngineSpecificSettings = EngineSpecificSettings(), parent: QObject|None = None):
        super().__init__(parent)
        self.tracker = Tracker()
        self.apply_settings(engine_name, settings)

    def apply_settings(self, engine_name: str, settings: EngineSpecificSettings) -> None:
        s = {}
        if settings.audio_device_id:
            for x in QMediaDevices.audioOutputs():
                if bytes(x.id) == settings.audio_device_id.id:
                    s['audioDevice'] = x
                    break
        self.tts = QTextToSpeech(engine_name, s, self)
        self.tts.setRate(max(-1, min(float(settings.rate), 1)))
        self.tts.setPitch(max(-1, min(float(settings.pitch), 1)))
        if settings.volume is not None:
            self.tts.setVolume(max(0, min(float(settings.volume), 1)))
        if settings.voice_name:
            for v in self.availableVoices():
                if v.name() == settings.voice_name:
                    self.setVoice(v)
                    break
        self.tts.sayingWord.connect(self._saying_word)
        self.tts.stateChanged.connect(self.state_changed.emit)

    def shutdown(self) -> None:
        self.tts.stop(QTextToSpeech.BoundaryHint.Immediate)

    def speak_simple_text(self, text: str) -> None:
        self.tts.say(text)

    def pause(self) -> None:
        self.tts.pause()

    def resume(self) -> None:
        self.tts.resume()

    def stop(self) -> None:
        self.tts.stop()

    def resume_after_configure(self) -> None:
        raise NotImplementedError('TODO: Implement me')

    def speak_marked_text(self, marked_text: list[str | int]) -> None:
        self.tts.say(self.tracker.parse_marked_text(marked_text))

    def error_message(self) -> str:
        return self.tts.errorString()

    def _saying_word(self, word: str, utterance_id: int, start: int, length: int) -> None:
        x = self.tracker.mark_word(start, length)
        if x is not None:
            self.saying.emit(x[0], x[1])


def develop():
    # {{{
    marked_text = [2, 'Demonstration', ' ', 16, 'of', ' ', 19, 'DOCX', ' ', 24, 'support', ' ', 32, 'in', ' ', 35, 'calibre', '\n\t', 44, 'This', ' ', 49, 'document', ' ', 58, 'demonstrates', ' ', 71, 'the', ' ', 75, 'ability', ' ', 83, 'of', ' ', 86, 'the', ' ', 90, 'calibre', ' ', 98, 'DOCX', ' ', 103, 'Input', ' ', 109, 'plugin', ' ', 116, 'to', ' ', 119, 'convert', ' ', 127, 'the', ' ', 131, 'various', ' ', 139, 'typographic', ' ', 151, 'features', ' ', 160, 'in', ' ', 163, 'a', ' ', 165, 'Microsoft', ' ', 175, 'Word', ' ', 180, '(2007', ' ', 186, 'and', ' ', 190, 'newer)', ' ', 197, 'document.', ' ', 207, 'Convert', ' ', 215, 'this', ' ', 220, 'document', ' ', 229, 'to', ' ', 232, 'a', ' ', 234, 'modern', ' ', 241, 'ebook', ' ', 247, 'format,', ' ', 255, 'such', ' ', 260, 'as', ' ', 263, 'AZW3', ' ', 268, 'for', ' ', 272, 'Kindles', ' ', 280, 'or', ' ', 283, 'EPUB', ' ', 288, 'for', ' ', 292, 'other', ' ', 298, 'ebook', ' ', 304, 'readers,', ' ', 313, 'to', ' ', 316, 'see', ' ', 320, 'it', ' ', 323, 'in', ' ', 326, 'action.', '\n\t', 335, 'There', ' ', 341, 'is', ' ', 344, 'support', ' ', 352, 'for', ' ', 356, 'images,', ' ', 364, 'tables,', ' ', 372, 'lists,', ' ', 379, 'footnotes,', ' ', 390, 'endnotes,', ' ', 400, 'links,', ' ', 407, 'dropcaps', ' ', 416, 'and', ' ', 420, 'various', ' ', 428, 'types', ' ', 434, 'of', ' ', 437, 'text', ' ', 442, 'and', ' ', 446, 'paragraph', ' ', 456, 'level', ' ', 462, 'formatting.', '\n\t', 475, 'To', ' ', 478, 'see', ' ', 482, 'the', ' ', 486, 'DOCX', ' ', 491, 'conversion', ' ', 502, 'in', ' ', 505, 'action,', ' ', 513, 'simply', ' ', 520, 'add', ' ', 524, 'this', ' ', 529, 'file', ' ', 534, 'to', ' ', 537, 'calibre', ' ', 545, 'using', ' ', 551, 'the', ' ', 555, '“Add', ' ', 560, 'Books”', ' ', 567, 'button', ' ', 574, 'and', ' ', 578, 'then', ' ', 583, 'click', ' ', 589, '“Convert”.', '  ', 601, 'Set', ' ', 605, 'the', ' ', 609, 'output', ' ', 616, 'format', ' ', 623, 'in', ' ', 626, 'the', ' ', 630, 'top', ' ', 634, 'right', ' ', 640, 'corner', ' ', 647, 'of', ' ', 650, 'the', ' ', 654, 'conversion', ' ', 665, 'dialog', ' ', 672, 'to', ' ', 675, 'EPUB', ' ', 680, 'or', ' ', 683, 'AZW3', ' ', 688, 'and', ' ', 692, 'click', ' ', 698, '“OK”.', '\n\t\xa0\n\t']  # noqa }}}

    from calibre.gui2 import Application
    app = Application([])
    app.shutdown_signal_received.connect(lambda: app.exit(1))
    engine_name = ''
    if islinux:
        engine_name = 'flite'
    tts = QtTTSBackend(engine_name=engine_name)
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
