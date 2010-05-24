#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, copy
import __builtin__

import cherrypy

from calibre.utils.genshi.template import MarkupTemplate
from calibre.library.server.utils import strftime, expose
from calibre.ebooks.metadata import fmt_sidx

# Templates {{{
MOBILE_BOOK = '''\
<tr xmlns:py="http://genshi.edgewall.org/">
<td class="thumbnail">
    <img type="image/jpeg" src="/get/thumb/${r[FM['id']]}" border="0"/>
</td>
<td>
    <py:for each="format in r[FM['formats']].split(',')">
        <span class="button"><a href="/get/${format}/${authors}-${r[FM['title']]}_${r[FM['id']]}.${format}">${format.lower()}</a></span>&nbsp;
    </py:for>
    ${r[FM['title']]}${(' ['+r[FM['series']]+'-'+r[FM['series_index']]+']') if r[FM['series']] else ''} by ${authors} - ${r[FM['size']]/1024}k - ${r[FM['publisher']] if r[FM['publisher']] else ''} ${pubdate} ${'['+r[FM['tags']]+']' if r[FM['tags']] else ''}
</td>
</tr>
'''

MOBILE = MarkupTemplate('''\
<html xmlns:py="http://genshi.edgewall.org/">
<head>
<style>
.navigation table.buttons {
    width: 100%;
}
.navigation .button {
    width: 50%;
}
.button a, .button:visited a {
    padding: 0.5em;
    font-size: 1.25em;
    border: 1px solid black;
    text-color: black;
    background-color: #ddd;
    border-top: 1px solid ThreeDLightShadow;
    border-right: 1px solid ButtonShadow;
    border-bottom: 1px solid ButtonShadow;
    border-left: 1 px solid ThreeDLightShadow;
    -moz-border-radius: 0.25em;
    -webkit-border-radius: 0.25em;
}

.button:hover a {
    border-top: 1px solid #666;
    border-right: 1px solid #CCC;
    border-bottom: 1 px solid #CCC;
    border-left: 1 px solid #666;


}
div.navigation {
    padding-bottom: 1em;
    clear: both;
}

#search_box {
    border: 1px solid #393;
    -moz-border-radius: 0.5em;
    -webkit-border-radius: 0.5em;
    padding: 1em;
    margin-bottom: 0.5em;
    float: right;
}

#listing {
    width: 100%;
    border-collapse: collapse;
}
#listing td {
    padding: 0.25em;
}

#listing td.thumbnail {
    height: 60px;
    width: 60px;
}

#listing tr:nth-child(even) {

    background: #eee;
}

#listing .button a{
    display: inline-block;
    width: 2.5em;
    padding-left: 0em;
    padding-right: 0em;
    overflow: hidden;
    text-align: center;
}

#logo {
    float: left;
}
#spacer {
    clear: both;
}

</style>
<link rel="icon" href="http://calibre-ebook.com/favicon.ico" type="image/x-icon" />
</head>
<body>
    <div id="logo">
    <img src="/static/calibre.png" alt="Calibre" />
    </div>
    <div id="search_box">
    <form method="get" action="/mobile">
    Show <select name="num">
        <py:for each="option in [5,10,25,100]">
                <option py:if="option == num" value="${option}" SELECTED="SELECTED">${option}</option>
                <option py:if="option != num" value="${option}">${option}</option>
        </py:for>
        </select>
    books matching <input name="search" id="s" value="${search}" /> sorted by

    <select name="sort">
        <py:for each="option in ['date','author','title','rating','size','tags','series']">
                <option py:if="option == sort" value="${option}" SELECTED="SELECTED">${option}</option>
                <option py:if="option != sort" value="${option}">${option}</option>
        </py:for>
    </select>
    <select name="order">
        <py:for each="option in ['ascending','descending']">
                <option py:if="option == order" value="${option}" SELECTED="SELECTED">${option}</option>
                <option py:if="option != order" value="${option}">${option}</option>
        </py:for>
    </select>
    <input id="go" type="submit" value="Search"/>
    </form>
    </div>
    <div class="navigation">
    <span style="display: block; text-align: center;">Books ${start} to ${ min((start+num-1) , total) } of ${total}</span>
    <table class="buttons">
    <tr>
    <td class="button" style="text-align:left;">
        <a py:if="start > 1" href="${url_base};start=1">First</a>
        <a py:if="start > 1" href="${url_base};start=${max(start-(num+1),1)}">Previous</a>
    </td>
    <td class="button" style="text-align: right;">
        <a py:if=" total > (start + num) " href="${url_base};start=${start+num}">Next</a>
        <a py:if=" total > (start + num) " href="${url_base};start=${total-num+1}">Last</a>
    </td>
    </tr>
    </table>
    </div>
    <hr class="spacer" />
    <table id="listing">
        <py:for each="book in books">
            ${Markup(book)}
        </py:for>
    </table>
</body>
</html>
''')

# }}}

class MobileServer(object):
    'A view optimized for browsers in mobile devices'

    MOBILE_UA = re.compile('(?i)(?:iPhone|Opera Mini|NetFront|webOS|Mobile|Android|imode|DoCoMo|Minimo|Blackberry|MIDP|Symbian|HD2)')

    @expose
    def mobile(self, start='1', num='25', sort='date', search='',
                _=None, order='descending'):
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
        ids = self.db.data.parse(search) if search and search.strip() else self.db.data.universal_set()
        ids = sorted(ids)
        FM = self.db.FIELD_MAP
        items = copy.deepcopy([r for r in iter(self.db) if r[FM['id']] in ids])
        if sort is not None:
            self.sort(items, sort, (order.lower().strip() == 'ascending'))

        book, books = MarkupTemplate(MOBILE_BOOK), []
        for record in items[(start-1):(start-1)+num]:
            if record[FM['formats']] is None:
                record[FM['formats']] = ''
            if record[FM['size']] is None:
                record[FM['size']] = 0
            aus = record[FM['authors']] if record[FM['authors']] else __builtin__._('Unknown')
            authors = '|'.join([i.replace('|', ',') for i in aus.split(',')])
            record[FM['series_index']] = \
                    fmt_sidx(float(record[FM['series_index']]))
            ts, pd = strftime('%Y/%m/%d %H:%M:%S', record[FM['timestamp']]), \
                strftime('%Y/%m/%d %H:%M:%S', record[FM['pubdate']])
            books.append(book.generate(r=record, authors=authors, timestamp=ts,
                pubdate=pd, FM=FM).render('xml').decode('utf-8'))
        updated = self.db.last_modified()

        cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)


        url_base = "/mobile?search=" + search+";order="+order+";sort="+sort+";num="+str(num)

        return MOBILE.generate(books=books, start=start, updated=updated,
                search=search, sort=sort, order=order, num=num, FM=FM,
                total=len(ids), url_base=url_base).render('html')


