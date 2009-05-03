#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

class MergeMetadata(object):
    'Merge in user metadata, including cover'

    def __call__(self, oeb, mi, prefer_metadata_cover=False,
            prefer_author_sort=False):
        from calibre.ebooks.oeb.base import DC
        self.oeb, self.log = oeb, oeb.log
        m = self.oeb.metadata
        self.log('Merging user specified metadata...')
        if mi.title:
            m.clear('title')
            m.add('title', mi.title)
        if mi.title_sort:
            if not m.title:
                m.add(DC('title'), mi.title_sort)
            m.title[0].file_as = mi.title_sort
        if prefer_author_sort and mi.author_sort:
            mi.authors = [mi.author_sort]
        if mi.authors:
            m.filter('creator', lambda x : x.role.lower() == 'aut')
            for a in mi.authors:
                attrib = {'role':'aut'}
                if mi.author_sort:
                    attrib['file_as'] = mi.author_sort
                m.add('creator', a, attrib=attrib)
        if mi.comments:
            m.clear('description')
            m.add('description', mi.comments)
        if mi.publisher:
            m.clear('publisher')
            m.add('publisher', mi.publisher)
        if mi.series:
            m.clear('series')
            m.add('series', mi.series)
        if mi.isbn:
            has = False
            for x in m.identifier:
                if x.scheme.lower() == 'isbn':
                    x.content = mi.isbn
                    has = True
            if not has:
                m.add('identifier', mi.isbn, scheme='ISBN')
        if mi.language:
            m.clear('language')
            m.add('language', mi.language)
        if mi.book_producer:
            m.filter('creator', lambda x : x.role.lower() == 'bkp')
            m.add('creator', mi.book_producer, role='bkp')
        if mi.series_index is not None:
            m.clear('series_index')
            m.add('series_index', '%.2f'%mi.series_index)
        if mi.rating is not None:
            m.clear('rating')
            m.add('rating', '%.2f'%mi.rating)
        if mi.tags:
            m.clear('subject')
            for t in mi.tags:
                m.add('subject', t)

        cover_id = self.set_cover(mi, prefer_metadata_cover)
        m.clear('cover')
        if cover_id is not None:
            m.add('cover', cover_id)

    def set_cover(self, mi, prefer_metadata_cover):
        cdata = ''
        if mi.cover and os.access(mi.cover, os.R_OK):
            cdata = open(mi.cover, 'rb').read()
        elif mi.cover_data and mi.cover_data[-1]:
            cdata = mi.cover_data[1]
        id = None
        if 'cover' in self.oeb.guide:
            href = self.oeb.guide['cover'].href
            id = self.oeb.manifest.hrefs[href].id
            if not prefer_metadata_cover and cdata:
                self.oeb.manifest.hrefs[href]._data = cdata
        elif cdata:
            id, href = self.oeb.manifest.generate('cover', 'cover.jpg')
            self.oeb.manifest.add(id, href, 'image/jpeg', data=cdata)
            self.oeb.guide.add('cover', 'Cover', href)
        return id

