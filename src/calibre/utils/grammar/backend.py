#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Grammar checking and sentence improvement suggestions using encoder-decoder
# neural networks.
#
# Checking a sentence works by asking the model to correct it while forcing
# its output to be the sentence itself (teacher forcing). If, at every
# position, the token the model considers most likely is the token of the
# sentence, then the model would leave the sentence unchanged, so it is
# correct. This needs only a single run of the encoder and decoder, which is
# much faster than generating a correction. Corrections are generated only for
# sentences that fail this check, starting from the first position where the
# model disagrees with the sentence.

import math
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from difflib import SequenceMatcher
from threading import Lock
from time import monotonic
from typing import TYPE_CHECKING, NamedTuple

from calibre.utils.grammar.gpu import DEFAULT_GPU_MODE, MIN_FRACTION_ON_GPU, GpuDecision, GpuMode, get_decision, providers_for_mode, set_decision
from calibre.utils.grammar.models import (
    ModelData,
    Task,
    Variant,
    available_variants,
    canonical_lang,
    default_model,
    is_downloaded,
    model_data,
    model_files,
    suggestion_kinds,
    variant_files,
)
from calibre.utils.grammar.tokenizer import NormalizedText, UnigramTokenizer, load_tokenizer

if TYPE_CHECKING:
    from calibre_extensions.seq2seq import Seq2SeqModel

# Increment when changes to this module change the results of checks, so that
# cached results are discarded
ALGORITHM_VERSION = 3
# A sentence is considered to have an error only where the model prefers a
# different token and the probability it gives to the token in the sentence
# is below this. Higher values find more errors at the cost of more false
# positives.
DEFAULT_ERROR_THRESHOLD = 0.1
BENCHMARK_SENTENCE = 'The quick brown fox jumps over the lazy dog and then it runs away into the dark forest.'
# Runs of letters (with internal apostrophes), runs of digits and individual
# punctuation characters. Letters and digits are separate units as the models
# were trained on text in which they were often separated by spaces, so they
# tend to insert spaces between them, for example, azw3 -> azw 3.
WORD_UNIT = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*|\d+|_+|[^\w\s]")
# Words such as ToC, iPhone or MOBI6 that are likely names or identifiers
IDENTIFIER_LIKE = re.compile(r'\w*(?:\d|[^\W\d_][A-Z])\w*')
HAS_WORD = re.compile(r'\w')
# (model id, provider) pairs that failed in this process, not tried again
failed_providers: set[tuple[str, str]] = set()
TYPOGRAPHIC_FOLDS = str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"', '„': '"', '–': '-', '—': '-', ' ': ' '})


class Edit(NamedTuple):
    # Offsets into the original sentence of the text to be replaced. start ==
    # end means an insertion.
    start: int
    end: int
    replacement: str


class CheckResult(NamedTuple):
    sentence: str
    correct: bool
    edits: tuple[Edit, ...]
    # The sentence with the edits applied
    corrected: str
    # The mean log probability of the tokens of the sentence according to the
    # model, higher means the model is more confident the sentence is correct
    score: float
    # True if the sentence could not be checked, for example, because it is
    # too long. Such sentences are reported as correct.
    skipped: bool = False


class Suggestion(NamedTuple):
    kind: str  # grammar, fluency, clarity, simplify, formal or paraphrase
    text: str
    score: float  # length normalized log probability of the suggestion
    edits: tuple[Edit, ...]


class ModelNotDownloaded(Exception):
    def __init__(self, model_id: str, variant: Variant) -> None:
        self.model_id, self.variant = model_id, variant
        super().__init__(f'The {variant} variant of the grammar model {model_id} has not been downloaded')


class SuggestionsAborted(Exception):
    pass


class UnsupportedLanguage(ValueError):
    def __init__(self, task: Task, lang: str) -> None:
        self.task, self.lang = task, lang
        super().__init__(f'The language {lang} is not supported for: {task}')


# Text processing {{{


def fold(text: str) -> str:
    return text.translate(TYPOGRAPHIC_FOLDS)


def word_units(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in WORD_UNIT.finditer(text)]


def is_spurious_change(old: str, new: str) -> bool:
    """True if the change from old to new is only in whitespace, typography, or the case of an identifier like word"""
    o, n = ''.join(fold(old).split()), ''.join(fold(new).split())
    if o == n:
        return True
    return o.lower() == n.lower() and IDENTIFIER_LIKE.search(old) is not None


def match_apostrophe_style(original: str, replacement: str) -> str:
    if '’' in original and "'" not in original:
        return replacement.replace("'", '’')
    return replacement


def compute_edits(original: str, nt: NormalizedText, corrected: str) -> list[Edit]:
    """
    Compute the edits that change original into corrected. nt is the
    normalized form of original, which is what the model saw. Differences in
    whitespace and typography (curly vs. straight quotes, etc.) are ignored.
    """
    a = word_units(nt.text)
    b = word_units(corrected)
    sm = SequenceMatcher(None, [fold(x[0]) for x in a], [fold(x[0]) for x in b], autojunk=False)
    ans: list[Edit] = []

    def orig_span(start: int, end: int) -> tuple[int, int]:
        # Convert a span in the normalized text to one in the original text
        return nt.spans[start][0], nt.spans[end - 1][1]

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'insert':
            # Express the insertion as a replacement of an adjacent unit so
            # that it comes with the correct whitespace. Punctuation attaches
            # to the preceding unit, words to the following one.
            attach_to_preceding = i1 > 0 and (i1 == len(a) or not b[j1][0][0].isalnum())
            if i1 < len(a) and not attach_to_preceding:
                start, end = orig_span(a[i1][1], a[i1][2])
                replacement = corrected[b[j1][1] : b[j2][2]]
            elif i1 > 0:
                start, end = orig_span(a[i1 - 1][1], a[i1 - 1][2])
                replacement = corrected[b[j1 - 1][1] : b[j2 - 1][2]]
            else:
                start = end = 0
                replacement = corrected[b[j1][1] : b[j2 - 1][2]]
        else:
            start, end = orig_span(a[i1][1], a[i2 - 1][2])
            replacement = corrected[b[j1][1] : b[j2 - 1][2]] if tag == 'replace' else ''
            if not replacement:
                # Remove the whitespace before the deleted text, or after it
                # if it is at the start
                while start > 0 and original[start - 1].isspace():
                    start -= 1
                if start == 0:
                    while end < len(original) and original[end].isspace():
                        end += 1
        replacement = match_apostrophe_style(original, replacement)
        if not is_spurious_change(original[start:end], replacement):
            ans.append(Edit(start, end, replacement))
    return ans


def apply_edits(text: str, edits: Iterable[Edit]) -> str:
    for e in sorted(edits, key=lambda e: e.start, reverse=True):
        text = text[: e.start] + e.replacement + text[e.end :]
    return text


def overlaps(e: Edit, ranges: Sequence[tuple[int, int]]) -> bool:
    return any((e.start < r_end and r_start < e.end) or (e.start == e.end and r_start <= e.start <= r_end) for r_start, r_end in ranges)


class PreparedSentence(NamedTuple):
    original: str  # the sentence as passed in
    offset: int  # offset of text in original
    text: str  # original with leading and trailing whitespace removed
    normalized: NormalizedText
    target_ids: list[int]
    # Ranges in text of characters the model cannot represent
    unknown_ranges: list[tuple[int, int]]

    def to_original(self, edits: Iterable[Edit]) -> tuple[Edit, ...]:
        return tuple(Edit(e.start + self.offset, e.end + self.offset, e.replacement) for e in edits)


# }}}


# Model loading {{{


def gpu_model_hash(model_id: str) -> str:
    return variant_files(model_id, 'gpu')['encoder']['sha256']


def choose_variant(model_id: str, mode: GpuMode = DEFAULT_GPU_MODE) -> Variant:
    """Return the variant of the model that should be used (and downloaded) for the specified GPU mode"""
    if mode == 'off' or 'gpu' not in available_variants(model_id):
        return 'cpu'
    providers = providers_for_mode(mode)
    if not providers:
        return 'cpu'
    if mode == 'auto':
        if not model_data(model_id)['auto_gpu']:
            return 'cpu'
        h = gpu_model_hash(model_id)
        if all((d := get_decision(model_id, h, p)) is not None and not d['use_gpu'] for p in providers):
            return 'cpu'
    return 'gpu'


def create_model(model_id: str, variant: Variant, provider: str = '', num_threads: int = 0) -> Seq2SeqModel:
    from calibre_extensions.seq2seq import Seq2SeqModel

    md = model_data(model_id)
    f = model_files(model_id, variant)
    return Seq2SeqModel(
        f.encoder,
        f.decoder,
        f.decoder_with_past,
        provider=provider,
        num_threads=num_threads,
        decoder_start_token_id=md['decoder_start_token_id'],
        eos_token_id=md['eos_token_id'],
        pad_token_id=md['pad_token_id'],
    )


def benchmark(model: Seq2SeqModel, tokenizer: UnigramTokenizer, md: ModelData) -> float:
    """Return the time in milliseconds to generate a short output, after a warm up run"""
    prompt = next(iter(md['prompts'].values()))
    ids = tokenizer.encode_ids(prompt + BENCHMARK_SENTENCE)
    model.generate(ids, max_length=8)
    st = monotonic()
    model.generate(ids, max_length=16)
    return 1000 * (monotonic() - st)


class LoadedModel:
    def __init__(self, model_id: str, gpu_mode: GpuMode = DEFAULT_GPU_MODE, num_threads: int = 0) -> None:
        self.model_id = model_id
        self.md = model_data(model_id)
        self.gpu_mode = gpu_mode
        # (provider, error) for providers that could not be used
        self.gpu_failures: list[tuple[str, str]] = []
        self.model, self.variant = self.load(num_threads)
        self.tokenizer = load_tokenizer(model_files(self.model_id, self.variant).tokenizer)
        self.lock = Lock()

    @property
    def provider(self) -> str:
        return self.model.provider

    def load(self, num_threads: int) -> tuple[Seq2SeqModel, Variant]:
        model_id, mode = self.model_id, self.gpu_mode
        variant = choose_variant(model_id, mode)
        if variant == 'gpu' and not is_downloaded(model_id, 'gpu'):
            if not is_downloaded(model_id, 'cpu'):
                raise ModelNotDownloaded(model_id, 'gpu')
            variant = 'cpu'
        if variant == 'gpu':
            if (m := self.load_on_gpu(num_threads)) is not None:
                return m, 'gpu'
        if not is_downloaded(model_id, 'cpu'):
            raise ModelNotDownloaded(model_id, 'cpu')
        return create_model(model_id, 'cpu', num_threads=num_threads), 'cpu'

    def load_on_gpu(self, num_threads: int) -> Seq2SeqModel | None:
        model_id, mode = self.model_id, self.gpu_mode
        h = gpu_model_hash(model_id)
        auto = mode == 'auto'
        tokenizer = load_tokenizer(model_files(model_id, 'gpu').tokenizer)

        def reject(provider: str, reason: str, gpu_ms: float = 0, cpu_ms: float = 0) -> None:
            self.gpu_failures.append((provider, reason))
            failed_providers.add((model_id, provider))
            if auto:
                set_decision(model_id, h, provider, GpuDecision(use_gpu=False, reason=reason, gpu_ms=gpu_ms, cpu_ms=cpu_ms))

        for provider in providers_for_mode(mode):
            if (model_id, provider) in failed_providers:
                continue
            decision = get_decision(model_id, h, provider) if auto else None
            if decision is not None and not decision['use_gpu']:
                continue
            try:
                m = create_model(model_id, 'gpu', provider, num_threads)
                gpu_ms = benchmark(m, tokenizer, self.md)
            except (OSError, RuntimeError) as e:
                reject(provider, str(e))
                continue
            on_provider, total = m.node_counts
            if auto and total and on_provider / total < MIN_FRACTION_ON_GPU:
                reject(provider, f'Only {on_provider} of {total} operations are supported by the GPU', gpu_ms)
                continue
            cpu_ms = 0.0
            if auto and decision is None and is_downloaded(model_id, 'cpu'):
                try:
                    cpu_ms = benchmark(create_model(model_id, 'cpu', num_threads=num_threads), load_tokenizer(model_files(model_id, 'cpu').tokenizer), self.md)
                except (OSError, RuntimeError) as e:
                    print(f'Failed to benchmark the CPU variant of {model_id} with error: {e}', file=sys.stderr)
                if cpu_ms and cpu_ms < gpu_ms:
                    reject(provider, 'The GPU is slower than the CPU', gpu_ms, cpu_ms)
                    continue
            if auto and decision is None:
                set_decision(model_id, h, provider, GpuDecision(use_gpu=True, reason='', gpu_ms=gpu_ms, cpu_ms=cpu_ms))
            return m
        return None

    def prepare(self, sentence: str) -> PreparedSentence:
        text = sentence.strip()
        offset = len(sentence) - len(sentence.lstrip())
        nt = self.tokenizer.normalize(text)
        tokens = self.tokenizer.encode(text)
        unk = self.tokenizer.unk_id
        return PreparedSentence(sentence, offset, text, nt, [t.id for t in tokens], [(t.start, t.end) for t in tokens if t.id == unk])

    def input_ids(self, prompt: str, text: str) -> list[int]:
        return self.tokenizer.encode_ids(prompt + text)

    def fits(self, ps: PreparedSentence) -> bool:
        # Leave room for the prompt and for corrections that are longer than
        # the sentence
        return len(ps.target_ids) <= self.md['max_length'] * 3 // 4

    def max_output_length(self, ps: PreparedSentence) -> int:
        return min(self.md['max_length'], len(ps.target_ids) * 3 // 2 + 16)


# }}}


class Backend:
    """
    Check sentences and generate suggestions for improving them. Models are
    loaded on first use. Raises ModelNotDownloaded if the needed model has
    not been downloaded and UnsupportedLanguage if there is no model for the
    language. Safe to use from multiple threads.
    """

    def __init__(self, gpu_mode: GpuMode = DEFAULT_GPU_MODE, num_threads: int = 0) -> None:
        self.gpu_mode = gpu_mode
        self.num_threads = num_threads
        self.models: dict[str, LoadedModel] = {}
        self.lock = Lock()

    def model_id_for(self, task: Task, lang: str | None) -> str:
        if (model_id := default_model(task, lang)) is None:
            raise UnsupportedLanguage(task, canonical_lang(lang))
        return model_id

    def model(self, model_id: str) -> LoadedModel:
        with self.lock:
            if (m := self.models.get(model_id)) is None:
                m = self.models[model_id] = LoadedModel(model_id, self.gpu_mode, self.num_threads)
            return m

    def load(self, model_id: str) -> None:
        """Load the model if it is not already loaded. Raises ModelNotDownloaded if it has not been downloaded."""
        self.model(model_id)

    def unload(self, model_id: str = '') -> None:
        with self.lock:
            if model_id:
                self.models.pop(model_id, None)
            else:
                self.models.clear()

    def check(self, sentence: str, lang: str | None = None, model_id: str = '', error_threshold: float = DEFAULT_ERROR_THRESHOLD) -> CheckResult:
        return self.check_sentences((sentence,), lang, model_id, error_threshold)[0]

    def check_sentences(
        self, sentences: Sequence[str], lang: str | None = None, model_id: str = '', error_threshold: float = DEFAULT_ERROR_THRESHOLD
    ) -> list[CheckResult]:
        """
        Check the sentences for grammatical errors. error_threshold is the
        probability below which the model must rate a token of the sentence, that
        it would change, for the sentence to be considered to have an error.
        """
        lm = self.model(model_id or self.model_id_for('check', lang))
        prompt = lm.md['prompts']['check']
        results: list[CheckResult | None] = [None] * len(sentences)
        todo: list[tuple[int, PreparedSentence]] = []
        for i, s in enumerate(sentences):
            if not HAS_WORD.search(s):
                results[i] = CheckResult(s, True, (), s, 0.0)
                continue
            ps = lm.prepare(s)
            if lm.fits(ps):
                todo.append((i, ps))
            else:
                results[i] = CheckResult(s, True, (), s, 0.0, skipped=True)
        max_logprob = math.log(max(1e-9, min(1.0, error_threshold)))
        # Sentences are scored one at a time, as with dynamically quantized
        # models the results for a sentence depend on the other sentences in a
        # batch, and batching is no faster on the CPU because of the padding
        for i, ps in todo:
            with lm.lock:
                logprobs, best = lm.model.score([(lm.input_ids(prompt, ps.text), ps.target_ids)])[0]
            score = sum(logprobs) / max(1, len(logprobs))
            mismatch = next((k for k, (x, y, lp) in enumerate(zip(best, ps.target_ids, logprobs)) if x != y and lp < max_logprob), -1)
            results[i] = CheckResult(ps.original, True, (), ps.original, score) if mismatch < 0 else self.correct(lm, prompt, ps, mismatch, score)
        return [r for r in results if r is not None]

    def correct(self, lm: LoadedModel, prompt: str, ps: PreparedSentence, mismatch: int, score: float) -> CheckResult:
        # The model agrees with the sentence up to the first mismatch, so
        # greedy decoding would produce the same tokens until there
        with lm.lock:
            r = lm.model.generate(lm.input_ids(prompt, ps.text), max_length=lm.max_output_length(ps), forced_prefix=ps.target_ids[:mismatch])
        if not r:
            return CheckResult(ps.original, True, (), ps.original, score, skipped=True)
        corrected = lm.tokenizer.decode(r[0][0])
        edits = [e for e in compute_edits(ps.text, ps.normalized, corrected) if not overlaps(e, ps.unknown_ranges)]
        if not edits:
            return CheckResult(ps.original, True, (), ps.original, score)
        oe = ps.to_original(edits)
        return CheckResult(ps.original, False, oe, apply_edits(ps.original, oe), score)

    def score_corrections(self, sentence: str, corrections: Sequence[str], lang: str | None = None, model_id: str = '') -> list[float | None]:
        """
        Return the log probability the checking model gives to correcting the
        sentence into each of the corrections, higher is better. The score is
        None for corrections that could not be scored because they are too
        long.
        """
        lm = self.model(model_id or self.model_id_for('check', lang))
        prompt = lm.md['prompts']['check']
        ps = lm.prepare(sentence)
        if not lm.fits(ps):
            return [None] * len(corrections)
        input_ids = lm.input_ids(prompt, ps.text)
        ans: list[float | None] = []
        for c in corrections:
            target_ids = lm.tokenizer.encode_ids(c.strip())
            if len(target_ids) > lm.md['max_length']:
                ans.append(None)
                continue
            # Scored one at a time for the same reason as in check_sentences()
            with lm.lock:
                logprobs, best = lm.model.score([(input_ids, target_ids)])[0]
            ans.append(sum(logprobs))
        return ans

    def suggest(
        self,
        sentence: str,
        lang: str | None = None,
        kinds: Sequence[str] = (),
        count: int = 1,
        num_beams: int = 1,
        model_id: str = '',
        should_abort: Callable[[], bool] | None = None,
    ) -> list[Suggestion]:
        """
        Return suggestions for improving the sentence. kinds are the kinds of
        suggestion wanted, by default all the kinds the model supports. count
        is the maximum number of suggestions of each kind, num_beams must be at
        least count. Suggestions that are the same as the sentence or as earlier
        suggestions are omitted. Raises SuggestionsAborted if aborted by a call to
        abort() or if should_abort() returns True.
        """
        lm = self.model(model_id or self.model_id_for('suggest', lang))
        kinds = kinds or suggestion_kinds(lm.model_id)
        ans: list[Suggestion] = []
        if not HAS_WORD.search(sentence):
            return ans
        ps = lm.prepare(sentence)
        if not lm.fits(ps):
            return ans
        seen = {fold(' '.join(sentence.split()))}
        for kind in kinds:
            if should_abort is not None and should_abort():
                raise SuggestionsAborted()
            prompt = lm.md['prompts'].get(kind)
            if prompt is None:
                raise KeyError(f'The model {lm.model_id} does not support suggestions of kind: {kind}')
            with lm.lock:
                r = lm.model.generate(
                    lm.input_ids(prompt, ps.text),
                    max_length=lm.max_output_length(ps),
                    num_beams=max(num_beams, count),
                    num_return_sequences=count,
                )
            if r is None:
                raise SuggestionsAborted()
            for ids, score in r:
                edits = compute_edits(ps.text, ps.normalized, lm.tokenizer.decode(ids))
                if not edits or any(overlaps(e, ps.unknown_ranges) for e in edits):
                    continue
                oe = ps.to_original(edits)
                text = apply_edits(ps.original, oe)
                if (key := fold(' '.join(text.split()))) not in seen:
                    seen.add(key)
                    ans.append(Suggestion(kind, text, score, oe))
        return ans

    def abort(self) -> None:
        """Abort any suggestions or corrections being generated. Can be called from any thread."""
        with self.lock:
            models = tuple(self.models.values())
        for m in models:
            m.model.abort()


_global_backend: Backend | None = None
_global_backend_lock = Lock()


def global_backend() -> Backend:
    global _global_backend
    with _global_backend_lock:
        if _global_backend is None:
            _global_backend = Backend()
        return _global_backend


def check(sentence: str, lang: str | None = None) -> CheckResult:
    """Check whether the sentence is grammatically correct"""
    return global_backend().check(sentence, lang)


def suggest(sentence: str, lang: str | None = None, kinds: Sequence[str] = (), count: int = 1) -> list[Suggestion]:
    """Return suggestions for improving the sentence"""
    return global_backend().suggest(sentence, lang, kinds, count)


def develop() -> None:
    import time

    b = Backend(gpu_mode='off')
    sentences = sys.argv[1:] or [
        'She go to school yesterday and buyed three apple.',
        'The quick brown fox jumps over the lazy dog.',
        '“What do you mean?” asked Elizabeth, her eyes wide with astonishment.',
        'Their going to the store tomorrow, isn’t it?',
        'Despite of the rain, we goes outside.',
    ]
    st = time.perf_counter()
    for r in b.check_sentences(sentences):
        print(r.correct, f'{r.score:.3f}', r.sentence)
        for e in r.edits:
            print('   ', repr(r.sentence[e.start : e.end]), '->', repr(e.replacement))
        if not r.correct:
            print('   =>', r.corrected)
    print(f'Checked {len(sentences)} sentences in {time.perf_counter() - st:.2f} seconds')
    st = time.perf_counter()
    for s in b.suggest(sentences[-1]):
        print(s.kind, f'{s.score:.3f}', s.text)
    print(f'Generated suggestions in {time.perf_counter() - st:.2f} seconds')
