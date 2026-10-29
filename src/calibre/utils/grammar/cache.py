#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# A cache of the results of grammar checks and suggestions, so that unchanged
# paragraphs and sentences are not checked again. Results are kept in memory
# and in an SQLite database in the calibre cache directory, so they persist
# across restarts.

import hashlib
import json
import os
import sys
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from contextlib import suppress
from threading import Lock
from time import time
from typing import TypedDict

import apsw

from calibre.utils.grammar.backend import ALGORITHM_VERSION, Edit, Suggestion
from calibre.utils.grammar.checker import ParagraphResult
from calibre.utils.grammar.models import variant_files
from calibre.utils.grammar.rules import Issue, IssueSource

DEFAULT_MAX_ENTRIES = 250_000
DEFAULT_MEMORY_ENTRIES = 20_000
# Access times are recorded with this granularity, in seconds, to avoid
# writing to the database on every cache hit
ATIME_GRANULARITY = 3600
PRUNE_EVERY = 1000

creation_sql = '''
CREATE TABLE IF NOT EXISTS results (
    key BLOB PRIMARY KEY,
    value TEXT NOT NULL,
    atime INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS results_atime ON results (atime);
'''


class SerializedIssue(TypedDict):
    start: int
    end: int
    replacements: list[str]
    message: str
    short_message: str
    rule_id: str
    category: str
    issue_type: str
    url: str
    source: str


class SerializedParagraph(TypedDict):
    sentences: list[tuple[int, int]]
    issues: list[SerializedIssue]
    deep_checked: bool
    ranked: bool


class SerializedSuggestion(TypedDict):
    kind: str
    text: str
    score: float
    edits: list[tuple[int, int, str]]


def model_cache_key(model_id: str) -> str:
    """A key identifying the model and the version of the algorithm used to process its output"""
    return f'{model_id}:{variant_files(model_id, "cpu")["encoder"]["sha256"][:16]}:{ALGORITHM_VERSION}'


def cache_key(model_key: str, task: str, sentence: str) -> bytes:
    return hashlib.sha256(f'{model_key}\0{task}\0{sentence}'.encode('utf-8', 'surrogatepass')).digest()[:20]


def serialize_paragraph(r: ParagraphResult) -> str:
    d: SerializedParagraph = {
        'sentences': [(s, e) for s, e in r.sentences],
        'issues': [
            {
                'start': i.start,
                'end': i.end,
                'replacements': list(i.replacements),
                'message': i.message,
                'short_message': i.short_message,
                'rule_id': i.rule_id,
                'category': i.category,
                'issue_type': i.issue_type,
                'url': i.url,
                'source': i.source,
            }
            for i in r.issues
        ],
        'deep_checked': r.deep_checked,
        'ranked': r.ranked,
    }
    return json.dumps(d, ensure_ascii=False)


def deserialize_paragraph(text: str, raw: str) -> ParagraphResult:
    d: SerializedParagraph = json.loads(raw)
    issues = []
    for i in d['issues']:
        source: IssueSource
        match i['source']:
            case 'rules':
                source = 'rules'
            case 'model':
                source = 'model'
            case x:
                raise ValueError(f'Unknown issue source: {x}')
        issues.append(
            Issue(
                int(i['start']),
                int(i['end']),
                tuple(str(x) for x in i['replacements']),
                str(i['message']),
                str(i['short_message']),
                str(i['rule_id']),
                str(i['category']),
                str(i['issue_type']),
                str(i['url']),
                source,
            )
        )
    sentences = tuple((int(s), int(e)) for s, e in d['sentences'])
    return ParagraphResult(text, sentences, tuple(issues), bool(d['deep_checked']), bool(d['ranked']))


def serialize_suggestions(suggestions: Sequence[Suggestion]) -> str:
    d: list[SerializedSuggestion] = [{'kind': s.kind, 'text': s.text, 'score': s.score, 'edits': [tuple(e) for e in s.edits]} for s in suggestions]
    return json.dumps(d, ensure_ascii=False)


def deserialize_suggestions(raw: str) -> list[Suggestion]:
    d: list[SerializedSuggestion] = json.loads(raw)
    return [Suggestion(str(s['kind']), str(s['text']), float(s['score']), tuple(Edit(int(a), int(b), str(c)) for a, b, c in s['edits'])) for s in d]


def default_cache_path() -> str:
    from calibre.constants import cache_dir

    return os.path.join(cache_dir(), 'grammar', 'results.sqlite')


class ResultCache:
    """Thread safe cache of check results and suggestions. If path is None, only an in-memory cache is used."""

    def __init__(self, path: str | None = '', max_entries: int = DEFAULT_MAX_ENTRIES, memory_entries: int = DEFAULT_MEMORY_ENTRIES):
        self.max_entries = max_entries
        self.memory_entries = memory_entries
        self.memory: OrderedDict[bytes, str] = OrderedDict()
        self.lock = Lock()
        self.puts_since_prune = 0
        self.conn: apsw.Connection | None = None
        if path is not None:
            self.conn = self.open_db(path or default_cache_path())
            if self.conn is not None:
                self.prune()

    def open_db(self, path: str) -> apsw.Connection | None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for attempt in range(2):
            try:
                conn = apsw.Connection(path)
                conn.setbusytimeout(2000)
                conn.cursor().execute(creation_sql)
                return conn
            except apsw.Error as e:
                if attempt == 0 and isinstance(e, (apsw.CorruptError, apsw.NotADBError)):
                    # Results can always be recomputed so discard a corrupted cache
                    for suffix in ('', '-wal', '-shm', '-journal'):
                        with suppress(FileNotFoundError):
                            os.remove(path + suffix)
                    continue
                print(f'Failed to open the grammar results cache at {path} with error: {e}', file=sys.stderr)
                return None
        return None

    def close(self) -> None:
        with self.lock:
            if self.conn is not None:
                self.conn.close()
                self.conn = None

    def clear(self) -> None:
        with self.lock:
            self.memory.clear()
            if self.conn is not None:
                with self.conn:
                    self.conn.cursor().execute('DELETE FROM results')

    def prune(self) -> None:
        if self.conn is None:
            return
        try:
            with self.conn:
                c = self.conn.cursor()
                count = next(c.execute('SELECT COUNT(*) FROM results'))[0]
                if count > self.max_entries:
                    # Remove the least recently used entries, leaving some
                    # room so that pruning is not needed on every write
                    remove = count - (self.max_entries * 9) // 10
                    c.execute('DELETE FROM results WHERE key IN (SELECT key FROM results ORDER BY atime LIMIT ?)', (remove,))
        except apsw.Error as e:
            print(f'Failed to prune the grammar results cache with error: {e}', file=sys.stderr)

    def remember(self, key: bytes, value: str) -> None:
        self.memory[key] = value
        self.memory.move_to_end(key)
        while len(self.memory) > self.memory_entries:
            self.memory.popitem(last=False)

    def get_many(self, keys: Sequence[bytes]) -> dict[bytes, str]:
        ans: dict[bytes, str] = {}
        missing: list[bytes] = []
        with self.lock:
            for k in keys:
                if (v := self.memory.get(k)) is not None:
                    self.memory.move_to_end(k)
                    ans[k] = v
                else:
                    missing.append(k)
            if not missing or self.conn is None:
                return ans
            now = int(time()) // ATIME_GRANULARITY
            try:
                with self.conn:
                    c = self.conn.cursor()
                    found: list[bytes] = []
                    # Stay well under the SQLite limit on the number of parameters
                    for i in range(0, len(missing), 500):
                        chunk = missing[i : i + 500]
                        placeholders = ','.join('?' * len(chunk))
                        for k, v in c.execute(f'SELECT key, value FROM results WHERE key IN ({placeholders})', chunk):
                            ans[k] = v
                            found.append(k)
                            self.remember(k, v)
                    for i in range(0, len(found), 500):
                        chunk = found[i : i + 500]
                        placeholders = ','.join('?' * len(chunk))
                        c.execute(f'UPDATE results SET atime=? WHERE atime<? AND key IN ({placeholders})', (now, now, *chunk))
            except apsw.Error as e:
                print(f'Failed to read from the grammar results cache with error: {e}', file=sys.stderr)
        return ans

    def set_many(self, items: Iterable[tuple[bytes, str]]) -> None:
        items = tuple(items)
        if not items:
            return
        with self.lock:
            for k, v in items:
                self.remember(k, v)
            if self.conn is None:
                return
            now = int(time()) // ATIME_GRANULARITY
            try:
                with self.conn:
                    self.conn.cursor().executemany('INSERT OR REPLACE INTO results (key, value, atime) VALUES (?, ?, ?)', ((k, v, now) for k, v in items))
            except apsw.Error as e:
                print(f'Failed to write to the grammar results cache with error: {e}', file=sys.stderr)
                return
            self.puts_since_prune += len(items)
            if self.puts_since_prune >= PRUNE_EVERY:
                self.puts_since_prune = 0
                self.prune()

    def get_paragraph_results(self, checker_key: str, paragraphs: Sequence[str]) -> dict[int, ParagraphResult]:
        """Return a map of the index of each paragraph that is in the cache to its result"""
        keys = [cache_key(checker_key, 'check', p) for p in paragraphs]
        found = self.get_many(keys)
        ans: dict[int, ParagraphResult] = {}
        for i, (p, k) in enumerate(zip(paragraphs, keys)):
            if (raw := found.get(k)) is not None:
                try:
                    ans[i] = deserialize_paragraph(p, raw)
                except (ValueError, KeyError, TypeError) as e:
                    print(f'Ignoring invalid entry in the grammar results cache: {e}', file=sys.stderr)
        return ans

    def set_paragraph_results(self, checker_key: str, results: Iterable[ParagraphResult]) -> None:
        self.set_many((cache_key(checker_key, 'check', r.text), serialize_paragraph(r)) for r in results)

    def suggestions_task(self, kinds: Sequence[str], count: int, num_beams: int) -> str:
        return f'suggest:{",".join(kinds)}:{count}:{num_beams}'

    def get_suggestions(self, model_key: str, sentence: str, kinds: Sequence[str], count: int, num_beams: int) -> list[Suggestion] | None:
        k = cache_key(model_key, self.suggestions_task(kinds, count, num_beams), sentence)
        if (raw := self.get_many((k,)).get(k)) is None:
            return None
        try:
            return deserialize_suggestions(raw)
        except (ValueError, KeyError, TypeError) as e:
            print(f'Ignoring invalid entry in the grammar results cache: {e}', file=sys.stderr)
            return None

    def set_suggestions(self, model_key: str, sentence: str, kinds: Sequence[str], count: int, num_beams: int, suggestions: Sequence[Suggestion]) -> None:
        k = cache_key(model_key, self.suggestions_task(kinds, count, num_beams), sentence)
        self.set_many(((k, serialize_suggestions(suggestions)),))
