#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Conversion of text to phonemes for the Kokoro TTS models. The English
# conversion is a port of the G2P from misaki
# (https://github.com/hexgrad/misaki) which is Copyright hexgrad and licensed
# under the Apache 2.0 license. Unlike misaki it does not use a part of speech
# tagger or a neural network for words not in its dictionaries, instead using
# espeak-ng for those.

import json
import re
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple, TypedDict

MAX_TOKENS = 510
SAMPLE_RATE = 24000
TIE = '^'


class FileData(TypedDict):
    url: str
    sha256: str
    size: int


class LanguageData(TypedDict):
    lang: str  # ISO 639-1 code
    country: str  # ISO 3166 code, can be empty
    espeak: str  # espeak-ng voice name
    lexicon: str  # name of the misaki lexicon used for English, empty for other languages


class VoiceData(FileData):
    name: str
    lang: str  # kokoro language code
    gender: str  # f or m
    grade: str  # quality grade as published by the creators of Kokoro, can be empty


class LexiconData(TypedDict):
    gold: FileData
    silver: FileData


class KokoroMetadata(TypedDict):
    version: int
    sample_rate: int
    model: FileData
    vocab: dict[str, int]
    lexicons: dict[str, LexiconData]
    languages: dict[str, LanguageData]
    default_voices: dict[str, str]  # ISO 639-2 language code to voice id
    voices: dict[str, VoiceData]


@lru_cache(2)
def kokoro_metadata() -> KokoroMetadata:
    from calibre.utils.resources import get_path as P

    ans: KokoroMetadata = json.loads(P('kokoro-voices.json', data=True))
    return ans


# Phonemes from espeak {{{
LANG_FLAG_PAT = re.compile(r'\([a-z^-]+\)')
# The phonemes for an entire string of text with clause terminators, such as
# punctuation, preserved
Phonemizer = Callable[[str], str]


def espeak_phonemizer(text: str) -> str:
    # The espeak voice must have been set already
    from calibre_extensions import piper

    parts: list[str] = []
    for phonemes, terminator, is_sentence_end in piper.phonemize(text, TIE):
        parts.append(LANG_FLAG_PAT.sub('', phonemes) + terminator)
    return ' '.join(p for p in parts if p)


class EspeakG2P:
    # Used for languages other than English

    E2M = sorted(
        {
            'a^ɪ': 'I',
            'a^ʊ': 'W',
            'd^z': 'ʣ',
            'd^ʒ': 'ʤ',
            'e^ɪ': 'A',
            'o^ʊ': 'O',
            'ə^ʊ': 'Q',
            's^s': 'S',
            't^s': 'ʦ',
            't^ʃ': 'ʧ',
            'ɔ^ɪ': 'Y',
        }.items()
    )

    def __init__(self, phonemizer: Phonemizer):
        self.phonemizer = phonemizer

    def __call__(self, text: str) -> str:
        ps = self.phonemizer(text).strip()
        for old, new in self.E2M:
            ps = ps.replace(old, new)
        return ps.replace(TIE, '').replace('-', '')


# }}}


# English {{{
DIPHTHONGS = frozenset('AIOQWYʤʧ')
SUBTOKEN_JUNKS = frozenset("',-._‘’/")
# The maximum number of parts of a group of words that are looked up as a
# single entry in the lexicon, entries such as non- have only two parts
MAX_SPAN_PARTS = 8
PUNCTS = frozenset(';:,.!?—…"“”')
NON_QUOTE_PUNCTS = frozenset(p for p in PUNCTS if p not in '"“”')
LEXICON_ORDS = frozenset((39, 45, *range(65, 91), *range(97, 123)))
CONSONANTS = frozenset('bdfhjklmnpstvwzðŋɡɹɾʃʒʤʧθ')
US_TAUS = frozenset('AIOWYiuæɑəɛɪɹʊʌ')
CURRENCIES = {
    '$': ('dollar', 'cent'),
    '£': ('pound', 'pence'),
    '€': ('euro', 'cent'),
}
ORDINALS = frozenset(['st', 'nd', 'rd', 'th'])
SYMBOLS = {'%': 'percent', '&': 'and', '+': 'plus', '@': 'at'}
STRESSES = 'ˌˈ'
PRIMARY_STRESS = STRESSES[1]
SECONDARY_STRESS = STRESSES[0]
VOWELS = frozenset('AIOQWYaiuæɑɒɔəɛɜɪʊʌᵻ')
LexiconValue = str | dict[str, str | None]
# Without a part of speech tagger, the previous word is used to guess whether
# words such as record, present and live are verbs or nouns
VERB_CUES = frozenset("to will would can could shall should may might must i we they you don't doesn't didn't won't can't couldn't wouldn't shouldn't".split())
NOUN_CUES = frozenset('the a an my your his her its our their this that these those of in on for with from by about into at'.split())


def guess_tag(previous_word: str) -> str | None:
    pw = previous_word.lower().replace('’', "'")
    if pw in VERB_CUES:
        return 'VERB'
    if pw in NOUN_CUES:
        return 'NOUN'
    return None


def stress_weight(ps: str) -> int:
    return sum(2 if c in DIPHTHONGS else 1 for c in ps) if ps else 0


def restress(ps: str) -> str:
    # Move stress markers to just before the next vowel
    ips: list[tuple[float, str]] = [(float(i), c) for i, c in enumerate(ps)]
    for i, (_, c) in enumerate(ips):
        if c in STRESSES:
            j = next((k for k in range(i, len(ps)) if ps[k] in VOWELS), None)
            if j is not None:
                ips[i] = (j - 0.5, c)
    return ''.join(c for _, c in sorted(ips))


def apply_stress(ps: str | None, stress: float | None) -> str | None:
    if ps is None or stress is None:
        return ps
    if stress < -1:
        return ps.replace(PRIMARY_STRESS, '').replace(SECONDARY_STRESS, '')
    if stress == -1 or (stress in (0, -0.5) and PRIMARY_STRESS in ps):
        return ps.replace(SECONDARY_STRESS, '').replace(PRIMARY_STRESS, SECONDARY_STRESS)
    if stress in (0, 0.5, 1) and all(s not in ps for s in STRESSES):
        if all(v not in ps for v in VOWELS):
            return ps
        return restress(SECONDARY_STRESS + ps)
    if stress >= 1 and PRIMARY_STRESS not in ps and SECONDARY_STRESS in ps:
        return ps.replace(SECONDARY_STRESS, PRIMARY_STRESS)
    if stress > 1 and all(s not in ps for s in STRESSES):
        if all(v not in ps for v in VOWELS):
            return ps
        return restress(PRIMARY_STRESS + ps)
    return ps


def is_digit(text: str) -> bool:
    return bool(text) and all('0' <= c <= '9' for c in text)


# Numbers as words {{{
# Numbers with more digits than this are read digit by digit
MAX_NUMBER_DIGITS = 15
SMALL_NUMBERS = ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
TENS = ('', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety')
SCALES = ((10**12, 'trillion'), (10**9, 'billion'), (10**6, 'million'), (1000, 'thousand'))
IRREGULAR_ORDINALS = {'one': 'first', 'two': 'second', 'three': 'third', 'five': 'fifth', 'eight': 'eighth', 'nine': 'ninth', 'twelve': 'twelfth'}


def cardinal_words(n: int) -> list[str]:
    if n < 0:
        return ['minus', *cardinal_words(-n)]
    if n >= 1000 * SCALES[0][0]:
        return [SMALL_NUMBERS[int(d)] for d in str(n)]
    if n < 20:
        return [SMALL_NUMBERS[n]]
    if n < 100:
        t, u = divmod(n, 10)
        return [TENS[t]] + ([SMALL_NUMBERS[u]] if u else [])
    if n < 1000:
        h, r = divmod(n, 100)
        return [SMALL_NUMBERS[h], 'hundred'] + (cardinal_words(r) if r else [])
    for scale, name in SCALES:
        if n >= scale:
            q, r = divmod(n, scale)
            return cardinal_words(q) + [name] + (cardinal_words(r) if r else [])
    raise ValueError(f'Cannot convert {n} to words')


def ordinal_words(n: int) -> list[str]:
    words = cardinal_words(n)
    last = words[-1]
    if last in IRREGULAR_ORDINALS:
        last = IRREGULAR_ORDINALS[last]
    elif last.endswith('y'):
        last = last[:-1] + 'ieth'
    else:
        last += 'th'
    return words[:-1] + [last]


def year_words(n: int) -> list[str]:
    hi, lo = divmod(n, 100)
    if hi % 10 == 0 and lo < 10:  # 2000, 2005, 1000
        return cardinal_words(n)
    if lo == 0:
        return cardinal_words(hi) + ['hundred']
    if lo < 10:
        return cardinal_words(hi) + ['O', SMALL_NUMBERS[lo]]
    return cardinal_words(hi) + cardinal_words(lo)


def decimal_words(text: str) -> list[str]:
    whole, _, frac = text.partition('.')
    ans = cardinal_words(int(whole)) if whole else []
    if frac:
        ans.append('point')
        ans.extend(SMALL_NUMBERS[int(d)] for d in frac)
    return ans


# }}}


class CaseFoldingLexicon:
    # A dictionary where words not present in the dictionary are also looked
    # up by their capitalized or lowercase forms. Equivalent to
    # misaki's grow_dictionary() without the memory cost.

    def __init__(self, d: dict[str, LexiconValue]):
        self.d = d

    def get(self, word: str) -> LexiconValue | None:
        ans = self.d.get(word)
        if ans is None and len(word) > 1:
            lw = word.lower()
            if word == lw:
                cw = word.capitalize()
                if cw != word:
                    ans = self.d.get(cw)
            elif word == lw.capitalize():
                ans = self.d.get(lw)
        return ans

    def __contains__(self, word: str) -> bool:
        return self.get(word) is not None


@dataclass
class TokenContext:
    future_vowel: bool | None = None
    future_to: bool = False


class Lexicon:
    cap_stresses = (0.5, 2)

    def __init__(self, golds: dict[str, LexiconValue], silvers: dict[str, LexiconValue], british: bool):
        self.british = british
        self.golds = CaseFoldingLexicon(golds)
        self.silvers = CaseFoldingLexicon(silvers)

    def gold_str(self, word: str, tag: str = 'DEFAULT') -> str:
        v = self.golds.get(word)
        if isinstance(v, dict):
            v = v.get(tag) or v.get('DEFAULT')
        if not isinstance(v, str):
            raise KeyError(f'{word} not in the gold dictionary')
        return v

    def get_nnp(self, word: str) -> tuple[str | None, int | None]:
        # Spell out the letters of the word
        ps: list[str] = []
        for c in word:
            if c.isalpha():
                v = self.golds.get(c.upper())
                if not isinstance(v, str):
                    return None, None
                ps.append(v)
        x = apply_stress(''.join(ps), 0) or ''
        parts = x.rsplit(SECONDARY_STRESS, 1)
        return PRIMARY_STRESS.join(parts), 3

    def get_special_case(self, word: str, stress: float | None, ctx: TokenContext) -> tuple[str | None, int | None]:
        # Without a part of speech tagger we assume the most common usage of
        # these words
        if word in SYMBOLS:
            return self.lookup(SYMBOLS[word], None, ctx)
        if '.' in word.strip('.') and word.replace('.', '').isalpha() and len(max(word.split('.'), key=len)) < 3:
            return self.get_nnp(word)
        if word in ('a', 'A'):
            return 'ɐ', 4
        if word in ('am', 'Am', 'AM'):
            if ctx.future_vowel is None or word != 'am' or (stress is not None and stress > 0):
                return self.gold_str('am'), 4
            return 'ɐm', 4
        if word in ('an', 'An', 'AN'):
            return 'ɐn', 4
        if word == 'I':
            return f'{SECONDARY_STRESS}I', 4
        if word in ('to', 'To', 'TO'):
            if ctx.future_vowel is None:
                return self.gold_str('to'), 4
            return ('tʊ' if ctx.future_vowel else 'tə'), 4
        if word in ('in', 'In', 'IN'):
            return (PRIMARY_STRESS if ctx.future_vowel is None else '') + 'ɪn', 4
        if word in ('the', 'The', 'THE'):
            return ('ði' if ctx.future_vowel is True else 'ðə'), 4
        if re.match(r'(?i)vs\.?$', word):
            return self.lookup('versus', None, ctx)
        if word in ('used', 'Used', 'USED'):
            return self.gold_str('used', 'VBD' if ctx.future_to else 'DEFAULT'), 4
        return None, None

    def is_known(self, word: str) -> bool:
        if word in self.golds or word in SYMBOLS or word in self.silvers:
            return True
        if not word.isalpha() or not all(ord(c) in LEXICON_ORDS for c in word):
            return False
        if len(word) == 1:
            return True
        if word == word.upper() and word.lower() in self.golds:
            return True
        return word[1:] == word[1:].upper()

    def lookup(self, word: str, stress: float | None, ctx: TokenContext | None, tag: str | None = None) -> tuple[str | None, int | None]:
        if word == word.upper() and word not in self.golds:
            word = word.lower()
        val: LexiconValue | None = self.golds.get(word)
        rating = 4
        if val is None:
            val, rating = self.silvers.get(word), 3
        ps: str | None
        if isinstance(val, dict):
            if ctx is not None and ctx.future_vowel is None and 'None' in val:
                tag = 'None'
            ps = val.get(tag or 'DEFAULT') or val.get('DEFAULT')
        else:
            ps = val
        if ps is None:
            nps, nrating = self.get_nnp(word)
            if nps is not None:
                return nps, nrating
            return None, None
        return apply_stress(ps, stress), rating

    def _s(self, stem: str | None) -> str | None:
        if not stem:
            return None
        if stem[-1] in 'ptkfθ':
            return stem + 's'
        if stem[-1] in 'szʃʒʧʤ':
            return stem + ('ɪ' if self.british else 'ᵻ') + 'z'
        return stem + 'z'

    def stem_s(self, word: str, stress: float | None, ctx: TokenContext | None, tag: str | None = None) -> tuple[str | None, int | None]:
        if len(word) < 3 or not word.endswith('s'):
            return None, None
        if not word.endswith('ss') and self.is_known(word[:-1]):
            stem = word[:-1]
        elif (word.endswith("'s") or (len(word) > 4 and word.endswith('es') and not word.endswith('ies'))) and self.is_known(word[:-2]):
            stem = word[:-2]
        elif len(word) > 4 and word.endswith('ies') and self.is_known(word[:-3] + 'y'):
            stem = word[:-3] + 'y'
        else:
            return None, None
        ps, rating = self.lookup(stem, stress, ctx, tag)
        return self._s(ps), rating

    def _ed(self, stem: str | None) -> str | None:
        if not stem:
            return None
        if stem[-1] in 'pkfθʃsʧ':
            return stem + 't'
        if stem[-1] == 'd':
            return stem + ('ɪ' if self.british else 'ᵻ') + 'd'
        if stem[-1] != 't':
            return stem + 'd'
        if self.british or len(stem) < 2:
            return stem + 'ɪd'
        if stem[-2] in US_TAUS:
            return stem[:-1] + 'ɾᵻd'
        return stem + 'ᵻd'

    def stem_ed(self, word: str, stress: float | None, ctx: TokenContext | None, tag: str | None = None) -> tuple[str | None, int | None]:
        if len(word) < 4 or not word.endswith('d'):
            return None, None
        if not word.endswith('dd') and self.is_known(word[:-1]):
            stem = word[:-1]
        elif len(word) > 4 and word.endswith('ed') and not word.endswith('eed') and self.is_known(word[:-2]):
            stem = word[:-2]
        else:
            return None, None
        ps, rating = self.lookup(stem, stress, ctx, tag)
        return self._ed(ps), rating

    def _ing(self, stem: str | None) -> str | None:
        if not stem:
            return None
        if self.british:
            if stem[-1] in 'əː':
                return None
        elif len(stem) > 1 and stem[-1] == 't' and stem[-2] in US_TAUS:
            return stem[:-1] + 'ɾɪŋ'
        return stem + 'ɪŋ'

    def stem_ing(self, word: str, stress: float | None, ctx: TokenContext | None, tag: str | None = None) -> tuple[str | None, int | None]:
        if len(word) < 5 or not word.endswith('ing'):
            return None, None
        if len(word) > 5 and self.is_known(word[:-3]):
            stem = word[:-3]
        elif self.is_known(word[:-3] + 'e'):
            stem = word[:-3] + 'e'
        elif len(word) > 5 and re.search(r'([bcdgklmnprstvxz])\1ing$|cking$', word) and self.is_known(word[:-4]):
            stem = word[:-4]
        else:
            return None, None
        ps, rating = self.lookup(stem, stress, ctx, tag)
        return self._ing(ps), rating

    def get_word(self, word: str, stress: float | None, ctx: TokenContext, tag: str | None = None) -> tuple[str | None, int | None]:
        ps, rating = self.get_special_case(word, stress, ctx)
        if ps is not None:
            return ps, rating
        wl = word.lower()
        if (
            len(word) > 1
            and word.replace("'", '').isalpha()
            and word != wl
            and word not in self.golds
            and word not in self.silvers
            and (word == word.upper() or word[1:] == word[1:].lower())
            and (wl in self.golds or wl in self.silvers or any(fn(wl, stress, ctx)[0] for fn in (self.stem_s, self.stem_ed, self.stem_ing)))
        ):
            word = wl
        if self.is_known(word):
            return self.lookup(word, stress, ctx, tag)
        if word.endswith("s'") and self.is_known(word[:-2] + "'s"):
            return self.lookup(word[:-2] + "'s", stress, ctx, tag)
        if word.endswith("'") and self.is_known(word[:-1]):
            return self.lookup(word[:-1], stress, ctx, tag)
        if word.endswith("s'") and len(word) > 2:
            # Plural possessives such as officers'
            return self.get_word(word[:-1], stress, ctx, tag)
        for fn in (self.stem_s, self.stem_ed):
            ps, rating = fn(word, stress, ctx, tag)
            if ps is not None:
                return ps, rating
        return self.stem_ing(word, 0.5 if stress is None else stress, ctx, tag)

    def number_words(self, word: str, currency: str) -> list[str] | None:
        m = re.search(r"[a-z']+$", word)
        suffix = m.group() if m else ''
        word = word[: -len(suffix)] if suffix else word
        prefix: list[str] = []
        if word.startswith('-'):
            prefix.append('minus')
            word = word[1:]
        plain = word.replace(',', '')
        if not plain or not all(is_digit(c) or c == '.' for c in plain) or plain.count('.') > 1 or plain == '.':
            return None
        whole, _, frac = plain.partition('.')
        if len(whole) > MAX_NUMBER_DIGITS:
            # Read very long numbers digit by digit, this also avoids the
            # limit on the number of digits int() can convert
            return prefix + [SMALL_NUMBERS[int(d)] for d in whole] + (['point'] + [SMALL_NUMBERS[int(d)] for d in frac] if frac else [])
        if is_digit(plain) and suffix in ORDINALS:
            return prefix + ordinal_words(int(plain))
        if not prefix and len(word) == 4 and not currency and is_digit(word):
            return year_words(int(word))
        if currency in CURRENCIES:
            if len(frac) < 3:
                unit, sub_unit = CURRENCIES[currency]
                parts = [(int(whole) if whole else 0, unit), (int(frac.ljust(2, '0')) if frac else 0, sub_unit)]
                if parts[1][0] == 0:
                    parts = parts[:1]
                elif parts[0][0] == 0:
                    parts = parts[1:]
                ans = list(prefix)
                for i, (num, u) in enumerate(parts):
                    if i > 0:
                        ans.append('and')
                    ans.extend(cardinal_words(num))
                    ans.append(u + 's' if num != 1 and u != 'pence' else u)
                return ans
        if '.' in plain:
            return prefix + decimal_words(plain)
        return prefix + cardinal_words(int(plain))

    def get_number(self, word: str, currency: str, ctx: TokenContext) -> tuple[str | None, int | None]:
        words = self.number_words(word, currency)
        if not words:
            return None, None
        results: list[str] = []
        rating = 4
        for w in words:
            stress = -2 if w in ('point', 'O') else None
            ps, r = self.lookup(w, stress, None)
            if ps is None:
                ps, r = self.stem_s(w, stress, None)
            if ps is None:
                return None, None
            results.append(ps)
            rating = min(rating, r or 0)
        ans = ' '.join(results)
        m = re.search(r"[a-z']+$", word)
        suffix = m.group() if m else ''
        if suffix in ('s', "'s"):
            return self._s(ans), rating
        if suffix in ('ed', "'d"):
            return self._ed(ans), rating
        if suffix == 'ing':
            return self._ing(ans), rating
        return ans, rating

    @staticmethod
    def is_number(word: str) -> bool:
        if not any(is_digit(c) for c in word):
            return False
        for s in ('ing', "'d", 'ed', "'s", *ORDINALS, 's'):
            if word.endswith(s):
                word = word[: -len(s)]
                break
        return all(is_digit(c) or c in ',.' or (i == 0 and c == '-') for i, c in enumerate(word))

    def __call__(self, word: str, currency: str, ctx: TokenContext, tag: str | None = None) -> tuple[str | None, int | None]:
        word = unicodedata.normalize('NFKC', word.replace('‘', "'").replace('’', "'"))
        stress = None if word == word.lower() else self.cap_stresses[int(word == word.upper())]
        if self.is_number(word):
            return self.get_number(word, currency, ctx)
        ps, rating = self.get_word(word, stress, ctx, tag)
        if ps is not None:
            return ps, rating
        return None, None


class EspeakFallback:
    # Used for English words not in the dictionaries

    E2M = sorted(
        {
            'ʔˌn̩': 'ʔn',
            'ʔn̩': 'ʔn',
            'a^ɪ': 'I',
            'a^ʊ': 'W',
            'd^ʒ': 'ʤ',
            'e^ɪ': 'A',
            'e': 'A',
            't^ʃ': 'ʧ',
            'ɔ^ɪ': 'Y',
            'ə^l': 'ᵊl',
            'ʲo': 'jo',
            'ʲə': 'jə',
            'ʲ': '',
            'ɚ': 'əɹ',
            'r': 'ɹ',
            'x': 'k',
            'ç': 'k',
            'ɐ': 'ə',
            'ɬ': 'l',
            '̃': '',
        }.items(),
        key=lambda kv: -len(kv[0]),
    )

    def __init__(self, phonemizer: Phonemizer, british: bool):
        self.phonemizer = phonemizer
        self.british = british

    def __call__(self, text: str) -> str:
        ps = self.phonemizer(text).strip()
        for old, new in self.E2M:
            ps = ps.replace(old, new)
        ps = re.sub(r'(\S)̩', r'ᵊ\1', ps).replace('̩', '')
        if self.british:
            ps = ps.replace('e^ə', 'ɛː').replace('iə', 'ɪə').replace('ə^ʊ', 'Q')
        else:
            ps = ps.replace('o^ʊ', 'O').replace('ɜːɹ', 'ɜɹ').replace('ɜː', 'ɜɹ').replace('ɪə', 'iə').replace('ː', '')
        ps = ps.replace('o', 'ɔ')
        ps = ps.replace('ɾ', 'T').replace('ʔ', 't')
        return ps.replace(TIE, '')


class Token(NamedTuple):
    text: str
    whitespace: str
    kind: str  # one of: word, number, dash, punct


TOKEN_PAT = re.compile(
    r'''
    (?P<number>(?:(?<![\w-])-)?\d(?:[\d,.]*\d)?(?:st|nd|rd|th|s|'s|ed|'d|ing)?)
    |(?P<abbr>(?:[^\W\d_]{1,2}\.){2,}(?![^\W\d_]))
    |(?P<word>[^\W\d_]+(?:['’][^\W\d_]+)*(?:(?<=s)['’])?)
    |(?P<dash>-{2,}|–)
    |(?P<space>\s+)
    |(?P<punct>.)
    ''',
    re.VERBOSE | re.DOTALL,
)


def split_camel_case(word: str) -> list[str]:
    # Split words such as iPad at transitions from lower to upper case
    ans: list[str] = []
    start = 0
    for i in range(1, len(word)):
        if word[i - 1].islower() and word[i].isupper():
            ans.append(word[start:i])
            start = i
    ans.append(word[start:])
    return ans


def tokenize(text: str) -> list[Token]:
    ans: list[Token] = []
    for m in TOKEN_PAT.finditer(text):
        kind = m.lastgroup or 'punct'
        t = m.group()
        if kind == 'space':
            if ans:
                ans[-1] = ans[-1]._replace(whitespace=ans[-1].whitespace + t)
            continue
        if kind == 'abbr':
            # Abbreviations such as U.S. are spelled out by the lexicon
            ans.append(Token(t, '', 'word'))
        elif kind == 'word':
            ans.extend(Token(x, '', 'word') for x in split_camel_case(t))
        else:
            ans.append(Token(t, '', kind))
    return ans


def is_word(tk: Token) -> bool:
    return tk.kind in ('word', 'number')


def group_tokens(tokens: list[Token]) -> list[list[Token]]:
    # Group words that are not separated by whitespace, such as well-known,
    # to/from and iPad, so they can be looked up as a whole or in parts
    groups: list[list[Token]] = []
    i = 0
    while i < len(tokens):
        group = [tokens[i]]
        if is_word(tokens[i]):
            while not group[-1].whitespace and i + 1 < len(tokens):
                nxt = tokens[i + 1]
                if is_word(nxt):
                    group.append(nxt)
                    i += 1
                elif nxt.kind == 'punct' and nxt.text in SUBTOKEN_JUNKS and not nxt.whitespace and i + 2 < len(tokens) and is_word(tokens[i + 2]):
                    group.extend((nxt, tokens[i + 2]))
                    i += 2
                else:
                    break
        groups.append(group)
        i += 1
    return groups


@dataclass
class EnglishG2P:
    lexicon: Lexicon
    fallback: Callable[[str], str]

    @staticmethod
    def token_context(ctx: TokenContext, ps: str | None, word: str) -> TokenContext:
        vowel = ctx.future_vowel
        if ps:
            for c in ps:
                if c in VOWELS or c in CONSONANTS or c in NON_QUOTE_PUNCTS:
                    vowel = None if c in NON_QUOTE_PUNCTS else (c in VOWELS)
                    break
        return TokenContext(future_vowel=vowel, future_to=word in ('to', 'To', 'TO'))

    def resolve_group(self, group: list[Token], ctx: TokenContext, tag: str | None) -> tuple[str, TokenContext]:
        # Find the longest spans of the group that are in the lexicon, working
        # from the end of the group, as done by misaki. Spans are limited to
        # MAX_SPAN_PARTS parts so that the time taken is linear in the size of
        # the group, rather than cubic.
        texts = [tk.text for tk in group]
        phonemes: list[str | None] = [None] * len(texts)
        right = len(texts)
        left = max(0, right - MAX_SPAN_PARTS)
        while left < right:
            merged = ''.join(texts[left:right])
            ps = None
            # Spans may end with junk to match prefixes such as non- but must
            # not start with it, otherwise 10-20 would be read as 10 minus 20
            if texts[left][0] not in SUBTOKEN_JUNKS:
                ps, _ = self.lexicon(merged, '', ctx, tag if left == 0 else None)
            if ps is not None:
                phonemes[left] = ps
                for k in range(left + 1, right):
                    phonemes[k] = ''
                ctx = self.token_context(ctx, ps, merged)
                right = left
                left = max(0, right - MAX_SPAN_PARTS)
            elif left + 1 < right:
                left += 1
            else:
                right -= 1
                if phonemes[right] is None:
                    if all(c in SUBTOKEN_JUNKS for c in texts[right]):
                        phonemes[right] = ''
                    else:
                        text = ''.join(texts)
                        ps = self.fallback(text)
                        return ps, self.token_context(ctx, ps, text)
                left = max(0, right - MAX_SPAN_PARTS)
        text = ''.join(texts)
        resolved = [x or '' for x in phonemes]
        classes = {0 if c.isalpha() else (1 if is_digit(c) else 2) for c in text if c not in SUBTOKEN_JUNKS}
        if '/' in text or len(classes) > 1 or any(tk.kind == 'number' for tk in group):
            return ' '.join(x for x in resolved if x), ctx
        # Reduce the stress of half the parts
        indices = sorted((PRIMARY_STRESS in x, stress_weight(x), i) for i, x in enumerate(resolved) if x)
        if len(indices) == 2 and len(texts[indices[0][2]]) == 1:
            i = indices[1][2]
            resolved[i] = apply_stress(resolved[i], -0.5) or ''
        elif len(indices) >= 2 and sum(b for b, _, _ in indices) > (len(indices) + 1) // 2:
            for _, _, i in indices[: len(indices) // 2]:
                resolved[i] = apply_stress(resolved[i], -0.5) or ''
        return ''.join(resolved), ctx

    def word_phonemes(self, word: str, currency: str, ctx: TokenContext, tag: str | None = None) -> str:
        ps, _ = self.lexicon(word, currency, ctx, tag)
        return self.fallback(word) if ps is None else ps

    def merge_abbreviations(self, tokens: list[Token]) -> list[Token]:
        # Words such as Mr. whose trailing period is not the end of a sentence
        ans: list[Token] = []
        i = 0
        while i < len(tokens):
            tk = tokens[i]
            if (
                tk.kind == 'word'
                and not tk.whitespace
                and i + 2 < len(tokens)
                and tokens[i + 1].text == '.'
                and tokens[i + 1].whitespace
                and (tk.text + '.') in self.lexicon.golds
            ):
                ans.append(Token(tk.text + '.', tokens[i + 1].whitespace, 'word'))
                i += 2
                continue
            ans.append(tk)
            i += 1
        return ans

    def __call__(self, text: str) -> str:
        groups = group_tokens(self.merge_abbreviations(tokenize(text)))
        phonemes: list[str] = [''] * len(groups)
        ctx = TokenContext()
        for i in range(len(groups) - 1, -1, -1):
            group = groups[i]
            tk = group[0]
            prev = groups[i - 1][-1] if i > 0 else None
            nxt = groups[i + 1][0] if i + 1 < len(groups) else None
            if is_word(tk):
                tag = guess_tag(prev.text) if prev is not None and prev.kind == 'word' else None
                if len(group) > 1:
                    ps, ctx = self.resolve_group(group, ctx, tag)
                else:
                    currency = prev.text if prev is not None and tk.kind == 'number' and prev.text in CURRENCIES and not prev.whitespace else ''
                    ps = self.word_phonemes(tk.text, currency, ctx, tag)
                    ctx = self.token_context(ctx, ps, tk.text)
            elif tk.text in CURRENCIES and nxt is not None and nxt.kind == 'number' and not tk.whitespace:
                ps = ''  # spoken after the number
            elif tk.text == '"':
                ps = '“' if prev is None or prev.whitespace or prev.text in '([' else '”'
                ctx = self.token_context(ctx, ps, tk.text)
            elif tk.text in SYMBOLS:
                ps = self.lexicon.lookup(SYMBOLS[tk.text], None, ctx)[0] or ''
                ctx = self.token_context(ctx, ps, tk.text)
            elif tk.kind == 'dash' or (tk.text == '-' and (tk.whitespace or prev is None or prev.whitespace)):
                ps = '—'
                ctx = self.token_context(ctx, ps, tk.text)
            elif tk.text in SUBTOKEN_JUNKS and nxt is not None and is_word(nxt) and not tk.whitespace and (prev is None or prev.whitespace):
                ps = ''  # leading junk such as the period in .epub
            elif tk.text in PUNCTS or tk.text in '()':
                ps = tk.text
                ctx = self.token_context(ctx, ps, tk.text)
            else:
                ps = ''
            phonemes[i] = ps
        parts: list[str] = []
        for group, ps in zip(groups, phonemes):
            if ps:
                parts.append(ps)
                if group[-1].whitespace:
                    parts.append(' ')
        ans = ''.join(parts).strip()
        return ans.replace('ɾ', 'T').replace('ʔ', 't')


# Only one lexicon is cached as they use a lot of memory and
# the cache is cleared when the voice changes to one that does not use it
@lru_cache(1)
def load_lexicon(gold_path: str, silver_path: str, british: bool) -> Lexicon:
    with open(gold_path, 'rb') as f:
        golds: dict[str, LexiconValue] = json.load(f)
    with open(silver_path, 'rb') as f:
        silvers: dict[str, LexiconValue] = json.load(f)
    return Lexicon(golds, silvers, british)


# }}}


# Splitting phonemes into chunks the model can handle {{{
WATERFALL = ('!.?…', ':;', ',—', ' ')


def split_phonemes(ps: str, vocab: dict[str, int], max_tokens: int = MAX_TOKENS) -> Iterator[str]:
    ps = ''.join(c for c in ps if c in vocab).strip()
    while len(ps) > max_tokens:
        head = ps[:max_tokens]
        for breakers in WATERFALL:
            idx = max(head.rfind(c) for c in breakers)
            if idx > 0:
                split_at = idx + 1
                break
        else:
            split_at = max_tokens
        chunk, ps = ps[:split_at].strip(), ps[split_at:].strip()
        if chunk:
            yield chunk
    if ps:
        yield ps


# }}}


class G2P:
    # Converts text to a list of phoneme strings suitable for the model

    def __init__(self, lang_code: str, lexicon_paths: tuple[str, str] | None = None, phonemizer: Phonemizer = espeak_phonemizer):
        md = kokoro_metadata()
        self.vocab = md['vocab']
        lang = md['languages'][lang_code]
        self.convert: Callable[[str], str]
        if lang['lexicon']:
            if lexicon_paths is None:
                raise ValueError(f'The Kokoro language {lang_code} requires a lexicon')
            british = lang['lexicon'] == 'gb'
            lexicon = load_lexicon(lexicon_paths[0], lexicon_paths[1], british)
            self.convert = EnglishG2P(lexicon, EspeakFallback(phonemizer, british))
        else:
            self.convert = EspeakG2P(phonemizer)

    def __call__(self, text: str) -> list[str]:
        return list(split_phonemes(self.convert(text), self.vocab))


def speed_from_rate(rate: float) -> float:
    # Map the rate in [-1, 1] to the model's speed using the same mapping
    # as is used for the length scale of Piper models
    m = max(0.1, 1 - max(-1, min(rate, 1)))
    return min(3, 1 / m)


def find_tests():
    import unittest

    class TestKokoro(unittest.TestCase):
        def test_kokoro_number_words(self):
            self.assertEqual(cardinal_words(1234), 'one thousand two hundred thirty four'.split())
            self.assertEqual(cardinal_words(-7), ['minus', 'seven'])
            self.assertEqual(ordinal_words(22), ['twenty', 'second'])
            self.assertEqual(ordinal_words(40), ['fortieth'])
            self.assertEqual(year_words(1984), 'nineteen eighty four'.split())
            self.assertEqual(year_words(1905), 'nineteen O five'.split())
            self.assertEqual(year_words(1900), 'nineteen hundred'.split())
            self.assertEqual(year_words(2005), 'two thousand five'.split())
            self.assertEqual(decimal_words('3.14'), 'three point one four'.split())

        def test_kokoro_english_g2p(self):
            golds: dict[str, LexiconValue] = {
                'hello': 'həlˈO',
                'world': 'wˈɜɹld',
                'record': {'DEFAULT': 'ɹˈɛkəɹd', 'VERB': 'ɹəkˈɔɹd'},
                'to': 'tʊ',
                'I': 'ˈI',
                'non-': 'nˈɑn',
                'English': 'ˈɪŋɡlɪʃ',
                'Mr.': 'mˈɪstəɹ',
                'Smith': 'smˈɪθ',
                'five': 'fˈIv',
                'fifty': 'fˈɪfti',
                'dollar': 'dˈɑləɹ',
                'cent': 'sˈɛnt',
                'and': 'ænd',
                'ten': 'tˈɛn',
                'twenty': 'twˈɛnti',
                'cat': 'kˈæt',
                'nineteen': 'nˌIntˈin',
                'eighty': 'ˈATi',
                'four': 'fˈɔɹ',
                'officer': 'ˈɔfəsəɹ',
            }
            g = EnglishG2P(Lexicon(golds, {}, False), lambda w: f'<{w}>')

            def t(text: str, expected: str) -> None:
                self.assertEqual(g(text), expected, text)

            t('Hello world.', 'həlˈO wˈɜɹld.')
            t('HELLO, World!', 'həlˈO, wˈɜɹld!')
            t('the record', 'ðə ɹˈɛkəɹd')
            t('I want to record', 'ˌI <want> tə ɹəkˈɔɹd')
            t('non-English', 'nˌɑnˈɪŋɡlɪʃ')
            t('Mr. Smith', 'mˈɪstəɹ smˈɪθ')
            t('$5.50', 'fˈIv dˈɑləɹz ænd fˈɪfti sˈɛnts')
            t('1984', 'nˌIntˈin ˈATi fˈɔɹ')
            t('10-20', 'tˈɛn twˈɛnti')
            t('cat/world', 'kˈæt wˈɜɹld')
            t('cats', 'kˈæts')
            t('officers’ cat', 'ˈɔfəsəɹz kˈæt')
            t('"hello"', '“həlˈO”')
            t('cat -- world', 'kˈæt — wˈɜɹld')
            t('Zyx', '<Zyx>')
            # Long numbers are read digit by digit instead of failing in int()
            self.assertEqual(g.lexicon.number_words('1' * 5000, ''), ['one'] * 5000)
            self.assertEqual(g.lexicon.number_words('9' * 20 + '.5', '$'), ['nine'] * 20 + ['point', 'five'])
            self.assertEqual(g.lexicon.number_words('1' * 16 + '.5', ''), ['one'] * 16 + ['point', 'five'])

        def test_kokoro_split_phonemes(self):
            vocab = {c: i for i, c in enumerate('abc ,.')}
            self.assertEqual(list(split_phonemes('ab, c. x', vocab, 100)), ['ab, c.'])
            self.assertEqual(list(split_phonemes('aaa, bbb. ccc', vocab, 10)), ['aaa, bbb.', 'ccc'])
            self.assertEqual(list(split_phonemes('aaaa, bbbb', vocab, 8)), ['aaaa,', 'bbbb'])
            self.assertEqual(list(split_phonemes('a' * 25, vocab, 10)), ['a' * 10, 'a' * 10, 'a' * 5])

        def test_kokoro_metadata(self):
            md = kokoro_metadata()
            self.assertTrue(md['model']['url'].startswith('https://'))
            self.assertEqual(len(md['model']['sha256']), 64)
            for k in md['vocab']:
                self.assertEqual(len(k), 1)
            for voice_id, vd in md['voices'].items():
                self.assertIn(vd['lang'], md['languages'], voice_id)
                self.assertEqual(len(vd['sha256']), 64, voice_id)
            for ld in md['languages'].values():
                if ld['lexicon']:
                    self.assertIn(ld['lexicon'], md['lexicons'])
            for v in md['default_voices'].values():
                self.assertIn(v, md['voices'])

        def test_kokoro_espeak(self):
            try:
                from calibre_extensions import piper
            except ImportError:
                raise unittest.SkipTest('The piper extension is not available')
            from calibre.utils.tts.piper import espeak_data_dir

            piper.initialize(espeak_data_dir())
            piper.set_espeak_voice_by_name('en-us')
            self.assertEqual(piper.phonemize('my choice', ''), piper.phonemize('my choice'))
            with self.assertRaises(ValueError):
                piper.phonemize('my choice', '^^')
            vocab = kokoro_metadata()['vocab']
            fallback = EspeakFallback(espeak_phonemizer, False)
            ps = fallback('Zyxwort')
            self.assertTrue(ps)
            self.assertNotIn(TIE, ps)
            self.assertFalse(set(ps) - set(vocab), ps)
            piper.set_espeak_voice_by_name('fr')
            ps = EspeakG2P(espeak_phonemizer)('Bonjour, le monde.')
            self.assertTrue(ps.endswith('.'))
            self.assertNotIn('(', ps)
            self.assertFalse(set(ps) - set(vocab), ps)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestKokoro)
