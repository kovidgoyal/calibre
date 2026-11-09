#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from lxml import etree

from calibre.ebooks.oeb.polish.container import OPF_NAMESPACES
from calibre.utils.localization import canonicalize_lang, lang_as_bcp47

if TYPE_CHECKING:
    from calibre.ebooks.oeb.polish.container import Container


def get_book_language(container: Container) -> str | None:
    for lang in container.opf_xpath('//dc:language'):
        raw = lang.text
        if raw:
            code = canonicalize_lang(raw.split(',')[0].strip())
            if code:
                return code


def get_book_language_tag(container: Container) -> str | None:
    # The language of the book as a BCP 47 language tag, for use in the lang
    # attributes of HTML files
    for lang in container.opf_xpath('//dc:language'):
        if ans := lang_as_bcp47(lang.text or ''):
            return ans
    return None


PACKAGE_LANG = '{http://www.w3.org/XML/1998/namespace}lang'


def has_package_language(container: Container) -> bool:
    return bool((container.opf.get(PACKAGE_LANG) or '').strip())


def set_package_language(container: Container, lang: str | None = None, replace: bool = False) -> bool:
    """
    Set the xml:lang attribute of the <package> element of an EPUB 3 OPF, which
    is the default language of the OPF and is required by accessibility
    checkers such as Ace. Defaults to the language of the book. Only set if
    missing, unless ``replace`` is True. Returns True if the OPF was changed.
    Not valid in the OPF of EPUB 2, so callers must check the OPF version.
    """
    if not (lang := lang or get_book_language_tag(container)):
        return False
    current = container.opf.get(PACKAGE_LANG)
    if current == lang or (has_package_language(container) and not replace):
        return False
    container.opf.set(PACKAGE_LANG, lang)
    container.dirty(container.opf_name)
    return True


def set_guide_item(container: Container, item_type: str, title: str, name: str | None, frag: str | None = None) -> None:
    ref_tag = '{{{}}}reference'.format(OPF_NAMESPACES['opf'])
    href = None
    if name:
        href = container.name_to_href(name, container.opf_name)
        if frag:
            href += '#' + frag

    guides = container.opf_xpath('//opf:guide')
    if not guides and href:
        g = container.opf.makeelement('{{{}}}guide'.format(OPF_NAMESPACES['opf']), nsmap={'opf': OPF_NAMESPACES['opf']})
        container.insert_into_xml(container.opf, g)
        guides = [g]

    for guide in guides:
        matches = []
        for child in guide.iterchildren(etree.Element):
            if child.tag == ref_tag and child.get('type', '').lower() == item_type.lower():
                matches.append(child)
        if not matches and href:
            r = guide.makeelement(ref_tag, type=item_type, nsmap={'opf': OPF_NAMESPACES['opf']})
            container.insert_into_xml(guide, r)
            matches.append(r)
        for m in matches:
            if href:
                m.set('title', title), m.set('href', href), m.set('type', item_type)
            else:
                container.remove_from_xml(m)
    container.dirty(container.opf_name)
