#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import os
import re
import sys
from collections import deque
from functools import lru_cache

from qt.core import QApplication, QAudio, QAudioFormat, QAudioSink, QObject, QProcess, QTextToSpeech, pyqtSignal, sip

from calibre.constants import bundled_binaries_dir, iswindows


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


class Utterance:
    synthesized: bool = False

    def __init__(self, id: int):
        self.id = id


class PiperIPC(QObject):

    state_changed = pyqtSignal(QTextToSpeech.State)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._audio_sink: QAudioSink | None = None
        self._utterance_id_counter = 0
        self._utterances_in_flight: deque[Utterance] = deque()
        self._write_buf: deque[memoryview] = deque()
        self._state = QTextToSpeech.State.Ready
        self._last_error = ''
        self._errors_from_piper: list[str] = []
        self._pending_stderr_data = b''
        self._stderr_pat = re.compile(rb'\[piper\] \[([a-zA-Z0-9_]+?)\] (.+)')
        atexit.register(self.shutdown)

    def say(self, text) -> int:
        if self._last_error:
            return 0
        if not self.process.waitForStarted():
            cmdline = [self.process.program()] + self.process.arguments()
            if self.process.error() is QProcess.ProcessError.TimedOut:
                self._set_error(f'Timed out waiting for piper process {cmdline} to start')
            else:
                self._set_error(f'Failed to start piper process: {cmdline}')
            return 0
        import json
        self._utterance_id_counter += 1
        self._utterances_in_flight.append(Utterance(self._utterance_id_counter))
        payload = json.dumps({"text": text}).encode() + b'\n'
        self._write(payload)
        return self._utterance_id_counter

    def pause(self):
        if self._audio_sink is not None:
            self._audio_sink.suspend()

    def resume(self):
        if self._audio_sink is not None:
            self._audio_sink.resume()

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

    def _write(self, payload: bytes) -> None:
        written = self.process.write(payload)
        if written < 0:
            self._set_error('Failed to write to piper process with error: {self.process.errorString()}')
        elif written < len(payload):
            self._write_buf.append(memoryview(payload)[written:])

    @property
    def process(self) -> QProcess:
        if self._process is None:
            self._errors_from_piper: list[str] = []
            self._process = QProcess(self)
            self._pending_stderr_data = b''
            model_path =  '/t/en_US-libritts-high.onnx' # TODO: Dont hardcode voice
            rate = 1.0  # TODO: Make rate configurable
            cmdline = list(piper_cmdline()) + ['--model', model_path, '--output-raw', '--json-input', '--length_scale', str(rate)]
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

    @property
    def all_synthesized(self) -> bool:
        for u in self._utterances_in_flight:
            if not u.synthesized:
                return False
        return True

    def _update_status(self):
        if self._process is not None and self._process.state() is QProcess.ProcessState.NotRunning:
            if self._process.exitStatus() is not QProcess.ExitStatus.NormalExit or self._process.exitCode():
                m = '\n'.join(self._errors_from_piper)
                self._set_error(f'piper process failed with exit code: {self._process.exitCode()} and error messages: {m}')
                return
        state = self._audio_sink.state()
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
            if self.all_synthesized:
                self._set_state(QTextToSpeech.State.Ready)
            else:
                self._set_state(QTextToSpeech.State.Speaking)

    def bytes_written(self, count: int) -> None:
        while self._write_buf:
            payload = self._write_buf[0]
            written = self.process.write(payload)
            if written < 0:
                self._set_error('Failed to write to piper process with error: {self.process.errorString()}')
                break
            elif written < len(payload):
                self._write_buf[0] = payload[written:]
                break
            else:
                self._write_buf.popleft()

    def audio_sink_state_changed(self, state: QAudio.State) -> None:
        self._update_status()


def develop():
    import tty

    from qt.core import QSocketNotifier

    from calibre.gui2 import must_use_qt
    must_use_qt()
    app = QApplication.instance()
    p = PiperIPC()
    play_started = False
    to_play = "Yes indeed, it is a very beautiful day today."
    def state_changed(s):
        print(s, end='\r\n')
        nonlocal play_started, to_play
        if s is QTextToSpeech.State.Error:
            print(p.error_message(), file=sys.stderr, end='\r\n')
            app.exit(1)
        elif s is QTextToSpeech.State.Speaking:
            play_started = True
        elif s is QTextToSpeech.State.Ready:
            if play_started:
                if to_play:
                    p.say(to_play)
                    to_play = ''
                else:
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

    p.state_changed.connect(state_changed)
    attr = tty.setraw(sys.stdin.fileno())
    os.set_blocking(sys.stdin.fileno(), False)
    sn = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read, p)
    sn.activated.connect(input_ready)
    try:
        p.say("Hello, it is a beautiful day today, isn't it?")
        app.exec()
    finally:
        import termios
        termios.tcsetattr(sys.stdout.fileno(), termios.TCSANOW, attr)


if __name__ == '__main__':
    develop()
