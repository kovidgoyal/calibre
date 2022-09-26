#!/usr/bin/env python
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


import sys

from calibre.ebooks.conversion.plugins.epub_input import (
    ADOBE_OBFUSCATION, IDPF_OBFUSCATION
)
from calibre.ebooks.metadata.opf3 import XPath
from calibre.ebooks.metadata.opf_2_to_3 import upgrade_metadata
from calibre.ebooks.oeb.base import DC, EPUB_NS, OEB_DOCS, xpath
from calibre.ebooks.oeb.parse_utils import ensure_namespace_prefixes
from calibre.ebooks.oeb.polish.opf import get_book_language
from calibre.ebooks.oeb.polish.toc import (
    commit_nav_toc, find_existing_ncx_toc, get_landmarks, get_toc
)
from calibre.ebooks.oeb.polish.utils import OEB_FONTS
from calibre.utils.short_uuid import uuid4


def add_properties(item, *props):
    existing = set((item.get('properties') or '').split())
    existing |= set(props)
    item.set('properties', ' '.join(sorted(existing)))


def fix_font_mime_types(container):
    changed = False
    for item in container.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
        mt = item.get('media-type') or ''
        if mt.lower() in OEB_FONTS:
            name = container.href_to_name(item.get('href'), container.opf_name)
            item.set('media-type', container.guess_type(name))
            changed = True
    return changed


def migrate_obfuscated_fonts(container):
    if not container.obfuscated_fonts:
        return
    name_to_elem_map = {}
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
        metadata = XPath('./opf:metadata')(container.opf)[0]
        ident = metadata.makeelement(DC('identifier'))
        ident.text = uuid4()
        metadata.append(ident)
        package_id, raw_unique_identifier, idpf_key = container.read_raw_unique_identifier()
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


def collect_properties(container):
    for item in container.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
        mt = item.get('media-type') or ''
        if mt.lower() not in OEB_DOCS:
            continue
        name = container.href_to_name(item.get('href'), container.opf_name)
        root = container.parsed(name)
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


guide_epubtype_map = {
     'acknowledgements'   : 'acknowledgments',
     'other.afterword'    : 'afterword',
     'other.appendix'     : 'appendix',
     'other.backmatter'   : 'backmatter',
     'bibliography'       : 'bibliography',
     'text'               : 'bodymatter',
     'other.chapter'      : 'chapter',
     'colophon'           : 'colophon',
     'other.conclusion'   : 'conclusion',
     'other.contributors' : 'contributors',
     'copyright-page'     : 'copyright-page',
     'cover'              : 'cover',
     'dedication'         : 'dedication',
     'other.division'     : 'division',
     'epigraph'           : 'epigraph',
     'other.epilogue'     : 'epilogue',
     'other.errata'       : 'errata',
     'other.footnotes'    : 'footnotes',
     'foreword'           : 'foreword',
     'other.frontmatter'  : 'frontmatter',
     'glossary'           : 'glossary',
     'other.halftitlepage': 'halftitlepage',
     'other.imprint'      : 'imprint',
     'other.imprimatur'   : 'imprimatur',
     'index'              : 'index',
     'other.introduction' : 'introduction',
     'other.landmarks'    : 'landmarks',
     'other.loa'          : 'loa',
     'loi'                : 'loi',
     'lot'                : 'lot',
     'other.lov'          : 'lov',
     'notes'              : '',
     'other.notice'       : 'notice',
     'other.other-credits': 'other-credits',
     'other.part'         : 'part',
     'other.preamble'     : 'preamble',
     'preface'            : 'preface',
     'other.prologue'     : 'prologue',
     'other.rearnotes'    : 'rearnotes',
     'other.subchapter'   : 'subchapter',
     'title-page'         : 'titlepage',
     'toc'                : 'toc',
     'other.volume'       : 'volume',
     'other.warning'      : 'warning'
}


def create_nav(container, toc, landmarks, previous_nav=None):
    lang = get_book_language(container)
    if lang == 'und':
        lang = None
    if landmarks:
        for entry in landmarks:
            entry['type'] = guide_epubtype_map.get(entry['type'].lower())
            if entry['type'] == 'cover' and container.mime_map.get(entry['dest'], '').lower() in OEB_DOCS:
                container.apply_unique_properties(entry['dest'], 'calibre:title-page')
    commit_nav_toc(container, toc, lang=lang, landmarks=landmarks, previous_nav=previous_nav)


def epub_2_to_3(container, report, previous_nav=None, remove_ncx=True):
    upgrade_metadata(container.opf)
    collect_properties(container)
    toc = get_toc(container)
    toc_name = find_existing_ncx_toc(container)
    if toc_name and remove_ncx:
        container.remove_item(toc_name)
        container.opf_xpath('./opf:spine')[0].attrib.pop('toc', None)
    landmarks = get_landmarks(container)
    for guide in container.opf_xpath('./opf:guide'):
        guide.getparent().remove(guide)
    create_nav(container, toc, landmarks, previous_nav)
    container.opf.set('version', '3.0')
    if fix_font_mime_types(container):
        container.refresh_mime_map()
    migrate_obfuscated_fonts(container)
    container.dirty(container.opf_name)


def upgrade_book(container, report, remove_ncx=True):
    if container.book_type != 'epub' or container.opf_version_parsed.major >= 3:
        report(_('No upgrade needed'))
        return False
    epub_2_to_3(container, report, remove_ncx=remove_ncx)
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
