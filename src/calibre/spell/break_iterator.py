#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

import threading
from typing import TYPE_CHECKING

from calibre.utils.icu import _icu
from calibre.utils.localization import get_lang, lang_as_iso639_1

if TYPE_CHECKING:
    import re
    from collections.abc import Iterator

    from calibre_extensions.icu import BreakIterator


class PerThreadIterators(threading.local):
    def __init__(self) -> None:
        self.iterators: dict[str, BreakIterator] = {}
        self.sentence_iterators: dict[str, BreakIterator] = {}
        self.extra_break_char_word_iterators: dict[tuple[str, str | None], BreakIterator] = {}


per_thread_iterators = PerThreadIterators()


def get_iterator(lang: str) -> BreakIterator:
    if (it := per_thread_iterators.iterators.get(lang)) is None:
        it = per_thread_iterators.iterators[lang] = _icu.BreakIterator(_icu.UBRK_WORD, lang_as_iso639_1(lang) or lang)
    return it


def get_word_break_iterator_with_extra_chars(lang: str = '', extra_break_chars: str | None = None) -> BreakIterator:
    extra_break_chars = extra_break_chars or None
    lang = lang or get_lang() or 'en'
    key = lang, extra_break_chars
    if (it := per_thread_iterators.extra_break_char_word_iterators.get(key)) is None:
        it = per_thread_iterators.extra_break_char_word_iterators[key] = _icu.BreakIterator(_icu.UBRK_WORD, lang_as_iso639_1(lang) or lang, extra_break_chars)
    return it


def get_sentence_iterator(lang: str) -> BreakIterator:
    if (it := per_thread_iterators.sentence_iterators.get(lang)) is None:
        it = per_thread_iterators.sentence_iterators[lang] = _icu.BreakIterator(_icu.UBRK_SENTENCE, lang_as_iso639_1(lang) or lang)
    return it


def split_into_words(text: str, lang: str = 'en') -> list[str]:
    it = get_iterator(lang)
    it.set_text(text)
    return [text[p : p + s] for p, s in it.split2()]


def split_into_words_and_positions(text: str, lang: str = 'en') -> list[tuple[int, int]]:
    it = get_iterator(lang)
    it.set_text(text)
    return it.split2()


def sentence_positions(text: str, lang: str = 'en') -> list[tuple[int, int]]:
    it = get_sentence_iterator(lang)
    it.set_text(text)
    return it.split2()


def split_into_sentences(text: str, lang: str = 'en') -> tuple[str, ...]:
    it = get_sentence_iterator(lang)
    it.set_text(text)
    return tuple(text[p : p + s] for p, s in it.split2())


def index_of(needle: str, haystack: str, lang: str = 'en') -> int:
    it = get_iterator(lang)
    it.set_text(haystack)
    return it.index(needle)


def count_words(text: str, lang: str = 'en') -> int:
    it = get_iterator(lang)
    it.set_text(text)
    return it.count_words()


def split_long_sentences(sentence: str, offset: int, lang: str = 'en', limit: int = 2048) -> Iterator[tuple[int, str]]:
    if len(sentence) <= limit:
        yield offset, sentence
        return
    buf: list[str] = []
    total, start_at = 0, 0

    def a(s: int, e: int) -> None:
        nonlocal total, start_at
        t = sentence[s:e]
        if not buf:
            start_at = s
        buf.append(t)
        total += len(t)

    for start, length in split_into_words_and_positions(sentence, lang):
        a(start, start + length)
        if total >= limit:
            yield offset + start_at, ' '.join(buf)
            buf, total = [], 0
    if buf:
        yield offset + start_at, ' '.join(buf)


PARAGRAPH_SEPARATOR = '\u2029'


def split_into_sentences_for_tts_embed(
    text: str,
    lang: str = 'en',
) -> Iterator[tuple[int, int]]:
    import re

    def sub(m: re.Match[str]) -> str:
        return PARAGRAPH_SEPARATOR + ' ' * (len(m.group()) - 1)

    text = re.sub(r'\n{2,}', sub, text.replace('\r', ' ')).replace('\n', ' ')
    yield from sentence_positions(text, lang)


def split_into_sentences_for_tts(
    text: str,
    lang: str = 'en',
    min_sentence_length: int = 32,
    max_sentence_length: int = 1024,
    PARAGRAPH_SEPARATOR: str = PARAGRAPH_SEPARATOR,
) -> Iterator[tuple[int, str]]:
    import re

    def sub(m: re.Match[str]) -> str:
        return PARAGRAPH_SEPARATOR + ' ' * (len(m.group()) - 1)

    text = re.sub(r'\n{2,}', sub, text.replace('\r', ' ')).replace('\n', ' ')
    pending_start, pending_sentence = 0, ''
    for start, length in sentence_positions(text, lang):
        end = start + length
        sentence = text[start:end].rstrip().replace('\n', ' ').strip()
        if not sentence:
            continue
        if len(sentence) < min_sentence_length and text[end - 1] != PARAGRAPH_SEPARATOR:
            if pending_sentence:
                pending_sentence += ' ' + sentence
                if len(pending_sentence) >= min_sentence_length:
                    yield pending_start, pending_sentence
                    pending_start, pending_sentence = 0, ''
            else:
                pending_start, pending_sentence = start, sentence
            continue
        for sentence_start, sentence_text in split_long_sentences(sentence, start, lang, limit=max_sentence_length):
            if pending_sentence:
                sentence_text = pending_sentence + ' ' + sentence_text
                sentence_start = pending_start
                pending_start, pending_sentence = 0, ''
            yield sentence_start, sentence_text
    if pending_sentence:
        yield pending_start, pending_sentence
