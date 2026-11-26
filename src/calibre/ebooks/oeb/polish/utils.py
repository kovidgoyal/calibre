#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
from bisect import bisect
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, TypedDict, overload

from calibre import guess_type as _guess_type
from calibre import replace_entities
from calibre.utils.icu import upper as icu_upper

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from kgcss import DeclarationBlock, Stylesheet
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container

type CaseFunc = Callable[[str], str]
type EntityHandler = Callable[[str, CaseFunc], str]
FixedLayoutData = TypedDict('FixedLayoutData', {'fixed-layout': bool, 'rendition': dict[str, str | None], 'original-resolution': str | None})

BLOCK_TAG_NAMES = frozenset((
    'address',
    'article',
    'aside',
    'blockquote',
    'center',
    'dir',
    'fieldset',
    'isindex',
    'menu',
    'noframes',
    'hgroup',
    'noscript',
    'pre',
    'section',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'header',
    'p',
    'div',
    'dd',
    'dl',
    'ul',
    'ol',
    'li',
    'body',
    'td',
    'th',
))


def guess_type(x: str) -> str:
    return _guess_type(x)[0] or 'application/octet-stream'


# All font mimetypes seen in e-books
OEB_FONTS = frozenset({
    'font/otf',
    'font/woff',
    'font/woff2',
    'font/ttf',
    'application/x-font-ttf',
    'application/x-font-otf',
    'application/font-sfnt',
    'application/vnd.ms-opentype',
    'application/x-font-truetype',
})


def adjust_mime_for_epub(filename: str = '', mime: str = '', opf_version: Sequence[int] = (2, 0)) -> str:
    mime = mime or guess_type(filename)
    if mime == 'text/html':
        # epubcheck complains if the mimetype for text documents is set to text/html in EPUB 2 books. Sigh.
        return 'application/xhtml+xml'
    if mime not in OEB_FONTS:
        return mime
    if 'ttf' in mime or 'truetype' in mime:
        mime = 'font/ttf'
    elif 'otf' in mime or 'opentype' in mime:
        mime = 'font/otf'
    elif mime == 'application/font-sfnt':
        mime = 'font/otf' if filename.lower().endswith('.otf') else 'font/ttf'
    elif 'woff2' in mime:
        mime = 'font/woff2'
    elif 'woff' in mime:
        mime = 'font/woff'
    opf_version = tuple(opf_version[:2])
    if opf_version == (3, 0):
        mime = {
            'font/ttf': 'application/vnd.ms-opentype',  # this is needed by the execrable epubchek
            'font/otf': 'application/vnd.ms-opentype',
            'font/woff': 'application/font-woff',
        }.get(mime, mime)
    elif opf_version == (3, 1):
        mime = {
            'font/ttf': 'application/font-sfnt',
            'font/otf': 'application/font-sfnt',
            'font/woff': 'application/font-woff',
        }.get(mime, mime)
    elif opf_version < (3, 0):
        mime = {
            'font/ttf': 'application/x-font-truetype',
            'font/otf': 'application/vnd.ms-opentype',
            'font/woff': 'application/font-woff',
        }.get(mime, mime)
    return mime


#: Map of folder path to a map of lowercased file name to file name for the files in that folder
type FolderCaseMap = dict[str, dict[str, str] | None]


def actual_case_for_name(container: Container, name: str, folder_case_map: FolderCaseMap | None = None) -> str:
    """Return the name, as stored on the filesystem, of the existing file
    referred to by name, which can differ from name in case on case
    insensitive filesystems. See :func:`corrected_case_for_name` for
    folder_case_map."""
    from calibre.utils.filenames import samefile

    if not container.exists(name):
        raise ValueError(f'Cannot get actual case for {name} as it does not exist')
    parts = name.split('/')
    base = ''
    ans: list[str] = []
    for i, x in enumerate(parts):
        base = '/'.join(ans + [x])
        path = container.name_to_abspath(base)
        pdir = os.path.dirname(path)
        # Try the file whose name differs only in case first, to avoid
        # comparing against every file in the folder
        folder_names = folder_names_by_case(pdir, folder_case_map)
        if folder_names and (q := folder_names.get(x.lower())) is not None and samefile(os.path.join(pdir, q), path):
            correctx = q
        else:
            candidates = {os.path.join(pdir, q) for q in os.listdir(pdir)}
            if x in candidates:
                correctx = x
            else:
                for q in candidates:
                    if samefile(q, path):
                        correctx = os.path.basename(q)
                        break
                else:
                    raise RuntimeError('Something bad happened')
        ans.append(correctx)
    return '/'.join(ans)


def folder_names_by_case(folder: str, folder_case_map: FolderCaseMap | None = None) -> dict[str, str] | None:
    """Return a map of lowercased file name to file name for the files in
    folder, or None if folder cannot be listed. The result is cached in
    folder_case_map, if specified."""
    if folder_case_map is not None and folder in folder_case_map:
        return folder_case_map[folder]
    ans: dict[str, str] | None = {}
    try:
        for q in os.listdir(folder):
            ans.setdefault(q.lower(), q)
    except OSError:
        ans = None
    if folder_case_map is not None:
        folder_case_map[folder] = ans
    return ans


def corrected_case_for_name(container: Container, name: str, folder_case_map: FolderCaseMap | None = None) -> str | None:
    """Return the name of the file that matches name ignoring case, or None if
    no such file exists. When looking up many names, pass in the same
    folder_case_map, initially empty, to avoid listing a folder repeatedly. It
    must be discarded when files are added, removed or renamed."""
    parts = name.split('/')
    ans: list[str] = []
    base = ''
    for i, x in enumerate(parts):
        base = '/'.join(ans + [x])
        if container.exists(base):
            correctx = x
        else:
            # candidates is None if one of the non-terminal components of name is a file instead of a directory
            candidates = folder_names_by_case(os.path.dirname(container.name_to_abspath(base)), folder_case_map)
            if candidates is None or (q := candidates.get(x.lower())) is None:
                return None
            correctx = q
        ans.append(correctx)
    return '/'.join(ans)


def case_mismatched_name(container: Container, name: str) -> str | None:
    """If name differs only in case from the name of a file in the book,
    return the name of that file, otherwise return None. Works on both case
    sensitive and case insensitive filesystems."""
    if name in container.mime_map:
        return None
    if container.exists(name):
        if os.path.isdir(container.name_to_abspath(name)):
            return None
        ans: str | None = actual_case_for_name(container, name)
    else:
        ans = corrected_case_for_name(container, name)
    return ans if ans is not None and ans != name and ans in container.mime_map else None


class PositionFinder:
    def __init__(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            self.new_lines = tuple(m.start() + 1 for m in re.finditer(rb'\n', raw))
        else:
            self.new_lines = tuple(m.start() + 1 for m in re.finditer(r'\n', raw))

    def __call__(self, pos: int) -> tuple[int, int]:
        lnum = bisect(self.new_lines, pos)
        try:
            offset = abs(pos - self.new_lines[lnum - 1])
        except IndexError:
            offset = pos
        return (lnum + 1, offset)


class CommentFinder:
    def __init__(self, raw: str, pat: str = r'(?s)/\*.*?\*/') -> None:
        self.starts: list[int] = []
        self.ends: list[int] = []
        for m in re.finditer(pat, raw):
            start, end = m.span()
            self.starts.append(start), self.ends.append(end)

    def __call__(self, offset: int) -> bool:
        if not self.starts:
            return False
        q = bisect(self.starts, offset) - 1
        return q >= 0 and self.starts[q] <= offset <= self.ends[q]


def link_stylesheets(container: Container, names: Iterable[str], sheets: Sequence[str], remove: bool = False, mtype: str = 'text/css') -> set[str]:
    from lxml import etree

    from calibre.ebooks.oeb.base import XHTML, XPath

    changed_names: set[str] = set()
    snames = set(sheets)
    lp = XPath('//h:link[@href]')
    hp = XPath('//h:head')
    for name in names:
        root = container.parsed(name)
        assert isinstance(root, etree._Element)
        if remove:
            for link in lp(root):
                if (link.get('type', mtype) or mtype) == mtype:
                    container.remove_from_xml(link)
                    changed_names.add(name)
                    container.dirty(name)
        existing = {container.href_to_name(l.get('href'), name) for l in lp(root) if (l.get('type', mtype) or mtype) == mtype}
        extra = snames - existing
        if extra:
            changed_names.add(name)
            try:
                parent = hp(root)[0]
            except TypeError, IndexError:
                parent = root.makeelement(XHTML('head'))
                container.insert_into_xml(root, parent, index=0)
            for sheet in sheets:
                if sheet in extra:
                    container.insert_into_xml(
                        parent,
                        parent.makeelement(XHTML('link'), rel='stylesheet', type=mtype, href=container.name_to_href(sheet, name)),
                    )
            container.dirty(name)

    return changed_names


def lead_text(top_elem: _Element, num_words: int = 10) -> str:
    """Return the leading text contained in top_elem (including descendants)
    up to a maximum of num_words words. More efficient than using
    etree.tostring(method='text') as it does not have to serialize the entire
    sub-tree rooted at top_elem."""
    pat = re.compile(r'\s+', flags=re.UNICODE)
    words: list[str] = []

    def get_text(x: _Element, attr: str = 'text') -> None:
        ans = getattr(x, attr)
        if ans:
            words.extend(filter(None, pat.split(ans)))

    stack = [(top_elem, 'text')]
    while stack and len(words) < num_words:
        elem, attr = stack.pop()
        get_text(elem, attr)
        if attr == 'text':
            if elem is not top_elem:
                stack.append((elem, 'tail'))
            stack.extend(reversed([(c, 'text') for c in elem.iterchildren('*')]))
    return ' '.join(words[:num_words])


@overload
def parse_css(
    data: str | bytes | None,
    fname: str = '<string>',
    is_declaration: Literal[False] = False,
    decode: Callable[[bytes], str] | None = None,
    css_preprocessor: Callable[[str], str] | None = None,
) -> Stylesheet: ...
@overload
def parse_css(
    data: str | bytes | None,
    fname: str = '<string>',
    *,
    is_declaration: Literal[True],
    decode: Callable[[bytes], str] | None = None,
    css_preprocessor: Callable[[str], str] | None = None,
) -> DeclarationBlock: ...
@overload
def parse_css(
    data: str | bytes | None,
    fname: str = '<string>',
    is_declaration: bool = False,
    decode: Callable[[bytes], str] | None = None,
    css_preprocessor: Callable[[str], str] | None = None,
) -> Stylesheet | DeclarationBlock: ...
def parse_css(
    data: str | bytes | None,
    fname: str = '<string>',
    is_declaration: bool = False,
    decode: Callable[[bytes], str] | None = None,
    css_preprocessor: Callable[[str], str] | None = None,
) -> Stylesheet | DeclarationBlock:
    from kgcss import parse_style, parse_stylesheet

    from calibre.ebooks.oeb.base import _css_logger

    data = data or ''
    if isinstance(data, bytes):
        data = data.decode('utf-8') if decode is None else decode(data)
    if css_preprocessor is not None:
        data = css_preprocessor(data)
    if is_declaration:
        return parse_style(data, log=_css_logger)
    # Without a fetcher @import rules are never loaded, polish code follows
    # them itself (porting.md §5.1)
    return parse_stylesheet(data, href=fname, log=_css_logger)


def handle_entities(text: str, func: CaseFunc) -> str:
    return func(replace_entities(text))


def apply_func_to_match_groups(match: re.Match[str], func: CaseFunc = icu_upper, handle_entities: EntityHandler = handle_entities) -> str:
    """Apply the specified function to individual groups in the match object (the result of re.search() or
    the whole match if no groups were defined. Returns the replaced string."""
    found_groups = False
    i = 0
    parts: list[str] = []
    pos = match.start()

    def f(text: str) -> str:
        return handle_entities(text, func)

    while True:
        i += 1
        try:
            start, end = match.span(i)
        except IndexError:
            break
        found_groups = True
        if start > -1:
            parts.append(match.string[pos:start])
            parts.append(f(match.string[start:end]))
            pos = end
    if not found_groups:
        return f(match.group())
    parts.append(match.string[pos : match.end()])
    return ''.join(parts)


def apply_func_to_html_text(match: re.Match[str], func: CaseFunc = icu_upper, handle_entities: EntityHandler = handle_entities) -> str:
    """Apply the specified function only to text between HTML tag definitions."""

    def f(text: str) -> str:
        return handle_entities(text, func)

    parts = re.split(r'(<[^>]+>)', match.group())
    parts = (x if x.startswith('<') else f(x) for x in parts)
    return ''.join(parts)


def extract(elem: _Element) -> None:
    """Remove an element from the tree, keeping elem.tail"""
    p = elem.getparent()
    if p is not None:
        idx = p.index(elem)
        p.remove(elem)
        if elem.tail:
            if idx > 0:
                p[idx - 1].tail = (p[idx - 1].tail or '') + elem.tail
            else:
                p.text = (p.text or '') + elem.tail


def insert_self_closing(parent: _Element, item: _Element, index: int | None = None) -> None:
    """Insert item into parent (or append if index is None), fixing
    indentation. Only works with self closing items."""
    if index is None:
        parent.append(item)
    else:
        parent.insert(index, item)
    idx = parent.index(item)
    if idx == 0:
        item.tail = parent.text
        # If this is the only child of this parent element, we need a
        # little extra work as we have gone from a self-closing <foo />
        # element to <foo><item /></foo>
        if len(parent) == 1:
            sibling = parent.getprevious()
            if sibling is None:
                # Give up!
                return
            parent.text = sibling.text
            item.tail = sibling.tail
    else:
        item.tail = parent[idx - 1].tail
        if idx == len(parent) - 1:
            parent[idx - 1].tail = parent.text


def fixed_layout_data(container: Container) -> FixedLayoutData | None:
    """
    Return a dict of the various data for a fixed-layout rendering.
    Return None if not supported.
    """
    if not container.opf_version:
        return None
    if container.opf_version_parsed < (3, 0):
        return None
    if not container.opf_xpath('//opf:metadata/opf:meta[@name="fixed-layout" and @content="true"]'):
        return None
    rslt: FixedLayoutData = {
        'fixed-layout': True,
        'rendition': {},
        'original-resolution': None,
    }
    for rendition in container.opf_xpath('//opf:metadata/opf:meta[starts-with(@property,"rendition:")]'):
        rslt['rendition'][rendition.attrib['property'].split(':', 1)[1]] = rendition.text
    for item in container.opf_xpath('//opf:metadata/opf:meta[@name="original-resolution" and @content]'):
        rslt['original-resolution'] = item.attrib['content']
    return rslt
