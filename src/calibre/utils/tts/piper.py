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

import calibre_extensions.piper as piper

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
        return ''
    return os.path.join(sys.executables_location, 'share', 'espeak-ng-data')


def create_voice_config(config_path: str, length_scale_multiplier: float = 0, sentence_delay: float = 0.2) -> VoiceConfig:
    cfg = load_voice_config(config_path)
    m = max(0.1, 1 + -1 * max(-1, min(length_scale_multiplier, 1)))  # maps -1 to 1 to 2 to 0.1
    cfg = cfg._replace(sentence_delay=sentence_delay, length_scale=cfg.length_scale * m)
    return cfg


def set_voice(config_path: str, model_path:str, length_scale_multiplier: float = 0, sentence_delay: float = 0.2) -> None:
    cfg = create_voice_config(config_path, length_scale_multiplier, sentence_delay)
    piper.set_voice(cfg, model_path)


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
    piper.set_espeak_voice_by_name('en-us')
    if not piper.phonemize('simple test'):
        raise AssertionError('No phonemes returned by phonemize()')


class Piper(Thread):

    def __init__(self):
        piper.initialize(espeak_data_dir())
        Thread.__init__(self, name='PiperSynth', daemon=True)
        self.commands = Queue()
        self.as_16bit_samples = True
        self._voice_id = 0
        self.lock = Lock()
        self.result_callback = lambda *a: None
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
            if voice_id != self.voice_id:
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
        self, result_callback: Callable[[SynthesisResult, Exception|None, str|None], None],
        config_path: str, model_path:str, length_scale_multiplier: float = 0, sentence_delay: float = 0.2,
        as_16bit_samples: bool = True,
    ) -> int:
        vid = self.increment_voice_id()
        self.result_callback = result_callback
        self.as_16bit_samples = as_16bit_samples
        cfg = create_voice_config(config_path, length_scale_multiplier, sentence_delay)
        self.commands.put((vid, partial(self._set_voice, cfg, model_path)))
        return cfg.sample_rate

    def _set_voice(self, cfg, model_path):
        piper.set_voice(cfg, model_path)

    def cancel(self) -> None:
        self.increment_voice_id()
        self.result_callback = lambda *a: None

    def synthesize(self, utterance_id: Any, text: str) -> None:
        vid = self.voice_id
        self.commands.put((vid, partial(self._synthesize, vid, utterance_id, text)))

    def _synthesize(self, voice_id: int, utterance_id: Any, text: str) -> None:
        piper.start(text)
        bytes_per_sample = 2 if self.as_16bit_samples else 4
        while True:
            audio_data, num_samples, sample_rate, is_last = piper.next(self.as_16bit_samples)
            if self.voice_id == voice_id:
                self.result_callback(SynthesisResult(utterance_id, bytes_per_sample, audio_data, num_samples, sample_rate, is_last), None, None)
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
    m.mediaStatusChanged.connect(
        lambda status: app.quit() if status == QMediaPlayer.MediaStatus.EndOfMedia else print(m.playbackState(), status)
    )
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
    sample_rate = p.set_voice(synthesized, model_path+'.json', model_path, sentence_delay=0.3)
    p.synthesize(1, 'Testing speech synthesis with piper. A second sentence.')
    all_data = []
    while (args := q.get()):
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
