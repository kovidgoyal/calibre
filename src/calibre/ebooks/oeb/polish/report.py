#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import os
import posixpath
import time
import types
from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, NamedTuple

from css_selectors import Select, SelectorError
from lxml import etree

from calibre import force_unicode, prepare_string_for_xml
from calibre.ebooks.oeb.base import XPath, xml2text
from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.spell import count_all_chars, get_all_words
from calibre.ebooks.oeb.polish.utils import OEB_FONTS
from calibre.utils.icu import numeric_sort_key, safe_chr
from calibre.utils.imghdr import identify

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from lxml.etree import XPath as XPathType
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.ebooks.oeb.polish.spell import Location
    from calibre.spell import DictionaryLocale


class File(NamedTuple):
    name: str
    dir: str
    basename: str
    size: int
    category: str
    word_count: int


def get_category(name: str, mt: str) -> str:
    category = 'misc'
    if mt.startswith('image/'):
        category = 'image'
    elif mt in OEB_FONTS:
        category = 'font'
    elif mt in OEB_STYLES:
        category = 'style'
    elif mt in OEB_DOCS:
        category = 'text'
    ext = name.rpartition('.')[-1].lower()
    if ext in {'ttf', 'otf', 'woff', 'woff2'}:
        # Probably wrong mimetype in the OPF
        category = 'font'
    elif ext == 'opf':
        category = 'opf'
    elif ext == 'ncx':
        category = 'toc'
    return category


def safe_size(container: Container, name: str) -> int:
    try:
        return os.path.getsize(container.name_to_abspath(name))
    except Exception:
        return 0


def safe_img_data(container: Container, name: str, mt: str) -> tuple[int, int]:
    if 'svg' in mt:
        return 0, 0
    try:
        fmt, width, height = identify(container.name_to_abspath(name))
    except Exception:
        width = height = 0
    return width, height


def files_data(container: Container, *args: object) -> Iterator[File]:
    fwc = file_words_counts or {}
    for name, path in container.name_path_map.items():
        yield File(
            name,
            posixpath.dirname(name),
            posixpath.basename(name),
            safe_size(container, name),
            get_category(name, container.mime_map.get(name, '')),
            fwc.get(name, -1),
        )


class Image(NamedTuple):
    name: str
    mime_type: str
    usage: list[LinkLocation]
    size: int
    basename: str
    id: int
    width: int
    height: int


class LinkLocation(NamedTuple):
    name: str
    line_number: int | None
    text_on_line: str | None


def sort_locations(container: Container, locations: Iterable[LinkLocation]) -> list[LinkLocation]:
    nmap = {n: i for i, (n, l) in enumerate(container.spine_names)}

    def sort_key(l: LinkLocation) -> tuple[int, bytes, int | None]:
        return (nmap.get(l.name, len(nmap)), numeric_sort_key(l.name), l.line_number)

    return sorted(locations, key=sort_key)


def safe_href_to_name(container: Container, href: str | None, base: str) -> str | None:
    try:
        return container.href_to_name(href, base)
    except ValueError:
        pass  # Absolute path on windows


def images_data(container: Container, *args: object) -> tuple[Image, ...]:
    image_usage: defaultdict[str, set[LinkLocation]] = defaultdict(set)
    link_sources = OEB_STYLES | OEB_DOCS
    for name, mt in container.mime_map.items():
        if mt in link_sources:
            for href, line_number, offset in container.iterlinks(name):
                target = safe_href_to_name(container, href, name)
                if target and container.exists(target):
                    mt = container.mime_map.get(target)
                    if mt and mt.startswith('image/'):
                        image_usage[target].add(LinkLocation(name, line_number, href))

    image_data: list[Image] = []
    for name, mt in container.mime_map.items():
        if mt.startswith('image/') and container.exists(name):
            image_data.append(
                Image(
                    name,
                    mt,
                    sort_locations(container, image_usage.get(name, set())),
                    safe_size(container, name),
                    posixpath.basename(name),
                    len(image_data),
                    *safe_img_data(container, name, mt),
                )
            )
    return tuple(image_data)


def description_for_anchor(elem: _Element) -> str | None:
    def check(x: str | None, min_len: int = 4) -> str | None:
        if x:
            x = x.strip()
            if len(x) >= min_len:
                return x[:30]

    desc = check(elem.get('title'))
    if desc is not None:
        return desc
    desc = check(elem.text)
    if desc is not None:
        return desc
    if len(elem) > 0:
        desc = check(elem[0].text)
        if desc is not None:
            return desc
    # Get full text for tags that have only a few descendants
    for i, x in enumerate(elem.iterdescendants('*')):
        if i > 5:
            break
    else:
        desc = check(xml2text(elem), min_len=1)
        if desc is not None:
            return desc


def create_anchor_map(root: _Element, pat: XPathType, name: str) -> dict[str, tuple[LinkLocation, str | None]]:
    ans: dict[str, tuple[LinkLocation, str | None]] = {}
    for elem in pat(root):
        anchor = elem.get('id') or elem.get('name')
        if anchor and anchor not in ans:
            ans[anchor] = (LinkLocation(name, elem.sourceline, anchor), description_for_anchor(elem))
    return ans


class Anchor(NamedTuple):
    id: str | None
    location: LinkLocation | None
    text: str | None


class LinkItem(NamedTuple):
    location: LinkLocation
    text: str | None
    is_external: bool
    href: str
    path_ok: bool
    anchor_ok: bool
    anchor: Anchor
    ok: bool | None


def Link(location: LinkLocation, text: str | None, is_external: bool, href: str, path_ok: bool, anchor_ok: bool, anchor: Anchor) -> LinkItem:
    if is_external:
        ok = None
    else:
        ok = path_ok and anchor_ok
    return LinkItem(location, text, is_external, href, path_ok, anchor_ok, anchor, ok)


def links_data(container: Container, *args: object) -> Iterator[LinkItem]:
    anchor_map: dict[str, dict[str, tuple[LinkLocation, str | None]]] = {}
    links: list[tuple[str, str, str | None, LinkLocation, str | None]] = []
    anchor_pat = XPath('//*[@id or @name]')
    link_pat = XPath('//h:a[@href]')
    for name, mt in container.mime_map.items():
        if mt in OEB_DOCS:
            root = container.parsed(name)
            assert isinstance(root, etree._Element)
            anchor_map[name] = create_anchor_map(root, anchor_pat, name)
            for a in link_pat(root):
                href = a.get('href')
                text = description_for_anchor(a)
                location = LinkLocation(name, a.sourceline, href)
                if href:
                    base, frag = href.partition('#')[0::2]
                    if frag and not base:
                        dest = name
                    else:
                        dest = safe_href_to_name(container, href, name)
                    links.append((base, frag, dest, location, text))
                else:
                    links.append(('', '', None, location, text))

    for base, frag, dest, location, text in links:
        if dest is None:
            link = Link(location, text, True, base, True, True, Anchor(frag, None, None))
        elif dest in anchor_map:
            loc = LinkLocation(dest, None, None)
            if frag:
                anchor = anchor_map[dest].get(frag)
                if anchor is None:
                    link = Link(location, text, False, dest, True, False, Anchor(frag, loc, None))
                else:
                    link = Link(location, text, False, dest, True, True, Anchor(frag, *anchor))
            else:
                link = Link(location, text, False, dest, True, True, Anchor(None, loc, None))
        else:
            link = Link(location, text, False, dest, False, False, Anchor(frag, None, None))
        yield link


class Word(NamedTuple):
    id: int
    word: str
    locale: DictionaryLocale
    usage: list[Location]


file_words_counts: dict[str, int] | None = None


def words_data(container: Container, book_locale: DictionaryLocale, *args: object) -> tuple[int, tuple[Word, ...]]:
    count, words = get_all_words(container, book_locale, get_word_count=True, file_words_counts=file_words_counts)
    return (count, tuple(Word(i, word, locale, v) for i, ((word, locale), v) in enumerate(words.items())))


class Char(NamedTuple):
    id: int
    char: str
    codepoint: int
    usage: list[str]
    count: int


def chars_data(container: Container, book_locale: DictionaryLocale, *args: object) -> Iterator[Char]:
    cc = count_all_chars(container, book_locale)
    nmap = {n: i for i, (n, l) in enumerate(container.spine_names)}

    def sort_key(name: str) -> tuple[int, bytes]:
        return nmap.get(name, len(nmap)), numeric_sort_key(name)

    for i, (codepoint, usage) in enumerate(cc.chars.items()):
        if c := safe_chr(codepoint):
            yield Char(i, c, codepoint, sorted(usage, key=sort_key), cc.counter[codepoint])


class CSSRule(NamedTuple):
    selector: str
    location: RuleLocation


class RuleLocation(NamedTuple):
    file_name: str
    line: int
    column: int


class MatchLocation(NamedTuple):
    tag: str
    sourceline: int | None


class CSSEntry(NamedTuple):
    rule: CSSRule
    count: int
    matched_files: tuple[CSSFileMatch, ...]
    sort_key: bytes


class CSSFileMatch(NamedTuple):
    file_name: str
    locations: tuple[MatchLocation, ...]
    sort_key: bytes


class ClassEntry(NamedTuple):
    cls: str
    num_of_matches: int
    matched_files: tuple[ClassFileMatch, ...]
    sort_key: bytes


class ClassFileMatch(NamedTuple):
    file_name: str
    class_elements: tuple[ClassElement, ...]
    sort_key: bytes


class ClassElement(NamedTuple):
    name: str
    line_number: int | None
    text_on_line: str | None
    tag: str
    matched_rules: tuple[CSSRule, ...]


def css_data(container: Container, book_locale: DictionaryLocale, result_data: dict[str, object], *args: object) -> list[CSSEntry]:
    import tinycss
    from tinycss.css21 import ImportRule, RuleSet

    #: Either a style rule or the name of an imported stylesheet
    type SheetItem = CSSRule | str

    def css_rules(file_name: str, rules: Iterable[object], sourceline: int = 0) -> list[SheetItem]:
        ans: list[SheetItem] = []
        for rule in rules:
            if isinstance(rule, RuleSet):
                selector = rule.selector.as_css()
                ans.append(CSSRule(selector, RuleLocation(file_name, sourceline + rule.line, rule.column)))
            elif isinstance(rule, ImportRule):
                import_name = safe_href_to_name(container, rule.uri, file_name)
                if import_name and container.exists(import_name):
                    ans.append(import_name)
            elif sub_rules := getattr(rule, 'rules', ()):
                ans.extend(css_rules(file_name, sub_rules, sourceline))
        return ans

    parser = tinycss.make_full_parser()
    importable_sheets: dict[str, list[SheetItem]] = {}
    html_sheets: dict[str, list[list[SheetItem]]] = {}
    spine_names = {name for name, is_linear in container.spine_names}
    style_path, link_path = XPath('//h:style'), XPath('//h:link/@href')

    for name, mt in container.mime_map.items():
        if mt in OEB_STYLES:
            importable_sheets[name] = css_rules(name, parser.parse_stylesheet(container.raw_data(name)).rules)
        elif mt in OEB_DOCS and name in spine_names:
            html_sheets[name] = []
            root = container.parsed(name)
            assert isinstance(root, etree._Element)
            for style in style_path(root):
                if style.get('type', 'text/css') == 'text/css' and style.text:
                    html_sheets[name].append(
                        css_rules(
                            name,
                            parser.parse_stylesheet(force_unicode(style.text, 'utf-8')).rules,
                            style.sourceline - 1,
                        )
                    )

    rule_map: defaultdict[CSSRule, defaultdict[str, list[MatchLocation]]] = defaultdict(lambda: defaultdict(list))

    def rules_in_sheet(sheet: list[SheetItem]) -> Iterator[CSSRule]:
        for rule in sheet:
            if isinstance(rule, CSSRule):
                yield rule
            else:  # @import rule
                isheet = importable_sheets.get(rule)
                if isheet is not None:
                    yield from rules_in_sheet(isheet)

    def sheets_for_html(name: str, root: _Element) -> Iterator[list[SheetItem]]:
        for href in link_path(root):
            tname = safe_href_to_name(container, href, name)
            sheet = importable_sheets.get(tname)
            if sheet is not None:
                yield sheet

    tt_cache: dict[_Element, str] = {}

    def tag_text(elem: _Element) -> str:
        ans = tt_cache.get(elem)
        if ans is None:
            etag = elem.tag
            assert isinstance(etag, str)  # elements matched by CSS selectors always have str tags
            tag = etag.rpartition('}')[-1]
            if elem.attrib:
                attribs = ' '.join('{}="{}"'.format(k, prepare_string_for_xml(elem.get(k, ''), True)) for k in elem.keys())
                ans = f'<{tag} {attribs}>'
            else:
                ans = f'<{tag}>'
            tt_cache[elem] = ans
        return ans

    type ClassUsageMap = defaultdict[str, defaultdict[_Element, list[CSSRule]]]

    def matches_for_selector(selector: str, select: Select, class_map: ClassUsageMap, rule: CSSRule) -> Iterable[MatchLocation]:
        lsel = selector.lower()
        try:
            matches = tuple(select(selector))
        except SelectorError:
            return ()
        seen: set[_Element] = set()

        def get_elem_and_ancestors(elem: _Element) -> Iterator[_Element]:
            p = elem
            while p is not None:
                if p not in seen:
                    yield p
                    seen.add(p)
                p = p.getparent()

        for e in matches:
            for elem in get_elem_and_ancestors(e):
                for cls in elem.get('class', '').split():
                    if '.' + cls.lower() in lsel:
                        class_map[cls][elem].append(rule)

        return (MatchLocation(tag_text(elem), elem.sourceline) for elem in matches)

    class_map: defaultdict[str, defaultdict[str, list[ClassElement]]] = defaultdict(lambda: defaultdict(list))

    for name, inline_sheets in html_sheets.items():
        root = container.parsed(name)
        assert isinstance(root, etree._Element)
        cmap: ClassUsageMap = defaultdict(lambda: defaultdict(list))
        for elem in root.xpath('//*[@class]'):
            for cls in elem.get('class', '').split():
                cmap[cls][elem] = []
        select = Select(root, ignore_inappropriate_pseudo_classes=True)
        for sheet in chain(sheets_for_html(name, root), inline_sheets):
            for rule in rules_in_sheet(sheet):
                rule_map[rule][name].extend(matches_for_selector(rule.selector, select, cmap, rule))
        for cls, elem_map in cmap.items():
            class_elements = class_map[cls][name]
            for elem, usage in elem_map.items():
                class_elements.append(ClassElement(name, elem.sourceline, elem.get('class'), tag_text(elem), tuple(usage)))

    class_entries: list[ClassEntry] = []
    result_data['classes'] = class_entries
    for cls, name_map in class_map.items():
        cla = tuple(ClassFileMatch(name, tuple(class_elements), numeric_sort_key(name)) for name, class_elements in name_map.items() if class_elements)
        num_of_matches = sum(sum(len(ce.matched_rules) for ce in cfm.class_elements) for cfm in cla)
        class_entries.append(ClassEntry(cls, num_of_matches, cla, numeric_sort_key(cls)))

    ans: list[CSSEntry] = []
    for rule, loc_map in rule_map.items():
        la = tuple(CSSFileMatch(name, tuple(locations), numeric_sort_key(name)) for name, locations in loc_map.items() if locations)
        count = sum(len(fm.locations) for fm in la)
        ans.append(CSSEntry(rule, count, la, numeric_sort_key(rule.selector)))

    return ans


def gather_data(container: Container, book_locale: DictionaryLocale) -> tuple[dict[str, object], dict[str, float]]:
    global file_words_counts
    timing: dict[str, float] = {}
    data: dict[str, object] = {}
    file_words_counts = {}
    for x in 'chars images links words css files'.split():
        st = time.time()
        data[x] = val = globals()[x + '_data'](container, book_locale, data)
        if isinstance(val, types.GeneratorType):
            data[x] = tuple(val)
        timing[x] = time.time() - st
    file_words_counts = None
    return data, timing


def debug_data_gather() -> None:
    import sys

    from calibre.gui2.tweak_book import dictionaries
    from calibre.gui2.tweak_book.boss import get_container

    c = get_container(sys.argv[-1])
    gather_data(c, dictionaries.default_locale)
