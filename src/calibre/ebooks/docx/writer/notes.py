#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

'''
Detection of footnotes/endnotes in HTML so that they can be output as native
Word footnotes or endnotes.

Detection is deliberately conservative, since a false positive moves body text
into a note. A link is considered to be a note reference if either:

  * it is semantically marked up as one (role="doc-noteref" or epub:type="noteref")
  * it is rendered as a superscript and the note it points to links back to it

The content of the note is the semantically marked up note element containing
the link target (role="doc-footnote", epub:type="footnote", an <li> in an
endnotes list, etc.), or failing that, the nearest block containing the link
target. Notes that cannot be extracted unambiguously are left alone, as
ordinary hyperlinks.
'''

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal
from urllib.parse import unquote, urlparse

from lxml import etree

from calibre.ebooks.oeb.base import EPUB_NS, XHTML_NS, barename, urlquote

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.ebooks.oeb.stylizer import Style, Stylizer
    from calibre.utils.logging import Log

NotesType = Literal['footnotes', 'endnotes']
EPUB_TYPE = f'{{{EPUB_NS}}}type'
INLINE_DISPLAYS = frozenset(('inline', 'inline-block'))
SUPERSCRIPT_ALIGNS = frozenset(('super', 'top', 'text-top'))
HEADINGS = frozenset(('h1', 'h2', 'h3', 'h4', 'h5', 'h6'))
NOTE_TYPES = frozenset(('note', 'footnote', 'endnote', 'rearnote'))
NOTE_ROLES = frozenset(('doc-note', 'doc-footnote', 'doc-endnote', 'doc-rearnote'))
NOTES_SECTION_TYPES = frozenset(('footnotes', 'endnotes', 'rearnotes'))
NOTES_SECTION_ROLES = frozenset(('doc-endnotes',))
# Elements whose presence means a block has content even without any text
CONTENT_TAGS = frozenset(('img', 'svg', 'math', 'video', 'audio', 'object', 'embed', 'iframe', 'canvas'))
# Wrappers around a note reference that are removed along with the brackets around them
BRACKET_PAIRS = {'[': ']', '(': ')', '{': '}'}
# Characters left at the start of a note after the link back to the note
# reference is removed, for example from "1. Note text" or "[↩] Note text"
LEADING_JUNK = ' \t\r\n\f\v\xa0           \u200b 　.,:;)]}–—|'
MAX_HEURISTIC_REF_LENGTH = 10
MAX_BACKLINK_LENGTH = 10
WORD_CHAR = re.compile(r'\w')


def tag_name(elem: etree._Element) -> str:
    tag = elem.tag
    if not isinstance(tag, str):
        return ''  # comments and processing instructions
    return barename(tag).lower()


def tokens(elem: etree._Element, attr: str) -> frozenset[str]:
    return frozenset((elem.get(attr) or '').lower().split())


def epub_types(elem: etree._Element) -> frozenset[str]:
    # epub:type without a namespace declaration ends up as epub_type when parsed as HTML
    return tokens(elem, EPUB_TYPE) | tokens(elem, 'epub_type')


def is_note_element(elem: etree._Element) -> bool:
    return bool(epub_types(elem) & NOTE_TYPES or tokens(elem, 'role') & NOTE_ROLES)


def is_notes_section(elem: etree._Element) -> bool:
    return bool(epub_types(elem) & NOTES_SECTION_TYPES or tokens(elem, 'role') & NOTES_SECTION_ROLES)


def is_semantic_noteref(a: etree._Element) -> bool:
    return 'noteref' in epub_types(a) or 'doc-noteref' in tokens(a, 'role')


def is_semantic_backlink(a: etree._Element) -> bool:
    return 'backlink' in epub_types(a) or 'doc-backlink' in tokens(a, 'role')


def text_of(elem: etree._Element) -> str:
    return ''.join(x for x in elem.itertext() if isinstance(x, str))


def ancestors_or_self(elem: etree._Element) -> Iterator[etree._Element]:
    """Yield elem and its ancestors, stopping before <body>"""
    x: etree._Element | None = elem
    while x is not None and tag_name(x) not in ('body', 'html'):
        yield x
        x = x.getparent()


def text_slots(root: etree._Element) -> Iterator[tuple[etree._Element, Literal['text', 'tail']]]:
    """Yield the text nodes inside root, in document order, as (element, attribute) pairs"""
    if isinstance(root.tag, str):
        yield root, 'text'
        for child in root.iterchildren():
            yield from text_slots(child)
            yield child, 'tail'


def has_word_chars_before(container: etree._Element, elem: etree._Element) -> bool:
    for x, attr in text_slots(container):
        if x is elem and attr == 'text':
            return False
        if tag_name(x) in CONTENT_TAGS:
            return True
        if WORD_CHAR.search(getattr(x, attr) or ''):
            return True
    return False


def strip_leading_junk(container: etree._Element) -> None:
    for x, attr in text_slots(container):
        if tag_name(x) in CONTENT_TAGS:
            break
        val = getattr(x, attr)
        if val:
            val = val.lstrip(LEADING_JUNK)
            setattr(x, attr, val or None)
            if val:
                break


def remove_preserving_tail(elem: etree._Element) -> None:
    parent = elem.getparent()
    if parent is None:
        return
    if elem.tail:
        prev = elem.getprevious()
        if prev is None:
            parent.text = (parent.text or '') + elem.tail
        else:
            prev.tail = (prev.tail or '') + elem.tail
    parent.remove(elem)


def strip_enclosing_brackets(elem: etree._Element) -> None:
    """Remove brackets around elem, as in [<a>1</a>] since Word generates its own note reference marks"""
    # Move up through inline wrappers, such as <sup>, that contain only elem
    x = elem
    while True:
        parent = x.getparent()
        if parent is None or tag_name(parent) not in ('sup', 'span', 'small', 'b', 'i', 'em', 'strong', 'a'):
            break
        if (parent.text or '').strip() or (x.tail or '').strip() or len(parent) != 1:
            break
        x = parent
    parent = x.getparent()
    if parent is None:
        return
    prev = x.getprevious()
    before = parent.text if prev is None else prev.tail
    after = x.tail
    if not before or not after:
        return
    b, a = before.rstrip(), after.lstrip()
    if b and a and BRACKET_PAIRS.get(b[-1]) == a[0]:
        before = b[:-1] + before[len(b) :]
        after = after[: len(after) - len(a)] + a[1:]
        if prev is None:
            parent.text = before
        else:
            prev.tail = before
        x.tail = after


@dataclass(eq=False)
class Note:
    item: Manifest.Item
    container: etree._Element
    is_semantic_container: bool
    targets: set[etree._Element] = field(default_factory=set)
    refs: list[etree._Element] = field(default_factory=list)  # The <a> tags referring to this note, in document order
    number: int = 0  # The 1-based number of the note, in order of first reference
    ref_bookmark: str = ''  # The bookmark wrapping the first reference, for use by subsequent references


@dataclass(eq=False)
class Candidate:
    a: etree._Element
    target: etree._Element
    container: etree._Element
    target_item: Manifest.Item
    is_semantic_ref: bool
    is_semantic_container: bool


class NotesManager:
    def __init__(self, oeb: OEBBook, notes_type: NotesType, stylizer_for: Callable[[Manifest.Item], Stylizer], log: Log) -> None:
        self.oeb, self.notes_type, self.stylizer_for, self.log = oeb, notes_type, stylizer_for, log
        self.id_maps: dict[str, dict[str, etree._Element]] = {}
        self.root_items: dict[etree._Element, Manifest.Item] = {}
        self.notes: list[Note] = []
        self.note_for_ref: dict[etree._Element, Note] = {}
        self.note_for_container: dict[etree._Element, Note] = {}
        # Elements whose contents are not output in the body of the document
        self.skipped_elements: set[etree._Element] = set()
        # Links inside notes that point back to their reference and are not output
        self.backlinks: set[etree._Element] = set()

    # Helpers {{{
    def style(self, elem: etree._Element) -> Style:
        return self.stylizer_for(self.root_items[elem.getroottree().getroot()]).style(elem)

    def display(self, elem: etree._Element) -> str:
        return str(self.style(elem)._get('display'))

    def is_inline(self, elem: etree._Element) -> bool:
        return self.display(elem) in INLINE_DISPLAYS

    def is_hidden(self, elem: etree._Element) -> bool:
        return any(self.style(x).is_hidden for x in ancestors_or_self(elem))

    def is_superscript(self, a: etree._Element) -> bool:
        for i, x in enumerate(ancestors_or_self(a)):
            if i > 3 or not self.is_inline(x):
                break
            if self.style(x)._get('vertical-align') in SUPERSCRIPT_ALIGNS:
                return True
        children = tuple(a.iterchildren('*'))
        if len(children) == 1 and not (a.text or '').strip() and not (children[0].tail or '').strip():
            child = children[0]
            return self.is_inline(child) and self.style(child)._get('vertical-align') in SUPERSCRIPT_ALIGNS
        return False

    def resolve(self, item: Manifest.Item, href: str) -> tuple[Manifest.Item, etree._Element] | None:
        """Return the element an internal link points to, if any"""
        try:
            purl = urlparse(href)
        except ValueError:
            return None
        if purl.scheme or purl.netloc or not purl.fragment:
            return None
        target_href = item.href
        if purl.path:
            target_href = item.abshref(purl.path)
        for h in (target_href, urlquote(target_href), unquote(target_href)):
            id_map = self.id_maps.get(h)
            if id_map is not None:
                break
        else:
            return None
        elem = id_map.get(purl.fragment)
        if elem is None:
            elem = id_map.get(unquote(purl.fragment))
        if elem is None:
            return None
        return self.root_items[elem.getroottree().getroot()], elem

    def find_container(self, target: etree._Element) -> tuple[etree._Element, bool] | None:
        """Return the element containing the note and whether it is semantically marked up as a note"""
        for x in ancestors_or_self(target):
            if is_note_element(x):
                return x, True
            if tag_name(x) == 'li' and any(is_notes_section(y) for y in ancestors_or_self(x)):
                return x, True
        for x in ancestors_or_self(target):
            if not self.is_inline(x):
                return x, False
        return None

    def is_backlink(self, link: etree._Element, refs: list[etree._Element]) -> bool:
        if is_semantic_backlink(link):
            return True
        href = link.get('href')
        if not href:
            return False
        r = self.resolve(self.root_items[link.getroottree().getroot()], href)
        if r is None:
            return False
        target = r[1]
        for ref in refs:
            for i, x in enumerate(ancestors_or_self(ref)):
                if x is target:
                    # A link to the reference itself or to some inline
                    # wrapper around it is a backlink, a link to the block
                    # containing the reference is a backlink only if it is
                    # short, i.e. not some text that just happens to be
                    # linked to the paragraph in which the note is
                    # referenced.
                    return i == 0 or self.is_inline(x) or len(text_of(link).strip()) <= MAX_BACKLINK_LENGTH
        return False

    def residual_is_empty(self, elem: etree._Element, allow_headings: bool) -> bool:
        """Return True if elem has no content other than extracted notes (and headings if allow_headings is True)"""
        if elem in self.note_for_container:
            return True
        tag = tag_name(elem)
        if allow_headings and tag in HEADINGS:
            return True
        if tag in CONTENT_TAGS or tag in HEADINGS or (elem.text or '').strip():
            return False
        for child in elem.iterchildren():
            if isinstance(child.tag, str) and not self.residual_is_empty(child, allow_headings):
                return False
            if (child.tail or '').strip():
                return False
        return True

    def contains_extracted_note(self, elem: etree._Element) -> bool:
        return any(x in self.note_for_container for x in elem.iter('*'))

    # }}}

    def __call__(self) -> bool:
        """Detect notes, returns True if any notes were found"""
        for item in self.oeb.spine:
            root = item.data
            if not isinstance(root, etree._Element):
                continue
            self.root_items[root] = item
            id_map: dict[str, etree._Element] = {}
            for elem in root.iter('*'):
                eid = elem.get('id')
                if eid:
                    id_map.setdefault(eid, elem)
                if tag_name(elem) == 'a' and (name := elem.get('name')):
                    id_map.setdefault(name, elem)
            self.id_maps[item.href] = id_map

        candidates = self.find_candidates()
        if not candidates:
            return False
        self.create_notes(candidates)
        if not self.notes:
            return False
        self.find_skipped_elements()
        self.cleanup_markup()
        return True

    def find_candidates(self) -> list[Candidate]:
        ans: list[Candidate] = []
        for item in self.oeb.spine:
            root = item.data
            if not isinstance(root, etree._Element):
                continue
            for a in root.iter(f'{{{XHTML_NS}}}a'):
                href = a.get('href')
                if not href or 'doc-link' in tokens(a, 'role'):
                    continue
                r = self.resolve(item, href)
                if r is None:
                    continue
                target_item, target = r
                if any(x is target for x in ancestors_or_self(a)):
                    continue
                is_semantic_ref = is_semantic_noteref(a)
                if not is_semantic_ref:
                    text = text_of(a).strip()
                    if not text or len(text) > MAX_HEURISTIC_REF_LENGTH or not self.is_superscript(a):
                        continue
                c = self.find_container(target)
                if c is None:
                    continue
                container, is_semantic_container = c
                if self.is_hidden(a) or self.is_hidden(container):
                    continue
                ans.append(Candidate(a, target, container, target_item, is_semantic_ref, is_semantic_container))
        return ans

    def is_valid_container(self, container: etree._Element, is_semantic: bool) -> bool:
        if tag_name(container) in HEADINGS or any(tag_name(x) in HEADINGS for x in container.iterdescendants('*')):
            return False
        if not is_semantic:
            # Extracting part of a table would leave behind a broken table
            if self.display(container).startswith('table-'):
                return False
            if any(self.display(x).startswith('table') for x in ancestors_or_self(container) if x is not container):
                return False
        return True

    def create_notes(self, candidates: list[Candidate]) -> None:
        by_container: dict[etree._Element, list[Candidate]] = {}
        for c in candidates:
            by_container.setdefault(c.container, []).append(c)
        valid: dict[etree._Element, list[Candidate]] = {}
        for container, cs in by_container.items():
            is_semantic = cs[0].is_semantic_container
            if not self.is_valid_container(container, is_semantic):
                continue
            # Links to different places in the same block, for example
            # several notes in a single paragraph separated by line breaks,
            # cannot be split up reliably
            if not is_semantic and len({c.target for c in cs}) > 1:
                continue
            if not any(c.is_semantic_ref for c in cs):
                # Heuristically detected reference, require a link back to the reference from the note
                refs = [c.a for c in cs]
                if not any(self.is_backlink(link, refs) for link in container.iter(f'{{{XHTML_NS}}}a')):
                    continue
            valid[container] = cs
        # Nested notes cannot be represented in Word, leave them alone
        for container in tuple(valid):
            if any(x in valid for x in ancestors_or_self(container) if x is not container) or any(x in valid for x in container.iterdescendants('*')):
                del valid[container]
        for container in tuple(valid):
            # References inside notes cannot be converted, as Word does not allow notes in notes
            refs = [c for c in valid[container] if not any(x in valid for x in ancestors_or_self(c.a))]
            if refs:
                valid[container] = refs
            else:
                del valid[container]
        # Create the notes in the order of their first reference in the document
        for c in candidates:
            cs = valid.get(c.container)
            if cs is None or c not in cs or any(x in valid for x in ancestors_or_self(c.a)):
                continue
            note = self.note_for_container.get(c.container)
            if note is None:
                note = self.note_for_container[c.container] = Note(c.target_item, c.container, c.is_semantic_container)
                self.notes.append(note)
                note.number = len(self.notes)
            note.targets.add(c.target)
            note.refs.append(c.a)
            self.note_for_ref[c.a] = note
        self.log.debug(f'Found {len(self.notes)} notes with {len(self.note_for_ref)} references')

    def find_skipped_elements(self) -> None:
        self.skipped_elements |= set(self.note_for_container)
        for item in self.oeb.spine:
            root = item.data
            if not isinstance(root, etree._Element):
                continue
            # Notes sections containing only extracted notes and headings and
            # other wrappers containing only extracted notes
            for elem in root.iter('*'):
                if tag_name(elem) in ('body', 'html') or not self.contains_extracted_note(elem):
                    continue
                if self.residual_is_empty(elem, allow_headings=is_notes_section(elem)):
                    if not any(ref in self.note_for_ref for ref in elem.iter(f'{{{XHTML_NS}}}a')):
                        self.skipped_elements.add(elem)
            # Headings followed only by extracted notes, such as "Notes", up to the next heading
            for elem in root.iter('*'):
                if tag_name(elem) not in HEADINGS or (elem.tail or '').strip():
                    continue
                if any(ref in self.note_for_ref for ref in elem.iter(f'{{{XHTML_NS}}}a')):
                    continue
                following: list[etree._Element] = []
                ok = True
                for sibling in elem.itersiblings():
                    if not isinstance(sibling.tag, str):
                        continue
                    if tag_name(sibling) in HEADINGS or any(tag_name(x) in HEADINGS for x in sibling.iterdescendants('*')):
                        break
                    if not self.residual_is_empty(sibling, allow_headings=False) or (sibling.tail or '').strip():
                        ok = False
                        break
                    following.append(sibling)
                if ok and any(self.contains_extracted_note(x) for x in following):
                    self.skipped_elements.add(elem)

    def cleanup_markup(self) -> None:
        for note in self.notes:
            for ref in note.refs:
                strip_enclosing_brackets(ref)
            backlinks = [link for link in note.container.iter(f'{{{XHTML_NS}}}a') if self.is_backlink(link, note.refs)]
            at_start = False
            for link in backlinks:
                if not has_word_chars_before(note.container, link):
                    at_start = True
                strip_enclosing_brackets(link)
                remove_preserving_tail(link)
            if at_start:
                strip_leading_junk(note.container)

    def skipped_anchors(self) -> set[tuple[str, str]]:
        """The (href, id) pairs of all anchors inside elements not output in the body"""
        ans: set[tuple[str, str]] = set()
        for elem in self.skipped_elements:
            item = self.root_items[elem.getroottree().getroot()]
            for x in elem.iter('*'):
                if eid := x.get('id') or x.get('name'):
                    ans.add((item.href, eid))
        return ans
