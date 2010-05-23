#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, __builtin__

import cherrypy

from calibre.utils.genshi.template import MarkupTemplate
from calibre.library.server.utils import strftime, expose
from calibre.ebooks.metadata import fmt_sidx

# Templates {{{
BOOK = '''\
<book xmlns:py="http://genshi.edgewall.org/"
    id="${r[FM['id']]}"
    title="${r[FM['title']]}"
    sort="${r[FM['sort']]}"
    author_sort="${r[FM['author_sort']]}"
    authors="${authors}"
    rating="${r[FM['rating']]}"
    timestamp="${timestamp}"
    pubdate="${pubdate}"
    size="${r[FM['size']]}"
    isbn="${r[FM['isbn']] if r[FM['isbn']] else ''}"
    formats="${r[FM['formats']] if r[FM['formats']] else ''}"
    series = "${r[FM['series']] if r[FM['series']] else ''}"
    series_index="${r[FM['series_index']]}"
    tags="${r[FM['tags']] if r[FM['tags']] else ''}"
    publisher="${r[FM['publisher']] if r[FM['publisher']] else ''}">${r[FM['comments']] if r[FM['comments']] else ''}
</book>
'''


LIBRARY = MarkupTemplate('''\
<?xml version="1.0" encoding="utf-8"?>
<library xmlns:py="http://genshi.edgewall.org/" start="$start" num="${len(books)}" total="$total" updated="${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}">
<py:for each="book in books">
    ${Markup(book)}
</py:for>
</library>
''')

# }}}

class XMLServer(object):
    'Serves XML and the Ajax based HTML frontend'

    @expose
    def library(self, start='0', num='50', sort=None, search=None,
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
        ids = self.db.data.parse(search) if search and search.strip() else self.db.data.universal_set()
        ids = sorted(ids)
        FM = self.db.FIELD_MAP
        items = copy.deepcopy([r for r in iter(self.db) if r[FM['id']] in ids])
        if sort is not None:
            self.sort(items, sort, order)

        book, books = MarkupTemplate(BOOK), []
        for record in items[start:start+num]:
            aus = record[FM['authors']] if record[FM['authors']] else __builtin__._('Unknown')
            authors = '|'.join([i.replace('|', ',') for i in aus.split(',')])
            record[FM['series_index']] = \
                fmt_sidx(float(record[FM['series_index']]))
            ts, pd = strftime('%Y/%m/%d %H:%M:%S', record[FM['timestamp']]), \
                strftime('%Y/%m/%d %H:%M:%S', record[FM['pubdate']])
            books.append(book.generate(r=record, authors=authors, timestamp=ts,
                pubdate=pd, FM=FM).render('xml').decode('utf-8'))
        updated = self.db.last_modified()

        cherrypy.response.headers['Content-Type'] = 'text/xml'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        return LIBRARY.generate(books=books, start=start, updated=updated,
                                     total=len(ids), FM=FM).render('xml')




