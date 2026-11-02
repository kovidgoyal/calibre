#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

import os
import re
from typing import TYPE_CHECKING, cast

from calibre import guess_type
from calibre.utils.date import isoformat, now

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.ebooks.oeb.base import Metadata as OEBMetadata
    from calibre.utils.logging import Log


def meta_info_to_oeb_metadata(mi: Metadata, m: OEBMetadata, log: Log, override_input_metadata: bool = False) -> None:
    from calibre.ebooks.oeb.base import OPF

    if not mi.is_null('title'):
        m.clear('title')
        m.add('title', mi.title)
    if mi.title_sort:
        if not m.title:
            m.add('title', mi.title_sort)
        m.clear('title_sort')
        m.add('title_sort', mi.title_sort)
    if not mi.is_null('authors'):
        m.filter('creator', lambda x: x.role.lower() in ['aut', ''])
        for a in mi.authors:
            attrib = {'role': 'aut'}
            if mi.author_sort:
                attrib[OPF('file-as')] = mi.author_sort
            m.add('creator', a, attrib=attrib)
    if not mi.is_null('book_producer'):
        m.filter('contributor', lambda x: x.role.lower() == 'bkp')
        assert mi.book_producer is not None  # not null
        m.add('contributor', mi.book_producer, role='bkp')
    elif override_input_metadata:
        m.filter('contributor', lambda x: x.role.lower() == 'bkp')
    if not mi.is_null('comments'):
        m.clear('description')
        assert mi.comments is not None  # not null
        m.add('description', mi.comments)
    elif override_input_metadata:
        m.clear('description')
    if not mi.is_null('publisher'):
        m.clear('publisher')
        assert mi.publisher is not None  # not null
        m.add('publisher', mi.publisher)
    elif override_input_metadata:
        m.clear('publisher')
    if not mi.is_null('series'):
        m.clear('series')
        assert mi.series is not None  # not null
        m.add('series', mi.series)
    elif override_input_metadata:
        m.clear('series')
    identifiers = mi.get_identifiers()
    set_isbn = False
    for typ, val in identifiers.items():
        has = False
        if typ.lower() == 'isbn':
            set_isbn = True
        for x in m.identifier:
            if x.scheme.lower() == typ.lower():
                x.content = val
                has = True
        if not has:
            m.add('identifier', val, scheme=typ.upper())
    if override_input_metadata and not set_isbn:
        m.filter('identifier', lambda x: x.scheme.lower() == 'isbn')
    if not mi.is_null('languages'):
        m.clear('language')
        for lang in mi.languages:
            if lang and lang.lower() not in ('und', ''):
                m.add('language', lang)
    if not mi.is_null('series_index'):
        m.clear('series_index')
        m.add('series_index', mi.format_series_index())
    elif override_input_metadata:
        m.clear('series_index')
    if not mi.is_null('rating'):
        m.clear('rating')
        m.add('rating', f'{mi.rating:.2f}')
    elif override_input_metadata:
        m.clear('rating')
    if not mi.is_null('tags'):
        m.clear('subject')
        for t in mi.tags:
            m.add('subject', t)
    elif override_input_metadata:
        m.clear('subject')
    if not mi.is_null('pubdate'):
        m.clear('date')
        assert mi.pubdate is not None  # not null
        m.add('date', isoformat(mi.pubdate))
    if not mi.is_null('timestamp'):
        m.clear('timestamp')
        assert mi.timestamp is not None  # not null
        m.add('timestamp', isoformat(mi.timestamp))
    if not mi.is_null('rights'):
        m.clear('rights')
        assert mi.rights is not None  # not null
        m.add('rights', mi.rights)
    if not mi.is_null('publication_type'):
        m.clear('publication_type')
        assert mi.publication_type is not None  # not null
        m.add('publication_type', mi.publication_type)

    if not m.timestamp:
        m.add('timestamp', isoformat(now()))


class MergeMetadata:
    "Merge in user metadata, including cover"

    def __call__(self, oeb: OEBBook, mi: Metadata, opts: Values | OptionValues, override_input_metadata: bool = False) -> None:
        self.oeb, self.log = oeb, oeb.log
        m = self.oeb.metadata
        self.log('Merging user specified metadata...')
        meta_info_to_oeb_metadata(mi, m, oeb.log, override_input_metadata=override_input_metadata)
        cover_id = self.set_cover(mi, opts.prefer_metadata_cover)
        m.clear('cover')
        if cover_id is not None:
            m.add('cover', cover_id)
        if mi.uuid is not None:
            m.filter('identifier', lambda x: x.id == 'uuid_id')
            self.oeb.metadata.add('identifier', mi.uuid, id='uuid_id', scheme='uuid')
            self.oeb.uid = self.oeb.metadata.identifier[-1]
        if mi.application_id is not None:
            m.filter('identifier', lambda x: x.scheme == 'calibre')
            # application_id is an int for metadata from a library
            self.oeb.metadata.add('identifier', str(mi.application_id), scheme='calibre')

    def set_cover(self, mi: Metadata, prefer_metadata_cover: bool) -> str | None:
        cdata, ext = b'', 'jpg'
        if mi.cover and os.access(mi.cover, os.R_OK):
            with open(mi.cover, 'rb') as f:
                cdata = f.read()
            ext = mi.cover.rpartition('.')[-1].lower().strip()
        elif mi.cover_data[-1]:
            cdata = mi.cover_data[1]
            ext = mi.cover_data[0]
        if ext not in ('png', 'jpg', 'jpeg'):
            ext = 'jpg'
        id = old_cover = None
        if 'cover' in self.oeb.guide:
            old_cover = self.oeb.guide['cover']
        if prefer_metadata_cover and old_cover is not None:
            cdata = b''
        if cdata:
            self.oeb.guide.remove('cover')
            self.oeb.guide.remove('titlepage')
        elif self.oeb.plumber_output_format in {'mobi', 'azw3'} and old_cover is not None:
            # The amazon formats don't support html cover pages, so remove them
            # even if no cover was specified.
            self.oeb.guide.remove('titlepage')
        do_remove_old_cover = False
        if old_cover is not None:
            if old_cover.href in self.oeb.manifest.hrefs:
                item = self.oeb.manifest.hrefs[old_cover.href]
                if not cdata:
                    return item.id
                do_remove_old_cover = True
            elif not cdata:
                id = self.oeb.manifest.generate(id='cover')[0]
                self.oeb.manifest.add(id, old_cover.href, 'image/jpeg')
                return id
        new_cover_item = None
        if cdata:
            id, href = self.oeb.manifest.generate('cover', 'cover.' + ext)
            new_cover_item = self.oeb.manifest.add(id, href, cast('str', guess_type('cover.' + ext)[0]), data=cdata)
            self.oeb.guide.add('cover', 'Cover', href)
        if do_remove_old_cover:
            assert new_cover_item is not None
            self.remove_old_cover(item, new_cover_item.href)
        return id

    def remove_old_cover(self, cover_item: Manifest.Item, new_cover_href: str | None = None) -> None:
        from lxml import etree

        from calibre.ebooks.oeb.base import XLINK, XPath

        self.oeb.manifest.remove(cover_item)

        # Remove any references to the cover in the HTML
        affected_items: set[Manifest.Item] = set()
        xp = XPath('//h:img[@src]|//svg:image[@xl:href]')
        for i, item in enumerate(self.oeb.spine):
            try:
                root = item.data
                assert isinstance(root, etree._Element)  # spine items are always (X)HTML documents
                images = xp(root)
            except Exception:
                images = ()
            removed = False
            for img in images:
                href = img.get('src') or img.get(XLINK('href'))
                try:
                    href = item.abshref(href)
                except Exception:
                    continue  # Invalid URL, ignore
                if href == cover_item.href:
                    if new_cover_href is not None:
                        replacement_href = item.relhref(new_cover_href)
                        attr = 'src' if img.tag.endswith('img') else XLINK('href')
                        img.set(attr, replacement_href)
                    else:
                        p = img.getparent()
                        if p.tag.endswith('}svg'):
                            p.getparent().remove(p)
                        else:
                            p.remove(img)
                        removed = True
            if removed:
                affected_items.add(item)

        # Check if the resulting HTML has no content, if so remove it
        for item in affected_items:
            root = item.data
            assert isinstance(root, etree._Element)  # affected_items are spine items
            body = XPath('//h:body')(root)
            if body:
                text = etree.tostring(body[0], method='text', encoding='unicode')
            else:
                text = ''
            text = re.sub(r'\s+', '', text)
            if not text and not XPath('//h:img|//svg:svg')(root):
                self.log(f'Removing {item.href} as it is a wrapper around the cover image')
                self.oeb.spine.remove(item)
                self.oeb.manifest.remove(item)
                self.oeb.guide.remove_by_href(item.href)
