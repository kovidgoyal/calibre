#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import json
import os
import sys
from collections import deque
from collections.abc import Iterable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from itertools import count
from time import monotonic
from typing import NamedTuple, cast

from qt.core import (
    QAudio,
    QAudioFormat,
    QAudioSink,
    QByteArray,
    QIODevice,
    QIODeviceBase,
    QMediaDevices,
    QObject,
    Qt,
    QTextToSpeech,
    QVoice,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre.constants import cache_dir, is_debugging, iswindows
from calibre.gui2 import error_dialog
from calibre.gui2.tts.types import TTS_EMBEDED_CONFIG, EngineSpecificSettings, Quality, TTSBackend, Voice, widget_parent
from calibre.spell.break_iterator import PARAGRAPH_SEPARATOR, split_into_sentences_for_tts
from calibre.utils.filenames import ascii_text
from calibre.utils.localization import _, canonicalize_lang, get_lang
from calibre.utils.resources import get_path as P
from calibre.utils.tts.kokoro import FileData, kokoro_metadata
from calibre.utils.tts.piper import KokoroVoice, ResultCallback, SynthesisResult, global_piper_instance, global_piper_instance_if_exists, play_pcm_data

HIGH_QUALITY_SAMPLE_RATE = 22050


def debug(*a, **kw):
    if is_debugging():
        if not hasattr(debug, 'first'):
            setattr(debug, 'first', monotonic())
        kw['end'] = kw.get('end', '\r\n')
        kw['flush'] = True
        print(f'[{monotonic() - getattr(debug, 'first'):.2f}]', *a, **kw)


def audio_format(audio_rate: int = HIGH_QUALITY_SAMPLE_RATE) -> QAudioFormat:
    fmt = QAudioFormat()
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    fmt.setSampleRate(audio_rate)
    fmt.setChannelConfig(QAudioFormat.ChannelConfig.ChannelConfigMono)
    return fmt


class VoiceFile(NamedTuple):
    url: str
    path: str
    description: str
    sha256: str = ''


def piper_cache_dir() -> str:
    return os.path.join(cache_dir(), 'piper-voices')


def kokoro_cache_dir() -> str:
    return os.path.join(cache_dir(), 'kokoro')


def kokoro_filename(prefix: str, fd: FileData) -> str:
    # The hash is part of the name so that updated files are downloaded again
    ext = os.path.splitext(fd['url'])[1]
    return f'{prefix}-{fd["sha256"][:12]}{ext}'


def is_kokoro_voice(voice: Voice) -> bool:
    return bool(voice.engine_data and voice.engine_data.get('model_type') == 'kokoro')


def kokoro_shared_files(lang_code: str) -> list[VoiceFile]:
    # The files needed by all Kokoro voices for the specified language
    md = kokoro_metadata()
    base = kokoro_cache_dir()
    ans = [VoiceFile(md['model']['url'], os.path.join(base, kokoro_filename('kokoro', md['model'])), _('Neural network data'), md['model']['sha256'])]
    if lexicon := md['languages'][lang_code]['lexicon']:
        ld = md['lexicons'][lexicon]
        for q, fd in (('gold', ld['gold']), ('silver', ld['silver'])):
            ans.append(VoiceFile(fd['url'], os.path.join(base, kokoro_filename(f'{lexicon}_{q}', fd)), _('Pronunciation dictionary'), fd['sha256']))
    return ans


def files_for_voice(voice: Voice) -> list[VoiceFile]:
    # All the files needed by the specified voice, the first file is the
    # neural network model
    assert voice.engine_data is not None
    if is_kokoro_voice(voice):
        voice_id = voice.engine_data['voice_id']
        assert isinstance(voice_id, str)
        vd = kokoro_metadata()['voices'][voice_id]
        ans = kokoro_shared_files(vd['lang'])
        ans.insert(1, VoiceFile(vd['url'], os.path.join(kokoro_cache_dir(), kokoro_filename(voice_id, vd)), _('Voice data'), vd['sha256']))
        return ans
    fname = voice.engine_data['model_filename']
    model_url, config_url = voice.engine_data['model_url'], voice.engine_data['config_url']
    assert isinstance(fname, str) and isinstance(model_url, str) and isinstance(config_url, str)
    model_path = os.path.join(piper_cache_dir(), fname)
    return [VoiceFile(model_url, model_path, _('Neural network data')), VoiceFile(config_url, model_path + '.json', _('Neural network metadata'))]


def kokoro_voice_spec(voice: Voice) -> KokoroVoice:
    assert voice.engine_data is not None
    voice_id = voice.engine_data['voice_id']
    assert isinstance(voice_id, str)
    lang_code = kokoro_metadata()['voices'][voice_id]['lang']
    files = files_for_voice(voice)
    lexicon_paths = (files[2].path, files[3].path) if len(files) > 3 else None
    return KokoroVoice(files[0].path, files[1].path, lang_code, lexicon_paths)


def load_voice_into_synthesizer(callback: ResultCallback, s: EngineSpecificSettings, voice: Voice) -> int:
    # Returns the sample rate of the audio produced by the voice
    files = files_for_voice(voice)
    if not all(os.path.exists(f.path) for f in files):
        raise Exception(f'The data for the voice {voice.human_name} has not been downloaded')
    if is_kokoro_voice(voice):
        return global_piper_instance().set_kokoro_voice(callback, kokoro_voice_spec(voice), rate=s.rate, sentence_delay=s.sentence_delay)
    assert voice.engine_data is not None
    if 'metadata' not in voice.engine_data:
        with open(files[1].path) as f:
            voice.engine_data['metadata'] = json.load(f)
    return global_piper_instance().set_voice(callback, files[1].path, files[0].path, length_scale_multiplier=s.rate, sentence_delay=s.sentence_delay)


def load_kokoro_voices(lang_voices_map: dict[str, list[Voice]]) -> list[Voice]:
    md = kokoro_metadata()
    ans = []
    downloaded = set()
    with suppress(OSError):
        downloaded = set(os.listdir(kokoro_cache_dir()))
    shared_downloaded = {lang_code: all(os.path.basename(f.path) in downloaded for f in kokoro_shared_files(lang_code)) for lang_code in md['languages']}
    for voice_id, vd in md['voices'].items():
        ld = md['languages'][vd['lang']]
        lang = canonicalize_lang(ld['lang']) or ld['lang']
        voice = Voice(
            'kokoro:' + voice_id,
            lang,
            ld['country'],
            human_name=_('{} (Kokoro)').format(vd['name']),
            gender=QVoice.Gender.Female if vd['gender'] == 'f' else QVoice.Gender.Male,
            quality=Quality.from_kokoro_grade(vd['grade']),
            engine_data={
                'model_type': 'kokoro',
                'voice_id': voice_id,
                'is_downloaded': shared_downloaded[vd['lang']] and kokoro_filename(voice_id, vd) in downloaded,
            },
        )
        ans.append(voice)
        lang_voices_map.setdefault(lang, []).append(voice)
    return ans


def load_voice_metadata() -> tuple[dict[str, Voice], tuple[Voice, ...], dict[str, Voice], dict[str, Voice]]:
    d = json.loads(P('piper-voices.json', data=True))
    ans = []
    lang_voices_map: dict[str, list[Voice]] = {}
    _voice_name_map = {}
    human_voice_name_map = {}
    downloaded = set()
    with suppress(OSError):
        downloaded = set(os.listdir(piper_cache_dir()))
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
                    mf = f'{bcp_code}-{ascii_text(voice_name)}-{qual}.onnx'
                    voice = Voice(
                        bcp_code + ':' + voice_name,
                        lang,
                        country,
                        human_name=voice_name,
                        quality=q,
                        engine_data={
                            'model_url': e['model'],
                            'config_url': e['config'],
                            'model_filename': mf,
                            'is_downloaded': mf in downloaded,
                        },
                    )
            if voice:
                ans.append(voice)
                voices_for_lang.append(voice)
    _voice_for_lang = {}
    for lang, voices in lang_voices_map.items():
        voices.sort(key=lambda v: v.quality.value)
        _voice_for_lang[lang] = voices[0]
        if lang == 'eng':
            for v in voices:
                if v.human_name == 'libritts':
                    _voice_for_lang[lang] = v
                    break
    ans.extend(load_kokoro_voices(lang_voices_map))
    for voice in ans:
        _voice_name_map[voice.name] = human_voice_name_map[voice.human_name] = voice
    for lang, voice_id in kokoro_metadata()['default_voices'].items():
        if (kv := _voice_name_map.get('kokoro:' + voice_id)) is not None:
            _voice_for_lang[lang] = kv
    return _voice_name_map, tuple(ans), _voice_for_lang, human_voice_name_map


def download_voice(voice: Voice, download_even_if_exists: bool = False, parent: QObject | None = None, headless: bool = False) -> bool:
    files = files_for_voice(voice)
    # Data shared by voices is never downloaded again as it is verified by its hash
    shared = {f.path for f in files[:1]} | {f.path for f in files[2:]} if is_kokoro_voice(voice) else set()
    needed = [f for f in files if not os.path.exists(f.path) or (download_even_if_exists and f.path not in shared)]
    assert voice.engine_data is not None
    if needed:
        for f in needed:
            os.makedirs(os.path.dirname(f.path), exist_ok=True)
        from calibre.gui2.tts.download import download_resources

        ok = download_resources(
            _('Downloading voice for Read aloud'),
            _('Downloading neural network for the {} voice').format(voice.human_name),
            {f.url: (f.path, f.description) for f in needed},
            parent=widget_parent(parent) if parent is not None else None,
            headless=headless,
            hashes={f.url: f.sha256 for f in needed if f.sha256},
        )
        if not ok:
            voice.engine_data['is_downloaded'] = False
            return False
    voice.engine_data['is_downloaded'] = True
    return True


def delete_voice_data(voice: Voice) -> None:
    files = files_for_voice(voice)
    if is_kokoro_voice(voice):
        # Delete only the voice data, the data shared by all Kokoro voices is
        # deleted once no voices remain
        with suppress(FileNotFoundError):
            os.remove(files[1].path)
        md = kokoro_metadata()
        try:
            remaining = set(os.listdir(kokoro_cache_dir()))
        except FileNotFoundError:
            remaining = set()
        if not remaining & {kokoro_filename(vid, vd) for vid, vd in md['voices'].items()}:
            for name in remaining:
                with suppress(OSError):
                    os.remove(os.path.join(kokoro_cache_dir(), name))
    else:
        for f in files:
            with suppress(FileNotFoundError):
                os.remove(f.path)
    assert voice.engine_data is not None
    voice.engine_data['is_downloaded'] = False


@dataclass
class Utterance:
    id: int
    start: int
    length: int
    sentence: str
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

    def readData(self, maxlen: int) -> bytes:
        if maxlen < 1:
            debug(f'Audio data sent to output: {maxlen=}')
            return cast('bytes', QByteArray())
        if maxlen >= len(self.current_audio_data):
            ans = self.current_audio_data
            self.current_audio_data = QByteArray()
        else:
            ans = self.current_audio_data.first(maxlen)
            self.current_audio_data = self.current_audio_data.last(len(self.current_audio_data) - maxlen)
        debug(f'Audio sent to output: {maxlen=} {len(ans)=}')
        return cast('bytes', ans)


def split_into_utterances(text: str, counter: count, lang: str = 'en'):
    for start, sentence in split_into_sentences_for_tts(text, lang):
        u = Utterance(id=next(counter), audio_data=QByteArray(), sentence=sentence, start=start, length=len(sentence))
        debug(f'Utterance created {u.id} {start=}: {sentence!r}')
        yield u


class Piper(TTSBackend):
    engine_name: str = 'piper'
    filler_char: str = PARAGRAPH_SEPARATOR
    _synthesis_done = pyqtSignal(object, object, object)

    def __init__(self, engine_name: str = '', parent: QObject | None = None):
        super().__init__(engine_name, parent)
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

        self._synthesis_done.connect(self._on_synthesis_done, type=Qt.ConnectionType.QueuedConnection)
        atexit.register(self.shutdown)

    @property
    def available_voices(self) -> dict[str, tuple[Voice, ...]]:
        self._load_voice_metadata()
        return {'': self._voices or ()}

    def say(self, text: str) -> None:
        if self._last_error:
            return
        self.stop()
        self.ensure_started()
        lang = 'en'
        if self._current_voice and self._current_voice.language_code:
            lang = self._current_voice.language_code
        self._utterances_being_synthesized.extend(split_into_utterances(text, self._utterance_counter, lang))
        self._queue_current_utterance()

    def pause(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.suspend()

    def resume(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.resume()

    def stop(self) -> None:
        if self._audio_sink is not None:
            if self._state is not QTextToSpeech.State.Ready or self._utterances_being_synthesized or self._utterances_being_spoken:
                self.shutdown()
                # We cannot call ensure_started() here as that will cause the
                # audio device to go to active state which will cause a
                # speaking event to be generated

    def shutdown(self) -> None:
        if self._audio_sink is not None:
            gp = global_piper_instance_if_exists()
            if gp is not None:
                gp.cancel()
            self._audio_sink.stateChanged.disconnect()
            with suppress(TypeError):
                self._utterances_being_spoken.readyRead.disconnect()
            # this dance is needed otherwise stop() is very slow on Linux
            self._audio_sink.suspend()
            self._audio_sink.reset()
            self._audio_sink.stop()
            sip.delete(self._audio_sink)
            self._audio_sink = None
            self._utterances_being_synthesized.clear()
            self._utterances_being_spoken.clear()
            self._set_state(QTextToSpeech.State.Ready)
            debug('Audio sink has been shutdown')

    def reload_after_configure(self) -> None:
        self.shutdown()

    def execution_provider_for_voice(self, voice: Voice | None = None) -> str:
        """
        Return the name of the onnxruntime execution provider running the model
        for the specified voice (the current voice by default), for example
        CPUExecutionProvider. Returns the empty string if the model for the voice
        is not currently loaded.
        """
        voice = voice or self._current_voice
        gp = global_piper_instance_if_exists()
        if voice is None or gp is None:
            return ''
        b = gp.current_backend()
        if b is None or os.path.abspath(b.model_path) != os.path.abspath(files_for_voice(voice)[0].path):
            return ''
        return b.execution_provider

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

    def ensure_started(self) -> None:
        if self._audio_sink is None:
            try:
                self._load_voice_metadata()
                s = EngineSpecificSettings.create_from_config(self.engine_name)
                voice = self._voice_name_map.get(s.voice_name) or self._default_voice
                if not self._ensure_voice_is_downloaded(voice):
                    raise Exception(f'Could not download the data for the voice: {voice.human_name}')
            except AttributeError as e:
                raise Exception(str(e)) from e
            self._current_voice = voice
            self._utterances_being_spoken.clear()
            self._utterances_being_synthesized.clear()
            self._errors_from_piper.clear()
            self._set_state(QTextToSpeech.State.Ready)

            audio_rate = load_voice_into_synthesizer(self.on_synthesis_done, s, voice)
            fmt = audio_format(audio_rate)
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
            self._audio_sink.stateChanged.connect(self._utterances_being_spoken.audio_state_changed)
            self._audio_sink.start(self._utterances_being_spoken)

    def on_synthesis_done(self, sr, err, tb):
        self._synthesis_done.emit(sr, err, tb)

    def _on_synthesis_done(self, sr: SynthesisResult, err: Exception, tb: str):
        if self._audio_sink is None:
            return
        if err is not None:
            self._errors_from_piper.append(str(err))
            self._errors_from_piper.append(tb)
        elif self._utterances_being_synthesized:
            u = self._utterances_being_synthesized[0]
            if u.id == sr.utterance_id:
                u.audio_data.append(sr.audio_data)
                if sr.is_last:
                    debug(f'Utterance {u.id} got {len(sr.audio_data)} bytes of audio data from piper')
                    self._utterances_being_synthesized.popleft()
                    u.synthesized = True
                    if len(u.audio_data):
                        self._utterances_being_spoken.add_utterance(u)
                else:
                    debug(f'Synthesized data read for utterance {u.id}: {len(sr.audio_data)} bytes')
        self._queue_current_utterance()
        self._update_status()

    def _update_status(self):
        if self._errors_from_piper:
            m = '\n'.join(self._errors_from_piper)
            self._set_error(f'piper failed with error: {m}')
            return
        if self._state is QTextToSpeech.State.Error:
            return
        state = self._utterances_being_spoken.audio_state
        if state is QAudio.State.ActiveState:
            self._set_state(QTextToSpeech.State.Speaking)
        elif state is QAudio.State.SuspendedState:
            self._set_state(QTextToSpeech.State.Paused)
        elif state is QAudio.State.StoppedState:
            _audio_sink = self._audio_sink
            assert _audio_sink is not None
            if _audio_sink.error() not in (QAudio.Error.NoError, QAudio.Error.UnderrunError):
                self._set_error(f'Audio playback failed with error: {_audio_sink.error()}')
            elif self._state is not QTextToSpeech.State.Error:
                self._set_state(QTextToSpeech.State.Ready)
        elif state is QAudio.State.IdleState:
            if not self._utterances_being_synthesized and not self._utterances_being_spoken:
                self._set_state(QTextToSpeech.State.Ready)

    def _queue_current_utterance(self) -> None:
        if self._utterances_being_synthesized and not (u := self._utterances_being_synthesized[0]).started:
            global_piper_instance().synthesize(u.id, u.sentence)
            u.started = True
            debug(f'Utterance {u.id} synthesis queued')

    def audio_sink_state_changed(self, state: QAudio.State) -> None:
        self._update_status()

    def _load_voice_metadata(self) -> None:
        if self._voices is not None:
            return
        self._voice_name_map, self._voices, self._voice_for_lang, self.human_voice_name_map = load_voice_metadata()

    @property
    def _default_voice(self) -> Voice:
        self._load_voice_metadata()
        lang = get_lang()
        lang = canonicalize_lang(lang) or lang
        _voice_for_lang = self._voice_for_lang
        assert _voice_for_lang is not None
        return _voice_for_lang.get(lang) or _voice_for_lang['eng']

    @property
    def cache_dir(self) -> str:
        return piper_cache_dir()

    def is_voice_downloaded(self, v: Voice) -> bool:
        if not v or not v.name:  # ty: ignore[redundant-condition]
            v = self._default_voice
        return all(os.path.exists(f.path) for f in files_for_voice(v))

    def delete_voice(self, v: Voice) -> None:
        if not v.name:
            v = self._default_voice
        delete_voice_data(v)

    def _download_voice(self, voice: Voice, download_even_if_exists: bool = False) -> bool:
        return download_voice(voice, download_even_if_exists, parent=self, headless=False)

    def download_voice(self, v: Voice) -> None:
        if not v.name:
            v = self._default_voice
        self._download_voice(v, download_even_if_exists=True)

    def _ensure_voice_is_downloaded(self, voice: Voice) -> bool:
        return self._download_voice(voice)

    def validate_settings(self, s: EngineSpecificSettings, parent: QWidget | None) -> bool:
        self._load_voice_metadata()
        voice = self._voice_name_map.get(s.voice_name) or self._default_voice
        try:
            if not self._ensure_voice_is_downloaded(voice):
                error_dialog(
                    parent,
                    _('Failed to download voice'),
                    _('Failed to download the voice: {}').format(voice.human_name),
                    show=True,
                )
                return False
        except Exception:
            import traceback

            error_dialog(
                parent,
                _('Failed to download voice'),
                _('Failed to download the voice: {}').format(voice.human_name),
                det_msg=traceback.format_exc(),
                show=True,
            )
            return False
        return True


class PiperEmbedded:
    def __init__(self):
        self._embedded_settings = EngineSpecificSettings.create_from_config('piper', TTS_EMBEDED_CONFIG)
        self._voice_name_map, self._voices, self._voice_for_lang, self.human_voice_name_map = load_voice_metadata()
        lang = get_lang()
        lang = canonicalize_lang(lang) or lang
        self._default_voice = self._voice_for_lang.get(lang) or self._voice_for_lang['eng']
        self._current_voice = None
        self._current_audio_rate = 0

    def resolve_voice(self, lang: str, voice_name: str) -> Voice:
        from calibre.utils.localization import canonicalize_lang, get_lang

        lang = canonicalize_lang(lang or get_lang() or 'en')
        pv = self._embedded_settings.preferred_voices or {}
        if voice_name and voice_name in self._voice_name_map:
            voice = self._voice_name_map[voice_name]
        elif voice_name and voice_name in self.human_voice_name_map:
            # Fallback for books marked up with display names, which are translated for Kokoro voices
            voice = self.human_voice_name_map[voice_name]
        elif (voice_name := pv.get(lang, '')) and voice_name in self._voice_name_map:
            voice = self._voice_name_map[voice_name]
        else:
            voice = self._voice_for_lang.get(lang) or self._default_voice
        return voice

    def text_to_raw_audio_data(
        self,
        texts: Iterable[str],
        lang: str = '',
        voice_name: str = '',
        sample_rate: int = HIGH_QUALITY_SAMPLE_RATE,
        timeout: float = 10.0,
    ) -> Iterator[tuple[bytes, float]]:
        voice = self.resolve_voice(lang, voice_name)
        if voice is not self._current_voice:
            self._current_voice = voice
            self.shutdown()
        self.ensure_started()
        needs_conversion = sample_rate != self._current_audio_rate
        if needs_conversion:
            from calibre_extensions.ffmpeg import resample_raw_audio_16bit

        for text in texts:
            text = text.strip()
            if not text:
                yield b'', 0.0
                continue
            all_data = []
            global_piper_instance().synthesize(1, text)
            while True:
                sr, exc, tb = self._queue.get()
                if exc is not None:
                    raise Exception(f'failed to synthesize text to audio with error: {exc} and traceback: {tb}')
                all_data.append(sr.audio_data)
                if sr.is_last:
                    break

            raw_data = b''.join(all_data)
            if needs_conversion:
                raw_data = resample_raw_audio_16bit(raw_data, self._current_audio_rate, sample_rate)
            yield raw_data, duration_of_raw_audio_data(raw_data, sample_rate)

    def ensure_voices_downloaded(self, specs: Iterable[tuple[str, str]], parent: QObject | None = None) -> bool:
        for lang, voice_name in specs:
            voice = self.resolve_voice(lang, voice_name)
            if not download_voice(voice, parent=parent, headless=parent is None):
                return False
        return True

    def shutdown(self):
        if self._current_audio_rate != 0:
            gp = global_piper_instance_if_exists()
            if gp is not None:
                gp.cancel()
            self._current_audio_rate = 0

    __del__ = shutdown

    def on_synthesis_done(self, sr: SynthesisResult | None, exc: Exception | None, tb: str | None) -> None:
        self._queue.put((sr, exc, tb))

    def ensure_started(self):
        if self._current_audio_rate == 0:
            from queue import Queue

            assert self._current_voice is not None
            if not download_voice(self._current_voice, headless=True):
                raise Exception(f'Could not download the data for the voice: {self._current_voice.human_name}')
            self._queue = Queue()
            self._current_audio_rate = load_voice_into_synthesizer(self.on_synthesis_done, self._embedded_settings, self._current_voice)


def duration_of_raw_audio_data(data: bytes, sample_rate: int = HIGH_QUALITY_SAMPLE_RATE, bytes_per_sample: int = 2, num_channels: int = 1) -> float:
    total_num_of_samples = len(data) / bytes_per_sample
    num_of_samples_per_channel = total_num_of_samples / num_channels
    return num_of_samples_per_channel / sample_rate


# develop {{{
def develop_embedded():
    p = PiperEmbedded()
    all_data = []
    for data, duration in p.text_to_raw_audio_data((
        'Hello, good day to you.',
        'This is the second sentence.',
        'This is the final sentence.',
    )):
        print(f'{duration=} {len(data)=}')
        all_data.append(data)
    play_pcm_data(b''.join(all_data), HIGH_QUALITY_SAMPLE_RATE)


def develop():

    from qt.core import QSocketNotifier

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

    def handle_input(q: bytes):
        nonlocal play_started
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
        debug('Saying:', repr(text[offset : offset + length]))

    p.state_changed.connect(state_changed)
    p.saying.connect(saying)
    if iswindows:
        from threading import Thread

        class Dispatcher(QObject):
            dispatch = pyqtSignal(object)

        o = Dispatcher(app)
        o.dispatch.connect(handle_input)

        def poll_input():
            import msvcrt

            while True:
                o.dispatch.emit(msvcrt.getch())

        Thread(target=poll_input, daemon=True).start()
    else:
        import tty

        from qt.core import sip

        attr = tty.setraw(sys.stdin.fileno())
        os.set_blocking(sys.stdin.fileno(), False)
        sn = QSocketNotifier(sip.voidptr(sys.stdin.fileno()), QSocketNotifier.Type.Read, p)
        sn.activated.connect(lambda: handle_input(sys.stdin.buffer.read()))
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
