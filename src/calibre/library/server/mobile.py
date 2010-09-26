#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os
import __builtin__

import cherrypy
from lxml import html
from lxml.html.builder import HTML, HEAD, TITLE, LINK, DIV, IMG, BODY, \
        OPTION, SELECT, INPUT, FORM, SPAN, TABLE, TR, TD, A, HR

from calibre.library.server.utils import strftime, format_tag_string
from calibre.ebooks.metadata import fmt_sidx
from calibre.constants import __appname__
from calibre import human_readable
from calibre.utils.date import utcfromtimestamp, format_date
from calibre.utils.filenames import ascii_filename

def CLASS(*args, **kwargs): # class is a reserved word in Python
    kwargs['class'] = ' '.join(args)
    return kwargs


def build_search_box(num, search, sort, order): # {{{
    div = DIV(id='search_box')
    form = FORM('Show ', method='get', action='mobile')
    div.append(form)

    num_select = SELECT(name='num')
    for option in (5, 10, 25, 100):
        kwargs = {'value':str(option)}
        if option == num:
            kwargs['SELECTED'] = 'SELECTED'
        num_select.append(OPTION(str(option), **kwargs))
    num_select.tail = ' books matching '
    form.append(num_select)

    searchf = INPUT(name='search', id='s', value=search if search else '')
    searchf.tail = ' sorted by '
    form.append(searchf)

    sort_select = SELECT(name='sort')
    for option in ('date','author','title','rating','size','tags','series'):
        kwargs = {'value':option}
        if option == sort:
            kwargs['SELECTED'] = 'SELECTED'
        sort_select.append(OPTION(option, **kwargs))
    form.append(sort_select)

    order_select = SELECT(name='order')
    for option in ('ascending','descending'):
        kwargs = {'value':option}
        if option == order:
            kwargs['SELECTED'] = 'SELECTED'
        order_select.append(OPTION(option, **kwargs))
    form.append(order_select)

    form.append(INPUT(id='go', type='submit', value='Search'))

    return div
    # }}}

def build_navigation(start, num, total, url_base): # {{{
    end = min((start+num-1), total)
    tagline = SPAN('Books %d to %d of %d'%(start, end, total),
            style='display: block; text-align: center;')
    left_buttons = TD(CLASS('button', style='text-align:left'))
    right_buttons = TD(CLASS('button', style='text-align:right'))

    if start > 1:
        for t,s in [('First', 1), ('Previous', max(start-(num+1),1))]:
            left_buttons.append(A(t, href='%s;start=%d'%(url_base, s)))

    if total > start + num:
        for t,s in [('Next', start+num), ('Last', total-num+1)]:
            right_buttons.append(A(t, href='%s;start=%d'%(url_base, s)))

    buttons = TABLE(
            TR(left_buttons, right_buttons),
            CLASS('buttons'))
    return DIV(tagline, buttons, CLASS('navigation'))

    # }}}

def build_index(books, num, search, sort, order, start, total, url_base, CKEYS):
    logo = DIV(IMG(src='/static/calibre.png', alt=__appname__), id='logo')

    search_box = build_search_box(num, search, sort, order)
    navigation = build_navigation(start, num, total, url_base)
    bookt = TABLE(id='listing')

    body = BODY(
        logo,
        search_box,
        navigation,
        HR(CLASS('spacer')),
        bookt
    )

    # Book list {{{
    for book in books:
        thumbnail = TD(
                IMG(type='image/jpeg', border='0', src='/get/thumb/%s' %
                            book['id']),
                CLASS('thumbnail'))

        data = TD()
        last = None
        for fmt in book['formats'].split(','):
            a = ascii_filename(book['authors'])
            t = ascii_filename(book['title'])
            s = SPAN(
                A(
                    fmt.lower(),
                    href='/get/%s/%s-%s_%d.%s' % (fmt, a, t,
                        book['id'], fmt)
                ),
                CLASS('button'))
            s.tail = u'\u202f' # &nbsp;
            last = s
            data.append(s)

        series = u'[%s - %s]'%(book['series'], book['series_index']) \
                if book['series'] else ''
        tags = u'Tags=[%s]'%book['tags'] if book['tags'] else ''

        ctext = ''
        for key in CKEYS:
            val = book.get(key, None)
            if val:
                ctext += '%s=[%s] '%tuple(val.split(':#:'))

        text = u'\u202f%s %s by %s - %s - %s %s %s' % (book['title'], series,
                book['authors'], book['size'], book['timestamp'], tags, ctext)

        if last is None:
            data.text = text
        else:
            last.tail += text

        bookt.append(TR(thumbnail, data))
    # }}}

    return HTML(
        HEAD(
            TITLE(__appname__ + ' Library'),
            LINK(rel='icon', href='http://calibre-ebook.com/favicon.ico',
                type='image/x-icon'),
            LINK(rel='stylesheet', type='text/css', href='/mobile/style.css')
        ), # End head
        body
    ) # End html


class MobileServer(object):
    'A view optimized for browsers in mobile devices'

    MOBILE_UA = re.compile('(?i)(?:iPhone|Opera Mini|NetFront|webOS|Mobile|Android|imode|DoCoMo|Minimo|Blackberry|MIDP|Symbian|HD2|Kindle)')

    def add_routes(self, connect):
        connect('mobile', '/mobile', self.mobile)
        connect('mobile_css', '/mobile/style.css', self.mobile_css)

    def mobile_css(self, *args, **kwargs):
        path = P('content_server/mobile.css')
        cherrypy.response.headers['Content-Type'] = 'text/css; charset=utf-8'
        updated = utcfromtimestamp(os.stat(path).st_mtime)
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        return open(path, 'rb').read()

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
        if not search:
            search = ''
        ids = self.db.search_getting_ids(search.strip(), self.search_restriction)
        FM = self.db.FIELD_MAP
        items = [r for r in iter(self.db) if r[FM['id']] in ids]
        if sort is not None:
            self.sort(items, sort, (order.lower().strip() == 'ascending'))

        CFM = self.db.field_metadata
        CKEYS = [key for key in sorted(CFM.get_custom_fields(),
             cmp=lambda x,y: cmp(CFM[x]['name'].lower(),
                                 CFM[y]['name'].lower()))]
        books = []
        for record in items[(start-1):(start-1)+num]:
            book = {'formats':record[FM['formats']], 'size':record[FM['size']]}
            if not book['formats']:
                book['formats'] = ''
            if not book['size']:
                book['size'] = 0
            book['size'] = human_readable(book['size'])

            aus = record[FM['authors']] if record[FM['authors']] else __builtin__._('Unknown')
            authors = '|'.join([i.replace('|', ',') for i in aus.split(',')])
            book['authors'] = authors
            book['series_index'] = fmt_sidx(float(record[FM['series_index']]))
            book['series'] = record[FM['series']]
            book['tags'] = format_tag_string(record[FM['tags']], ',')
            book['title'] = record[FM['title']]
            for x in ('timestamp', 'pubdate'):
                book[x] = strftime('%Y/%m/%d %H:%M:%S', record[FM[x]])
            book['id'] = record[FM['id']]
            books.append(book)
            for key in CKEYS:
                def concat(name, val):
                    return '%s:#:%s'%(name, unicode(val))
                val = record[CFM[key]['rec_index']]
                if val:
                    datatype = CFM[key]['datatype']
                    if datatype in ['comments']:
                        continue
                    name = CFM[key]['name']
                    if datatype == 'text' and CFM[key]['is_multiple']:
                        book[key] = concat(name, format_tag_string(val, '|'))
                    elif datatype == 'series':
                        book[key] = concat(name, '%s [%s]'%(val,
                            fmt_sidx(record[CFM.cc_series_index_column_for(key)])))
                    elif datatype == 'datetime':
                        book[key] = concat(name,
                            format_date(val, CFM[key]['display'].get('date_format','dd MMM yyyy')))
                    elif datatype == 'bool':
                        if val:
                            book[key] = concat(name, __builtin__._('Yes'))
                        else:
                            book[key] = concat(name, __builtin__._('No'))
                    else:
                        book[key] = concat(name, val)

        updated = self.db.last_modified()

        cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)


        url_base = "/mobile?search=" + search+";order="+order+";sort="+sort+";num="+str(num)

        return html.tostring(build_index(books, num, search, sort, order,
                             start, len(ids), url_base, CKEYS),
                             encoding='utf-8', include_meta_content_type=True,
                             pretty_print=True)

