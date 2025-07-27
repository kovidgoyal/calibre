#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import json
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
    for s, pid in x.get('phoneme_id_map', {}).items():
        if s:
            phoneme_id_map.setdefault(ord(s[0]), []).append(pid)
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
    return ''   # TODO: get the correct path when using frozen builds


def set_voice(config_path: str, model_path:str, length_scale_multiplier: float, sentence_delay: float) -> None:
    piper.initialize(espeak_data_dir())
    cfg = load_voice_config(config_path)
    cfg = cfg._replace(sentence_delay=sentence_delay, length_scale=cfg.length_scale * length_scale_multiplier)
    piper.set_voice(cfg, model_path)
