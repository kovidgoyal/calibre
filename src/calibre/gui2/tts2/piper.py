#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import os
import re
import sys
from collections import deque
from dataclasses import dataclass
from functools import lru_cache

from qt.core import QApplication, QAudio, QAudioFormat, QAudioSink, QByteArray, QObject, QProcess, QTextToSpeech, sip

from calibre.constants import bundled_binaries_dir, iswindows
from calibre.gui2.tts2.types import TTSBackend
from calibre.spell.break_iterator import sentence_positions


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
    start: int
    length: int
    payload_size: int
    left_to_write: QByteArray

    synthesized: bool = False
    started: bool = False


PARAGRAPH_SEPARATOR = '\u2029'
UTTERANCE_SEPARATOR = b'\n'


def split_into_utterances(text: str, lang: str = 'en'):
    text = re.sub(r'\n{2,}', PARAGRAPH_SEPARATOR, text.replace('\r', '')).replace('\n', ' ')
    for start, length in sentence_positions(text, lang):
        sentence = text[start:start+length].rstrip().replace('\n', ' ')
        payload = sentence.encode('utf-8')
        ba = QByteArray()
        ba.reserve(len(payload) + 1)
        ba.append(payload)
        ba.append(UTTERANCE_SEPARATOR)
        yield Utterance(payload_size=len(ba), left_to_write=ba, start=start, length=length)


class Piper(TTSBackend):

    engine_name: str = 'piper'

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._audio_sink: QAudioSink | None = None
        self._utterances_in_flight: deque[Utterance] = deque()
        self._state = QTextToSpeech.State.Ready
        self._last_error = ''
        self._errors_from_piper: list[str] = []
        self._pending_stderr_data = b''
        self._waiting_for_utterance_to_start = False
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
        self._utterances_in_flight.extend(split_into_utterances(text)) # TODO: Use voice language
        self._waiting_for_utterance_to_start = False
        self._write_current_utterance()

    def pause(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.suspend()

    def resume(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.resume()

    def stop(self) -> None:
        if self._process is not None:
            if self._state is not QTextToSpeech.State.Ready or self._utterances_in_flight:
                self.shutdown()
                self.process

    def shutdown(self) -> None:
        if self._process is not None:
            self._audio_sink.stateChanged.disconnect()
            self._audio_sink.stop()
            sip.delete(self._audio_sink)
            # self._audio_sink.stop()
            self._process.readyReadStandardError.disconnect()
            self._process.bytesWritten.disconnect()
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
            self._utterances_in_flight.clear()
            self._errors_from_piper.clear()
            self._process = QProcess(self)
            self._pending_stderr_data = b''
            self._waiting_for_utterance_to_start = False
            self._set_state(QTextToSpeech.State.Ready)

            model_path =  '/t/en_US-libritts-high.onnx' # TODO: Dont hardcode voice
            rate = 1.0  # TODO: Make rate configurable
            cmdline = list(piper_cmdline()) + ['--model', model_path, '--output-raw', '--length_scale', str(rate)]
            self._process.setProgram(cmdline[0])
            self._process.setArguments(cmdline[1:])
            self._process.readyReadStandardError.connect(self.piper_stderr_available)
            self._process.bytesWritten.connect(self.bytes_written)
            # See https://www.riverbankcomputing.com/pipermail/pyqt/2024-September/046002.html
            # self._process.stateChanged.connect(self._update_status)
            fmt = QAudioFormat()
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            fmt.setSampleRate(22050)  # TODO: Read this from voice JSON
            fmt.setChannelConfig(QAudioFormat.ChannelConfig.ChannelConfigMono)
            self._audio_sink = QAudioSink(fmt, self)  # TODO: Make audio device configurable
            self._audio_sink.stateChanged.connect(self.audio_sink_state_changed)
            self._process.start()
            self._audio_sink.start(self._process)
        return self._process

    def piper_stderr_available(self) -> None:
        needs_status_update = False
        if self._process is not None:
            data = self._pending_stderr_data + bytes(self._process.readAllStandardError())
            lines = data.split(b'\n')
            for line in lines[:-1]:
                if m := self._stderr_pat.search(line):
                    which, payload = m.group(1), m.group(2)
                    if which == b'info':
                        if payload.startswith(b'Real-time factor:'):
                            for u in self._utterances_in_flight:
                                if not u.synthesized:
                                    u.synthesized = True
                                    needs_status_update = True
                                    break
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
        state = self._audio_sink.state()
        if state is QAudio.State.ActiveState:
            self._waiting_for_utterance_to_start = False
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
            if not self._waiting_for_utterance_to_start:
                if self._utterances_in_flight and (u := self._utterances_in_flight[0]) and u.synthesized:
                    self._utterances_in_flight.popleft()
                if self._utterances_in_flight:
                    self._write_current_utterance()
                else:
                    self._set_state(QTextToSpeech.State.Ready)

    def bytes_written(self, count: int) -> None:
        self._write_current_utterance()

    def _write_current_utterance(self) -> None:
        if self._utterances_in_flight:
            u = self._utterances_in_flight[0]
            while len(u.left_to_write):
                written = self.process.write(u.left_to_write)
                if written < 0:
                    self._set_error('Failed to write to piper process with error: {self.process.errorString()}')
                    break
                if not u.started and written:
                    self._waiting_for_utterance_to_start = True
                    u.started = True
                    self.saying.emit(u.start, u.length)
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
        print(s, end='\r\n')
        nonlocal play_started
        if s is QTextToSpeech.State.Error:
            print(p.error_message(), file=sys.stderr, end='\r\n')
            app.exit(1)
        elif s is QTextToSpeech.State.Speaking:
            play_started = True
        elif s is QTextToSpeech.State.Ready:
            if play_started:
                app.quit()

    def input_ready():
        q = sys.stdin.buffer.read()
        if q in (b'\x03', b'\x1b'):
            app.exit(1)
        elif q == b' ':
            if p.state is QTextToSpeech.State.Speaking:
                p.pause()
            elif p.state is QTextToSpeech.State.Paused:
                p.resume()

    text = "Hello, it is a beautiful day today, isn't it? Yes indeed, it is a very beautiful day!"

    def saying(offset, length):
        print('Saying:', repr(text[offset:offset+length]), end='\r\n')

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
