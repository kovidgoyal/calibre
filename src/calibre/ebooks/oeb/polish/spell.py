#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Literal, cast, overload

from lxml import etree

from calibre import replace_entities
from calibre.ebooks.oeb.base import barename
from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES, get_container
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.toc import find_existing_nav_toc, find_existing_ncx_toc
from calibre.spell.break_iterator import index_of, split_into_words
from calibre.spell.dictionary import parse_lang_code
from calibre.utils.icu import ord_string

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sequence

    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.spell import DictionaryLocale

#: Maps (word, locale) to the list of locations of that word. The special key None holds the total word count.
type WordsMap = defaultdict[tuple[str, DictionaryLocale] | None, list[Location] | int]
#: The type of the undo cache used by :func:`replace_word`
type UndoCache = dict[tuple[str, _Element, bool, str], str | None]

_patterns: Patterns | None = None


class Patterns:
    __slots__ = ('digit_pat', 'fr_elision_pat', 'sanitize_invisible_pat', 'split_pat')

    def __init__(self) -> None:
        import regex

        # Remove soft hyphens/zero width spaces/control codes
        self.sanitize_invisible_pat = regex.compile(r'[\u00ad\u200b\u200c\u200d\ufeff\0-\x08\x0b\x0c\x0e-\x1f\x7f]', regex.VERSION1 | regex.UNICODE)
        self.split_pat = regex.compile(r'\W+', flags=regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.UNICODE)
        self.digit_pat = regex.compile(r'^\d+$', flags=regex.VERSION1 | regex.WORD | regex.UNICODE)
        # French words with prefixes are reduced to the stem word, so that the
        # words appear only once in the word list
        self.fr_elision_pat = regex.compile(r"^(?:l|d|m|t|s|j|c|ç|lorsqu|puisqu|quoiqu|qu)['’]", flags=regex.UNICODE | regex.VERSION1 | regex.IGNORECASE)


def patterns() -> Patterns:
    global _patterns
    if _patterns is None:
        _patterns = Patterns()
    return _patterns


class CharCounter:
    def __init__(self) -> None:
        self.counter: Counter[int] = Counter()
        self.chars: defaultdict[int, set[str]] = defaultdict(set)
        self.update = self.counter.update


class Location:
    __slots__ = ('elided_prefix', 'file_name', 'location_node', 'node_item', 'original_word', 'sourceline')

    def __init__(
        self,
        file_name: str | None = None,
        elided_prefix: str = '',
        original_word: str | None = None,
        location_node: _Element | None = None,
        node_item: tuple[bool | None, str | None] = (None, None),
    ) -> None:
        self.file_name, self.elided_prefix, self.original_word = file_name, elided_prefix, original_word
        assert location_node is not None
        self.location_node, self.node_item, self.sourceline = location_node, node_item, location_node.sourceline

    def __repr__(self) -> str:
        return f'{self.original_word} @ {self.file_name}:{self.sourceline}'

    __str__ = __repr__

    def replace(self, new_word: str) -> None:
        self.original_word = self.elided_prefix + new_word


file_word_count = 0


def filter_words(word: str) -> bool:
    if not word:
        return False
    p = patterns()
    return p.digit_pat.match(word) is None


def get_words(text: object, lang: str) -> Sequence[str]:
    global file_word_count
    try:
        ans = split_into_words(str(text), lang)
    except TypeError, ValueError:
        return ()
    file_word_count += len(ans)
    return list(filter(filter_words, ans))


def add_words(text: object, node: _Element, words: WordsMap, file_name: str, locale: DictionaryLocale, node_item: tuple[bool, str]) -> None:
    candidates = get_words(text, locale.langcode)
    if candidates:
        p = patterns()
        is_fr = locale.langcode == 'fra'
        for word in candidates:
            sword = p.sanitize_invisible_pat.sub('', word).strip()
            elided_prefix = ''
            if is_fr:
                m = p.fr_elision_pat.match(sword)
                if m is not None and len(sword) > len(elided_prefix):
                    elided_prefix = m.group()
                    sword = sword[len(elided_prefix) :]
            loc = Location(file_name, elided_prefix, word, node, node_item)
            cast('list[Location]', words[(sword, locale)]).append(loc)
            words[None] = cast('int', words[None]) + 1


def add_chars(text: str | bytes | None, counter: CharCounter, file_name: str) -> None:
    if text:
        if isinstance(text, bytes):
            text = text.decode('utf-8', 'ignore')
        counts = Counter(ord_string(text))
        counter.update(counts)
        for codepoint in counts:
            counter.chars[codepoint].add(file_name)


def add_words_from_attr(node: _Element, attr: str, words: WordsMap, file_name: str, locale: DictionaryLocale) -> None:
    text = node.get(attr, None)
    if text:
        add_words(text, node, words, file_name, locale, (True, attr))


def count_chars_in_attr(node: _Element, attr: str, counter: CharCounter, file_name: str, locale: DictionaryLocale) -> None:
    text = node.get(attr, None)
    if text:
        add_chars(text, counter, file_name)


def add_words_from_text(node: _Element, attr: str, words: WordsMap, file_name: str, locale: DictionaryLocale) -> None:
    add_words(getattr(node, attr), node, words, file_name, locale, (False, attr))


def count_chars_in_text(node: _Element, attr: str, counter: CharCounter, file_name: str, locale: DictionaryLocale) -> None:
    add_chars(getattr(node, attr), counter, file_name)


def add_words_from_escaped_html(text: str, words: WordsMap, file_name: str, node: _Element, attr: str, locale: DictionaryLocale) -> None:
    text = replace_entities(text)
    root = parse(f'<html><body><div>{text}</div></body></html>', decoder=lambda x: x.decode('utf-8'))
    ewords: WordsMap = defaultdict(list)
    ewords[None] = 0
    read_words_from_html(root, ewords, file_name, locale)
    words[None] = cast('int', words[None]) + cast('int', ewords.pop(None))
    for k, locs in cast('dict[tuple[str, DictionaryLocale], list[Location]]', ewords).items():
        for loc in locs:
            loc.location_node, loc.node_item = node, (False, attr)
        cast('list[Location]', words[k]).extend(locs)


def count_chars_in_escaped_html(text: str, counter: CharCounter, file_name: str, node: _Element, attr: str, locale: DictionaryLocale) -> None:
    text = replace_entities(text)
    root = parse(f'<html><body><div>{text}</div></body></html>', decoder=lambda x: x.decode('utf-8'))
    count_chars_in_html(root, counter, file_name, locale)


_opf_file_as = '{{{}}}file-as'.format(OPF_NAMESPACES['opf'])
opf_spell_tags = {'title', 'creator', 'subject', 'description', 'publisher'}

# We can only use barename() for tag names and simple attribute checks so that
# this code matches up with the syntax highlighter base spell checking


def read_words_from_opf(root: _Element, words: WordsMap, file_name: str, book_locale: DictionaryLocale) -> None:
    for tag in root.iterdescendants('*'):
        tag_name = tag.tag
        assert isinstance(tag_name, str)  # iterdescendants('*') yields only elements
        if barename(tag_name) in opf_spell_tags:
            if barename(tag_name) == 'description':
                if tag.text:
                    add_words_from_escaped_html(tag.text, words, file_name, tag, 'text', book_locale)
                for child in tag:
                    if child.tail:
                        add_words_from_escaped_html(child.tail, words, file_name, child, 'tail', book_locale)
            else:
                if tag.text:
                    add_words_from_text(tag, 'text', words, file_name, book_locale)
                for child in tag:
                    if child.tail:
                        add_words_from_text(child, 'tail', words, file_name, book_locale)
        add_words_from_attr(tag, _opf_file_as, words, file_name, book_locale)


def count_chars_in_opf(root: _Element, counter: CharCounter, file_name: str, book_locale: DictionaryLocale) -> None:
    for tag in root.iterdescendants('*'):
        tag_name = tag.tag
        assert isinstance(tag_name, str)  # iterdescendants('*') yields only elements
        if barename(tag_name) in opf_spell_tags:
            if barename(tag_name) == 'description':
                if tag.text:
                    count_chars_in_escaped_html(tag.text, counter, file_name, tag, 'text', book_locale)
                for child in tag:
                    if child.tail:
                        count_chars_in_escaped_html(child.tail, counter, file_name, tag, 'tail', book_locale)
            else:
                if tag.text:
                    count_chars_in_text(tag, 'text', counter, file_name, book_locale)
                for child in tag:
                    if child.tail:
                        count_chars_in_text(tag, 'tail', counter, file_name, book_locale)
        count_chars_in_attr(tag, _opf_file_as, counter, file_name, book_locale)


ncx_spell_tags = {'text'}
xml_spell_tags = opf_spell_tags | ncx_spell_tags


def read_words_from_ncx(root: _Element, words: WordsMap, file_name: str, book_locale: DictionaryLocale) -> None:
    for tag in root.xpath('//*[local-name()="text"]'):
        if tag.text is not None:
            add_words_from_text(tag, 'text', words, file_name, book_locale)


def count_chars_in_ncx(root: _Element, counter: CharCounter, file_name: str, book_locale: DictionaryLocale) -> None:
    for tag in root.xpath('//*[local-name()="text"]'):
        if tag.text is not None:
            count_chars_in_text(tag, 'text', counter, file_name, book_locale)


html_spell_tags = {'script', 'style', 'link'}


def read_words_from_html_tag(tag: _Element, words: WordsMap, file_name: str, parent_locale: DictionaryLocale, locale: DictionaryLocale) -> None:
    if tag.text is not None and isinstance(tag.tag, str) and barename(tag.tag) not in html_spell_tags:
        add_words_from_text(tag, 'text', words, file_name, locale)
    for attr in ('alt', 'title'):
        add_words_from_attr(tag, attr, words, file_name, locale)
    if tag.tail is not None and (parent := tag.getparent()) is not None:
        ptag = parent.tag
        assert isinstance(ptag, str)  # the parent of a node is always an element
        if barename(ptag) not in html_spell_tags:
            add_words_from_text(tag, 'tail', words, file_name, parent_locale)


def count_chars_in_html_tag(tag: _Element, counter: CharCounter, file_name: str, parent_locale: DictionaryLocale, locale: DictionaryLocale) -> None:
    if tag.text is not None and isinstance(tag.tag, str) and barename(tag.tag) not in html_spell_tags:
        count_chars_in_text(tag, 'text', counter, file_name, locale)
    for attr in ('alt', 'title'):
        count_chars_in_attr(tag, attr, counter, file_name, locale)
    if tag.tail is not None and (parent := tag.getparent()) is not None:
        ptag = parent.tag
        assert isinstance(ptag, str)  # the parent of a node is always an element
        if barename(ptag) not in html_spell_tags:
            count_chars_in_text(tag, 'tail', counter, file_name, parent_locale)


def locale_from_tag(tag: _Element) -> DictionaryLocale | None:
    a = tag.attrib
    if 'lang' in a:
        try:
            loc = parse_lang_code(tag.get('lang'))
        except ValueError:
            loc = None
        if loc is not None:
            return loc
    if '{http://www.w3.org/XML/1998/namespace}lang' in a:
        try:
            loc = parse_lang_code(tag.get('{http://www.w3.org/XML/1998/namespace}lang'))
        except ValueError:
            loc = None
        if loc is not None:
            return loc


def read_words_from_html(root: _Element, words: WordsMap, file_name: str, book_locale: DictionaryLocale) -> None:
    stack = [(root, book_locale)]
    while stack:
        parent, parent_locale = stack.pop()
        locale = locale_from_tag(parent) or parent_locale
        read_words_from_html_tag(parent, words, file_name, parent_locale, locale)
        stack.extend((tag, locale) for tag in parent)


def count_chars_in_html(root: _Element, counter: CharCounter, file_name: str, book_locale: DictionaryLocale) -> None:
    stack = [(root, book_locale)]
    while stack:
        parent, parent_locale = stack.pop()
        locale = locale_from_tag(parent) or parent_locale
        count_chars_in_html_tag(parent, counter, file_name, parent_locale, locale)
        stack.extend((tag, locale) for tag in parent)


def group_sort(locations: Sequence[Location]) -> list[Location]:
    order: dict[str | None, int] = {}
    for loc in locations:
        if loc.file_name not in order:
            order[loc.file_name] = len(order)
    return sorted(locations, key=lambda l: (order[l.file_name], l.sourceline or 0))


def get_checkable_file_names(container: Container) -> tuple[list[str], str | None]:
    file_names = [name for name, linear in container.spine_names] + [container.opf_name]
    ncx_toc = find_existing_ncx_toc(container)
    if ncx_toc is not None and container.exists(ncx_toc) and ncx_toc not in file_names:
        file_names.append(ncx_toc)
    else:
        ncx_toc = None
    toc = find_existing_nav_toc(container)
    if toc is not None and container.exists(toc) and toc not in file_names:
        file_names.append(toc)
    return file_names, ncx_toc


def root_is_excluded_from_spell_check(root: _Element) -> bool:
    for child in root:
        q = (getattr(child, 'text', '') or '').strip().lower()
        if q == 'calibre-no-spell-check':
            return True
    return False


@overload
def get_all_words(
    container: Container,
    book_locale: DictionaryLocale,
    get_word_count: Literal[False] = False,
    excluded_files: Collection[str] = (),
    file_words_counts: dict[str, int] | None = None,
) -> dict[tuple[str, DictionaryLocale], list[Location]]: ...
@overload
def get_all_words(
    container: Container,
    book_locale: DictionaryLocale,
    get_word_count: Literal[True],
    excluded_files: Collection[str] = (),
    file_words_counts: dict[str, int] | None = None,
) -> tuple[int, dict[tuple[str, DictionaryLocale], list[Location]]]: ...
def get_all_words(
    container: Container,
    book_locale: DictionaryLocale,
    get_word_count: bool = False,
    excluded_files: Collection[str] = (),
    file_words_counts: dict[str, int] | None = None,
) -> dict[tuple[str, DictionaryLocale], list[Location]] | tuple[int, dict[tuple[str, DictionaryLocale], list[Location]]]:
    global file_word_count
    if file_words_counts is None:
        file_words_counts = {}
    words: WordsMap = defaultdict(list)
    words[None] = 0
    file_names, ncx_toc = get_checkable_file_names(container)
    for file_name in file_names:
        if not container.exists(file_name) or file_name in excluded_files:
            continue
        root = container.parsed(file_name)
        # Non XML spine items (parsed into bytes or stylesheets) contain no words
        is_xml = isinstance(root, etree._Element)
        if is_xml and root_is_excluded_from_spell_check(root):
            continue
        file_word_count = 0
        if not is_xml:
            pass
        elif file_name == container.opf_name:
            read_words_from_opf(root, words, file_name, book_locale)
        elif file_name == ncx_toc:
            read_words_from_ncx(root, words, file_name, book_locale)
        else:
            read_words_from_html(root, words, file_name, book_locale)
        file_words_counts[file_name] = file_word_count
        file_word_count = 0
    count = cast('int', words.pop(None))
    ans = {k: group_sort(v) for k, v in cast('dict[tuple[str, DictionaryLocale], list[Location]]', words).items()}
    if get_word_count:
        return count, ans
    return ans


def count_all_chars(container: Container, book_locale: DictionaryLocale) -> CharCounter:
    ans = CharCounter()
    file_names, ncx_toc = get_checkable_file_names(container)
    for file_name in file_names:
        if not container.exists(file_name):
            continue
        root = container.parsed(file_name)
        if not isinstance(root, etree._Element):
            continue  # non XML spine items (parsed into bytes or stylesheets) contain no characters to count
        if file_name == container.opf_name:
            count_chars_in_opf(root, ans, file_name, book_locale)
        elif file_name == ncx_toc:
            count_chars_in_ncx(root, ans, file_name, book_locale)
        else:
            count_chars_in_html(root, ans, file_name, book_locale)
    return ans


def merge_locations(locs1: list[Location], locs2: list[Location]) -> list[Location]:
    return group_sort(locs1 + locs2)


def replace(text: str | None, original_word: str | None, new_word: str, lang: str) -> tuple[str, bool]:
    indices: list[int] = []
    original_word, new_word, text = str(original_word), str(new_word), str(text)
    q = text
    offset = 0
    while True:
        idx = index_of(original_word, q, lang=lang)
        if idx == -1:
            break
        indices.append(offset + idx)
        offset += idx + len(original_word)
        q = text[offset:]
    for idx in reversed(indices):
        text = text[:idx] + new_word + text[idx + len(original_word) :]
    return text, bool(indices)


def replace_word(container: Container, new_word: str, locations: Iterable[Location], locale: DictionaryLocale, undo_cache: UndoCache | None = None) -> set[str]:
    changed: set[str] = set()
    for loc in locations:
        node = loc.location_node
        # locations are always created with a file name and node item, see add_words()
        is_attr, attr = cast('tuple[bool, str]', loc.node_item)
        file_name = cast('str', loc.file_name)
        if is_attr:
            text = node.get(attr)
        else:
            text = getattr(node, attr)
        replacement = loc.elided_prefix + new_word
        rtext, replaced = replace(text, loc.original_word, replacement, locale.langcode)
        if replaced:
            if undo_cache is not None:
                undo_cache[(file_name, node, is_attr, attr)] = text
            if is_attr:
                node.set(attr, rtext)
            else:
                setattr(node, attr, rtext)
            container.replace(file_name, node.getroottree().getroot())
            changed.add(file_name)
    return changed


def undo_replace_word(container: Container, undo_cache: UndoCache) -> set[str]:
    changed: set[str] = set()
    for (file_name, node, is_attr, attr), text in undo_cache.items():
        # attribute values are only cached when they contained the replaced word, so are never None
        node.set(attr, cast('str', text)) if is_attr else setattr(node, attr, text)
        container.replace(file_name, node.getroottree().getroot())
        changed.add(file_name)
    return changed


if __name__ == '__main__':
    import pprint

    from calibre.gui2.tweak_book import dictionaries, set_book_locale

    container = get_container(sys.argv[-1], tweak_mode=True)
    set_book_locale(container.mi.language)
    pprint.pprint(get_all_words(container, dictionaries.default_locale))
