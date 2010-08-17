#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import __builtin__

import cherrypy
from lxml.builder import ElementMaker
from lxml import etree

from calibre.library.server.utils import strftime
from calibre.ebooks.metadata import fmt_sidx
from calibre.constants import preferred_encoding
from calibre import isbytestring

E = ElementMaker()

class XMLServer(object):
    'Serves XML and the Ajax based HTML frontend'

    def add_routes(self, connect):
        connect('xml', '/xml', self.xml)

    def xml(self, start='0', num='50', sort=None, search=None,
                _=None, order='ascending'):
        '''
        Serves metadata from the calibre database as XML.

        :param sort: Sort results by ``sort``. Can be one of `title,author,rating`.
        :param search: Filter results by ``search`` query. See :class:`SearchQueryParser` for query syntax
        :param start,num: Return the slice `[start:start+num]` of the sorted and filtered results
        :param _: Firefox seems to sometimes send this when using XMLHttpRequest with no caching
        '''
        try:
            start = int(start)
        except ValueError:
            raise cherrypy.HTTPError(400, 'start: %s is not an integer'%start)
        try:
            num = int(num)
        except ValueError:
            raise cherrypy.HTTPError(400, 'num: %s is not an integer'%num)

        order = order.lower().strip() == 'ascending'

        ids = self.db.search_getting_ids(search, self.search_restriction)

        FM = self.db.FIELD_MAP

        items = [r for r in iter(self.db) if r[FM['id']] in ids]
        if sort is not None:
            self.sort(items, sort, order)

        books = []

        def serialize(x):
            if isinstance(x, unicode):
                return x
            if isbytestring(x):
                return x.decode(preferred_encoding, 'replace')
            return unicode(x)

        for record in items[start:start+num]:
            kwargs = {}
            aus = record[FM['authors']] if record[FM['authors']] else __builtin__._('Unknown')
            authors = '|'.join([i.replace('|', ',') for i in aus.split(',')])
            kwargs['authors'] = authors

            kwargs['series_index'] = \
                fmt_sidx(float(record[FM['series_index']]))

            for x in ('timestamp', 'pubdate'):
                kwargs[x] = strftime('%Y/%m/%d %H:%M:%S', record[FM[x]])

            for x in ('id', 'title', 'sort', 'author_sort', 'rating', 'size'):
                kwargs[x] = serialize(record[FM[x]])

            for x in ('isbn', 'formats', 'series', 'tags', 'publisher',
                    'comments'):
                y = record[FM[x]]
                kwargs[x] = serialize(y) if y else ''

            c = kwargs.pop('comments')
            books.append(E.book(c, **kwargs))

        updated = self.db.last_modified()
        kwargs = dict(
                start = str(start),
                updated=updated.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                total=str(len(ids)),
                num=str(len(books)))
        ans = E.library(*books, **kwargs)

        cherrypy.response.headers['Content-Type'] = 'text/xml'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)

        return etree.tostring(ans, encoding='utf-8', pretty_print=True,
                xml_declaration=True)




