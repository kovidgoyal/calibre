#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Lock

from calibre.utils.icu import _icu
from calibre.utils.localization import lang_as_iso639_1

_iterators = {}
_sentence_iterators = {}
_lock = Lock()


def get_iterator(lang):
    it = _iterators.get(lang)
    if it is None:
        it = _iterators[lang] = _icu.BreakIterator(_icu.UBRK_WORD, lang_as_iso639_1(lang) or lang)
    return it


def get_sentence_iterator(lang):
    it = _sentence_iterators.get(lang)
    if it is None:
        it = _sentence_iterators[lang] = _icu.BreakIterator(_icu.UBRK_SENTENCE, lang_as_iso639_1(lang) or lang)
    return it


def split_into_words(text, lang='en'):
    with _lock:
        it = get_iterator(lang)
        it.set_text(text)
        return [text[p:p+s] for p, s in it.split2()]


def split_into_words_and_positions(text, lang='en'):
    with _lock:
        it = get_iterator(lang)
        it.set_text(text)
        return it.split2()


def sentence_positions(text, lang='en'):
    with _lock:
        it = get_sentence_iterator(lang)
        it.set_text(text)
        return it.split2()


def split_into_sentences(text, lang='en'):
    with _lock:
        it = get_sentence_iterator(lang)
        it.set_text(text)
        return tuple(text[p:p+s] for p, s in it.split2())


def index_of(needle, haystack, lang='en'):
    with _lock:
        it = get_iterator(lang)
        it.set_text(haystack)
        return it.index(needle)


def count_words(text, lang='en'):
    with _lock:
        it = get_iterator(lang)
        it.set_text(text)
        return it.count_words()


def split_long_sentences(sentence: str, offset: int, lang: str = 'en', limit: int = 2048):
    if len(sentence) <= limit:
        yield offset, sentence
        return
    buf, total, start_at = [], 0, 0

    def a(s, e):
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


def split_into_sentences_for_tts(
    text: str, lang: str = 'en', min_sentence_length: int = 32, max_sentence_length: int = 1024, PARAGRAPH_SEPARATOR: str = PARAGRAPH_SEPARATOR):
    import re
    def sub(m):
        return PARAGRAPH_SEPARATOR + ' ' * (len(m.group()) - 1)
    text = re.sub(r'\n{2,}', sub, text.replace('\r', ' ')).replace('\n', ' ')
    pending_start, pending_sentence = 0, ''
    for start, length in sentence_positions(text, lang):
        end = start + length
        sentence = text[start:end].rstrip().replace('\n', ' ').strip()
        if not sentence:
            continue
        if len(sentence) < min_sentence_length and text[end-1] != PARAGRAPH_SEPARATOR:
            if pending_sentence:
                pending_sentence += ' ' + sentence
                if len(pending_sentence) >= min_sentence_length:
                    yield pending_start, pending_sentence
                    pending_start, pending_sentence = 0, ''
            else:
                pending_start, pending_sentence = start, sentence
            continue
        for start, sentence in split_long_sentences(sentence, start, lang, limit=max_sentence_length):
            if pending_sentence:
                sentence = pending_sentence + ' ' + sentence
                start = pending_start
                pending_start, pending_sentence = 0, ''
            yield start, sentence
    if pending_sentence:
        yield pending_start, pending_sentence
