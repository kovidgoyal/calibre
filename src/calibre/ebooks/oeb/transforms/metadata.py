#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re
from calibre.utils.date import isoformat, now
from calibre import guess_type
from polyglot.builtins import iteritems


def meta_info_to_oeb_metadata(mi, m, log, override_input_metadata=False):
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
        m.filter('creator', lambda x : x.role.lower() in ['aut', ''])
        for a in mi.authors:
            attrib = {'role':'aut'}
            if mi.author_sort:
                attrib[OPF('file-as')] = mi.author_sort
            m.add('creator', a, attrib=attrib)
    if not mi.is_null('book_producer'):
        m.filter('contributor', lambda x : x.role.lower() == 'bkp')
        m.add('contributor', mi.book_producer, role='bkp')
    elif override_input_metadata:
        m.filter('contributor', lambda x : x.role.lower() == 'bkp')
    if not mi.is_null('comments'):
        m.clear('description')
        m.add('description', mi.comments)
    elif override_input_metadata:
        m.clear('description')
    if not mi.is_null('publisher'):
        m.clear('publisher')
        m.add('publisher', mi.publisher)
    elif override_input_metadata:
        m.clear('publisher')
    if not mi.is_null('series'):
        m.clear('series')
        m.add('series', mi.series)
    elif override_input_metadata:
        m.clear('series')
    identifiers = mi.get_identifiers()
    set_isbn = False
    for typ, val in iteritems(identifiers):
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
        m.add('rating', '%.2f'%mi.rating)
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
        m.add('date', isoformat(mi.pubdate))
    if not mi.is_null('timestamp'):
        m.clear('timestamp')
        m.add('timestamp', isoformat(mi.timestamp))
    if not mi.is_null('rights'):
        m.clear('rights')
        m.add('rights', mi.rights)
    if not mi.is_null('publication_type'):
        m.clear('publication_type')
        m.add('publication_type', mi.publication_type)

    if not m.timestamp:
        m.add('timestamp', isoformat(now()))


class MergeMetadata:
    'Merge in user metadata, including cover'

    def __call__(self, oeb, mi, opts, override_input_metadata=False):
        self.oeb, self.log = oeb, oeb.log
        m = self.oeb.metadata
        self.log('Merging user specified metadata...')
        meta_info_to_oeb_metadata(mi, m, oeb.log,
                override_input_metadata=override_input_metadata)
        cover_id = self.set_cover(mi, opts.prefer_metadata_cover)
        m.clear('cover')
        if cover_id is not None:
            m.add('cover', cover_id)
        if mi.uuid is not None:
            m.filter('identifier', lambda x:x.id=='uuid_id')
            self.oeb.metadata.add('identifier', mi.uuid, id='uuid_id',
                                  scheme='uuid')
            self.oeb.uid = self.oeb.metadata.identifier[-1]
        if mi.application_id is not None:
            m.filter('identifier', lambda x:x.scheme=='calibre')
            self.oeb.metadata.add('identifier', mi.application_id, scheme='calibre')

    def set_cover(self, mi, prefer_metadata_cover):
        cdata, ext = b'', 'jpg'
        if mi.cover and os.access(mi.cover, os.R_OK):
            with open(mi.cover, 'rb') as f:
                cdata = f.read()
            ext = mi.cover.rpartition('.')[-1].lower().strip()
        elif mi.cover_data and mi.cover_data[-1]:
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
            # The amazon formats dont support html cover pages, so remove them
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
            id, href = self.oeb.manifest.generate('cover', 'cover.'+ext)
            new_cover_item = self.oeb.manifest.add(id, href, guess_type('cover.'+ext)[0], data=cdata)
            self.oeb.guide.add('cover', 'Cover', href)
        if do_remove_old_cover:
            self.remove_old_cover(item, new_cover_item.href)
        return id

    def remove_old_cover(self, cover_item, new_cover_href=None):
        from calibre.ebooks.oeb.base import XPath, XLINK
        from lxml import etree

        self.oeb.manifest.remove(cover_item)

        # Remove any references to the cover in the HTML
        affected_items = set()
        xp = XPath('//h:img[@src]|//svg:image[@xl:href]')
        for i, item in enumerate(self.oeb.spine):
            try:
                images = xp(item.data)
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
            body = XPath('//h:body')(item.data)
            if body:
                text = etree.tostring(body[0], method='text', encoding='unicode')
            else:
                text = ''
            text = re.sub(r'\s+', '', text)
            if not text and not XPath('//h:img|//svg:svg')(item.data):
                self.log('Removing %s as it is a wrapper around'
                        ' the cover image'%item.href)
                self.oeb.spine.remove(item)
                self.oeb.manifest.remove(item)
                self.oeb.guide.remove_by_href(item.href)
