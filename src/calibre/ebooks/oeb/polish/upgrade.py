#!/usr/bin/env python
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from typing import TYPE_CHECKING, cast

from calibre.ebooks import escape_xpath_attr
from calibre.ebooks.conversion.plugins.epub_input import ADOBE_OBFUSCATION, IDPF_OBFUSCATION
from calibre.ebooks.metadata.opf3 import XPath
from calibre.ebooks.metadata.opf_2_to_3 import upgrade_metadata
from calibre.ebooks.oeb.base import DC, EPUB_NS, OEB_DOCS, XML, xpath
from calibre.ebooks.oeb.parse_utils import ensure_namespace_prefixes
from calibre.ebooks.oeb.polish.opf import get_book_language
from calibre.ebooks.oeb.polish.toc import commit_nav_toc, find_existing_ncx_toc, get_landmarks, get_toc
from calibre.ebooks.oeb.polish.utils import OEB_FONTS
from calibre.ebooks.oeb.transforms.guide import CUSTOM_GUIDE_TYPE_PREFIX, KNOWN_GUIDE_TYPES
from calibre.utils.localization import _
from calibre.utils.short_uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container, EpubContainer
    from calibre.ebooks.oeb.polish.toc import TOC

    type PreviousNav = tuple[str, _Element]


def add_properties(item: _Element, *props: str) -> None:
    existing = set((item.get('properties') or '').split())
    existing |= set(props)
    item.set('properties', ' '.join(sorted(existing)))


def fix_font_mime_types(container: Container) -> bool:
    changed = False
    for item in container.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
        mt = item.get('media-type') or ''
        if mt.lower() in OEB_FONTS:
            name = container.href_to_name(item.get('href'), container.opf_name)
            if name is None:  # href does not point into the book
                continue
            item.set('media-type', container.guess_type(name))
            changed = True
    return changed


def migrate_obfuscated_fonts(container: EpubContainer) -> None:
    if not container.obfuscated_fonts:
        return
    name_to_elem_map: dict[str | None, tuple[_Element, _Element]] = {}
    for em, cr in container.iter_encryption_entries():
        alg = em.get('Algorithm')
        if cr is None or alg not in {ADOBE_OBFUSCATION, IDPF_OBFUSCATION}:
            continue
        name = container.href_to_name(cr.get('URI'))
        name_to_elem_map[name] = em, cr
    package_id, raw_unique_identifier, idpf_key = container.read_raw_unique_identifier()
    if not idpf_key:
        if not package_id:
            package_id = uuid4()
            container.opf.set('unique-identifier', package_id)
        existing = container.opf_xpath(f'//*[@id={escape_xpath_attr(package_id)}]')
        if existing:  # the unique identifier element exists but is empty
            ident = existing[0]
        else:
            metadata = XPath('./opf:metadata')(container.opf)[0]
            ident = metadata.makeelement(DC('identifier'), id=package_id)
            metadata.append(ident)
        ident.text = uuid4()
        package_id, raw_unique_identifier, idpf_key = container.read_raw_unique_identifier()
        assert idpf_key is not None  # the unique identifier element now exists and has text
    for name in tuple(container.obfuscated_fonts):
        try:
            em, cr = name_to_elem_map[name]
        except KeyError:
            container.obfuscated_fonts.pop(name)
            continue
        em.set('Algorithm', IDPF_OBFUSCATION)
        cr.set('URI', container.name_to_href(name))
        container.obfuscated_fonts[name] = (IDPF_OBFUSCATION, idpf_key)
    container.commit_item('META-INF/encryption.xml')


def collect_properties(container: Container) -> None:
    for item in container.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
        mt = item.get('media-type') or ''
        if mt.lower() not in OEB_DOCS:
            continue
        name = container.href_to_name(item.get('href'), container.opf_name)
        if name is None:  # href does not point into the book
            continue
        try:
            root = cast('_Element', container.parsed(name))  # HTML files are parsed into lxml trees
        except KeyError:
            continue
        root = ensure_namespace_prefixes(root, {'epub': EPUB_NS})
        properties = set()
        container.replace(name, root)  # Ensure entities are converted
        if xpath(root, '//svg:svg'):
            properties.add('svg')
        if xpath(root, '//h:script'):
            properties.add('scripted')
        if xpath(root, '//mathml:math'):
            properties.add('mathml')
        if xpath(root, '//epub:switch'):
            properties.add('switch')
        if properties:
            add_properties(item, *tuple(properties))


def add_lang_attributes(container: Container) -> None:
    # The lang attribute is not valid in the XHTML 1.1 used by EPUB 2, so
    # files may only have xml:lang, add lang as well for software that only
    # looks at it
    for name, mt in container.mime_map.items():
        if mt.lower() not in OEB_DOCS:
            continue
        root = cast('_Element', container.parsed(name))  # HTML files are parsed into lxml trees
        if (lang := root.get(XML('lang'))) and not root.get('lang'):
            root.set('lang', lang)
            container.dirty(name)


guide_epubtype_map = {
    'acknowledgements': 'acknowledgments',
    'other.afterword': 'afterword',
    'other.appendix': 'appendix',
    'other.backmatter': 'backmatter',
    'bibliography': 'bibliography',
    'text': 'bodymatter',
    'other.chapter': 'chapter',
    'colophon': 'colophon',
    'other.conclusion': 'conclusion',
    'other.contributors': 'contributors',
    'copyright-page': 'copyright-page',
    'cover': 'cover',
    'dedication': 'dedication',
    'other.division': 'division',
    'epigraph': 'epigraph',
    'other.epilogue': 'epilogue',
    'other.errata': 'errata',
    'other.footnotes': 'footnotes',
    'foreword': 'foreword',
    'other.frontmatter': 'frontmatter',
    'glossary': 'glossary',
    'other.halftitlepage': 'halftitlepage',
    'other.imprint': 'imprint',
    'other.imprimatur': 'imprimatur',
    'index': 'index',
    'other.introduction': 'introduction',
    'other.landmarks': 'landmarks',
    'other.loa': 'loa',
    'loi': 'loi',
    'lot': 'lot',
    'other.lov': 'lov',
    'notes': '',
    'other.notice': 'notice',
    'other.other-credits': 'other-credits',
    'other.part': 'part',
    'other.preamble': 'preamble',
    'preface': 'preface',
    'other.prologue': 'prologue',
    'other.rearnotes': 'rearnotes',
    'other.subchapter': 'subchapter',
    'title-page': 'titlepage',
    'toc': 'toc',
    'other.volume': 'volume',
    'other.warning': 'warning',
}
epubtype_guide_map = {v: k for k, v in guide_epubtype_map.items() if v}


def epubtype_for_guide_type(gtype: str) -> str | None:
    if gtype.lower().startswith(CUSTOM_GUIDE_TYPE_PREFIX):
        return gtype[len(CUSTOM_GUIDE_TYPE_PREFIX) :] or None
    return guide_epubtype_map.get(gtype.lower())


def guide_type_for_epubtype(epubtype: str) -> str:
    # Conversion keeps only known guide types, so use a custom type for the rest
    gtype = epubtype_guide_map.get(epubtype)
    return gtype if gtype in KNOWN_GUIDE_TYPES else (CUSTOM_GUIDE_TYPE_PREFIX + epubtype)


def create_nav(container: Container, toc: TOC, landmarks: list[dict[str, str | None]] | None, previous_nav: PreviousNav | None = None) -> None:
    lang = get_book_language(container)
    if lang == 'und':
        lang = None
    if landmarks:
        for entry in landmarks:
            # landmarks from get_landmarks() always have a str type
            entry['type'] = epubtype_for_guide_type(cast('str', entry['type']))
            if entry['type'] == 'cover' and container.mime_map.get(entry['dest'], '').lower() in OEB_DOCS:
                container.apply_unique_properties(entry['dest'], 'calibre:title-page')
    commit_nav_toc(container, toc, lang=lang, landmarks=landmarks, previous_nav=previous_nav)


def epub_2_to_3(container: EpubContainer, report: Callable[[str], object], previous_nav: PreviousNav | None = None, remove_ncx: bool = True) -> None:
    upgrade_metadata(container.opf)
    collect_properties(container)
    add_lang_attributes(container)
    toc = get_toc(container)
    toc_name = find_existing_ncx_toc(container)
    if toc_name and remove_ncx:
        container.remove_item(toc_name)
        container.opf_xpath('./opf:spine')[0].attrib.pop('toc', None)
    landmarks = get_landmarks(container)
    for guide in container.opf_xpath('./opf:guide'):
        cast('_Element', guide.getparent()).remove(guide)  # <guide> is always inside <package>
    create_nav(container, toc, landmarks, previous_nav)
    container.opf.set('version', '3.0')
    if fix_font_mime_types(container):
        container.refresh_mime_map()
    migrate_obfuscated_fonts(container)
    container.dirty(container.opf_name)


def upgrade_book(container: Container, report: Callable[[str], object], remove_ncx: bool = True) -> bool:
    if container.book_type not in ('epub', 'kepub') or container.opf_version_parsed.major >= 3:
        report(_('No upgrade needed'))
        return False
    # book_type is epub or kepub, so container is an EpubContainer
    epub_2_to_3(cast('EpubContainer', container), report, remove_ncx=remove_ncx)
    report(_('Updated EPUB from version 2 to 3'))
    return True


if __name__ == '__main__':
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.utils.logging import default_log

    default_log.filter_level = default_log.DEBUG
    inbook = sys.argv[-1]
    ebook = get_container(inbook, default_log)
    if upgrade_book(ebook, print):
        outbook = inbook.rpartition('.')[0] + '-upgraded.' + inbook.rpartition('.')[-1]
        ebook.commit(outbook)
        print('Upgraded book written to:', outbook)
