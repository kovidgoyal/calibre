#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from functools import partial
from lxml.html import tostring
from lxml.html.builder import E as E_
from urllib import urlencode

from calibre import strftime
from calibre.constants import __appname__
from calibre.db.view import sanitize_sort_field_name
from calibre.ebooks.metadata import authors_to_string
from calibre.srv.content import get, book_filename
from calibre.srv.errors import HTTPRedirect, HTTPBadRequest
from calibre.srv.routes import endpoint
from calibre.srv.utils import get_library_data, http_date
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.date import timestampfromdt, dt_as_local, is_date_undefined

# /mobile {{{


def clean(x):
    if isinstance(x, basestring):
        x = clean_xml_chars(x)
    return x


def E(tag, *children, **attribs):
    children = list(map(clean, children))
    attribs = {k.rstrip('_').replace('_', '-'):clean(v) for k, v in attribs.iteritems()}
    return getattr(E_, tag)(*children, **attribs)


for tag in 'HTML HEAD TITLE LINK DIV IMG BODY OPTION SELECT INPUT FORM SPAN TABLE TR TD A HR META'.split():
    setattr(E, tag, partial(E, tag))
    tag = tag.lower()
    setattr(E, tag, partial(E, tag))


def html(ctx, rd, endpoint, output):
    rd.outheaders.set('Content-Type', 'text/html; charset=UTF-8', replace_all=True)
    if isinstance(output, bytes):
        ans = output  # Assume output is already UTF-8 encoded html
    else:
        ans = tostring(output, include_meta_content_type=True, pretty_print=True, encoding='utf-8', doctype='<!DOCTYPE html>', with_tail=False)
        if not isinstance(ans, bytes):
            ans = ans.encode('utf-8')
    return ans


def build_search_box(num, search, sort, order, ctx, field_metadata):  # {{{
    div = E.div(id='search_box')
    form = E.form(_('Show '), method='get', action=ctx.url_for('/mobile'))
    form.set('accept-charset', 'UTF-8')

    div.append(form)

    num_select = E.select(name='num')
    for option in (5, 10, 25, 100):
        kwargs = {'value':str(option)}
        if option == num:
            kwargs['SELECTED'] = 'SELECTED'
        num_select.append(E.option(str(option), **kwargs))
    num_select.tail = ' books matching '
    form.append(num_select)

    searchf = E.input(name='search', id='s', value=search if search else '')
    searchf.tail = _(' sorted by ')
    form.append(searchf)

    sort_select = E.select(name='sort')
    for option in ('date','author','title','rating','size','tags','series'):
        q = sanitize_sort_field_name(field_metadata, option)
        kwargs = {'value':option}
        if q == sanitize_sort_field_name(field_metadata, sort):
            kwargs['SELECTED'] = 'SELECTED'
        sort_select.append(E.option(option, **kwargs))
    form.append(sort_select)

    order_select = E.select(name='order')
    for option in ('ascending','descending'):
        kwargs = {'value':option}
        if option == order:
            kwargs['SELECTED'] = 'SELECTED'
        order_select.append(E.option(option, **kwargs))
    form.append(order_select)

    form.append(E.input(id='go', type='submit', value=_('Search')))

    return div
# }}}


def build_navigation(start, num, total, url_base):  # {{{
    end = min((start+num-1), total)
    tagline = E.span('Books %d to %d of %d'%(start, end, total),
            style='display: block; text-align: center;')
    left_buttons = E.td(class_='button', style='text-align:left')
    right_buttons = E.td(class_='button', style='text-align:right')

    if start > 1:
        for t,s in [('First', 1), ('Previous', max(start-num,1))]:
            left_buttons.append(E.a(t, href='%s&start=%d'%(url_base, s)))

    if total > start + num:
        for t,s in [('Next', start+num), ('Last', total-num+1)]:
            right_buttons.append(E.a(t, href='%s&start=%d'%(url_base, s)))

    buttons = E.table(
            E.tr(left_buttons, right_buttons),
            class_='buttons')
    return E.div(tagline, buttons, class_='navigation')

# }}}


def build_choose_library(ctx, library_map):
    select = E.select(name='library_id')
    for library_id, library_name in library_map.iteritems():
        select.append(E.option(library_name, value=library_id))
    return E.div(
        E.form(
            _('Change library to: '), select, ' ', E.input(type='submit', value=_('Change library')),
            method='GET', action=ctx.url_for('/mobile'), accept_charset='UTF-8'
        ),
        id='choose_library')


def build_index(rd, books, num, search, sort, order, start, total, url_base, field_metadata, ctx, library_map, library_id):  # {{{
    logo = E.div(E.img(src=ctx.url_for('/static', what='calibre.png'), alt=__appname__), id='logo')
    search_box = build_search_box(num, search, sort, order, ctx, field_metadata)
    navigation = build_navigation(start, num, total, url_base)
    navigation2 = build_navigation(start, num, total, url_base)
    if library_map:
        choose_library = build_choose_library(ctx, library_map)
    books_table = E.table(id='listing')

    body = E.body(
        logo,
        search_box,
        navigation,
        E.hr(class_='spacer'),
        books_table,
        E.hr(class_='spacer'),
        navigation2
    )

    for book in books:
        thumbnail = E.td(
                E.img(type='image/jpeg', border='0', src=ctx.url_for('/get', what='thumb', book_id=book.id, library_id=library_id),
                      class_='thumbnail')
        )

        data = E.td()
        for fmt in book.formats or ():
            if not fmt or fmt.lower().startswith('original_'):
                continue
            s = E.span(
                E.a(
                    fmt.lower(),
                    href=ctx.url_for('/legacy/get', what=fmt, book_id=book.id, library_id=library_id, filename=book_filename(rd, book.id, book, fmt))
                ),
                class_='button')
            s.tail = u''
            data.append(s)

        div = E.div(class_='data-container')
        data.append(div)

        series = ('[%s - %s]'%(book.series, book.series_index)) if book.series else ''
        tags = ('Tags=[%s]'%', '.join(book.tags)) if book.tags else ''

        ctext = ''
        for key in filter(ctx.is_field_displayable, field_metadata.ignorable_field_keys()):
            fm = field_metadata[key]
            if fm['datatype'] == 'comments':
                continue
            name, val = book.format_field(key)
            if val:
                ctext += '%s=[%s] '%(name, val)

        first = E.span(u'\u202f%s %s by %s' % (book.title, series,
            authors_to_string(book.authors)), class_='first-line')
        div.append(first)
        ds = '' if is_date_undefined(book.timestamp) else strftime('%d %b, %Y', t=dt_as_local(book.timestamp).timetuple())
        second = E.span(u'%s %s %s' % (ds, tags, ctext), class_='second-line')
        div.append(second)

        books_table.append(E.tr(thumbnail, data))

    if library_map:
        body.append(choose_library)
    body.append(E.div(
        E.a(_('Switch to the full interface (non-mobile interface)'),
            href=ctx.url_for(None),
            style="text-decoration: none; color: blue",
            title=_('The full interface gives you many more features, '
                    'but it may not work well on a small screen')),
        style="text-align:center")
    )
    return E.html(
        E.head(
            E.title(__appname__ + ' Library'),
            E.link(rel='icon', href=ctx.url_for('/favicon.png'), type='image/png'),
            E.link(rel='stylesheet', type='text/css', href=ctx.url_for('/static', what='mobile.css')),
            E.link(rel='apple-touch-icon', href=ctx.url_for("/static", what='calibre.png')),
            E.meta(name="robots", content="noindex")
        ),  # End head
        body
    )  # End html
# }}}


@endpoint('/mobile', postprocess=html)
def mobile(ctx, rd):
    db, library_id, library_map, default_library = get_library_data(ctx, rd)
    try:
        start = max(1, int(rd.query.get('start', 1)))
    except ValueError:
        raise HTTPBadRequest('start is not an integer')
    try:
        num = max(0, int(rd.query.get('num', 25)))
    except ValueError:
        raise HTTPBadRequest('num is not an integer')
    search = rd.query.get('search') or ''
    with db.safe_read_lock:
        book_ids = ctx.search(rd, db, search)
        total = len(book_ids)
        ascending = rd.query.get('order', '').lower().strip() == 'ascending'
        sort_by = sanitize_sort_field_name(db.field_metadata, rd.query.get('sort') or 'date')
        try:
            book_ids = db.multisort([(sort_by, ascending)], book_ids)
        except Exception:
            sort_by = 'date'
            book_ids = db.multisort([(sort_by, ascending)], book_ids)
        books = [db.get_metadata(book_id) for book_id in book_ids[(start-1):(start-1)+num]]
    rd.outheaders['Last-Modified'] = http_date(timestampfromdt(db.last_modified()))
    order = 'ascending' if ascending else 'descending'
    q = {b'search':search.encode('utf-8'), b'order':bytes(order), b'sort':sort_by.encode('utf-8'), b'num':bytes(num), 'library_id':library_id}
    url_base = ctx.url_for('/mobile') + '?' + urlencode(q)
    lm = {k:v for k, v in library_map.iteritems() if k != library_id}
    return build_index(rd, books, num, search, sort_by, order, start, total, url_base, db.field_metadata, ctx, lm, library_id)
# }}}


@endpoint('/browse/{+rest=""}')
def browse(ctx, rd, rest):
    raise HTTPRedirect(ctx.url_for(None))


@endpoint('/stanza/{+rest=""}')
def stanza(ctx, rd, rest):
    raise HTTPRedirect(ctx.url_for('/opds'))


@endpoint('/legacy/get/{what}/{book_id}/{library_id}/{+filename=""}', android_workaround=True)
def legacy_get(ctx, rd, what, book_id, library_id, filename):
    # See https://www.mobileread.com/forums/showthread.php?p=3531644 for why
    # this is needed for Kobo browsers
    return get(ctx, rd, what, book_id, library_id)
