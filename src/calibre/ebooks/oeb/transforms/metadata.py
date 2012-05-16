#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re
from calibre.utils.date import isoformat, now
from calibre import guess_type

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
    for typ, val in identifiers.iteritems():
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


class MergeMetadata(object):
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

    def set_cover(self, mi, prefer_metadata_cover):
        cdata, ext = '', 'jpg'
        if mi.cover and os.access(mi.cover, os.R_OK):
            cdata = open(mi.cover, 'rb').read()
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
            cdata = ''
        if cdata:
            self.oeb.guide.remove('cover')
            self.oeb.guide.remove('titlepage')
        if old_cover is not None:
            if old_cover.href in self.oeb.manifest.hrefs:
                item = self.oeb.manifest.hrefs[old_cover.href]
                if not cdata:
                    return item.id
                self.remove_old_cover(item)
            elif not cdata:
                id = self.oeb.manifest.generate(id='cover')
                self.oeb.manifest.add(id, old_cover.href, 'image/jpeg')
                return id
        if cdata:
            id, href = self.oeb.manifest.generate('cover', 'cover.'+ext)
            self.oeb.manifest.add(id, href, guess_type('cover.'+ext)[0], data=cdata)
            self.oeb.guide.add('cover', 'Cover', href)
        return id

    def remove_old_cover(self, cover_item):
        from calibre.ebooks.oeb.base import XPath
        from lxml import etree

        self.oeb.manifest.remove(cover_item)

        # Remove any references to the cover in the HTML
        affected_items = set()
        for item in self.oeb.spine:
            try:
                images = XPath('//h:img[@src]')(item.data)
            except:
                images = []
            removed = False
            for img in images:
                href = item.abshref(img.get('src'))
                if href == cover_item.href:
                    img.getparent().remove(img)
                    removed = True
            if removed:
                affected_items.add(item)

        # Check if the resulting HTML has no content, if so remove it
        for item in affected_items:
            body = XPath('//h:body')(item.data)
            if body:
                text = etree.tostring(body[0], method='text', encoding=unicode)
            else:
                text = ''
            text = re.sub(r'\s+', '', text)
            if not text:
                self.log('Removing %s as it is a wrapper around'
                        ' the cover image'%item.href)
                self.oeb.spine.remove(item)
                self.oeb.manifest.remove(item)



