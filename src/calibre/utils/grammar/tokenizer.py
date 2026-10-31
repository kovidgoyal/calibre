#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# A tokenizer for SentencePiece Unigram models such as those used by the T5
# family of models, reading the tokenizer.json files produced by the Hugging
# Face tokenizers library. Normalization follows SentencePiece, using the
# longest match in the precompiled character map.

import json
import re
import struct
from base64 import b64decode
from collections.abc import Callable, Sequence
from typing import NamedTuple, NotRequired, TypedDict

METASPACE = '▁'
UNK_PENALTY = 10.0
WHITESPACE = re.compile(r'\S+')


class AddedToken(TypedDict):
    id: int
    content: str
    special: bool


class UnigramModel(TypedDict):
    type: str
    unk_id: int
    vocab: list[tuple[str, float]]


class ReplacePattern(TypedDict):
    Regex: NotRequired[str]
    String: NotRequired[str]


class Normalizer(TypedDict):
    type: str
    precompiled_charsmap: NotRequired[str]  # Precompiled
    normalizers: NotRequired[list[Normalizer]]  # Sequence
    pattern: NotRequired[ReplacePattern]  # Replace
    content: NotRequired[str]  # Replace


class TokenizerData(TypedDict):
    model: UnigramModel
    normalizer: Normalizer | None
    added_tokens: NotRequired[list[AddedToken]]


class Token(NamedTuple):
    id: int
    # Offsets into the original, un-normalized text. The Metaspace character
    # at the start of a word does not correspond to any text, so tokens
    # consisting only of it have start == end.
    start: int
    end: int


class NormalizedText(NamedTuple):
    text: str
    # For every character in text, the span of the original text it came from
    spans: list[tuple[int, int]]


def identity_spans(text: str) -> list[tuple[int, int]]:
    return [(i, i + 1) for i in range(len(text))]


class Replace:
    def __init__(self, pattern: ReplacePattern, content: str) -> None:
        if 'Regex' in pattern:
            self.pat = re.compile(pattern['Regex'])
        elif 'String' in pattern:
            self.pat = re.compile(re.escape(pattern['String']))
        else:
            raise ValueError(f'Unsupported Replace normalizer pattern: {pattern}')
        self.content = content

    def __call__(self, nt: NormalizedText) -> NormalizedText:
        out: list[str] = []
        spans: list[tuple[int, int]] = []
        pos = 0
        for m in self.pat.finditer(nt.text):
            out.append(nt.text[pos : m.start()])
            spans.extend(nt.spans[pos : m.start()])
            if m.end() > m.start():
                span = nt.spans[m.start()][0], nt.spans[m.end() - 1][1]
            else:
                o = nt.spans[m.start()][0] if m.start() < len(nt.spans) else (nt.spans[-1][1] if nt.spans else 0)
                span = o, o
            out.append(self.content)
            spans.extend(span for _ in self.content)
            pos = m.end()
        out.append(nt.text[pos:])
        spans.extend(nt.spans[pos:])
        return NormalizedText(''.join(out), spans)


class PrecompiledCharsMap:
    """
    The character normalization map used by SentencePiece. It consists of a
    darts-clone double array trie, mapping UTF-8 byte sequences to offsets in a
    blob of NUL terminated replacement strings.
    """

    def __init__(self, data: bytes) -> None:
        if len(data) < 4:
            raise ValueError('Precompiled charsmap is too short')
        (trie_size,) = struct.unpack_from('<I', data)
        if trie_size % 4 or 4 + trie_size > len(data):
            raise ValueError('Precompiled charsmap has an invalid trie size')
        self.units: tuple[int, ...] = struct.unpack_from(f'<{trie_size // 4}I', data, 4)
        self.normalized = data[4 + trie_size :]
        self.cache: dict[int, str] = {}

    def longest_prefix(self, key: bytes, pos: int) -> tuple[int, str] | None:
        """Return (length in bytes, replacement) for the longest key in the trie that is a prefix of key[pos:]"""
        units = self.units
        unit = units[0]
        node_pos = (unit >> 10) << ((unit & (1 << 9)) >> 6)
        ans: tuple[int, int] | None = None
        for i in range(pos, len(key)):
            c = key[i]
            node_pos ^= c
            if node_pos >= len(units):
                break
            unit = units[node_pos]
            if (unit & ((1 << 31) | 0xFF)) != c:
                break
            node_pos ^= (unit >> 10) << ((unit & (1 << 9)) >> 6)
            if (unit >> 8) & 1:
                ans = i + 1 - pos, units[node_pos] & ((1 << 31) - 1)
        if ans is None:
            return None
        length, offset = ans
        if (r := self.cache.get(offset)) is None:
            end = self.normalized.find(b'\0', offset)
            r = self.cache[offset] = self.normalized[offset : end if end > -1 else len(self.normalized)].decode('utf-8', 'replace')
        return length, r

    def __call__(self, nt: NormalizedText) -> NormalizedText:
        ans = self.normalize(nt.text)
        return NormalizedText(ans.text, [(nt.spans[a][0], nt.spans[b - 1][1]) for a, b in ans.spans])

    def normalize(self, text: str) -> NormalizedText:
        raw = text.encode('utf-8')
        # Map byte offsets to character offsets
        char_at_byte = [0] * (len(raw) + 1)
        bpos = 0
        for ci, ch in enumerate(text):
            n = len(ch.encode('utf-8'))
            for k in range(n):
                char_at_byte[bpos + k] = ci
            bpos += n
        char_at_byte[len(raw)] = len(text)
        out: list[str] = []
        spans: list[tuple[int, int]] = []
        pos = 0
        while pos < len(raw):
            start_char = char_at_byte[pos]
            if (m := self.longest_prefix(raw, pos)) is not None:
                length, replacement = m
                end_char = char_at_byte[pos + length]
                if end_char == start_char:  # match ends inside a character
                    end_char = start_char + 1
                    length = len(text[start_char].encode('utf-8'))
                out.append(replacement)
                spans.extend((start_char, end_char) for _ in replacement)
                pos += length
            else:
                ch = text[start_char]
                out.append(ch)
                spans.append((start_char, start_char + 1))
                pos += len(ch.encode('utf-8'))
        return NormalizedText(''.join(out), spans)


class UnigramTokenizer:
    def __init__(self, data: TokenizerData) -> None:
        model = data['model']
        if model['type'] != 'Unigram':
            raise ValueError(f'Unsupported tokenizer model type: {model["type"]}')
        self.unk_id: int = int(model['unk_id'])
        pieces: dict[str, tuple[int, float]] = {}
        id_to_piece: list[str] = []
        min_score = 0.0
        for i, (piece, score) in enumerate(model['vocab']):
            pieces[piece] = i, float(score)
            id_to_piece.append(piece)
            min_score = min(min_score, float(score))
        self.unk_score = min_score - UNK_PENALTY
        self.special_ids: set[int] = set()
        for t in data.get('added_tokens') or ():
            tid = int(t['id'])
            while len(id_to_piece) <= tid:
                id_to_piece.append('')
            id_to_piece[tid] = t['content']
            if t.get('special'):
                self.special_ids.add(tid)
                pieces.pop(t['content'], None)
        self.pieces = pieces
        self.id_to_piece = id_to_piece
        self.max_piece_length = max(map(len, pieces)) if pieces else 1
        self.normalizers: list[Callable[[NormalizedText], NormalizedText]] = []
        if (n := data.get('normalizer')) is not None:
            self.add_normalizer(n)
        self.eos_id = self.special_id('</s>', 1)
        self.pad_id = self.special_id('<pad>', 0)

    def special_id(self, content: str, default: int) -> int:
        for tid in self.special_ids:
            if self.id_to_piece[tid] == content:
                return tid
        return default

    @property
    def vocab_size(self) -> int:
        return len(self.id_to_piece)

    def add_normalizer(self, n: Normalizer) -> None:
        match n['type']:
            case 'Sequence':
                for x in n.get('normalizers', ()):
                    self.add_normalizer(x)
            case 'Precompiled':
                if 'precompiled_charsmap' not in n:
                    raise ValueError('Precompiled normalizer has no charsmap')
                self.normalizers.append(PrecompiledCharsMap(b64decode(n['precompiled_charsmap'])))
            case 'Replace':
                if 'pattern' not in n:
                    raise ValueError('Replace normalizer has no pattern')
                self.normalizers.append(Replace(n['pattern'], n.get('content', '')))
            case _:
                raise ValueError(f'Unsupported tokenizer normalizer: {n["type"]}')

    def normalize(self, text: str) -> NormalizedText:
        ans = NormalizedText(text, identity_spans(text))
        for n in self.normalizers:
            ans = n(ans)
        return ans

    def encode_word(self, word: str) -> list[tuple[int, int, int]]:
        """Return (id, start, end) for the tokens of word, which must start with METASPACE. start and end are offsets into word."""
        n = len(word)
        pieces, maxlen, unk_id, unk_score = self.pieces, self.max_piece_length, self.unk_id, self.unk_score
        best_score = [float('-inf')] * (n + 1)
        best_score[0] = 0.0
        back: list[tuple[int, int]] = [(0, -1)] * (n + 1)  # (start, token id)
        for start in range(n):
            base = best_score[start]
            if base == float('-inf'):
                continue
            has_single = False
            for end in range(start + 1, min(n, start + maxlen) + 1):
                if (p := pieces.get(word[start:end])) is not None:
                    if end == start + 1:
                        has_single = True
                    s = base + p[1]
                    if s > best_score[end]:
                        best_score[end] = s
                        back[end] = start, p[0]
            if not has_single:
                s = base + unk_score
                if s > best_score[start + 1]:
                    best_score[start + 1] = s
                    back[start + 1] = start, unk_id
        ans: list[tuple[int, int, int]] = []
        end = n
        while end > 0:
            start, tid = back[end]
            if tid == unk_id and ans and ans[-1][0] == unk_id:  # fuse consecutive unknowns
                ans[-1] = unk_id, start, ans[-1][2]
            else:
                ans.append((tid, start, end))
            end = start
        ans.reverse()
        return ans

    def encode(self, text: str, add_eos: bool = True) -> list[Token]:
        nt = self.normalize(text)
        ans: list[Token] = []
        for m in WHITESPACE.finditer(nt.text):
            word_start = m.start()
            for tid, s, e in self.encode_word(METASPACE + m.group()):
                # Offsets in the word are shifted by one because of the
                # prepended METASPACE
                s, e = max(0, s - 1), e - 1
                if s == e:
                    o = nt.spans[word_start][0]
                    ans.append(Token(tid, o, o))
                else:
                    ans.append(Token(tid, nt.spans[word_start + s][0], nt.spans[word_start + e - 1][1]))
        if add_eos:
            ans.append(Token(self.eos_id, len(text), len(text)))
        return ans

    def encode_ids(self, text: str, add_eos: bool = True) -> list[int]:
        return [t.id for t in self.encode(text, add_eos)]

    def decode(self, ids: Sequence[int], skip_special_tokens: bool = True) -> str:
        parts = []
        for tid in ids:
            if skip_special_tokens and (tid in self.special_ids or tid == self.unk_id):
                continue
            parts.append(self.id_to_piece[tid] if 0 <= tid < len(self.id_to_piece) else '')
        ans = ''.join(parts).replace(METASPACE, ' ')
        return ans.removeprefix(' ')


def load_tokenizer(path: str) -> UnigramTokenizer:
    with open(path, 'rb') as f:
        data = json.loads(f.read())
    return UnigramTokenizer(data)


def develop(path: str = '/tmp/gm/gec/tokenizer.json') -> None:
    import sys

    t = load_tokenizer(path)
    text = ' '.join(sys.argv[1:]) or 'Hello, world! This is a test of the tokenizer.'
    tokens = t.encode(text)
    print([(t.id_to_piece[x.id], text[x.start : x.end]) for x in tokens])
    print(t.decode([x.id for x in tokens]))
