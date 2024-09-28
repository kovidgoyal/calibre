#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import json
import os
import re
import sys
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from itertools import count
from time import monotonic

from qt.core import (
    QApplication,
    QAudio,
    QAudioFormat,
    QAudioSink,
    QByteArray,
    QIODevice,
    QIODeviceBase,
    QMediaDevices,
    QObject,
    QProcess,
    Qt,
    QTextToSpeech,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre.constants import cache_dir, is_debugging, piper_cmdline
from calibre.gui2 import error_dialog
from calibre.gui2.tts.types import EngineSpecificSettings, Quality, TTSBackend, Voice, widget_parent
from calibre.spell.break_iterator import PARAGRAPH_SEPARATOR, split_into_sentences_for_tts
from calibre.utils.localization import canonicalize_lang, get_lang
from calibre.utils.resources import get_path as P


def debug(*a, **kw):
    if is_debugging():
        if not hasattr(debug, 'first'):
            debug.first = monotonic()
        kw['end'] = kw.get('end', '\r\n')
        print(f'[{monotonic() - debug.first:.2f}]', *a, **kw)


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
        self.utterance_being_played = None
        return super().close()

    def clear(self):
        self.utterances.clear()
        self.utterance_being_played = None
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
            debug(f'Audio data sent to output: {maxlen=}')
            return QByteArray()
        if maxlen >= len(self.current_audio_data):
            ans = self.current_audio_data
            self.current_audio_data = QByteArray()
        else:
            ans = self.current_audio_data.first(maxlen)
            self.current_audio_data = self.current_audio_data.last(len(self.current_audio_data) - maxlen)
            if len(self.current_audio_data):
                self.readyRead.emit()
        debug(f'Audio sent to output: {maxlen=} {len(ans)=}')
        return ans


def split_into_utterances(text: str, counter: count, lang: str = 'en'):
    for start, sentence in split_into_sentences_for_tts(text, lang):
        payload = json.dumps({'text': sentence}).encode('utf-8')
        ba = QByteArray()
        ba.reserve(len(payload) + 1)
        ba.append(payload)
        ba.append(UTTERANCE_SEPARATOR)
        u = Utterance(id=next(counter), payload_size=len(ba), audio_data=QByteArray(),
                        left_to_write=ba, start=start, length=len(sentence))
        debug(f'Utterance created {u.id} {start=}: {sentence!r}')
        yield u


class Piper(TTSBackend):

    engine_name: str = 'piper'
    filler_char: str = PARAGRAPH_SEPARATOR
    _synthesis_done = pyqtSignal()

    def __init__(self, engine_name: str = '', parent: QObject|None = None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._audio_sink: QAudioSink | None = None

        self._current_voice: Voice | None = None
        self._utterances_being_synthesized: deque[Utterance] = deque()
        self._utterance_counter = count(start=1)
        self._utterances_being_spoken = UtteranceAudioQueue()
        self._utterances_being_spoken.saying.connect(self.saying)
        self._utterances_being_spoken.update_status.connect(self._update_status, type=Qt.ConnectionType.QueuedConnection)
        self._state = QTextToSpeech.State.Ready
        self._voices = self._voice_for_lang = None
        self._last_error = ''
        self._errors_from_piper: list[str] = []
        self._pending_stderr_data = b''

        self._stderr_pat = re.compile(rb'\[piper\] \[([a-zA-Z0-9_]+?)\] (.+)')
        self._synthesis_done.connect(self._utterance_synthesized, type=Qt.ConnectionType.QueuedConnection)
        atexit.register(self.shutdown)

    @property
    def available_voices(self) -> dict[str, tuple[Voice, ...]]:
        self._load_voice_metadata()
        return {'': self._voices}

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
        lang = 'en'
        if self._current_voice and self._current_voice.language_code:
            lang = self._current_voice.language_code
        self._utterances_being_synthesized.extend(split_into_utterances(text, self._utterance_counter, lang))
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
                # We cannot re-create self.process here as that will cause the
                # audio device to go to active state which will cause a
                # speaking event to be generated

    def shutdown(self) -> None:
        if self._process is not None:
            self._audio_sink.stateChanged.disconnect()
            self._process.readyReadStandardError.disconnect()
            self._process.bytesWritten.disconnect()
            self._process.readyReadStandardOutput.disconnect()
            self._process.stateChanged.disconnect()
            self._process.kill()
            self._process.waitForFinished(-1)
            # this dance is needed otherwise stop() is very slow on Linux
            self._audio_sink.suspend()
            self._audio_sink.reset()
            self._audio_sink.stop()
            sip.delete(self._audio_sink)
            sip.delete(self._process)
            self._process = self._audio_sink = None
            self._set_state(QTextToSpeech.State.Ready)

    def reload_after_configure(self) -> None:
        self.shutdown()

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
            model_path = config_path = ''
            try:
                self._load_voice_metadata()
                s = EngineSpecificSettings.create_from_config(self.engine_name)
                length_scale = max(0.1, 1 + -1 * s.rate)  # maps -1 to 1 to 2 to 0.1
                voice = self._voice_name_map.get(s.voice_name) or self._default_voice
                model_path, config_path = self._ensure_voice_is_downloaded(voice)
            except AttributeError as e:
                raise Exception(str(e)) from e
            if not model_path:
                raise Exception('Could not download voice data')
            if 'metadata' not in voice.engine_data:
                with open(config_path) as f:
                    voice.engine_data['metadata'] = json.load(f)
            audio_rate = voice.engine_data['metadata']['audio']['sample_rate']
            self._current_voice = voice
            self._utterances_being_spoken.clear()
            self._utterances_being_synthesized.clear()
            self._errors_from_piper.clear()
            self._process = QProcess(self)
            self._pending_stderr_data = b''
            self._set_state(QTextToSpeech.State.Ready)

            cmdline = list(piper_cmdline()) + [
                '--model', model_path, '--config', config_path, '--output-raw', '--json-input',
                '--sentence-silence', str(s.sentence_delay), '--length_scale', str(length_scale)]
            if is_debugging():
                cmdline.append('--debug')
            self._process.setProgram(cmdline[0])
            self._process.setArguments(cmdline[1:])
            debug('Running piper:', cmdline)
            self._process.readyReadStandardError.connect(self.piper_stderr_available)
            self._process.readyReadStandardOutput.connect(self.piper_stdout_available)
            self._process.bytesWritten.connect(self.bytes_written)
            self._process.stateChanged.connect(self._update_status)
            fmt = QAudioFormat()
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            fmt.setSampleRate(audio_rate)
            fmt.setChannelConfig(QAudioFormat.ChannelConfig.ChannelConfigMono)
            dev = None
            if s.audio_device_id:
                for q in QMediaDevices.audioOutputs():
                    if bytes(q.id()) == s.audio_device_id.id:
                        dev = q
                        break
            if dev:
                self._audio_sink = QAudioSink(dev, fmt, self)
            else:
                self._audio_sink = QAudioSink(fmt, self)
            if s.volume is not None:
                self._audio_sink.setVolume(s.volume)
            # On Windows, the buffer is zero causing data to be discarded.
            # Ensure we have a nice large buffer on all platforms.
            self._audio_sink.setBufferSize(2 * 1024 * 1024)
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
                debug('Synthesized data read:', len(ba), 'bytes')
                u.audio_data.append(ba)

    def piper_stderr_available(self) -> None:
        if self._process is not None:
            data = self._pending_stderr_data + bytes(self._process.readAllStandardError())
            lines = data.split(b'\n')
            for line in lines[:-1]:
                if m := self._stderr_pat.search(line):
                    which, payload = m.group(1), m.group(2)
                    if which == b'info':
                        debug(f'[piper-info] {payload.decode("utf-8", "replace")}')
                        if payload.startswith(b'Real-time factor:') and self._utterances_being_synthesized:
                            self._synthesis_done.emit()
                    elif which == b'error':
                        self._errors_from_piper.append(payload.decode('utf-8', 'replace'))
                    elif which == b'debug':
                        debug(f'[piper-debug] {payload.decode("utf-8", "replace")}')
            self._pending_stderr_data = lines[-1]

    def _utterance_synthesized(self):
        self.piper_stdout_available()  # just in case
        u = self._utterances_being_synthesized.popleft()
        u.synthesized = True
        debug(f'Utterance {u.id} got {len(u.audio_data)} bytes of audio data from piper')
        if len(u.audio_data):
            self._utterances_being_spoken.add_utterance(u)
        self._write_current_utterance()
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

    def _load_voice_metadata(self) -> None:
        if self._voices is not None:
            return
        d = json.loads(P('piper-voices.json', data=True))
        ans = []
        lang_voices_map = {}
        self._voice_name_map = {}
        downloaded = set()
        with suppress(OSError):
            downloaded = set(os.listdir(self.cache_dir))
        for bcp_code, voice_map in d['lang_map'].items():
            lang, sep, country = bcp_code.partition('_')
            lang = canonicalize_lang(lang) or lang
            voices_for_lang = lang_voices_map.setdefault(lang, [])
            for voice_name, qual_map in voice_map.items():
                best_qual = voice = None
                for qual, e in qual_map.items():
                    q = Quality.from_piper_quality(qual)
                    if best_qual is None or q.value < best_qual.value:
                        best_qual = q
                        mf = f'{bcp_code}-{voice_name}-{qual}.onnx'
                        voice = Voice(bcp_code + ':' + voice_name, lang, country, human_name=voice_name, quality=q, engine_data={
                            'model_url': e['model'], 'config_url': e['config'],
                            'model_filename': mf, 'is_downloaded': mf in downloaded,
                        })
                if voice:
                    ans.append(voice)
                    self._voice_name_map[voice.name] = voice
                    voices_for_lang.append(voice)
        self._voices = tuple(ans)
        self._voice_for_lang = {}
        for lang, voices in lang_voices_map.items():
            voices.sort(key=lambda v: v.quality.value)
            self._voice_for_lang[lang] = voices[0]
            if lang == 'eng':
                for v in voices:
                    if v.human_name == 'libritts':
                        self._voice_for_lang[lang] = v
                        break

    @property
    def _default_voice(self) -> Voice:
        self._load_voice_metadata()
        lang = get_lang()
        lang = canonicalize_lang(lang) or lang
        return self._voice_for_lang.get(lang) or self._voice_for_lang['eng']

    @property
    def cache_dir(self) -> str:
        return os.path.join(cache_dir(), 'piper-voices')

    def _paths_for_voice(self, voice: Voice) -> tuple[str, str]:
        fname = voice.engine_data['model_filename']
        model_path = os.path.join(self.cache_dir, fname)
        config_path = os.path.join(os.path.dirname(model_path), fname + '.json')
        return model_path, config_path

    def is_voice_downloaded(self, v: Voice) -> bool:
        if not v.name:
            v = self._default_voice
        for path in self._paths_for_voice(v):
            if not os.path.exists(path):
                return False
        return True

    def delete_voice(self, v: Voice) -> None:
        if not v.name:
            v = self._default_voice
        for path in self._paths_for_voice(v):
            with suppress(FileNotFoundError):
                os.remove(path)
        v.engine_data['is_downloaded'] = False

    def _download_voice(self, voice: Voice, download_even_if_exists: bool = False) -> tuple[str, str]:
        model_path, config_path = self._paths_for_voice(voice)
        if os.path.exists(model_path) and os.path.exists(config_path):
            if not download_even_if_exists:
                return model_path, config_path
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        from calibre.gui2.tts.download import download_resources
        ok = download_resources(_('Downloading voice for Read aloud'), _('Downloading neural network for the {} voice').format(voice.human_name), {
                voice.engine_data['model_url']: (model_path, _('Neural network data')),
                voice.engine_data['config_url']: (config_path, _('Neural network metadata')),
            }, parent=widget_parent(self), headless=getattr(QApplication.instance(), 'headless', False)
        )
        voice.engine_data['is_downloaded'] = bool(ok)
        return (model_path, config_path) if ok else ('', '')

    def download_voice(self, v: Voice) -> None:
        if not v.name:
            v = self._default_voice
        self._download_voice(v, download_even_if_exists=True)

    def _ensure_voice_is_downloaded(self, voice: Voice) -> tuple[str, str]:
        return self._download_voice(voice)

    def validate_settings(self, s: EngineSpecificSettings, parent: QWidget | None) -> bool:
        self._load_voice_metadata()
        voice = self._voice_name_map.get(s.voice_name) or self._default_voice
        try:
            m, c = self._ensure_voice_is_downloaded(voice)
            if not m:
                error_dialog(parent, _('Failed to download voice'), _('Failed to download the voice: {}').format(voice.human_name), show=True)
                return False
        except Exception:
            import traceback
            error_dialog(parent, _('Failed to download voice'), _('Failed to download the voice: {}').format(voice.human_name),
                         det_msg=traceback.format_exc(), show=True)
            return False
        return True


def develop():  # {{{

    from qt.core import QSocketNotifier

    from calibre.constants import iswindows
    from calibre.gui2 import Application
    app = Application([])
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
    if not iswindows:
        import tty
        attr = tty.setraw(sys.stdin.fileno())
        os.set_blocking(sys.stdin.fileno(), False)
    sn = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read, p)
    sn.activated.connect(input_ready)
    try:
        p.say(text)
        app.exec()
    finally:
        if not iswindows:
            import termios
            termios.tcsetattr(sys.stdout.fileno(), termios.TCSANOW, attr)


if __name__ == '__main__':
    develop()
# }}}
