#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Extraction of the paragraphs of text to check from the HTML source of a
# file, and the conversion of corrections to that text into edits of the
# source that preserve inline markup such as bold, italics and colors.
#
# The source is tokenized rather than parsed into a tree, with a tokenizer
# that tolerates malformed markup, as the source being edited is often
# temporarily invalid, and so that the source offset of every character of
# the text is known exactly. Paragraphs are delimited by block elements.
# Inline elements are transparent, whitespace is collapsed as when rendering
# and character references are decoded.
#
# Corrections are converted into the smallest changes to the text, which are
# applied to the text in the source, never to the markup. A change that
# spans text in more than one element puts the new text into the first
# element and deletes the old text from the rest. Text inserted at the
# boundary between two elements goes into the preceding element. Formatting
# elements whose text is completely deleted are removed.

import re
from collections.abc import Iterable, Sequence
from difflib import SequenceMatcher
from html import unescape
from html.parser import HTMLParser
from typing import NamedTuple

from calibre import prepare_string_for_xml
from calibre.utils.grammar.backend import HAS_WORD, Edit, overlaps
from calibre.utils.grammar.rules import Issue

# Elements that start a new paragraph
BLOCK_TAGS = frozenset(
    'address article aside blockquote body caption center dd details dialog dir div dl dt fieldset figcaption figure footer form'
    ' frameset h1 h2 h3 h4 h5 h6 header hgroup hr html legend li main menu nav ol p section summary table tbody td tfoot th thead tr ul'.split()
)
# Elements whose contents are not checked, they also delimit paragraphs
EXCLUDED_BLOCK_TAGS = frozenset('head script style template noscript textarea select pre iframe object'.split())
# Inline elements whose contents are not part of the text, for example, ruby
# annotations
EXCLUDED_INLINE_TAGS = frozenset('rt rp'.split())
# Inline elements that are replaced by a placeholder character in the text,
# so that the sentences they are in remain grammatical
PLACEHOLDER_TAGS = frozenset('math svg'.split())
PLACEHOLDER = '￼'
# Inline elements whose text is checked as part of its sentence, but which
# have no issues reported in them and cannot be changed
UNCHANGEABLE_TAGS = frozenset('code kbd samp var'.split())
VOID_TAGS = frozenset('area base br col embed hr img input link meta param source track wbr'.split())
# Elements that are only formatting and can be removed when all their text is
# deleted
FORMATTING_TAGS = frozenset('abbr b big cite del dfn em font i ins mark q s small span strike strong sub sup tt u'.split())
# Characters that are not rendered and are left out of the text, as they
# would break up words
INVISIBLE_CHARS = frozenset('­\u200b⁠﻿')
COLLAPSIBLE_WHITESPACE = frozenset(' \t\n\r\f')
# Paragraphs longer than this are split at line breaks
MAX_PARAGRAPH_LENGTH = 5000
ENTITY_REF = re.compile(r'&[a-zA-Z][-.a-zA-Z0-9]*;?')
CHAR_REF = re.compile(r'&#(?:[0-9]+|[xX][0-9a-fA-F]+);?')
DIFF_UNIT = re.compile(r'\w+|\s+|[^\w\s]')


class InlineElement(NamedTuple):
    name: str
    # Source spans of the start and end tags
    start_tag: tuple[int, int]
    end_tag: tuple[int, int]
    # The range of the text of the paragraph inside the element
    text_start: int
    text_end: int
    # True if the element can be removed when all its text is deleted
    removable: bool


class Paragraph(NamedTuple):
    text: str
    # The language of the paragraph, from the lang attributes in the source or
    # the default language. Can be empty if unknown.
    lang: str
    # The source span of every character of text. Characters from a character
    # reference map to the whole reference and collapsed whitespace to all of
    # it.
    source_starts: tuple[int, ...]
    source_ends: tuple[int, ...]
    # Characters with the same segment number are in the same run of text in
    # the source, without markup between them
    segments: tuple[int, ...]
    # Ranges of text that are not checked and cannot be changed, such as code
    # and text in other languages
    ignore_ranges: tuple[tuple[int, int], ...]
    elements: tuple[InlineElement, ...]

    @property
    def source_span(self) -> tuple[int, int]:
        return self.source_starts[0], self.source_ends[-1]

    def source_ranges(self, start: int, end: int) -> list[tuple[int, int]]:
        """The source spans of the text from start to end, one for each run of text, so that markup is not included"""
        return [(self.source_starts[a], self.source_ends[b - 1]) for a, b in self.runs(start, end)]

    def runs(self, start: int, end: int) -> list[tuple[int, int]]:
        """Split the range of text into ranges that are each in a single run of text in the source"""
        ans: list[tuple[int, int]] = []
        for i in range(start, end):
            if ans and self.segments[i] == self.segments[i - 1]:
                ans[-1] = ans[-1][0], i + 1
            else:
                ans.append((i, i + 1))
        return ans

    def is_ignored(self, i: int) -> bool:
        return any(s <= i < e for s, e in self.ignore_ranges)


class SourceEdit(NamedTuple):
    # Offsets into the source and the replacement as source text, that is,
    # with special characters escaped
    start: int
    end: int
    replacement: str


class EditNotPossible(ValueError):
    pass


# Extraction {{{


def local_name(tag: str) -> str:
    return tag.rpartition(':')[2]


def primary_language(lang: str) -> str:
    return lang.replace('_', '-').partition('-')[0].lower()


class OpenElement:
    __slots__ = ('end_tag', 'has_other_content', 'ignored_from', 'lang', 'name', 'paragraph', 'removable', 'start_tag', 'text_start')

    def __init__(self, name: str, lang: str, start_tag: tuple[int, int], paragraph: int, text_start: int, removable: bool, ignored_from: int) -> None:
        self.name, self.lang, self.start_tag = name, lang, start_tag
        self.paragraph, self.text_start = paragraph, text_start
        self.removable = removable
        self.has_other_content = False
        # The start of the range of text in this element that is ignored, or -1
        self.ignored_from = ignored_from


class Extractor(HTMLParser):
    def __init__(self, source: str, default_lang: str = '') -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.default_lang = default_lang
        self.line_starts = [0] + [i + 1 for i, c in enumerate(source) if c == '\n']
        self.paragraphs: list[Paragraph] = []
        self.stack: list[OpenElement] = []
        self.paragraph_count = 0
        self.segment = 0
        # The name and nesting depth of the element whose contents are being skipped
        self.skipping = ''
        self.skip_depth = 0
        self.skip_start = 0
        self.skip_placeholder = False
        self.reset_paragraph()

    def reset_paragraph(self) -> None:
        self.chars: list[str] = []
        self.starts: list[int] = []
        self.ends: list[int] = []
        self.segs: list[int] = []
        self.ignore: list[tuple[int, int]] = []
        self.elements: list[InlineElement] = []
        self.paragraph_lang = self.current_lang()

    def current_lang(self) -> str:
        for e in reversed(self.stack):
            if e.lang:
                return e.lang
        return self.default_lang

    def source_offset(self) -> int:
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def boundary(self) -> None:
        self.segment += 1

    def mark_other_content(self) -> None:
        for e in self.stack:
            e.has_other_content = True

    # Paragraphs {{{
    def flush(self) -> None:
        while self.chars and self.chars[-1] in ' \n':
            self.pop_char()
        text = ''.join(self.chars)
        if HAS_WORD.search(text):
            n = len(text)
            ignore = merge_ranges((s, min(e, n)) for s, e in self.ignore if s < n)
            elements = tuple(e._replace(text_end=min(e.text_end, n)) for e in self.elements)
            self.paragraphs.append(Paragraph(text, self.paragraph_lang, tuple(self.starts), tuple(self.ends), tuple(self.segs), ignore, elements))
        self.paragraph_count += 1
        self.reset_paragraph()

    def pop_char(self) -> None:
        self.chars.pop()
        self.starts.pop()
        self.ends.pop()
        self.segs.pop()

    def add_char(self, c: str, start: int, end: int) -> None:
        if c in INVISIBLE_CHARS:
            self.mark_other_content()
            return
        if c in COLLAPSIBLE_WHITESPACE:
            if not self.chars or self.chars[-1] in ' \n':
                if self.chars and self.chars[-1] == ' ' and self.segs[-1] == self.segment:
                    self.ends[-1] = end
                return
            c = ' '
        self.chars.append(c)
        self.starts.append(start)
        self.ends.append(end)
        self.segs.append(self.segment)

    def add_text(self, text: str, start: int) -> None:
        for i, c in enumerate(text):
            self.add_char(c, start + i, start + i + 1)

    def add_line_break(self, start: int, end: int) -> None:
        if len(self.chars) > MAX_PARAGRAPH_LENGTH:
            self.flush()
            return
        while self.chars and self.chars[-1] == ' ':
            self.pop_char()
        if self.chars and self.chars[-1] != '\n':
            self.boundary()
            self.add_char_raw('\n', start, end)
            self.boundary()

    def add_char_raw(self, c: str, start: int, end: int) -> None:
        self.chars.append(c)
        self.starts.append(start)
        self.ends.append(end)
        self.segs.append(self.segment)

    # }}}

    # Tokenizer callbacks {{{
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tag(tag, attrs, self.get_starttag_text() or '', False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tag(tag, attrs, self.get_starttag_text() or '', True)

    def start_tag(self, tag: str, attrs: list[tuple[str, str | None]], raw: str, self_closing: bool) -> None:
        name = local_name(tag)
        start = self.source_offset()
        end = start + len(raw)
        if self.skipping:
            if name == self.skipping and not self_closing:
                self.skip_depth += 1
            elif name == 'body' and self.skipping == 'head':
                # The head was not closed
                self.stop_skipping(start)
            else:
                return
            if self.skipping:
                return
        self.boundary()
        a = {k: v or '' for k, v in attrs}
        if name == 'br':
            self.add_line_break(start, end)
            return
        if name in BLOCK_TAGS or name in EXCLUDED_BLOCK_TAGS:
            self.flush()
            if name in EXCLUDED_BLOCK_TAGS:
                if not self_closing:
                    self.start_skipping(name, start, False)
                return
            if not self_closing and name not in VOID_TAGS:
                self.push(name, a, (start, end), False)
                self.paragraph_lang = self.current_lang()
            return
        if name in VOID_TAGS or self_closing:
            self.mark_other_content()
            return
        is_noteref = 'noteref' in a.get('epub:type', '').split() or a.get('role') == 'doc-noteref'
        if name in EXCLUDED_INLINE_TAGS or is_noteref:
            self.mark_other_content()
            self.start_skipping(name, start, False)
            return
        if name in PLACEHOLDER_TAGS:
            self.mark_other_content()
            self.start_skipping(name, start, True)
            return
        self.push(name, a, (start, end), name not in FORMATTING_TAGS or 'id' in a)

    def push(self, name: str, attrs: dict[str, str], start_tag: tuple[int, int], keep: bool) -> None:
        lang = attrs.get('lang') or attrs.get('xml:lang') or ''
        parent_lang = self.current_lang()
        foreign = bool(lang and self.paragraph_lang and primary_language(lang) != primary_language(self.paragraph_lang))
        ignored_from = len(self.chars) if name in UNCHANGEABLE_TAGS or foreign else -1
        self.stack.append(OpenElement(name, lang or parent_lang, start_tag, self.paragraph_count, len(self.chars), not keep, ignored_from))

    def start_skipping(self, name: str, start: int, placeholder: bool) -> None:
        self.skipping, self.skip_depth, self.skip_start, self.skip_placeholder = name, 1, start, placeholder

    def end_tag_span(self) -> tuple[int, int]:
        start = self.source_offset()
        end = self.source.find('>', start)
        return start, (len(self.source) if end < 0 else end + 1)

    def handle_endtag(self, tag: str) -> None:
        name = local_name(tag)
        start, end = self.end_tag_span()
        if self.skipping:
            if name == self.skipping:
                self.skip_depth -= 1
                if self.skip_depth < 1:
                    self.stop_skipping(end)
            return
        self.boundary()
        if name == 'br':  # </br> is treated as <br> by browsers
            self.add_line_break(start, end)
            return
        idx = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i].name == name), -1)
        if idx < 0:
            if name in BLOCK_TAGS:
                self.flush()
            return
        # Elements that were not closed are closed implicitly and so are not
        # removable as their end tags are unknown
        while len(self.stack) > idx + 1:
            self.close_element(self.stack.pop(), None)
        self.close_element(self.stack.pop(), (start, end))
        if name in BLOCK_TAGS:
            self.flush()

    def close_element(self, e: OpenElement, end_tag: tuple[int, int] | None) -> None:
        if e.ignored_from > -1 and e.paragraph == self.paragraph_count and e.ignored_from < len(self.chars):
            self.ignore.append((e.ignored_from, len(self.chars)))
        if e.name in BLOCK_TAGS:
            return
        removable = e.removable and not e.has_other_content and end_tag is not None and e.paragraph == self.paragraph_count
        if end_tag is not None and e.paragraph == self.paragraph_count and e.text_start < len(self.chars):
            self.elements.append(InlineElement(e.name, e.start_tag, end_tag, e.text_start, len(self.chars), removable))
        if not removable and self.stack:
            self.stack[-1].has_other_content = True

    def stop_skipping(self, end: int) -> None:
        if self.skip_placeholder:
            self.boundary()
            n = len(self.chars)
            self.add_char_raw(PLACEHOLDER, self.skip_start, end)
            self.ignore.append((n, n + 1))
        self.skipping = ''
        self.boundary()

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.add_text(data, self.source_offset())

    def handle_ref(self, pat: re.Pattern[str]) -> None:
        if self.skipping:
            return
        start = self.source_offset()
        if (m := pat.match(self.source, start)) is None:
            return
        raw = m.group()
        if (decoded := unescape(raw)) == raw:
            # Not a known reference, so it is literal text
            self.add_text(raw, start)
            return
        for c in decoded:
            self.add_char(c, start, m.end())

    def handle_entityref(self, name: str) -> None:
        self.handle_ref(ENTITY_REF)

    def handle_charref(self, name: str) -> None:
        self.handle_ref(CHAR_REF)

    def handle_comment(self, data: str) -> None:
        self.boundary()

    def handle_decl(self, decl: str) -> None:
        self.boundary()

    def handle_pi(self, data: str) -> None:
        self.boundary()

    def unknown_decl(self, data: str) -> None:
        self.boundary()

    # }}}

    def __call__(self) -> list[Paragraph]:
        self.feed(self.source)
        self.close_parser()
        return self.paragraphs

    def close_parser(self) -> None:
        super().close()
        while self.stack:
            self.close_element(self.stack.pop(), None)
        self.flush()


def merge_ranges(ranges: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    ans: list[tuple[int, int]] = []
    for s, e in sorted(ranges):
        if ans and s <= ans[-1][1]:
            ans[-1] = ans[-1][0], max(e, ans[-1][1])
        else:
            ans.append((s, e))
    return tuple(ans)


def extract_paragraphs(source: str, default_lang: str = '') -> list[Paragraph]:
    """
    Return the paragraphs of text in the HTML source. Offsets into the source
    are offsets into the Python string, not UTF-16 offsets.
    """
    return Extractor(source, default_lang)()


# }}}


def visible_issues(p: Paragraph, issues: Iterable[Issue]) -> list[Issue]:
    """Return the issues that should be shown, leaving out the ones in text that is not checked"""
    return [i for i in issues if not overlaps(Edit(i.start, i.end, ''), p.ignore_ranges)]


# Edits {{{


def minimal_edits(text: str, edit: Edit) -> list[Edit]:
    """Split an edit of text into the smallest edits that have the same effect"""
    old = text[edit.start : edit.end]
    a = [(m.group(), m.start()) for m in DIFF_UNIT.finditer(old)]
    b = [m.group() for m in DIFF_UNIT.finditer(edit.replacement)]
    ans: list[Edit] = []

    def pos(i: int) -> int:
        return edit.start + (a[i][1] if i < len(a) else len(old))

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, [x[0] for x in a], b, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        replacement = ''.join(b[j1:j2])
        if tag == 'replace' and i2 - i1 == 1 and j2 - j1 == 1:
            # A single changed unit, change only the characters that differ so
            # that, for example, markup around its first letter is kept
            base = pos(i1)
            ow = a[i1][0]
            for ctag, c1, c2, d1, d2 in SequenceMatcher(None, ow, replacement, autojunk=False).get_opcodes():
                if ctag != 'equal':
                    ans.append(Edit(base + c1, base + c2, replacement[d1:d2]))
            continue
        ans.append(Edit(pos(i1), pos(i2), replacement))
    return ans


def insertion_point(p: Paragraph, at: int) -> int:
    """The source offset at which to insert text at the specified position in the text"""
    n = len(p.text)
    before_ok = at > 0 and not p.is_ignored(at - 1)
    after_ok = at < n and not p.is_ignored(at)
    if 0 < at < n and p.segments[at - 1] == p.segments[at]:
        if p.is_ignored(at):
            raise EditNotPossible('Cannot insert text into text that must not be changed')
        return p.source_starts[at]
    # At the boundary between runs of text, text goes into the preceding run
    if before_ok:
        return p.source_ends[at - 1]
    if after_ok:
        return p.source_starts[at]
    if n == 0:
        raise EditNotPossible('Cannot insert text into an empty paragraph')
    raise EditNotPossible('Cannot insert text next to text that must not be changed')


def source_edits(p: Paragraph, edits: Iterable[Edit]) -> list[SourceEdit]:
    """
    Convert edits of the text of the paragraph into edits of the source,
    preserving inline markup. The edits must not overlap. Raises
    EditNotPossible if an edit changes text that must not be changed, such as
    code, text in another language, placeholders or line breaks.
    """
    # (source start, source end, replacement, order)
    ops: list[tuple[int, int, str, int]] = []
    deleted: set[int] = set()
    for edit in sorted(edits, key=lambda e: (e.start, e.end)):
        if edit.start < 0 or edit.end > len(p.text) or edit.start > edit.end:
            raise EditNotPossible(f'The edit {edit} is outside the paragraph')
        for e in minimal_edits(p.text, edit):
            replacement = prepare_string_for_xml(e.replacement)
            if e.start == e.end:
                pt = insertion_point(p, e.start)
                ops.append((pt, pt, replacement, len(ops)))
                continue
            for i in range(e.start, e.end):
                if p.is_ignored(i) or p.text[i] == '\n':
                    raise EditNotPossible('Cannot change text that must not be changed')
            deleted.update(range(e.start, e.end))
            for k, (a, b) in enumerate(p.runs(e.start, e.end)):
                ops.append((p.source_starts[a], p.source_ends[b - 1], replacement if k == 0 else '', len(ops)))
    insertions = [s for s, e, r, o in ops if r]
    for el in p.elements:
        if (
            el.removable
            and el.text_start < el.text_end
            and all(i in deleted for i in range(el.text_start, el.text_end))
            and not any(el.start_tag[1] <= pt <= el.end_tag[0] for pt in insertions)
        ):
            ops.append((el.start_tag[0], el.start_tag[1], '', len(ops)))
            ops.append((el.end_tag[0], el.end_tag[1], '', len(ops)))
    ops.sort(key=lambda x: (x[0], x[1], x[3]))
    return [SourceEdit(s, e, r) for s, e, r, o in ops]


def apply_source_edits(source: str, edits: Sequence[SourceEdit]) -> str:
    """Apply the edits, which must be sorted by position and not overlap, to the source"""
    prev_end = -1
    for e in edits:
        if e.start < prev_end:
            raise EditNotPossible(f'The edit {e} overlaps a previous edit')
        prev_end = e.end
    for e in reversed(edits):
        source = source[: e.start] + e.replacement + source[e.end :]
    return source


def issue_source_edits(p: Paragraph, issue: Issue, replacement: str) -> list[SourceEdit]:
    """The edits of the source that replace the text of the issue with the replacement"""
    return source_edits(p, (Edit(issue.start, issue.end, replacement),))


# }}}


def develop() -> None:
    import sys

    from calibre.utils.grammar.checker import Checker

    if len(sys.argv) > 1:
        with open(sys.argv[-1]) as f:
            source = f.read()
    else:
        source = (
            '<html><body><p>She <i>go</i> to school yesterday. Despite <b>of</b> the rain, we <span style="color:red">goes</span> outside.</p>'
            '<p>I has a idea about <code>foo()</code> and <i lang="fr">je ne sais quoi</i>.</p></body></html>'
        )
    paragraphs = extract_paragraphs(source, 'en')
    c = Checker()
    for p, r in zip(paragraphs, c.check_paragraphs([p.text for p in paragraphs], 'en')):
        print(p.text)
        for issue in visible_issues(p, r.issues):
            if issue.replacements:
                fixed = apply_source_edits(source, issue_source_edits(p, issue, issue.replacements[0]))
                s, e = p.source_span
                print(f'    {p.text[issue.start : issue.end]!r} -> {issue.replacements[0]!r}: {fixed[s : e + len(fixed) - len(source)]}')
