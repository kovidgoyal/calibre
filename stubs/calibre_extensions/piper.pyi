from typing import Any

def initialize(espeak_data_dir: str = '') -> None:
    """initialize(espeak_data_dir) -> Initialize this module. Must be called once before
    using any other functions from this module. If espeak_data_dir is not specified or
    is the empty string the default data location is used.
    """
    pass

def set_voice(voice_config: Any, model_path: str) -> None:
    "set_voice(voice_config, model_path) -> Load the model in preparation for synthesis."
    pass

def start(text: str) -> None:
    "start(text) -> Start synthesizing the specified text, call next() repeatedly to get the audiodata."
    pass

def next(as_16bit_samples: bool = True) -> tuple[bytes, int, int, bool]:
    """next(as_16bit_samples=True) -> Return the next chunk of audio data
    (audio_data, num_samples, sample_rate, is_last). Here audio_data is a bytes object
    consisting of either native 16bit integer audio samples or native floats in the
    range [-1, 1].
    """
    pass

def set_espeak_voice_by_name(name: str) -> None:
    "set_espeak_voice_by_name(name) -> Set the voice to be used to phonemize text"
    pass

def phonemize(text: str) -> list[tuple[str, str, bool]]:
    "phonemize(text) -> Convert the specified text into espeak-ng phonemes"
    pass

def set_use_gpu(use_gpu: bool) -> None:
    """set_use_gpu(use_gpu) -> Set whether hardware accelerated execution providers
    (GPU, etc.) are used to run the model, falling back to the CPU if they fail. If a
    voice is already loaded it is reloaded. Defaults to False. Must not be called
    concurrently with other functions from this module.
    """
    pass

def gpu_providers() -> tuple[str, ...]:
    """gpu_providers() -> Return the hardware accelerated execution providers available
    in this build of onnxruntime, in the order in which they are tried
    """
    pass

def current_backend() -> tuple[str, str, int, int] | None:
    """current_backend() -> Return (model_path, execution_provider_name,
    num_nodes_on_provider, num_nodes) for the currently loaded model or None if no model
    is loaded. The provider can change from a GPU provider to CPUExecutionProvider if
    the GPU fails while synthesizing. Nodes the provider does not support run on the
    CPU. The node counts are zero if onnxruntime is too old to report them.
    """
    pass
