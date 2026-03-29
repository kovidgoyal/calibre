#!/usr/bin/env python
# License: GPLv3 Copyright: 2026


from functools import partial
from urllib.parse import urlencode

from lxml.html import fragments_fromstring, tostring
from lxml.html.builder import E as E_

from calibre import strftime
from calibre.constants import __appname__
from calibre.db.view import sanitize_sort_field_name
from calibre.ebooks.metadata import authors_to_string
from calibre.srv.content import book_filename
from calibre.srv.errors import BookNotFound, HTTPBadRequest, HTTPRedirect
from calibre.srv.routes import endpoint
from calibre.srv.utils import get_library_data, http_date
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.date import dt_as_local, is_date_undefined, timestampfromdt
from calibre.utils.localization import _
from polyglot.builtins import as_bytes


def clean(x):
    if isinstance(x, (str, bytes)):
        x = clean_xml_chars(x)
    return x


def E(tag, *children, **attribs):
    children = list(map(clean, children))
    attribs = {k.rstrip('_').replace('_', '-'): clean(v) for k, v in attribs.items()}
    return getattr(E_, tag)(*children, **attribs)


for tag in '''
HTML HEAD TITLE LINK STYLE DIV SPAN P STRONG EM SMALL
BODY OPTION SELECT INPUT FORM TABLE THEAD TBODY TR TH TD
A HR META H1 H2 H3 UL LI IMG BR
'''.split():
    setattr(E, tag, partial(E, tag))
    setattr(E, tag.lower(), partial(E, tag))


def html(ctx, rd, endpoint, output):
    rd.outheaders.set('Content-Type', 'text/html; charset=UTF-8', replace_all=True)
    if isinstance(output, bytes):
        ans = output
    else:
        ans = tostring(
            output,
            include_meta_content_type=True,
            pretty_print=True,
            encoding='utf-8',
            doctype='<!DOCTYPE html>',
            with_tail=False
        )
        if not isinstance(ans, bytes):
            ans = ans.encode('utf-8')
    return ans


def safe_date(dt, fmt='%d %b %Y'):
    if not dt or is_date_undefined(dt):
        return ''
    return strftime(fmt, t=dt_as_local(dt).timetuple())


def query_val(rd, name, default=''):
    return rd.query.get(name) or default


def build_classic_url(ctx, library_id=None, **kwargs):
    q = {}
    for k, v in kwargs.items():
        if v not in (None, '', False):
            q[k] = v
    if library_id:
        q['library_id'] = library_id
    base = ctx.url_for('/classic')
    if q:
        return base + '?' + urlencode(q)
    return base


def build_book_url(ctx, book_id, library_id=None, **kwargs):
    q = {}
    for k, v in kwargs.items():
        if v not in (None, '', False):
            q[k] = v
    if library_id:
        q['library_id'] = library_id
    base = ctx.url_for('/classic/book', book_id=book_id)
    if q:
        return base + '?' + urlencode(q)
    return base


def inline_style():
    return '''
html, body {
    margin: 0;
    padding: 0;
    background: #f6f3e9;
    color: #1f2937;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 14px;
}
a { color: #1d4ed8; text-decoration: none; }
a:hover { text-decoration: underline; }
.page {
    max-width: 1360px;
    margin: 0 auto;
    padding: 16px;
}
.topbar {
    background: #ffffff;
    border: 1px solid #d1d5db;
    padding: 14px 18px;
    margin-bottom: 14px;
}
.brand {
    display: flex;
    align-items: center;
    gap: 14px;
}
.brand img {
    height: 40px;
}
.brand-title {
    font-size: 24px;
    font-weight: bold;
}
.brand-sub {
    color: #6b7280;
    margin-top: 2px;
}
.toolbar {
    background: #ffffff;
    border: 1px solid #d1d5db;
    padding: 14px 18px;
    margin-bottom: 14px;
}
.toolbar form {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
}
.toolbar input[type="text"], .toolbar select {
    padding: 6px 8px;
    border: 1px solid #cbd5e1;
    background: #fff;
}
.toolbar input[type="submit"] {
    padding: 7px 12px;
    border: 1px solid #2563eb;
    background: #2563eb;
    color: white;
    cursor: pointer;
}
.switch-links {
    margin-top: 10px;
    color: #4b5563;
}
.switch-links a {
    margin-right: 14px;
}
.navigation {
    background: #39322b;
    border: 1px solid #d1d5db;
    padding: 12px 18px;
    margin-bottom: 14px;
}
.navigation-inner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
}
.button-row a {
    display: inline-block;
    margin-left: 8px;
    padding: 6px 10px;
    border: 1px solid #cbd5e1;
    background: #f8fafc;
}
.listing {
    width: 100%;
    border-collapse: collapse;
    background: #ffffff;
    border: 1px solid #d1d5db;
}
.listing tr {
    border-top: 1px solid #e5e7eb;
}
.listing td {
    vertical-align: top;
    padding: 14px;
}
.thumb-cell {
    width: 110px;
}
.thumb-link {
    display: inline-block;
}
.thumbnail {
    width: 90px;
    height: auto;
    border: 1px solid #cbd5e1;
    background: #fff;
}
.book-title {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 6px;
}
.book-title a {
    color: #111827;
}
.book-title a:hover {
    color: #1d4ed8;
}
.meta-line {
    color: #374151;
    margin-bottom: 6px;
}
.count {
    color: #ffffff;
}
.secondary {
    color: #6b7280;
}
.format-row {
    margin-top: 10px;
}
a.calibre-push-button {
    border-radius: 1em;
    background-clip: padding-box;
    background-color: #39322b;
    background-image: linear-gradient(to bottom, #39322b, #d9d9d9);
    padding: 0.5ex 1em;
    color: #fff;
    cursor: pointer;
    font-size: inherit;
    display: inline-flex;
    align-items: center;
    user-select: none;
    box-shadow: 0px 2px 1px rgba(50, 50, 50, 0.75);
    white-space: nowrap;
}
a.calibre-push-button:hover {
    transform: scale(1.05);
    text-decoration: none;
}

a.calibre-push-button:active {
    transform: scale(1.1);
}

a.calibre-push-button:visited {
    color: #fff;
}
.format-pill {
    display: inline-block;
    margin-right: 8px;
    margin-bottom: 6px;
    padding: 5px 8px;
    border: 1px solid #cbd5e1;
    background: #f8fafc;
}
.library-box {
    background: #ffffff;
    border: 1px solid #d1d5db;
    padding: 12px 18px;
    margin-top: 14px;
}
.library-box form {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
}
.details-layout {
    display: table;
    width: 100%;
    border-collapse: separate;
    border-spacing: 18px 0;
}
.details-left, .details-right {
    display: table-cell;
    vertical-align: top;
}
.details-left {
    width: 240px;
}
.cover-large {
    width: 300px;
    max-width: 100%;
    height: auto;
    border: 1px solid #cbd5e1;
    background: #fff;
}
.panel {
    background: #ffffff;
    border: 1px solid #d1d5db;
    padding: 18px;
    margin-bottom: 14px;
}
.details-title {
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 8px;
}
.details-authors {
    font-size: 16px;
    margin-bottom: 10px;
}
.details-table {
    width: 100%;
    border-collapse: collapse;
}
.details-table th, .details-table td {
    text-align: left;
    vertical-align: top;
    padding: 8px 6px;
    border-top: 1px solid #e5e7eb;
}
.details-table th {
    width: 180px;
    color: #374151;
}
.comments {
    line-height: 1.55;
}
.comments div {
    margin: 0;
    padding: 0;
}
.comments p {
    margin: 0 0 0.9em 0;
    padding: 0;
}
.comments p:last-child {
    margin-bottom: 0;
}
.back-links a {
    margin-right: 14px;
}
.footer-space {
    height: 12px;
}
'''


def build_search_box(num, search, sort, order, ctx, field_metadata, library_id, view_mode='list'):
    form = E.form(method='get', action=ctx.url_for('/classic'))
    form.set('accept-charset', 'UTF-8')

    num_select = E.select(name='num')
    for option in (10, 25, 50, 100):
        kwargs = {'value': str(option)}
        if option == num:
            kwargs['selected'] = 'selected'
        num_select.append(E.option(str(option), **kwargs))

    searchf = E.input(type='text', name='search', value=search or '', size='32')

    sort_select = E.select(name='sort')
    for option in ('date', 'author', 'title', 'rating', 'size', 'tags', 'series'):
        q = sanitize_sort_field_name(field_metadata, option)
        kwargs = {'value': option}
        if q == sanitize_sort_field_name(field_metadata, sort):
            kwargs['selected'] = 'selected'
        sort_select.append(E.option(option, **kwargs))

    order_select = E.select(name='order')
    for option in ('ascending', 'descending'):
        kwargs = {'value': option}
        if option == order:
            kwargs['selected'] = 'selected'
        order_select.append(E.option(option, **kwargs))

    view_select = E.select(name='view')
    for option in ('list', 'compact'):
        kwargs = {'value': option}
        if option == view_mode:
            kwargs['selected'] = 'selected'
        view_select.append(E.option(option.title(), **kwargs))

    form.append(E.span(_('Show ')))
    form.append(num_select)
    form.append(E.span(_(' books matching ')))
    form.append(searchf)
    form.append(E.span(_(' sorted by ')))
    form.append(sort_select)
    form.append(order_select)
    form.append(E.span(_(' view ')))
    form.append(view_select)

    if library_id:
        form.append(E.input(name='library_id', type='hidden', value=library_id))

    form.append(E.input(type='submit', value=_('Search')))
    return form


def build_navigation(start, num, total, url_base):
    if total < 1:
        tagline = 'Books 0 to 0 of 0'
    else:
        end = min((start + num - 1), total)
        tagline = f'Books {start} to {end} of {total}'

    left = E.span(tagline, class_='count')
    right = E.span(class_='button-row')

    if start > 1:
        for text, pos in (('First', 1), ('Previous', max(start - num, 1))):
            right.append(E.a(text, href=f'{url_base}&start={pos}'))

    if total > start + num - 1:
        for text, pos in (('Next', start + num), ('Last', max(total - num + 1, 1))):
            right.append(E.a(text, href=f'{url_base}&start={pos}'))

    return E.div(
        E.div(left, right, class_='navigation-inner'),
        class_='navigation'
    )


def build_choose_library(ctx, library_map):
    select = E.select(name='library_id')
    for library_id, library_name in library_map.items():
        select.append(E.option(library_name, value=library_id))
    return E.div(
        E.form(
            _('Change library to: '),
            select,
            E.input(type='submit', value=_('Change library')),
            method='get',
            action=ctx.url_for('/classic'),
            accept_charset='UTF-8'
        ),
        class_='library-box'
    )


def field_text(book, key):
    try:
        name, val = book.format_field(key)
    except Exception:
        return '', ''
    return name or '', val or ''

def build_author_search_url(ctx, author, library_id=None):
    return build_classic_url(
        ctx,
        library_id=library_id,
        search=f'authors:"{author}"'
    )

def build_book_row(ctx, rd, book, field_metadata, library_id, search, sort, order, num, start, view_mode):
    details_url = build_book_url(
        ctx, book.id, library_id=library_id,
        search=search, sort=sort, order=order, num=num, start=start, view=view_mode
    )
    thumb_url = ctx.url_for('/get', what='cover', book_id=book.id, library_id=library_id)

    thumbnail = E.td(
        E.a(
            E.img(
                type='image/jpeg',
                border='0',
                src=thumb_url,
                class_='thumbnail',
                alt=book.title or _('Cover')
            ),
            href=details_url,
            class_='thumb-link'
        ),
        class_='thumb-cell'
    )

    data = E.td()

    title = book.title or _('Unknown title')
    authors = authors_to_string(book.authors) if book.authors else _('Unknown author')
    title_line = E.div(
        E.a(title, href=details_url),
        class_='book-title'
    )
    data.append(title_line)

    series = ''
    if getattr(book, 'series', None):
        series = f'{book.series} [{book.series_index}]'

    pubdate = safe_date(getattr(book, 'pubdate', None))
    added = safe_date(getattr(book, 'timestamp', None))

    meta1 = f'by {authors}'
    if series:
        meta1 += f' • Series: {series}'
    data.append(E.div(meta1, class_='meta-line'))

    meta2_parts = []
    if added:
        meta2_parts.append(f'Added: {added}')
    if pubdate:
        meta2_parts.append(f'Published: {pubdate}')
    if getattr(book, 'publisher', None):
        meta2_parts.append(f'Publisher: {book.publisher}')
    if getattr(book, 'rating', None):
        try:
            if int(book.rating) > 0:
                meta2_parts.append(f'Rating: {book.rating}')
        except Exception:
            pass
    if getattr(book, 'tags', None):
        meta2_parts.append('Tags: ' + ', '.join(book.tags))

    if meta2_parts:
        data.append(E.div(' • '.join(meta2_parts), class_='meta-line secondary'))

    if view_mode != 'compact':
        extra = []
        for key in filter(ctx.is_field_displayable, field_metadata.ignorable_field_keys()):
            fm = field_metadata[key]
            if fm['datatype'] == 'comments':
                continue
            name, val = field_text(book, key)
            if val:
                extra.append(f'{name}: {val}')
        if extra:
            data.append(E.div(' | '.join(extra), class_='meta-line secondary'))

    fmt_row = E.div(class_='format-row')
    for fmt in book.formats or ():
        if not fmt or fmt.lower().startswith('original_'):
            continue
        fmt_row.append(
            E.a(
                fmt.lower(),
                href=ctx.url_for(
                    '/legacy/get',
                    what=fmt,
                    book_id=book.id,
                    library_id=library_id,
                    filename=book_filename(rd, book.id, book, fmt)
                ),
                class_='calibre-push-button'
            )
        )
    fmt_row.append(E.a(_('Details'), href=details_url, class_='calibre-push-button'))
    data.append(fmt_row)

    return E.tr(thumbnail, data)


def build_index(rd, books, num, search, sort, order, start, total, url_base, field_metadata, ctx, library_map, library_id, view_mode='list'):
    logo = E.div(
        E.div(
            E.img(src=ctx.url_for('/static', what='calibre.png'), alt=__appname__),
            E.div(
                E.div(__appname__ + ' Library', class_='brand-title'),
                E.div(_('Classic interface'), class_='brand-sub')
            ),
            class_='brand'
        ),
        class_='topbar'
    )

    toolbar = E.div(
        build_search_box(num, search, sort, order, ctx, field_metadata, library_id, view_mode),
        E.div(
            E.a(_('Switch to mobile interface'), href=ctx.url_for('/mobile')),
            E.a(_('Switch to full modern interface'), href=ctx.url_for(None)),
            class_='switch-links'
        ),
        class_='toolbar'
    )

    navigation1 = build_navigation(start, num, total, url_base)
    navigation2 = build_navigation(start, num, total, url_base)

    books_table = E.table(class_='listing')
    for book in books:
        books_table.append(
            build_book_row(ctx, rd, book, field_metadata, library_id, search, sort, order, num, start, view_mode)
        )

    page = E.div(
        logo,
        toolbar,
        navigation1,
        books_table,
        navigation2,
        class_='page'
    )

    if library_map:
        page.append(build_choose_library(ctx, library_map))

    page.append(E.div(class_='footer-space'))

    return E.html(
        E.head(
            E.title(__appname__ + ' Classic Library'),
            E.meta(name='robots', content='noindex'),
            E.link(rel='icon', href=ctx.url_for('/favicon.png'), type='image/png'),
            E.link(rel='apple-touch-icon', href=ctx.url_for('/static', what='calibre.png')),
            E.style(inline_style(), type='text/css')
        ),
        E.body(page)
    )


def add_detail_row(table, label, value):
    if value in (None, '', (), []):
        return
    table.append(E.tr(E.th(label), E.td(value)))

def render_comments_block(raw_comments):
    if not raw_comments:
        return E.div('', class_='comments')

    if isinstance(raw_comments, bytes):
        try:
            raw_comments = raw_comments.decode('utf-8', 'replace')
        except Exception:
            raw_comments = ''
    else:
        raw_comments = str(raw_comments or '')

    container = E.div(class_='comments')

    try:
        fragments = fragments_fromstring(raw_comments)
        for frag in fragments:
            if isinstance(frag, str):
                text = frag.strip()
                if text:
                    container.append(E.p(text))
            else:
                container.append(frag)
    except Exception:
        text = raw_comments.strip()
        if text:
            container.append(E.p(text))

    return container

def build_author_search_url(ctx, author, library_id=None):
    return build_classic_url(
        ctx,
        library_id=library_id,
        search=f'authors:"{author}"'
    )

def build_details_page(ctx, rd, book, library_id, search, sort, order, num, start, view_mode):
    back_url = build_classic_url(
        ctx, library_id=library_id,
        search=search, sort=sort, order=order, num=num, start=start, view=view_mode
    )
    cover_url = ctx.url_for('/get', what='cover', book_id=book.id, library_id=library_id)

    authors = authors_to_string(book.authors) if book.authors else _('Unknown author')
    title = book.title or _('Unknown title')
    series = ''
    if getattr(book, 'series', None):
        series = f'{book.series} [{book.series_index}]'

    formats_box = E.div()
    has_formats = False
    for fmt in book.formats or ():
        if not fmt or fmt.lower().startswith('original_'):
            continue
        has_formats = True
        formats_box.append(
            E.a(
                fmt.lower(),
                href=ctx.url_for(
                    '/legacy/get',
                    what=fmt,
                    book_id=book.id,
                    library_id=library_id,
                    filename=book_filename(rd, book.id, book, fmt)
                ),
                class_='calibre-push-button'
            )
        )
    if not has_formats:
        formats_box.append(E.span(_('No downloadable formats available'), class_='secondary'))

    info = E.table(class_='details-table')
    add_detail_row(info, _('Title'), title)
    add_detail_row(info, _('Authors'), authors)
    add_detail_row(info, _('Series'), series)
    add_detail_row(info, _('Publisher'), getattr(book, 'publisher', '') or '')
    add_detail_row(info, _('Published'), safe_date(getattr(book, 'pubdate', None)))
    add_detail_row(info, _('Added'), safe_date(getattr(book, 'timestamp', None)))
    add_detail_row(info, _('Last modified'), safe_date(getattr(book, 'last_modified', None)))
    add_detail_row(info, _('Languages'), ', '.join(getattr(book, 'languages', ()) or ()))
    add_detail_row(info, _('Tags'), ', '.join(getattr(book, 'tags', ()) or ()))
    add_detail_row(info, _('Formats'), formats_box)

    identifiers = getattr(book, 'identifiers', None) or {}
    if identifiers:
        add_detail_row(
            info,
            _('Identifiers'),
            ' | '.join(f'{k}: {v}' for k, v in sorted(identifiers.items()))
        )

    comments_val = getattr(book, 'comments', None) or ''
    comments_block = render_comments_block(comments_val)

    details_right = E.div(
        E.div(
            E.div(title, class_='details-title'),
            E.div(authors, class_='details-authors'),
            E.div(
                E.a(_('Back to classic list'), href=back_url),
                E.a(_('Mobile interface'), href=ctx.url_for('/mobile')),
                E.a(_('Classic interface'), href=ctx.url_for(None)),
                class_='back-links'
            ),
            class_='panel'
        ),
        E.div(info, class_='panel'),
        class_='details-right'
    )

    if comments_val:
        details_right.append(
            E.div(
                comments_block,
                class_='panel'
            )
        )

    details_left = E.div(
        E.div(
            E.img(
                src=cover_url,
                class_='cover-large',
                alt=title
            ),
            E.div(class_='format-row'),
            class_='panel'
        ),
        class_='details-left'
    )

    layout = E.div(
        details_left,
        details_right,
        class_='details-layout'
    )

    page = E.div(
        E.div(
            E.div(
                E.img(src=ctx.url_for('/static', what='calibre.png'), alt=__appname__),
                E.div(
                    E.div(__appname__ + ' Library', class_='brand-title'),
                    E.div(_('Classic interface'), class_='brand-sub')
                ),
                class_='brand'
            ),
            class_='topbar'
        ),
        E.div(layout, class_='page')
    )

    return E.html(
        E.head(
            E.title(f'{title} - {__appname__}'),
            E.meta(name='robots', content='noindex'),
            E.link(rel='icon', href=ctx.url_for('/favicon.png'), type='image/png'),
            E.link(rel='apple-touch-icon', href=ctx.url_for('/static', what='calibre.png')),
            E.style(inline_style(), type='text/css')
        ),
        E.body(page)
    )


@endpoint('/classic', postprocess=html)
def classic(ctx, rd):
    db, library_id, library_map, default_library = get_library_data(ctx, rd)

    try:
        start = max(1, int(rd.query.get('start', 1)))
    except ValueError:
        raise HTTPBadRequest('start is not an integer')

    try:
        num = max(1, int(rd.query.get('num', 25)))
    except ValueError:
        raise HTTPBadRequest('num is not an integer')

    search = query_val(rd, 'search', '')
    view_mode = query_val(rd, 'view', 'list')
    if view_mode not in ('list', 'compact'):
        view_mode = 'list'

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
        books = [db.get_metadata(book_id) for book_id in book_ids[(start - 1):(start - 1) + num]]

    rd.outheaders['Last-Modified'] = http_date(timestampfromdt(db.last_modified()))
    order = 'ascending' if ascending else 'descending'

    q = {
        b'search': search.encode('utf-8'),
        b'order': order.encode('ascii'),
        b'sort': sort_by.encode('utf-8'),
        b'num': as_bytes(num),
        b'view': view_mode.encode('utf-8'),
        'library_id': library_id,
    }
    url_base = ctx.url_for('/classic') + '?' + urlencode(q)
    lm = {k: v for k, v in library_map.items() if k != library_id}

    return build_index(
        rd, books, num, search, sort_by, order, start, total,
        url_base, db.field_metadata, ctx, lm, library_id, view_mode
    )


@endpoint('/classic/book/{book_id}', postprocess=html)
def classic_book(ctx, rd, book_id):
    db, library_id, library_map, default_library = get_library_data(ctx, rd)

    try:
        book_id = int(book_id)
    except Exception:
        raise HTTPRedirect(ctx.url_for('/classic'))

    search = query_val(rd, 'search', '')
    sort_by = query_val(rd, 'sort', 'date')
    order = query_val(rd, 'order', 'descending')
    view_mode = query_val(rd, 'view', 'list')

    try:
        num = max(1, int(rd.query.get('num', 25)))
    except Exception:
        num = 25

    try:
        start = max(1, int(rd.query.get('start', 1)))
    except Exception:
        start = 1

    with db.safe_read_lock:
        if not ctx.has_id(rd, db, book_id):
            raise BookNotFound(book_id, db)
        book = db.get_metadata(book_id)

    rd.outheaders['Last-Modified'] = http_date(timestampfromdt(db.last_modified()))
    return build_details_page(ctx, rd, book, library_id, search, sort_by, order, num, start, view_mode)


@endpoint('/classic/browse/{+rest=""}')
def classic_browse(ctx, rd, rest):
    if rest.startswith('book/'):
        try:
            book_id = int(rest[5:])
        except Exception:
            raise HTTPRedirect(ctx.url_for('/classic'))
        raise HTTPRedirect(ctx.url_for('/classic/book', book_id=book_id))
    raise HTTPRedirect(ctx.url_for('/classic'))