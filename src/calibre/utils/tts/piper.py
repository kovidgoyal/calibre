#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import json
import os
import sys
from collections.abc import Callable
from functools import partial
from queue import Queue
from threading import Lock, Thread
from typing import Any, NamedTuple

from calibre.constants import ismacos, iswindows
from calibre_extensions import piper

DEFAULT_LENGTH_SCALE = 1.0
DEFAULT_NOISE_SCALE = 0.667
DEFAULT_NOISE_W_SCALE = 0.8


class VoiceConfig(NamedTuple):
    espeak_voice_name: str
    sample_rate: int
    phoneme_id_map: dict[int, list[int]]
    length_scale: float
    noise_scale: float
    noise_w: float
    num_speakers: int
    sentence_delay: float = 0
    normalize_volume: bool = False
    model_type: str = 'piper'  # piper or kokoro
    # Used only for Kokoro models
    speed: float = 1
    style: bytes = b''


class KokoroVoice(NamedTuple):
    model_path: str
    voice_path: str
    lang_code: str  # Kokoro language code such as a for American English
    lexicon_paths: tuple[str, str] | None = None  # gold and silver lexicons for English


def create_kokoro_voice_config(voice: KokoroVoice, rate: float = 0, sentence_delay: float = 0.2) -> VoiceConfig:
    from calibre.utils.tts.kokoro import kokoro_metadata, speed_from_rate

    md = kokoro_metadata()
    with open(voice.voice_path, 'rb') as f:
        style = f.read()
    return VoiceConfig(
        espeak_voice_name=md['languages'][voice.lang_code]['espeak'],
        sample_rate=md['sample_rate'],
        phoneme_id_map={ord(k): [v] for k, v in md['vocab'].items() if len(k) == 1},
        length_scale=1,
        noise_scale=1,
        noise_w=1,
        num_speakers=1,
        sentence_delay=sentence_delay,
        model_type='kokoro',
        speed=speed_from_rate(rate),
        style=style,
    )


def translate_voice_config(x: Any) -> VoiceConfig:
    phoneme_id_map: dict[int, list[int]] = {}
    for s, pids in x.get('phoneme_id_map', {}).items():
        if s:
            phoneme_id_map.setdefault(ord(s[0]), []).extend(map(int, pids))
    inf = x.get('inference')

    def g(d, prop, defval):
        ans = d.get(prop, VoiceConfig)
        if ans is VoiceConfig:
            ans = defval
        return ans

    return VoiceConfig(
        espeak_voice_name=x.get('espeak', {}).get('voice') or 'en-us',
        sample_rate=int(g(x.get('audio', {}), 'sample_rate', 22050)),
        phoneme_id_map=phoneme_id_map,
        length_scale=float(g(inf, 'length_scale', DEFAULT_LENGTH_SCALE)),
        noise_scale=float(g(inf, 'noise_scale', DEFAULT_NOISE_SCALE)),
        noise_w=float(g(inf, 'noise_w', DEFAULT_NOISE_W_SCALE)),
        num_speakers=int(g(x, 'num_speakers', 1)),
    )


def load_voice_config(path: str) -> VoiceConfig:
    with open(path, 'rb') as f:
        return translate_voice_config(json.load(f))


def espeak_data_dir() -> str:
    if not getattr(sys, 'frozen', False):
        return os.environ.get('CALIBRE_ESPEAK_DATA_DIR', '')
    if iswindows:
        return os.path.join(os.path.dirname(getattr(sys, 'executables_location')), 'share', 'espeak-ng-data')
    if ismacos:
        return os.path.join(os.path.dirname(getattr(sys, 'frameworks_dir')), 'Resources', 'espeak-ng-data')
    return os.path.join(getattr(sys, 'executables_location'), 'share', 'espeak-ng-data')


def create_voice_config(config_path: str, length_scale_multiplier: float = 0, sentence_delay: float = 0.2) -> VoiceConfig:
    cfg = load_voice_config(config_path)
    m = max(0.1, 1 + -1 * max(-1, min(length_scale_multiplier, 1)))  # maps -1 to 1 to 2 to 0.1
    cfg = cfg._replace(sentence_delay=sentence_delay, length_scale=cfg.length_scale * m)
    return cfg


def set_voice(config_path: str, model_path: str, length_scale_multiplier: float = 0, sentence_delay: float = 0.2) -> None:
    cfg = create_voice_config(config_path, length_scale_multiplier, sentence_delay)
    piper.set_voice(cfg, model_path)


class Backend(NamedTuple):
    model_path: str
    # The onnxruntime execution provider running the model, for example
    # CPUExecutionProvider or MIGraphXExecutionProvider
    execution_provider: str
    # Nodes of the model not supported by execution_provider run on the CPU.
    # Both counts are zero if onnxruntime is too old to report them.
    num_nodes_on_provider: int
    num_nodes: int

    @property
    def uses_gpu(self) -> bool:
        return self.execution_provider != 'CPUExecutionProvider'

    @property
    def fraction_on_provider(self) -> float | None:
        return self.num_nodes_on_provider / self.num_nodes if self.num_nodes else None


class SynthesisResult(NamedTuple):
    utterance_id: Any
    bytes_per_sample: int
    audio_data: bytes
    num_samples: int
    sample_rate: int
    is_last: bool


def simple_test():
    d = espeak_data_dir()
    if d and not os.path.exists(os.path.join(d, 'voices')):
        raise AssertionError(f'{d} does not contain espeak-ng data')
    piper.initialize(d)
    # Some espeak-ng builds cannot resolve en-gb by name, ensure the language
    # fallback selects the British voice rather than leaving no voice set.
    piper.set_espeak_voice_by_name('en-gb')
    if 'əʊ' not in piper.phonemize('hello')[0][0]:
        raise AssertionError('Setting the en-gb espeak voice did not select a British English voice')
    try:
        piper.set_espeak_voice_by_name('nonexistent')
    except ValueError:
        pass
    else:
        raise AssertionError('Setting a non-existent espeak voice did not raise an error')
    piper.set_espeak_voice_by_name('en-us')
    if not piper.phonemize('simple test'):
        raise AssertionError('No phonemes returned by phonemize()')
    if '^' not in piper.phonemize('my choice', '^')[0][0]:
        raise AssertionError('No tie characters returned by phonemize()')
    if not isinstance(piper.gpu_providers(), tuple):
        raise AssertionError('gpu_providers() did not return a tuple')  # noqa: TRY004
    if piper.current_backend() is not None:
        raise AssertionError('current_backend() is not None with no model loaded')
    piper.set_use_gpu(True)
    piper.set_use_gpu(False)


ResultCallback = Callable[[SynthesisResult | None, Exception | None, str | None], None]


class Piper(Thread):
    def __init__(self):
        piper.initialize(espeak_data_dir())
        Thread.__init__(self, name='PiperSynth', daemon=True)
        self.commands = Queue()
        self.as_16bit_samples = True
        self._voice_id = 0
        self.lock = Lock()
        self.result_callback: ResultCallback = lambda *a: None
        # Converts text to phonemes for Kokoro voices, only used in the synthesis thread
        self.g2p: Callable[[str], list[str]] | None = None
        # The lexicons used by self.g2p, only used in the synthesis thread
        self.lexicon_paths: tuple[str, str] | None = None
        self.start()

    @property
    def voice_id(self) -> int:
        with self.lock:
            ans = self._voice_id
        return ans

    def increment_voice_id(self) -> int:
        with self.lock:
            self._voice_id += 1
            ans = self._voice_id
        return ans

    def run(self):
        while True:
            voice_id, cmd = self.commands.get(True)
            if cmd is None:
                break
            if voice_id is not None and voice_id != self.voice_id:
                continue
            try:
                cmd()
            except Exception as e:
                import traceback

                self.result_callback(None, e, traceback.format_exc())

    def shutdown(self):
        vid = self.increment_voice_id()
        self.commands.put((vid, None))
        self.join()

    def set_voice(
        self,
        result_callback: ResultCallback,
        config_path: str,
        model_path: str,
        length_scale_multiplier: float = 0,
        sentence_delay: float = 0.2,
        as_16bit_samples: bool = True,
    ) -> int:
        vid = self.increment_voice_id()
        self.result_callback = result_callback
        self.as_16bit_samples = as_16bit_samples
        cfg = create_voice_config(config_path, length_scale_multiplier, sentence_delay)
        self.commands.put((vid, partial(self._set_voice, cfg, model_path)))
        return cfg.sample_rate

    def _release_g2p(self, lexicon_paths: tuple[str, str] | None = None) -> None:
        # Free the memory used by cached lexicons unless they are needed by
        # the new voice
        self.g2p = None
        if self.lexicon_paths != lexicon_paths:
            from calibre.utils.tts.kokoro import load_lexicon

            load_lexicon.cache_clear()
            self.lexicon_paths = None

    def _set_voice(self, cfg: VoiceConfig, model_path: str) -> None:
        self._release_g2p()
        piper.set_voice(cfg, model_path)

    def set_kokoro_voice(
        self,
        result_callback: ResultCallback,
        voice: KokoroVoice,
        rate: float = 0,
        sentence_delay: float = 0.2,
        as_16bit_samples: bool = True,
    ) -> int:
        from calibre.utils.tts.kokoro import kokoro_metadata

        vid = self.increment_voice_id()
        self.result_callback = result_callback
        self.as_16bit_samples = as_16bit_samples
        self.commands.put((vid, partial(self._set_kokoro_voice, voice, rate, sentence_delay)))
        return kokoro_metadata()['sample_rate']

    def _set_kokoro_voice(self, voice: KokoroVoice, rate: float, sentence_delay: float) -> None:
        from calibre.utils.tts.kokoro import G2P

        self._release_g2p(voice.lexicon_paths)
        piper.set_voice(create_kokoro_voice_config(voice, rate, sentence_delay), voice.model_path)
        self.g2p = G2P(voice.lang_code, voice.lexicon_paths)
        self.lexicon_paths = voice.lexicon_paths

    def set_use_gpu(self, use_gpu: bool) -> None:
        # Not tied to a voice so that it is not discarded by cancel() or set_voice()
        self.commands.put((None, partial(piper.set_use_gpu, use_gpu)))

    def current_backend(self) -> Backend | None:
        # Safe to call from any thread. Returns None while a model is being
        # loaded or if no model has been loaded.
        ans = piper.current_backend()
        return None if ans is None else Backend(*ans)

    def cancel(self) -> None:
        self.increment_voice_id()
        self.result_callback = lambda *a: None

    def synthesize(self, utterance_id: Any, text: str) -> None:
        vid = self.voice_id
        self.commands.put((vid, partial(self._synthesize, vid, utterance_id, text)))

    def _synthesize(self, voice_id: int, utterance_id: Any, text: str) -> None:
        if self.g2p is None:
            piper.start(text)
        else:
            piper.start_phonemes(self.g2p(text))
        bytes_per_sample = 2 if self.as_16bit_samples else 4
        while True:
            audio_data, num_samples, sample_rate, is_last = piper.next(self.as_16bit_samples)
            if self.voice_id == voice_id:
                self.result_callback(
                    SynthesisResult(utterance_id, bytes_per_sample, audio_data, num_samples, sample_rate, is_last),
                    None,
                    None,
                )
            else:
                break
            if is_last:
                break


_global_piper_instance = None


def global_piper_instance() -> Piper:
    global _global_piper_instance
    if _global_piper_instance is None:
        _global_piper_instance = Piper()
        atexit.register(_global_piper_instance.shutdown)
    return _global_piper_instance


def global_piper_instance_if_exists() -> Piper | None:
    return _global_piper_instance


def play_wav_data(wav_data: bytes):
    from qt.core import QAudioOutput, QBuffer, QByteArray, QCoreApplication, QIODevice, QMediaPlayer, QUrl

    app = QCoreApplication([])
    m = QMediaPlayer()
    ao = QAudioOutput(m)
    m.setAudioOutput(ao)
    qbuffer = QBuffer()
    qbuffer.setData(QByteArray(wav_data))
    qbuffer.open(QIODevice.OpenModeFlag.ReadOnly)
    m.setSourceDevice(qbuffer, QUrl.fromLocalFile('piper.wav'))
    m.mediaStatusChanged.connect(lambda status: app.quit() if status == QMediaPlayer.MediaStatus.EndOfMedia else print(m.playbackState(), status))
    m.errorOccurred.connect(lambda e, s: (print(e, s, file=sys.stderr), app.quit()))
    m.play()
    app.exec()


def play_pcm_data(pcm_data, sample_rate):
    from calibre_extensions.ffmpeg import wav_header_for_pcm_data

    play_wav_data(wav_header_for_pcm_data(len(pcm_data), sample_rate) + pcm_data)


def develop():
    from calibre.gui2.tts.piper import piper_cache_dir

    p = global_piper_instance()
    model_path = os.path.join(piper_cache_dir(), 'en_US-libritts-high.onnx')
    q = Queue()

    def synthesized(*args):
        q.put(args)

    sample_rate = p.set_voice(synthesized, model_path + '.json', model_path, sentence_delay=0.3)
    p.synthesize(1, 'Testing speech synthesis with piper. A second sentence.')
    all_data = []
    while args := q.get():
        sr, exc, tb = args
        if exc is not None:
            print(tb, file=sys.stderr, flush=True)
            print(exc, file=sys.stderr, flush=True)
            raise SystemExit(1)
        all_data.append(sr.audio_data)
        print(f'Got {len(sr.audio_data)} bytes of audio data', flush=True)
        if sr.is_last:
            break
    play_pcm_data(b''.join(all_data), sample_rate)


if __name__ == '__main__':
    develop()
