#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os
import __builtin__
from urllib import quote

import cherrypy
from lxml import html
from lxml.html.builder import HTML, HEAD, TITLE, LINK, DIV, IMG, BODY, \
        OPTION, SELECT, INPUT, FORM, SPAN, TABLE, TR, TD, A, HR

from calibre.library.server import custom_fields_to_display
from calibre.library.server.utils import strftime, format_tag_string
from calibre.ebooks.metadata import fmt_sidx
from calibre.constants import __appname__
from calibre import human_readable, isbytestring
from calibre.utils.date import utcfromtimestamp
from calibre.utils.filenames import ascii_filename
from calibre.utils.icu import sort_key

def CLASS(*args, **kwargs): # class is a reserved word in Python
    kwargs['class'] = ' '.join(args)
    return kwargs


def build_search_box(num, search, sort, order, prefix): # {{{
    div = DIV(id='search_box')
    form = FORM('Show ', method='get', action=prefix+'/mobile')
    form.set('accept-charset', 'UTF-8')

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
        for t,s in [('First', 1), ('Previous', max(start-num,1))]:
            left_buttons.append(A(t, href='%s;start=%d'%(url_base, s)))

    if total > start + num:
        for t,s in [('Next', start+num), ('Last', total-num+1)]:
            right_buttons.append(A(t, href='%s;start=%d'%(url_base, s)))

    buttons = TABLE(
            TR(left_buttons, right_buttons),
            CLASS('buttons'))
    return DIV(tagline, buttons, CLASS('navigation'))

    # }}}

def build_index(books, num, search, sort, order, start, total, url_base, CKEYS,
        prefix):
    logo = DIV(IMG(src=prefix+'/static/calibre.png', alt=__appname__), id='logo')

    search_box = build_search_box(num, search, sort, order, prefix)
    navigation = build_navigation(start, num, total, prefix+url_base)
    navigation2 = build_navigation(start, num, total, prefix+url_base)
    bookt = TABLE(id='listing')

    body = BODY(
        logo,
        search_box,
        navigation,
        HR(CLASS('spacer')),
        bookt,
        HR(CLASS('spacer')),
        navigation2
    )

    # Book list {{{
    for book in books:
        thumbnail = TD(
                IMG(type='image/jpeg', border='0',
                    src=prefix+'/get/thumb/%s' %
                            book['id']),
                CLASS('thumbnail'))

        data = TD()
        for fmt in book['formats'].split(','):
            if not fmt or fmt.lower().startswith('original_'):
                continue
            a = quote(ascii_filename(book['authors']))
            t = quote(ascii_filename(book['title']))
            s = SPAN(
                A(
                    fmt.lower(),
                    href=prefix+'/get/%s/%s-%s_%d.%s' % (fmt, a, t,
                        book['id'], fmt.lower())
                ),
                CLASS('button'))
            s.tail = u''
            data.append(s)

        div = DIV(CLASS('data-container'))
        data.append(div)

        series = u'[%s - %s]'%(book['series'], book['series_index']) \
                if book['series'] else ''
        tags = u'Tags=[%s]'%book['tags'] if book['tags'] else ''

        ctext = ''
        for key in CKEYS:
            val = book.get(key, None)
            if val:
                ctext += '%s=[%s] '%tuple(val.split(':#:'))

        first = SPAN(u'\u202f%s %s by %s' % (book['title'], series,
            book['authors']), CLASS('first-line'))
        div.append(first)
        second = SPAN(u'%s - %s %s %s' % ( book['size'],
            book['timestamp'],
            tags, ctext), CLASS('second-line'))
        div.append(second)

        bookt.append(TR(thumbnail, data))
    # }}}

    body.append(DIV(
        A(_('Switch to the full interface (non-mobile interface)'),
            href=prefix+"/browse",
            style="text-decoration: none; color: blue",
            title=_('The full interface gives you many more features, '
                'but it may not work well on a small screen')),
        style="text-align:center"))
    return HTML(
        HEAD(
            TITLE(__appname__ + ' Library'),
            LINK(rel='icon', href='http://calibre-ebook.com/favicon.ico',
                type='image/x-icon'),
            LINK(rel='stylesheet', type='text/css',
                href=prefix+'/mobile/style.css'),
            LINK(rel='apple-touch-icon', href="/static/calibre.png")
        ), # End head
        body
    ) # End html


class MobileServer(object):
    'A view optimized for browsers in mobile devices'

    MOBILE_UA = re.compile('(?i)(?:iPhone|Opera Mini|NetFront|webOS|Mobile|Android|imode|DoCoMo|Minimo|Blackberry|MIDP|Symbian|HD2|Kindle)')

    def is_mobile_browser(self, ua):
        match = self.MOBILE_UA.search(ua)
        return match is not None and 'iPad' not in ua

    def add_routes(self, connect):
        connect('mobile', '/mobile', self.mobile)
        connect('mobile_css', '/mobile/style.css', self.mobile_css)

    def mobile_css(self, *args, **kwargs):
        path = P('content_server/mobile.css')
        cherrypy.response.headers['Content-Type'] = 'text/css; charset=utf-8'
        updated = utcfromtimestamp(os.stat(path).st_mtime)
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        with open(path, 'rb') as f:
            ans = f.read()
        return ans.replace('{prefix}', self.opts.url_prefix)

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
        if isbytestring(search):
            search = search.decode('UTF-8')
        ids = self.db.search_getting_ids(search.strip(), self.search_restriction)
        FM = self.db.FIELD_MAP
        items = [r for r in iter(self.db) if r[FM['id']] in ids]
        if sort is not None:
            self.sort(items, sort, (order.lower().strip() == 'ascending'))

        CFM = self.db.field_metadata
        CKEYS = [key for key in sorted(custom_fields_to_display(self.db),
                                       key=lambda x:sort_key(CFM[x]['name']))]
        # This method uses its own book dict, not the Metadata dict. The loop
        # below could be changed to use db.get_metadata instead of reading
        # info directly from the record made by the view, but it doesn't seem
        # worth it at the moment.
        books = []
        for record in items[(start-1):(start-1)+num]:
            book = {'formats':record[FM['formats']], 'size':record[FM['size']]}
            if not book['formats']:
                book['formats'] = ''
            if not book['size']:
                book['size'] = 0
            book['size'] = human_readable(book['size'])

            aus = record[FM['authors']] if record[FM['authors']] else __builtin__._('Unknown')
            aut_is = CFM['authors']['is_multiple']
            authors = aut_is['list_to_ui'].join([i.replace('|', ',') for i in aus.split(',')])
            book['authors'] = authors
            book['series_index'] = fmt_sidx(float(record[FM['series_index']]))
            book['series'] = record[FM['series']]
            book['tags'] = format_tag_string(record[FM['tags']], ',',
                                             no_tag_count=True)
            book['title'] = record[FM['title']]
            for x in ('timestamp', 'pubdate'):
                book[x] = strftime('%d %b, %Y', record[FM[x]])
            book['id'] = record[FM['id']]
            books.append(book)
            for key in CKEYS:
                def concat(name, val):
                    return '%s:#:%s'%(name, unicode(val))
                mi = self.db.get_metadata(record[CFM['id']['rec_index']], index_is_id=True)
                name, val = mi.format_field(key)
                if not val:
                    continue
                datatype = CFM[key]['datatype']
                if datatype in ['comments']:
                    continue
                if datatype == 'text' and CFM[key]['is_multiple']:
                    book[key] = concat(name,
                                       format_tag_string(val,
                                           CFM[key]['is_multiple']['ui_to_list'],
                                           no_tag_count=True,
                                           joinval=CFM[key]['is_multiple']['list_to_ui']))
                else:
                    book[key] = concat(name, val)

        updated = self.db.last_modified()

        cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)

        url_base = "/mobile?search=" + search+";order="+order+";sort="+sort+";num="+str(num)

        raw = html.tostring(build_index(books, num, search, sort, order,
                             start, len(ids), url_base, CKEYS,
                             self.opts.url_prefix),
                             encoding='utf-8',
                             pretty_print=True)
        # tostring's include_meta_content_type is broken
        raw = raw.replace('<head>', '<head>\n'
                '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">')
        return raw

