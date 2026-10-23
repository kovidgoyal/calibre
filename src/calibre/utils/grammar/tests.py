#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import hashlib
import io
import os
import re
import shutil
import struct
import tempfile
import unittest
from base64 import b64encode
from collections.abc import Callable, Sequence
from multiprocessing import Pipe
from threading import Event, Thread
from unittest.mock import patch

from calibre.utils.grammar.backend import CheckResult, Edit, ModelNotDownloaded, Suggestion, SuggestionsAborted, apply_edits, compute_edits, fold, overlaps
from calibre.utils.grammar.cache import ResultCache
from calibre.utils.grammar.tokenizer import METASPACE, NormalizedText, PrecompiledCharsMap, TokenizerData, UnigramTokenizer, identity_spans
from calibre.utils.grammar.worker import (
    CHECK_CHUNK_SIZE,
    CheckResponse,
    Connection,
    GrammarCheckWorker,
    Server,
    SuggestionWorker,
    SuggestResponse,
    WorkerClient,
)

# Token ids produced by the Hugging Face tokenizers library for the tokenizer
# of the gec-t5-small model
T5_REFERENCE = {
    'Hello, world! This is a test of the tokenizer.': [8774, 6, 296, 55, 100, 19, 3, 9, 794, 13, 8, 14145, 8585, 5, 1],
    'gec: She go to school yesterday and buyed three apple.': [873, 75, 10, 451, 281, 12, 496, 4981, 11, 805, 15, 26, 386, 8947, 5, 1],
    'Ünïcödé façade naïve café — “quotes” ‘single’ … ellipsis': [
        3,
        14858,
        29,
        2,
        75,
        1872,
        3764,
        24369,
        3,
        29,
        9,
        2,
        162,
        11949,
        3,
        318,
        105,
        8270,
        15,
        7,
        153,
        458,
        7,
        53,
        109,
        22,
        3,
        233,
        3,
        7999,
        102,
        7,
        159,
        1,
    ],
    'Numbers 1,234.56 and 3½ fractions ① ② ﬁ ligature': [7720, 7, 1914, 2773, 12451, 948, 11, 2664, 2, 357, 12211, 7, 209, 204, 361, 3, 17140, 2693, 1],
    'Unknown chars: ~ { } \\ ^ ` 漢字 ñ õ łódź Привет': [
        597,
        5661,
        3,
        4059,
        7,
        10,
        3,
        2,
        3,
        2,
        3,
        2,
        3,
        2,
        3,
        2,
        3,
        2,
        3,
        2,
        3,
        2,
        3,
        2,
        3,
        2,
        4922,
        26,
        2,
        3,
        2,
        14709,
        6609,
        15042,
        1,
    ],
    'ＦＵＬＬＷＩＤＴＨ ｶﾀｶﾅ': [27645, 518, 4309, 4611, 3, 2, 1],
    "Don't won't can't I'm we're it's": [1008, 31, 17, 751, 31, 17, 54, 31, 17, 27, 31, 51, 62, 31, 60, 34, 31, 7, 1],
}


def build_double_array(entries: dict[bytes, int]) -> bytes:
    """Build a darts-clone double array trie mapping keys to values, in the format used by SentencePiece"""
    trie: dict[bytes, dict[int, bytes]] = {b'': {}}
    for key in entries:
        for i in range(1, len(key) + 1):
            trie.setdefault(key[: i - 1], {})[key[i - 1]] = key[:i]
            trie.setdefault(key[:i], {})
    units: dict[int, int] = {}
    used: set[int] = {0}
    # Every node must have a distinct base, otherwise a transition from one
    # node could land on a child of another node with the same label
    used_bases: set[int] = set()

    def place(node: bytes, pos: int) -> None:
        children = trie[node]
        labels = sorted(children)
        has_leaf = node in entries
        base = 1
        while base in used_bases or any((base ^ c) in used for c in labels) or (has_leaf and base in used) or base == pos:
            base += 1
        used_bases.add(base)
        offset = pos ^ base
        assert offset < (1 << 21)
        label = node[-1] if node else 0
        units[pos] = label | (int(has_leaf) << 8) | (offset << 10)
        if has_leaf:
            used.add(base)
            units[base] = (1 << 31) | entries[node]
        for c in labels:
            used.add(base ^ c)
        for c in labels:
            place(children[c], base ^ c)

    place(b'', 0)
    size = max(units) + 1
    return struct.pack(f'<{size}I', *(units.get(i, 0) for i in range(size)))


def build_charsmap(mapping: dict[str, str]) -> bytes:
    normalized = b''
    entries: dict[bytes, int] = {}
    for src, dest in mapping.items():
        entries[src.encode('utf-8')] = len(normalized)
        normalized += dest.encode('utf-8') + b'\0'
    trie = build_double_array(entries)
    return struct.pack('<I', len(trie)) + trie + normalized


def make_tokenizer(vocab: Sequence[tuple[str, float]], charsmap: dict[str, str] | None = None) -> UnigramTokenizer:
    data: TokenizerData = {
        'model': {'type': 'Unigram', 'unk_id': 2, 'vocab': [('<pad>', 0.0), ('</s>', 0.0), ('<unk>', 0.0), *vocab]},
        'normalizer': None,
        'added_tokens': [
            {'id': 0, 'content': '<pad>', 'special': True},
            {'id': 1, 'content': '</s>', 'special': True},
            {'id': 2, 'content': '<unk>', 'special': True},
        ],
    }
    if charsmap is not None:
        data['normalizer'] = {
            'type': 'Sequence',
            'normalizers': [
                {'type': 'Precompiled', 'precompiled_charsmap': b64encode(build_charsmap(charsmap)).decode()},
                {'type': 'Replace', 'pattern': {'Regex': ' {2,}'}, 'content': ' '},
            ],
        }
    return UnigramTokenizer(data)


class StubBackend:
    """Stands in for Backend in the worker server, results depend only on the sentence"""

    def __init__(self) -> None:
        self.aborted = Event()
        self.block = Event()
        self.block.set()

    def check_sentences(self, sentences: Sequence[str], lang: str | None = None, model_id: str = '', error_threshold: float = 0.1) -> list[CheckResult]:
        if any(s == 'NOT_DOWNLOADED' for s in sentences):
            raise ModelNotDownloaded('gec-t5-small', 'cpu')
        if any(s == 'CRASH' for s in sentences):
            raise RuntimeError('crash')
        ans = []
        for s in sentences:
            if 'bad' in s:
                e = Edit(s.index('bad'), s.index('bad') + 3, 'good')
                ans.append(CheckResult(s, False, (e,), apply_edits(s, (e,)), -1.0))
            else:
                ans.append(CheckResult(s, True, (), s, -0.1))
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
        while not self.block.wait(0.01):
            if self.aborted.is_set():
                self.aborted.clear()
                raise SuggestionsAborted()
        return [Suggestion(k, f'{k}: {sentence}', -0.5, ()) for k in kinds]

    def abort(self) -> None:
        self.aborted.set()


class InProcessWorker:
    """Run the worker server in a thread of this process, with a stub backend"""

    def __init__(self, client: WorkerClient, backend: StubBackend):
        self.client, self.backend = client, backend

    def ensure_worker(self) -> Connection:
        c = self.client
        if c.requests is not None:
            return c.requests
        req_read, req_write = Pipe(False)
        resp_read, resp_write = Pipe(False)
        Thread(target=Server(req_read, resp_write, self.backend).run, daemon=True).start()
        Thread(target=c.read_responses, args=(resp_read, None), daemon=True).start()
        c.requests = req_write
        return req_write


class InProcessCheckWorker(GrammarCheckWorker):
    def __init__(self, backend: StubBackend, cache: ResultCache):
        super().__init__(cache=cache)
        self.inprocess = InProcessWorker(self, backend)

    def ensure_worker(self) -> Connection:
        return self.inprocess.ensure_worker()

    def cleanup_worker(self) -> None:
        pass


class InProcessSuggestionWorker(SuggestionWorker):
    def __init__(self, backend: StubBackend, cache: ResultCache):
        super().__init__(cache=cache)
        self.inprocess = InProcessWorker(self, backend)

    def ensure_worker(self) -> Connection:
        return self.inprocess.ensure_worker()

    def cleanup_worker(self) -> None:
        pass


class TestGrammar(unittest.TestCase):
    def setUp(self) -> None:
        self.tdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tdir, ignore_errors=True)

    def test_grammar_unigram_tokenizer(self):
        t = make_tokenizer([(METASPACE, -2.0), (f'{METASPACE}hello', -1.0), ('lo', -3.0), (f'{METASPACE}hel', -3.0), ('w', -4.0), ('o', -4.0), ('r', -4.0)])
        tokens = t.encode('hello  wor')
        pieces = [t.id_to_piece[x.id] for x in tokens]
        self.assertEqual(pieces, [f'{METASPACE}hello', METASPACE, 'w', 'o', 'r', '</s>'])
        self.assertEqual([(x.start, x.end) for x in tokens], [(0, 5), (7, 7), (7, 8), (8, 9), (9, 10), (10, 10)])
        # Consecutive unknown characters are fused into a single token
        tokens = t.encode('xyz hello', add_eos=False)
        self.assertEqual([x.id for x in tokens], [t.pieces[METASPACE][0], t.unk_id, t.pieces[f'{METASPACE}hello'][0]])
        self.assertEqual((tokens[1].start, tokens[1].end), (0, 3))
        self.assertEqual(t.decode(t.encode_ids('hello wor')), 'hello wor')
        self.assertEqual(t.decode(t.encode_ids('xyz hello')), ' hello')
        self.assertEqual(t.encode_ids(''), [t.eos_id])

    def test_grammar_precompiled_charsmap(self):
        mapping = {'ﬁ': 'fi', 'Å': 'A', 'Å': 'Å', '\t': ' ', 'ab': 'X'}
        cm = PrecompiledCharsMap(build_charsmap(mapping))
        for src, dest in mapping.items():
            self.assertEqual(cm.longest_prefix(src.encode(), 0), (len(src.encode()), dest))
        self.assertIsNone(cm.longest_prefix(b'z', 0))
        # The longest match wins
        self.assertEqual(cm.longest_prefix('Å!'.encode(), 0), (3, 'Å'))
        nt = cm.normalize('a ﬁ\tÅ ab c')
        self.assertEqual(nt.text, 'a fi Å X c')
        self.assertEqual(nt.spans[2:4], [(2, 3), (2, 3)])
        self.assertEqual(nt.spans[5], (4, 6))
        t = make_tokenizer([(METASPACE, -2.0), ('f', -1.0), ('i', -1.0), (f'{METASPACE}fi', -1.0), ('X', -1.0)], mapping)
        self.assertEqual(t.normalize('ﬁ    ab').text, 'fi X')
        tokens = t.encode('ﬁ   ab', add_eos=False)
        self.assertEqual([t.id_to_piece[x.id] for x in tokens], [f'{METASPACE}fi', METASPACE, 'X'])
        self.assertEqual([(x.start, x.end) for x in tokens], [(0, 1), (4, 4), (4, 6)])

    def test_grammar_reference_tokenization(self):
        from calibre.utils.grammar.models import is_downloaded, model_files

        if not is_downloaded('gec-t5-small', 'cpu'):
            raise unittest.SkipTest('The gec-t5-small model is not downloaded')
        from calibre.utils.grammar.tokenizer import load_tokenizer

        t = load_tokenizer(model_files('gec-t5-small', 'cpu').tokenizer)
        for text, expected in T5_REFERENCE.items():
            self.assertEqual(t.encode_ids(text), expected, text)

    def test_grammar_edits(self):
        def edits(original: str, corrected: str, expected: str = '') -> list[tuple[str, str]]:
            nt = NormalizedText(original, identity_spans(original))
            ans = compute_edits(original, nt, corrected)
            expected = expected or (corrected if ans else original)
            self.assertEqual(fold(apply_edits(original, ans)), fold(expected))
            return [(original[e.start : e.end], e.replacement) for e in ans]

        self.assertEqual(edits('She go to school.', 'She went to school.'), [('go', 'went')])
        self.assertEqual(edits('Despite of the rain.', 'Despite the rain.'), [(' of', '')])
        self.assertEqual(edits('of the rain.', 'the rain.'), [('of ', '')])
        self.assertEqual(edits('I have dog.', 'I have a dog.'), [('dog', 'a dog')])
        self.assertEqual(edits('I have a dog', 'I have a dog.'), [('dog', 'dog.')])
        self.assertEqual(edits('Their going.', 'They are going.'), [('Their', 'They are')])
        # Whitespace and typography differences are ignored
        self.assertEqual(edits('“What do you mean?” he asked.', '" What do you mean ?" he asked.'), [])
        self.assertEqual(edits('Yes I know.', 'Yes, I know.'), [('Yes', 'Yes,')])
        self.assertEqual(edits('It’s fine.', "It's fine."), [])
        # Spaces inserted between letters and digits are ignored, as are case
        # changes to words that look like identifiers
        self.assertEqual(edits('Files have the .azw3 extension.', 'Files have the .azw 3 extension.'), [])
        self.assertEqual(edits('Two types Mobi6 and KF8.', 'Two types, Mobi 6 and KF 8.', 'Two types, Mobi6 and KF8.'), [('types', 'types,')])
        self.assertEqual(edits('The metadata ToC is here.', 'The metadata toC is here.'), [])
        self.assertEqual(edits('the end.', 'The end.'), [('the', 'The')])
        # The apostrophe style of the original is used
        self.assertEqual(edits('They’re here, isnt it?', "They're here, isn't it?"), [('isnt', 'isn’t')])
        self.assertTrue(overlaps(Edit(2, 5, 'x'), [(4, 6)]))
        self.assertFalse(overlaps(Edit(2, 4, 'x'), [(4, 6)]))
        self.assertTrue(overlaps(Edit(4, 4, 'x'), [(4, 6)]))
        # Offsets map back to the un-normalized text
        original = 'The ﬁsh are big.'
        normalized = 'The fish are big.'
        spans = [(i, i + 1) for i in range(4)] + [(4, 5), (4, 5)] + [(i - 1, i) for i in range(6, len(original) + 1)]
        nt = NormalizedText(normalized, spans)
        e = compute_edits(original, nt, 'The fish is big.')
        self.assertEqual([(original[x.start : x.end], x.replacement) for x in e], [('are', 'is')])

    def test_grammar_metadata(self):
        from calibre.utils.grammar.models import (
            FILE_ROLES,
            canonical_lang,
            default_model,
            file_path,
            grammar_metadata,
            iter_files,
            models_for,
            suggestion_kinds,
            supports_task,
        )

        md = grammar_metadata()
        self.assertEqual(md['version'], 1)
        for task, lang_map in md['defaults'].items():
            for lang, model_id in lang_map.items():
                self.assertIn(model_id, md['models'])
                self.assertTrue(supports_task(md['models'][model_id], 'check' if task == 'check' else 'suggest'))
        for model_id, m in md['models'].items():
            self.assertIn('cpu', m['variants'])
            for vname, v in m['variants'].items():
                for role in FILE_ROLES:
                    fd = v[role]
                    if fd is None:
                        self.assertEqual(role, 'decoder_with_past')
                        continue
                    self.assertRegex(fd['sha256'], r'^[0-9a-f]{64}$')
                    self.assertGreater(fd['size'], 0)
                    self.assertTrue(fd['url'].startswith('https://huggingface.co/'))
                    self.assertTrue(re.search(r'/resolve/[0-9a-f]{40}/', fd['url']), fd['url'])
                paths = [p for r, fd, p in iter_files(model_id, 'cpu')]
                self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(canonical_lang('en_US'), 'en')
        self.assertEqual(canonical_lang('en-GB'), 'en')
        self.assertEqual(canonical_lang('eng'), 'en')
        self.assertEqual(canonical_lang(None), 'en')
        self.assertEqual(default_model('check', 'en_US'), 'gec-t5-small')
        self.assertIsNone(default_model('check', 'xx'))
        self.assertEqual(models_for('check', 'en')[0], 'gec-t5-small')
        self.assertIn('fluency', suggestion_kinds('coedit-large'))
        self.assertNotIn('check', suggestion_kinds('coedit-large'))
        fd = md['models']['gec-t5-small']['variants']['cpu']['tokenizer']
        self.assertEqual(file_path('gec-t5-small', fd), file_path('gec-t5-small', md['models']['gec-t5-small']['variants']['gpu']['tokenizer']))

    def test_grammar_download(self):
        from calibre.utils.grammar.models import DownloadAborted, DownloadCorrupted, FileData, download_file

        data = os.urandom(3 * 1024 * 1024 + 17)
        fd: FileData = {'url': 'https://example.com/x/model.onnx', 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
        path = os.path.join(self.tdir, 'sub', 'model.onnx')
        progress: list[int] = []
        download_file(fd, path, progress.append, opener=lambda url: io.BytesIO(data))
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), data)
        self.assertEqual(progress[-1], len(data))
        os.remove(path)
        bad: FileData = {'url': fd['url'], 'sha256': '0' * 64, 'size': len(data)}
        with self.assertRaises(DownloadCorrupted):
            download_file(bad, path, opener=lambda url: io.BytesIO(data))
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(path + '.part'))
        abort = Event()
        abort.set()
        with self.assertRaises(DownloadAborted):
            download_file(fd, path, abort=abort, opener=lambda url: io.BytesIO(data))
        self.assertFalse(os.listdir(os.path.dirname(path)))

    def test_grammar_cache(self):
        path = os.path.join(self.tdir, 'cache.sqlite')
        e = Edit(0, 3, 'Good')
        results = [CheckResult('bad dog', False, (e,), 'Good dog', -1.5), CheckResult('ok', True, (), 'ok', -0.1)]
        suggestions = [Suggestion('fluency', 'A better sentence', -0.3, (Edit(2, 8, 'better'),))]
        for p in (None, path):
            c = ResultCache(p)
            c.set_check_results('m1', results)
            c.set_check_results('m1', [CheckResult('skipped', True, (), 'skipped', 0.0, skipped=True)])
            c.set_suggestions('m1', 'A good sentence', ('fluency',), 1, 1, suggestions)
            self.assertEqual(c.get_check_results('m1', ['ok', 'missing', 'bad dog', 'skipped']), {0: results[1], 2: results[0]})
            self.assertEqual(c.get_check_results('m2', ['ok']), {})
            self.assertEqual(c.get_suggestions('m1', 'A good sentence', ('fluency',), 1, 1), suggestions)
            self.assertIsNone(c.get_suggestions('m1', 'A good sentence', ('formal',), 1, 1))
            c.close()
        # Results persist and are read back from the database
        c = ResultCache(path, memory_entries=1)
        self.assertEqual(c.get_check_results('m1', ['bad dog', 'ok']), {0: results[0], 1: results[1]})
        c.close()
        # Pruning removes the least recently used entries
        c = ResultCache(path, max_entries=10)
        c.set_check_results('m3', [CheckResult(f's{i}', True, (), f's{i}', 0.0) for i in range(30)])
        c.prune()
        conn = c.conn
        assert conn is not None
        self.assertLessEqual(next(conn.cursor().execute('SELECT COUNT(*) FROM results'))[0], 10)
        c.close()
        # A corrupted database is replaced
        with open(path, 'wb') as f:
            f.write(b'not a database' * 100)
        c = ResultCache(path)
        self.assertIsNotNone(c.conn)
        c.set_check_results('m1', results[:1])
        self.assertEqual(c.get_check_results('m1', ['bad dog']), {0: results[0]})
        c.close()

    def test_grammar_gpu_decisions(self):
        from calibre.utils.grammar import backend, gpu

        with patch.object(gpu, 'decisions_path', lambda: os.path.join(self.tdir, 'gpu.json')), patch.object(gpu, 'onnxruntime_version', lambda: '1.0'):
            self.assertIsNone(gpu.get_decision('m', 'h' * 64, 'P'))
            gpu.set_decision('m', 'h' * 64, 'P', {'use_gpu': False, 'reason': 'slow', 'gpu_ms': 2.0, 'cpu_ms': 1.0})
            d = gpu.get_decision('m', 'h' * 64, 'P')
            assert d is not None
            self.assertFalse(d['use_gpu'])
            with patch.object(backend, 'providers_for_mode', lambda mode: () if mode == 'off' else ('P',)):
                self.assertEqual(backend.choose_variant('coedit-large', 'off'), 'cpu')
                self.assertEqual(backend.choose_variant('coedit-large', 'on'), 'gpu')
                # auto mode does not use the GPU for small models
                self.assertEqual(backend.choose_variant('gec-t5-small', 'auto'), 'cpu')
                self.assertEqual(backend.choose_variant('coedit-large', 'auto'), 'gpu')
                h = backend.gpu_model_hash('coedit-large')
                gpu.set_decision('coedit-large', h, 'P', {'use_gpu': False, 'reason': 'slow', 'gpu_ms': 2.0, 'cpu_ms': 1.0})
                self.assertEqual(backend.choose_variant('coedit-large', 'auto'), 'cpu')
                self.assertEqual(backend.choose_variant('coedit-large', 'on'), 'gpu')
            gpu.clear_decisions()
            self.assertIsNone(gpu.get_decision('m', 'h' * 64, 'P'))
        self.assertEqual(gpu.gpu_mode_from_string('on'), 'on')
        self.assertEqual(gpu.gpu_mode_from_string('nonsense'), gpu.DEFAULT_GPU_MODE)

    def test_grammar_worker_protocol(self):
        cache = ResultCache(None)
        backend = StubBackend()
        client = InProcessCheckWorker(backend, cache)
        responses: list[CheckResponse] = []
        done = Event()

        def on_check(r: CheckResponse) -> None:
            responses.append(r)
            if r.done:
                done.set()

        def check(sentences: Sequence[str], lang: str | None = None) -> tuple[dict[int, CheckResult], CheckResponse]:
            responses.clear()
            done.clear()
            client.check(sentences, on_check, lang)
            self.assertTrue(done.wait(10))
            results: dict[int, CheckResult] = {}
            for r in responses:
                results.update(r.results)
            return results, responses[-1]

        sentences = [f'sentence {i} is bad' if i % 3 == 0 else f'sentence {i}' for i in range(2 * CHECK_CHUNK_SIZE + 3)]
        sentences.append(sentences[0])  # duplicates are checked only once
        results, last = check(sentences)
        self.assertEqual(set(results), set(range(len(sentences))))
        self.assertFalse(results[0].correct)
        self.assertEqual(results[0].corrected, 'sentence 0 is good')
        self.assertTrue(results[1].correct)
        self.assertEqual(results[len(sentences) - 1], results[0])
        self.assertTrue(last.done)
        self.assertGreaterEqual(len(responses), 4)
        # Everything is now cached, so the worker is not used
        results, last = check(sentences)
        self.assertEqual(len(results), len(sentences))
        self.assertEqual(len(responses), 2)
        results, last = check(['NOT_DOWNLOADED'])
        self.assertEqual((last.model_id, last.variant), ('gec-t5-small', 'cpu'))
        results, last = check(['CRASH'])
        self.assertIn('crash', last.error)
        self.assertIn('RuntimeError', last.details)
        results, last = check(['x'], lang='xx')
        self.assertTrue(last.error)
        client.shutdown()

        sclient = InProcessSuggestionWorker(backend, cache)
        sresponses: list[SuggestResponse] = []
        sdone = Event()

        def on_suggest(r: SuggestResponse) -> None:
            sresponses.append(r)
            if r.done and r.request_id == second:
                sdone.set()

        second = -1
        backend.block.clear()
        first = sclient.suggest('slow sentence', on_suggest, kinds=('fluency',))
        second = sclient.suggest('quick sentence', on_suggest, kinds=('fluency', 'formal'))
        backend.block.set()
        self.assertTrue(sdone.wait(10))
        by_id: dict[int, list[SuggestResponse]] = {}
        for r in sresponses:
            by_id.setdefault(r.request_id, []).append(r)
        self.assertTrue(by_id[first][-1].cancelled)
        self.assertEqual([s.text for r in by_id[second] for s in r.suggestions], ['fluency: quick sentence', 'formal: quick sentence'])
        # Cached suggestions are returned before suggest() returns
        sresponses.clear()
        third = sclient.suggest('quick sentence', on_suggest, kinds=('fluency', 'formal'))
        self.assertEqual([r.request_id for r in sresponses], [third, third])
        self.assertEqual(len(sresponses[0].suggestions), 2)
        self.assertTrue(sresponses[-1].done)
        sclient.shutdown()

    def test_grammar_backend(self):
        from calibre.utils.grammar.models import is_downloaded

        if not is_downloaded('gec-t5-small', 'cpu'):
            raise unittest.SkipTest('The gec-t5-small model is not downloaded')
        from calibre.utils.grammar.backend import Backend

        b = Backend(gpu_mode='off')
        r = b.check_sentences(['  She go to school yesterday.', 'The quick brown fox jumps over the lazy dog.', '...', ''])
        self.assertFalse(r[0].correct)
        self.assertEqual(r[0].corrected, '  She went to school yesterday.')
        self.assertEqual([(r[0].sentence[e.start : e.end], e.replacement) for e in r[0].edits], [('go', 'went')])
        self.assertTrue(r[1].correct)
        self.assertTrue(r[2].correct)
        self.assertTrue(r[3].correct)
        self.assertGreater(r[1].score, r[0].score)
        # Characters the model cannot represent are not changed
        r = b.check('The cost is ~5 {approx} dollars.')
        self.assertNotIn('~', ''.join(e.replacement for e in r.edits))
        self.assertIn('~', r.corrected)


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestGrammar)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
