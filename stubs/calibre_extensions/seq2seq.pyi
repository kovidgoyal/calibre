from collections.abc import Sequence

class Seq2SeqModel:
    """Seq2SeqModel(encoder_path, decoder_path, decoder_with_past_path=None, provider='',
    num_threads=0, decoder_start_token_id=0, eos_token_id=1, pad_token_id=0) -> An
    encoder-decoder model. provider is the name of an onnxruntime execution provider,
    the empty string means use only the CPU. num_threads of zero means use the
    onnxruntime default.
    """

    provider: str
    'The name of the onnxruntime execution provider used to run the model'
    node_counts: tuple[int, int]
    '''(number of nodes run by the provider, total number of nodes) for all the
    sessions of this model. Both are zero if onnxruntime is too old to report this
    information.
    '''
    layout: str
    'The layout of the model files: separate, merged or nocache'

    def __init__(
        self,
        encoder_path: str,
        decoder_path: str,
        decoder_with_past_path: str | None = None,
        provider: str = '',
        num_threads: int = 0,
        decoder_start_token_id: int = 0,
        eos_token_id: int = 1,
        pad_token_id: int = 0,
    ) -> None: ...
    def score(self, pairs: Sequence[tuple[Sequence[int], Sequence[int]]]) -> list[tuple[tuple[float, ...], tuple[int, ...]]]:
        """score(pairs) -> For every (input_ids, target_ids) pair return (logprobs, best_ids)
        where logprobs is the log probability of each target token given the input and
        the preceding target tokens and best_ids are the tokens the model considers most
        likely at each position. target_ids should end with the end of sequence token.
        """
        ...
    def generate(
        self,
        input_ids: Sequence[int],
        max_length: int = 256,
        num_beams: int = 1,
        num_return_sequences: int = 1,
        length_penalty: float = 1.0,
        forced_prefix: Sequence[int] = (),
    ) -> list[tuple[tuple[int, ...], float]] | None:
        """generate(input_ids, max_length=256, num_beams=1, num_return_sequences=1,
        length_penalty=1.0, forced_prefix=()) -> Return a list of (token_ids, score)
        sorted by descending score, or None if aborted. The token_ids start with
        forced_prefix and exclude the start and end of sequence tokens. Uses greedy
        decoding when num_beams is 1, otherwise beam search.
        """
        ...
    def abort(self) -> None:
        "abort() -> Abort any generate() calls that are running. Can be called from any thread."
        ...

def gpu_providers() -> tuple[str, ...]:
    """gpu_providers() -> Return the hardware accelerated execution providers available
    in this build of onnxruntime, in order of preference
    """
    ...

def onnxruntime_version() -> str:
    "onnxruntime_version() -> The version of the loaded onnxruntime library"
    ...
