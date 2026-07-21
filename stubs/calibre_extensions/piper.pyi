from typing import Any

def initialize(espeak_data_dir: str = '') -> None:
    (
        "initialize(espeak_data_dir) -> Initialize this module. Must be called once before using any other functions from this module. If espeak_data_dir is"
        " not specified or is the empty string the default data location is used."
    )
    pass

def set_voice(voice_config: Any, model_path: str) -> None:
    "set_voice(voice_config, model_path) -> Load the model in preparation for synthesis."
    pass

def start(text: str) -> None:
    "start(text) -> Start synthesizing the specified text, call next() repeatedly to get the audiodata."
    pass

def next(as_16bit_samples: bool = True) -> tuple[bytes, int, int, bool]:
    (
        "next(as_16bit_samples=True) -> Return the next chunk of audio data (audio_data, num_samples, sample_rate, is_last). Here audio_data is a bytes object"
        " consisting of either native 16bit integer audio samples or native floats in the range [-1, 1]."
    )
    pass

def set_espeak_voice_by_name(name: str) -> None:
    "set_espeak_voice_by_name(name) -> Set the voice to be used to phonemize text"
    pass

def phonemize(text: str) -> list[tuple[str, str, bool]]:
    "phonemize(text) -> Convert the specified text into espeak-ng phonemes"
    pass
