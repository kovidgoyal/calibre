#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import json
import os
import re
import sys
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from itertools import count
from time import monotonic

from qt.core import QApplication, QAudio, QAudioFormat, QAudioSink, QByteArray, QIODevice, QIODeviceBase, QObject, QProcess, Qt, QTextToSpeech, pyqtSignal, sip

from calibre.constants import bundled_binaries_dir, get_windows_username, is_debugging, iswindows
from calibre.gui2.tts2.types import TTSBackend
from calibre.ptempfile import base_dir
from calibre.spell.break_iterator import sentence_positions, split_into_words_and_positions


@lru_cache(2)
def sentinel_path() -> str:
    fname = f'piper-sentinel-{os.getpid()}'
    if iswindows:
        fname += f'-{get_windows_username()}'
    else:
        fname += f'-{os.geteuid()}'
    return os.path.join(base_dir(), fname)


def debug(*a, **kw):
    if is_debugging():
        if not hasattr(debug, 'first'):
            debug.first = monotonic()
        kw['end'] = kw.get('end', '\r\n')
        print(f'[{monotonic() - debug.first:.2f}]', *a, **kw)


@lru_cache(2)
def piper_cmdline() -> tuple[str, ...]:
    ext = '.exe' if iswindows else ''
    if bbd := bundled_binaries_dir():
        # TODO: Add path to espeak-ng-data with --
        return (os.path.join(bbd, 'piper' + ext),)
    import shutil
    exe = shutil.which('piper-tts')
    if exe:
        return (exe,)
    return ()


@dataclass
class Utterance:
    id: int
    start: int
    length: int
    payload_size: int
    left_to_write: QByteArray
    audio_data: QByteArray

    started: bool = False
    synthesized: bool = False


PARAGRAPH_SEPARATOR = '\u2029'
UTTERANCE_SEPARATOR = b'\n'


class UtteranceAudioQueue(QIODevice):

    saying = pyqtSignal(int, int)
    update_status = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.utterances: deque[Utterance] = deque()
        self.current_audio_data = QByteArray()
        self.audio_state = QAudio.State.IdleState
        self.utterance_being_played: Utterance | None = None
        self.open(QIODeviceBase.OpenModeFlag.ReadOnly)

    def audio_state_changed(self, s: QAudio.State) -> None:
        debug('Audio state:', s)
        prev_state, self.audio_state = self.audio_state, s
        if s == prev_state:
            return
        if s == QAudio.State.IdleState and prev_state == QAudio.State.ActiveState:
            if self.utterance_being_played:
                debug(f'Utterance {self.utterance_being_played.id} audio output finished')
            self.utterance_being_played = None
            self.start_utterance()
        self.update_status.emit()

    def add_utterance(self, u: Utterance) -> None:
        self.utterances.append(u)
        if not self.utterance_being_played:
            self.start_utterance()

    def start_utterance(self):
        if self.utterances:
            u = self.utterances.popleft()
            self.current_audio_data = u.audio_data
            self.utterance_being_played = u
            self.readyRead.emit()
            self.saying.emit(u.start, u.length)

    def close(self):
        self.utterances.clear()
        self.current_audio_data = QByteArray()
        return super().close()

    def clear(self):
        self.utterances.clear()
        self.current_audio_data = QByteArray()
        self.audio_state = QAudio.State.IdleState

    def atEnd(self) -> bool:
        return not len(self.current_audio_data)

    def bytesAvailable(self) -> int:
        return len(self.current_audio_data)

    def __bool__(self) -> bool:
        return bool(self.utterances) or self.utterance_being_played is not None

    def isSequential(self) -> bool:
        return True

    def seek(self, pos):
        return False

    def readData(self, maxlen: int) -> QByteArray:
        if maxlen < 1:
            return QByteArray()
        if maxlen >= len(self.current_audio_data):
            ans = self.current_audio_data
            self.current_audio_data = QByteArray()
        else:
            ans = self.current_audio_data.first(maxlen)
            self.current_audio_data = self.current_audio_data.last(len(self.current_audio_data) - maxlen)
            if len(self.current_audio_data):
                self.readyRead.emit()
        return ans


def split_long_sentences(sentence: str, offset: int, lang: str = 'en', limit: int = 2048):
    if len(sentence) <= limit:
        yield offset, sentence
        return
    buf, total, start_at = [], 0, 0

    def a(s, e):
        nonlocal total, start_at
        t = sentence[s:e]
        if not buf:
            start_at = s
        buf.append(t)
        total += len(t)

    for start, length in split_into_words_and_positions(sentence, lang):
        a(start, start + length)
        if total >= limit:
            yield offset + start_at, ' '.join(buf)
            buf, total = [], 0
    if buf:
        yield offset + start_at, ' '.join(buf)


def split_into_utterances(text: str, counter: count, lang: str = 'en'):
    text = re.sub(r'\n{2,}', PARAGRAPH_SEPARATOR, text.replace('\r', '')).replace('\n', ' ')
    for start, length in sentence_positions(text, lang):
        sentence = text[start:start+length].rstrip().replace('\n', ' ')
        for start, sentence in split_long_sentences(sentence, start, lang):
            payload = json.dumps({'text': sentence}).encode('utf-8')
            ba = QByteArray()
            ba.reserve(len(payload) + 1)
            ba.append(payload)
            ba.append(UTTERANCE_SEPARATOR)
            u = Utterance(id=next(counter), payload_size=len(ba), audio_data=QByteArray(), left_to_write=ba, start=start, length=len(sentence))
            debug(f'Utterance created {u.id}: {sentence}')
            yield u


class Piper(TTSBackend):

    engine_name: str = 'piper'

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._audio_sink: QAudioSink | None = None

        self._utterances_being_synthesized: deque[Utterance] = deque()
        self._utterance_counter = count(start=1)
        self._utterances_being_spoken = UtteranceAudioQueue()
        self._utterances_being_spoken.saying.connect(self.saying)
        self._utterances_being_spoken.update_status.connect(self._update_status, type=Qt.ConnectionType.QueuedConnection)
        self._state = QTextToSpeech.State.Ready
        self._last_error = ''
        self._errors_from_piper: list[str] = []
        self._pending_stderr_data = b''

        self._stderr_pat = re.compile(rb'\[piper\] \[([a-zA-Z0-9_]+?)\] (.+)')
        atexit.register(self.shutdown)

    def say(self, text: str) -> None:
        if self._last_error:
            return
        self.stop()
        if not self.process.waitForStarted():
            cmdline = [self.process.program()] + self.process.arguments()
            if self.process.error() is QProcess.ProcessError.TimedOut:
                self._set_error(f'Timed out waiting for piper process {cmdline} to start')
            else:
                self._set_error(f'Failed to start piper process: {cmdline}')
            return
        self._utterances_being_synthesized.extend(split_into_utterances(text, self._utterance_counter)) # TODO: Use voice language
        self._write_current_utterance()

    def pause(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.suspend()

    def resume(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.resume()

    def stop(self) -> None:
        if self._process is not None:
            if self._state is not QTextToSpeech.State.Ready or self._utterances_being_synthesized or self._utterances_being_spoken:
                self.shutdown()
                self.process

    def shutdown(self) -> None:
        if self._process is not None:
            self._audio_sink.stateChanged.disconnect()
            self._audio_sink.stop()
            sip.delete(self._audio_sink)
            self._process.readyReadStandardError.disconnect()
            self._process.bytesWritten.disconnect()
            self._process.readyReadStandardOutput.disconnect()
            # self._process.stateChanged.disconnect()
            self._process.kill()
            self._process.waitForFinished(-1)
            sip.delete(self._process)
            self._process = None

    def reload_after_configure(self) -> None:
        self.shutdown()
        self.process

    @property
    def state(self) -> QTextToSpeech.State:
        return self._state

    def error_message(self) -> str:
        return self._last_error

    def _set_state(self, s: QTextToSpeech.State) -> None:
        if self._state is not s:
            self._state = s
            self.state_changed.emit(s)

    def _set_error(self, msg: str) -> None:
        self._last_error = msg
        self._set_state(QTextToSpeech.State.Error)

    @property
    def process(self) -> QProcess:
        if self._process is None:
            self._utterances_being_spoken.clear()
            self._utterances_being_synthesized.clear()
            self._errors_from_piper.clear()
            self._process = QProcess(self)
            self._pending_stderr_data = b''
            self._set_state(QTextToSpeech.State.Ready)

            model_path =  '/t/en_US-libritts-high.onnx' # TODO: Dont hardcode voice
            rate = 1.0  # TODO: Make rate configurable
            cmdline = list(piper_cmdline()) + [
                '--model', model_path, '--output-raw', '--json-input', '--sentence-silence', '0', '--length_scale', str(rate)]
            self._process.setProgram(cmdline[0])
            self._process.setArguments(cmdline[1:])
            self._process.readyReadStandardError.connect(self.piper_stderr_available, type=Qt.ConnectionType.QueuedConnection)
            self._process.readyReadStandardOutput.connect(self.piper_stdout_available)
            self._process.bytesWritten.connect(self.bytes_written)
            # See https://www.riverbankcomputing.com/pipermail/pyqt/2024-September/046002.html
            # self._process.stateChanged.connect(self._update_status)
            fmt = QAudioFormat()
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            fmt.setSampleRate(22050)  # TODO: Read this from voice JSON
            fmt.setChannelConfig(QAudioFormat.ChannelConfig.ChannelConfigMono)
            self._audio_sink = QAudioSink(fmt, self)  # TODO: Make audio device configurable
            self._audio_sink.stateChanged.connect(self._utterances_being_spoken.audio_state_changed)
            self._process.start()
            self._audio_sink.start(self._utterances_being_spoken)
        return self._process

    def piper_stdout_available(self) -> None:
        if self._utterances_being_synthesized:
            u = self._utterances_being_synthesized[0]
            while True:
                ba = self.process.readAll()
                if not len(ba):
                    break
                u.audio_data.append(ba)

    def piper_stderr_available(self) -> None:
        needs_status_update = False
        if self._process is not None:
            data = self._pending_stderr_data + bytes(self._process.readAllStandardError())
            lines = data.split(b'\n')
            for line in lines[:-1]:
                if m := self._stderr_pat.search(line):
                    which, payload = m.group(1), m.group(2)
                    if which == b'info':
                        if payload.startswith(b'Real-time factor:') and self._utterances_being_synthesized:
                            u = self._utterances_being_synthesized.popleft()
                            u.synthesized = True
                            debug(f'Utterance {u.id} synthesized')
                            needs_status_update = True
                            self._utterances_being_spoken.add_utterance(u)
                            self._write_current_utterance()
                    elif which == b'error':
                        self._errors_from_piper.append(payload.decode('utf-8', 'replace'))
            self._pending_stderr_data = lines[-1]
            if needs_status_update:
                self._update_status()

    def _update_status(self):
        if self._process is not None and self._process.state() is QProcess.ProcessState.NotRunning:
            if self._process.exitStatus() is not QProcess.ExitStatus.NormalExit or self._process.exitCode():
                m = '\n'.join(self._errors_from_piper)
                self._set_error(f'piper process failed with exit code: {self._process.exitCode()} and error messages: {m}')
                return
        if self._state is QTextToSpeech.State.Error:
            return
        state = self._utterances_being_spoken.audio_state
        if state is QAudio.State.ActiveState:
            self._set_state(QTextToSpeech.State.Speaking)
        elif state is QAudio.State.SuspendedState:
            self._set_state(QTextToSpeech.State.Paused)
        elif state is QAudio.State.StoppedState:
            if self._audio_sink.error() not in (QAudio.Error.NoError, QAudio.Error.UnderrunError):
                self._set_error(f'Audio playback failed with error: {self._audio_sink.error()}')
            else:
                if self._state is not QTextToSpeech.State.Error:
                    self._set_state(QTextToSpeech.State.Ready)
        elif state is QAudio.State.IdleState:
            if not self._utterances_being_synthesized and not self._utterances_being_spoken:
                self._set_state(QTextToSpeech.State.Ready)

    def bytes_written(self, count: int) -> None:
        self._write_current_utterance()

    def _write_current_utterance(self) -> None:
        if self._utterances_being_synthesized:
            u = self._utterances_being_synthesized[0]
            while len(u.left_to_write):
                written = self.process.write(u.left_to_write)
                if written < 0:
                    self._set_error('Failed to write to piper process with error: {self.process.errorString()}')
                    break
                if not u.started and written:
                    u.started = True
                    debug(f'Utterance {u.id} synthesis started')
                u.left_to_write = u.left_to_write.last(len(u.left_to_write) - written)

    def audio_sink_state_changed(self, state: QAudio.State) -> None:
        self._update_status()


def develop():  # {{{
    import tty

    from qt.core import QSocketNotifier

    from calibre.gui2 import must_use_qt
    must_use_qt()
    app = QApplication.instance()
    p = Piper()
    play_started = False
    def state_changed(s):
        nonlocal play_started
        debug('TTS State:', s)
        if s is QTextToSpeech.State.Error:
            debug(p.error_message(), file=sys.stderr)
            app.exit(1)
        elif s is QTextToSpeech.State.Speaking:
            play_started = True
        elif s is QTextToSpeech.State.Ready:
            if play_started:
                debug('Quitting on completion')
                app.quit()

    def input_ready():
        nonlocal play_started
        q = sys.stdin.buffer.read()
        if q in (b'\x03', b'\x1b'):
            app.exit(1)
        elif q == b' ':
            if p.state is QTextToSpeech.State.Speaking:
                p.pause()
            elif p.state is QTextToSpeech.State.Paused:
                p.resume()
        elif q == b'r':
            debug('Stopping')
            play_started = False
            p.stop()
            p.say(text)

    text = (
        'First, relatively short sentence. '
        'Second, much longer sentence which hopefully finishes synthesizing before the first finishes speaking. '
        'Third, and final short sentence.'
    )
    # text = f'Hello world{PARAGRAPH_SEPARATOR}.{PARAGRAPH_SEPARATOR}Bye world'

    def saying(offset, length):
        debug('Saying:', repr(text[offset:offset+length]))

    p.state_changed.connect(state_changed)
    p.saying.connect(saying)
    attr = tty.setraw(sys.stdin.fileno())
    os.set_blocking(sys.stdin.fileno(), False)
    sn = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read, p)
    sn.activated.connect(input_ready)
    try:
        p.say(text)
        app.exec()
    finally:
        import termios
        termios.tcsetattr(sys.stdout.fileno(), termios.TCSANOW, attr)


if __name__ == '__main__':
    develop()
# }}}
