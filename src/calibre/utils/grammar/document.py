#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Support for showing the issues found by grammar checks in the source of a
# document that is being edited, and for applying corrections to it. As the
# source can change between when it is checked and when a correction is
# applied, checked paragraphs are identified by their text and the number of
# earlier paragraphs with the same text, rather than by their position, and
# are located again in the current source when a correction is applied.
# Suggestions for rewriting sentences are applied in the same way, with the
# sentence identified by its paragraph and its position in it.

import re
from bisect import bisect_left, bisect_right
from typing import TYPE_CHECKING, NamedTuple

from calibre.utils.grammar.backend import Edit
from calibre.utils.grammar.checker import containing_sentence
from calibre.utils.grammar.markup import EditNotPossible, Paragraph, SourceEdit, apply_source_edits, extract_paragraphs, issue_source_edits, source_edits

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from calibre.utils.grammar.checker import ParagraphResult
    from calibre.utils.grammar.rules import Issue

NON_BMP = re.compile(r'[\U00010000-\U0010ffff]')
# The end of a sentence, used to split paragraphs into sentences when they
# have not been split by a check
SENTENCE_END = re.compile(r'[.!?…]+[’”"\')\]]*(\s+|$)')


class ParagraphNotFound(EditNotPossible):
    pass


class Utf16Map:
    """Convert between offsets into a Python string and UTF-16 offsets, as used by Qt"""

    def __init__(self, text: str) -> None:
        # Offsets of the characters that are two UTF-16 code units long
        self.non_bmp = [m.start() for m in NON_BMP.finditer(text)]
        # Their UTF-16 offsets
        self.non_bmp16 = [pos + i for i, pos in enumerate(self.non_bmp)]

    def to_utf16(self, pos: int) -> int:
        return pos + bisect_left(self.non_bmp, pos)

    def from_utf16(self, pos: int) -> int:
        """Convert a UTF-16 offset, an offset in the middle of a surrogate pair maps to the start of the character"""
        return pos - bisect_left(self.non_bmp16, pos)


class ParagraphRef(NamedTuple):
    # Identifies a paragraph in a document by its text and the number of
    # earlier paragraphs in the document with the same text
    text: str
    occurrence: int


class SentenceRef(NamedTuple):
    # Identifies a sentence by its paragraph and its position in the text of the paragraph
    paragraph: ParagraphRef
    start: int
    end: int
    # The language of the paragraph
    lang: str

    @property
    def text(self) -> str:
        return self.paragraph.text[self.start : self.end]

    def shifted(self, edits: Sequence[Edit]) -> list[Edit]:
        """Convert edits of the sentence into edits of its paragraph"""
        return [Edit(e.start + self.start, e.end + self.start, e.replacement) for e in edits]


class IgnoreKey(NamedTuple):
    # Identifies an issue by the rule that found it and its position in the
    # sentence it is in, so that it stays ignored when other sentences
    # change
    rule_id: str
    sentence: str
    start: int
    end: int


def paragraph_refs(paragraphs: Sequence[Paragraph]) -> list[ParagraphRef]:
    seen: dict[str, int] = {}
    ans = []
    for p in paragraphs:
        n = seen.get(p.text, 0)
        seen[p.text] = n + 1
        ans.append(ParagraphRef(p.text, n))
    return ans


def relocate(paragraphs: Sequence[Paragraph], ref: ParagraphRef) -> Paragraph | None:
    """Find the paragraph identified by ref, or None if it no longer exists"""
    n = 0
    for p in paragraphs:
        if p.text == ref.text:
            if n == ref.occurrence:
                return p
            n += 1
    return None


def paragraphs_by_language(paragraphs: Sequence[Paragraph], default_lang: str) -> dict[str, list[int]]:
    """Map the language of the paragraphs to the indices of the paragraphs in it, in order"""
    ans: dict[str, list[int]] = {}
    for i, p in enumerate(paragraphs):
        lang = (p.lang or default_lang).replace('_', '-')
        ans.setdefault(lang, []).append(i)
    return ans


def ignore_key(result: ParagraphResult, issue: Issue) -> IgnoreKey:
    s, e = containing_sentence(result.sentences, issue.start, issue.end) or (0, len(result.text))
    return IgnoreKey(issue.rule_id, result.text[s:e], issue.start - s, issue.end - s)


def marked_range(p: Paragraph, issue: Issue) -> tuple[int, int]:
    """The range of the text of the paragraph to mark as having the issue. An issue about missing text marks a neighboring character."""
    if issue.start < issue.end:
        return issue.start, issue.end
    if issue.start > 0:
        return issue.start - 1, issue.start
    return 0, min(1, len(p.text))


def issue_source_ranges(p: Paragraph, issue: Issue) -> list[tuple[int, int]]:
    """The ranges of the source to mark as having the issue, excluding markup"""
    start, end = marked_range(p, issue)
    return [(s, e) for s, e in p.source_ranges(start, end) if s < e]


def correction_edits(source: str, default_lang: str, ref: ParagraphRef, issue: Issue, replacement: str) -> list[SourceEdit]:
    """
    The edits of the source that replace the text of the issue in the paragraph
    identified by ref with the replacement. Raises ParagraphNotFound if the
    paragraph no longer exists and EditNotPossible if the edit cannot be made.
    """
    p = relocate(extract_paragraphs(source, default_lang), ref)
    if p is None:
        raise ParagraphNotFound('The text has changed since it was checked')
    return issue_source_edits(p, issue, replacement)


def correct_source(source: str, default_lang: str, ref: ParagraphRef, issue: Issue, replacement: str) -> str:
    """Return the source with the issue in the paragraph identified by ref corrected. See correction_edits()."""
    return apply_source_edits(source, correction_edits(source, default_lang, ref, issue, replacement))


# Sentences {{{


def simple_sentences(text: str) -> list[tuple[int, int]]:
    """Split text into sentences at sentence ending punctuation, returning their (start, end) offsets without surrounding whitespace"""
    ans: list[tuple[int, int]] = []
    start = 0

    def add(end: int) -> None:
        piece = text[start:end]
        if stripped := piece.strip():
            s = start + len(piece) - len(piece.lstrip())
            ans.append((s, s + len(stripped)))

    for m in SENTENCE_END.finditer(text):
        add(m.start(1))
        start = m.end()
    add(len(text))
    return ans


def text_index(p: Paragraph, source_pos: int) -> int:
    """The index of the character of the text of the paragraph at, or just before, the source offset"""
    return max(0, bisect_right(p.source_starts, source_pos) - 1)


def sentence_at(
    paragraphs: Sequence[Paragraph], refs: Sequence[ParagraphRef], results: Mapping[int, ParagraphResult], source_pos: int, default_lang: str
) -> SentenceRef | None:
    """
    The sentence at the source offset, or None if there is none. The sentences
    of a paragraph are taken from its check result, if it has one, otherwise it
    is split into sentences at sentence ending punctuation.
    """
    for idx, p in enumerate(paragraphs):
        s, e = p.source_span
        if s > source_pos:
            break
        if source_pos > e:
            continue
        i = text_index(p, source_pos)
        sentences = (results[idx].sentences if idx in results else ()) or simple_sentences(p.text)
        # A position between sentences belongs to the sentence before it
        span = next((x for x in sentences if x[0] <= i < x[1]), None) or next((x for x in reversed(sentences) if x[0] <= i), None)
        if span is None:
            return None
        return SentenceRef(refs[idx], span[0], span[1], p.lang or default_lang)
    return None


def can_apply_suggestion(p: Paragraph, sentence: SentenceRef, edits: Sequence[Edit]) -> bool:
    """False if the edits of the sentence change text that must not be changed, such as code or text in other languages"""
    try:
        source_edits(p, sentence.shifted(edits))
    except EditNotPossible:
        return False
    return True


def suggestion_edits(source: str, default_lang: str, sentence: SentenceRef, edits: Sequence[Edit]) -> list[SourceEdit]:
    """
    The edits of the source that apply the edits of the sentence. Raises
    ParagraphNotFound if the paragraph of the sentence no longer exists and
    EditNotPossible if the edits cannot be made.
    """
    p = relocate(extract_paragraphs(source, default_lang), sentence.paragraph)
    if p is None:
        raise ParagraphNotFound('The text has changed since it was checked')
    return source_edits(p, sentence.shifted(edits))


def apply_suggestion(source: str, default_lang: str, sentence: SentenceRef, edits: Sequence[Edit]) -> str:
    """Return the source with the edits of the sentence applied. See suggestion_edits()."""
    return apply_source_edits(source, suggestion_edits(source, default_lang, sentence, edits))


# }}}
