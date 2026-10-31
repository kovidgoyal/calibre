#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache, partial
from typing import Any, NamedTuple, cast
from urllib.parse import urlencode

from html5_parser import parse
from lxml import etree
from lxml.builder import ElementMaker

from calibre import force_unicode, guess_type
from calibre import prepare_string_for_xml as xml
from calibre.constants import __appname__
from calibre.db import FTSQueryError
from calibre.db.cache import Cache
from calibre.db.categories import Tag
from calibre.db.view import sanitize_sort_field_name
from calibre.ebooks.metadata import authors_to_string, fmt_sidx, rating_to_stars
from calibre.ebooks.metadata.book.base import Metadata
from calibre.library.comments import comments_to_html
from calibre.srv.errors import HTTPBadRequest, HTTPInternalServerError, HTTPNotFound, HTTPPreconditionRequired, HTTPUnprocessableEntity
from calibre.srv.fts import book_ids_from_user_restriction
from calibre.srv.handler import Context, UrlForCallable
from calibre.srv.http_request import parse_uri
from calibre.srv.http_response import RequestData
from calibre.srv.opts import Options
from calibre.srv.routes import endpoint
from calibre.srv.utils import MultiDict, Offsets, get_library_data, http_date
from calibre.utils.config import prefs
from calibre.utils.date import as_utc, is_date_undefined, timestampfromdt
from calibre.utils.icu import sort_key
from calibre.utils.localization import _, lang_as_iso639_1, ngettext
from calibre.utils.search_query_parser import ParseException
from calibre.utils.xml_parse import safe_xml_fromstring
from polyglot.binary import as_hex_unicode, from_hex_unicode
from polyglot.builtins import as_bytes
from polyglot.urllib import unquote_plus


class Group(NamedTuple):
    text: str
    count: int


OPDS2_MIME: str = 'application/opds+json'
DIVINA_MIME: str = 'application/divina+json'


def accepts_opds2(rd: RequestData) -> bool:
    """
    Whether the client prefers OPDS 2.0 to OPDS 1 according to the Accept
    header, see https://specs.opds.io/opds-2.0 OPDS 1 is the default, so OPDS
    2.0 is used only when it has a higher quality value than Atom.
    """
    qualities = {OPDS2_MIME: 0.0, 'application/atom+xml': 0.0}
    for header in rd.inheaders.get('Accept', all=True):
        for media_range in header.split(','):
            media_type, *params = (x.strip() for x in media_range.split(';'))
            media_type = media_type.lower()
            if media_type not in qualities:
                continue
            q = 1.0
            for param in params:
                name, _sep, val = param.partition('=')
                if name.strip().lower() == 'q':
                    try:
                        q = float(val)
                    except ValueError:
                        q = 0.0
                    if not 0 <= q <= 1:  # also rejects nan
                        q = 0.0
                    break
            qualities[media_type] = max(qualities[media_type], q)
    return qualities[OPDS2_MIME] > qualities['application/atom+xml']


def atom(ctx: Context, rd: RequestData, endpoint: Callable, output: bytes | str | etree.Element | dict[str, Any]) -> bytes:
    # The same URLs serve both OPDS 1 and OPDS 2.0 feeds, depending on the Accept header
    rd.outheaders.set('Vary', 'Accept', replace_all=True)
    rd.outheaders.set('Calibre-Instance-Id', force_unicode(prefs['installation_uuid'], 'utf-8'), replace_all=True)
    if isinstance(output, dict):
        rd.outheaders.set('Content-Type', OPDS2_MIME, replace_all=True)
        return json.dumps(output, ensure_ascii=False).encode('utf-8')
    rd.outheaders.set('Content-Type', 'application/atom+xml; charset=UTF-8', replace_all=True)
    if isinstance(output, bytes):
        ans = output  # Assume output is already UTF-8 XML
    elif isinstance(output, str):
        ans = output.encode('utf-8')
    else:
        ans = etree.tostring(output, encoding='utf-8', xml_declaration=True, pretty_print=True)
    return ans


def format_tag_string(tags: list[str] | str, sep: str | None, joinval: str = ', ') -> str:
    if tags:
        tlist = list(tags) if sep is None else [t.strip() for t in cast('str', tags).split(sep)]
    else:
        tlist = []
    tlist.sort(key=sort_key)
    return joinval.join(tlist) if tlist else ''


# Vocabulary for building OPDS feeds {{{
DC_NS: str = 'http://purl.org/dc/terms/'
E: ElementMaker[etree.Element] = ElementMaker(
    namespace='http://www.w3.org/2005/Atom',
    nsmap={
        None: 'http://www.w3.org/2005/Atom',
        'dc': DC_NS,
        'opds': 'http://opds-spec.org/2010/catalog',
    },
)

FEED: Callable[..., etree.Element] = E.feed
TITLE: Callable[..., etree.Element] = E.title
ID: Callable[..., etree.Element] = E.id
ICON: Callable[..., etree.Element] = E.icon


def UPDATED(dt: datetime.datetime, *args: Any, **kwargs: Any) -> etree.Element:
    return E.updated(as_utc(dt).strftime('%Y-%m-%dT%H:%M:%S+00:00'), *args, **kwargs)


@lru_cache(maxsize=2)
def rel_title_map() -> dict[str, str]:
    return {'start': _('Start'), 'up': _('Up'), 'first': _('First'), 'last': _('Last'), 'next': _('Next'), 'previous': _('Previous')}


class LINK:
    type: str = 'application/atom+xml'
    catalog_type: str = ''
    rel: str = ''

    def __call__(self, **kw: str) -> etree.Element:
        t = self.type
        if self.catalog_type:
            t += f';kind={self.catalog_type}'
        kw['type'] = kw.get('type', t)
        if self.rel:
            kw['rel'] = kw.get('rel', self.rel)
            if title := rel_title_map().get(kw['rel'], ''):
                kw['title'] = kw.get('title', title)
        return E.link(**kw)


class NAVLINK(LINK):
    type = LINK.type + ';type=feed;profile=opds-catalog'


class CATALOG_LINK(NAVLINK):
    catalog_type = 'navigation'


def search_url(url_for: Callable[..., str], template: str = '{searchTerms}', full_text: bool = False) -> str:
    if template == '{query}':
        ans = url_for('/opds/search', query='')
        ans += ('&' if '?' in ans else '?') + 'query={query}'
    else:
        ans = url_for('/opds/search', query='XXX').replace('XXX', template)
    if full_text:
        ans += ('&' if '?' in ans else '?') + 'full_text=y'
    return ans


def SEARCH_LINK(url_for: Callable[..., str], full_text: bool = False, **kwargs: str) -> etree.Element:
    kwargs['rel'] = 'search'
    kwargs['title'] = _('Search book contents') if full_text else 'Search'
    kwargs['href'] = search_url(url_for, full_text=full_text)
    return LINK()(**kwargs)


def AUTHOR(name: str, uri: str | None = None) -> etree.Element:
    args = [E.name(name)]
    if uri is not None:
        args.append(E.uri(uri))
    return E.author(*args)


SUBTITLE: Callable[..., etree.Element] = E.subtitle


def navcatalog_url(url_for: UrlForCallable, query: str) -> str:
    return url_for('/opds/navcatalog', which=as_hex_unicode(query))


def NAVCATALOG_ENTRY(url_for: UrlForCallable, updated: datetime.datetime, title: str, description: str, query: str) -> etree.Element:
    href = navcatalog_url(url_for, query)
    id_ = 'calibre-navcatalog:' + hashlib.sha1(as_bytes(href)).hexdigest()
    return E.entry(TITLE(title), ID(id_), UPDATED(updated), E.content(description, type='text'), CATALOG_LINK()(href=href))


class START_LINK(CATALOG_LINK):
    rel = 'start'


class UP_LINK(CATALOG_LINK):
    rel = 'up'


class FIRST_LINK(CATALOG_LINK):
    rel = 'first'


class LAST_LINK(CATALOG_LINK):
    rel = 'last'


class NEXT_LINK(CATALOG_LINK):
    rel = 'next'


class PREVIOUS_LINK(CATALOG_LINK):
    rel = 'previous'


def html_to_lxml(raw: str) -> etree.Element:
    raw = f'<div>{raw}</div>'
    root = parse(raw, keep_doctype=False, namespace_elements=False, maybe_xhtml=False, sanitize_names=True)
    root = next(root.iterdescendants('div'))
    root.set('xmlns', 'http://www.w3.org/1999/xhtml')
    raw = etree.tostring(root, encoding='unicode')
    try:
        return safe_xml_fromstring(raw, recover=False)
    except Exception:
        for x in root.iterdescendants():
            remove = []
            for attr in x.attrib:
                if ':' in attr:
                    remove.append(attr)
            for a in remove:
                del x.attrib[a]
        raw = etree.tostring(root, encoding='unicode')
        try:
            return safe_xml_fromstring(raw, recover=False)
        except Exception:
            from calibre.ebooks.oeb.parse_utils import _html4_parse

            return _html4_parse(raw)


def catalog_entry_data(item: Tag, item_kind: str, request_context: RequestContext, catalog_name: str, add_kind: bool = False) -> tuple[str, str]:
    "The title of a category item and the URL of its books"
    iid = 'N' + item.name
    if item.id is not None:
        iid = 'I' + str(item.id)
        iid += ':' + item_kind
    href = request_context.url_for('/opds/category', category=as_hex_unicode(catalog_name), which=as_hex_unicode(iid))
    if item.use_sort_as_name:
        name = item.sort
    else:
        name = item.name
    return str(name) + ('' if not add_kind else f' ({item_kind})'), href


def CATALOG_ENTRY(
    item: Tag,
    item_kind: str,
    request_context: RequestContext,
    updated: datetime.datetime,
    catalog_name: str,
    ignore_count: bool = False,
    add_kind: bool = False,
) -> etree.Element:
    id_ = 'calibre:category:' + item.name
    title, href = catalog_entry_data(item, item_kind, request_context, catalog_name, add_kind)
    link = CATALOG_LINK()(href=href)
    if ignore_count:
        count = ''
    else:
        count = ngettext('one book', '{} books', item.count).format(item.count)
    return E.entry(
        TITLE(title),
        ID(id_),
        UPDATED(updated),
        E.content(count, type='text'),
        link,
    )


def category_group_url(item: Group, category: str, request_context: RequestContext) -> str:
    return request_context.url_for('/opds/categorygroup', category=as_hex_unicode(category), which=as_hex_unicode(item.text))


def CATALOG_GROUP_ENTRY(item: Group, category: str, request_context: RequestContext, updated: datetime.datetime) -> etree.Element:
    id_ = 'calibre:category-group:' + category + ':' + (item.text or '')
    link = CATALOG_LINK()(href=category_group_url(item, category, request_context))
    return E.entry(
        TITLE(item.text),
        ID(id_),
        UPDATED(updated),
        E.content(ngettext('one item', '{} items', item.count).format(item.count), type='text'),
        link,
    )


def acquisition_extra(mi: Metadata, request_context: RequestContext) -> list[str]:
    "The metadata of a book as HTML, to be shown as its description"
    field_metadata = request_context.db.field_metadata
    extra = []
    if (mi.rating or 0) > 0:
        rating = rating_to_stars(mi.rating)
        extra.append(_('RATING: %s<br />') % rating)
    if mi.tags:
        extra.append(_('TAGS: %s<br />') % xml(format_tag_string(mi.tags, None)))
    if mi.series:
        extra.append(_('SERIES: %(series)s [%(sidx)s]<br />') % dict(series=xml(mi.series), sidx=fmt_sidx(mi.series_index)))
    for key in filter(request_context.ctx.is_field_displayable, field_metadata.ignorable_field_keys()):
        name, val = mi.format_field(key)
        if val:
            fm = field_metadata[key]
            datatype = fm['datatype']
            if datatype == 'text' and fm['is_multiple']:
                extra.append(
                    '{}: {}<br />'.format(
                        xml(name),
                        xml(format_tag_string(val, fm['is_multiple']['ui_to_list'], joinval=fm['is_multiple']['list_to_ui'])),
                    )
                )
            elif datatype == 'comments' or (fm['datatype'] == 'composite' and fm['display'].get('contains_html', False)):
                extra.append(f'{xml(name)}: {comments_to_html(str(val))}<br />')
            else:
                extra.append(f'{xml(name)}: {xml(str(val))}<br />')
    if mi.comments:
        comments = comments_to_html(mi.comments)
        extra.append(comments)
    return extra


def ACQUISITION_ENTRY(book_id: int, updated: datetime.datetime, request_context: RequestContext) -> etree.Element:
    mi = request_context.db.get_metadata(book_id)
    extra = acquisition_extra(mi, request_context)
    ans = E.entry(
        TITLE(mi.title),
        E.author(E.name(authors_to_string(mi.authors))),
        ID('urn:uuid:' + (mi.uuid or '')),
        UPDATED(mi.last_modified),
        E.published(mi.timestamp.isoformat()),
    )
    if mi.pubdate and not is_date_undefined(mi.pubdate):
        ans.append(ans.makeelement(f'{{{DC_NS}}}date'))
        ans[-1].text = mi.pubdate.isoformat()
    if extra:
        extra_tag = html_to_lxml('\n'.join(extra))
        if len(extra_tag):
            ans.append(E.content(extra_tag, type='xhtml'))

    def get(**kwargs: Any) -> str:
        return request_context.ctx.url_for('/get', book_id=book_id, library_id=request_context.library_id, **kwargs)

    if mi.formats:
        fm = mi.format_metadata
        for fmt in mi.formats:
            fmt = fmt.lower()
            mt = guess_type('a.' + fmt)[0]
            if mt:
                link = E.link(type=mt, href=get(what=fmt), rel='http://opds-spec.org/acquisition')
                ffm = fm.get(fmt.upper())
                if ffm:
                    link.set('length', str(ffm['size']))
                    link.set('mtime', ffm['mtime'].isoformat())
                ans.append(link)
    ans.append(E.link(type='image/jpeg', href=get(what='cover'), rel='http://opds-spec.org/cover'))
    ans.append(E.link(type='image/jpeg', href=get(what='thumb'), rel='http://opds-spec.org/thumbnail'))
    ans.append(E.link(type='image/jpeg', href=get(what='cover'), rel='http://opds-spec.org/image'))
    ans.append(E.link(type='image/jpeg', href=get(what='thumb'), rel='http://opds-spec.org/image/thumbnail'))

    return ans


# }}}

default_feed_title: str = __appname__ + ' ' + _('Library')


class Feed:  # {{{
    base_href: str
    root: etree.Element
    is_acquisition_feed: bool = False

    def link(self, link_cls: type[CATALOG_LINK] = CATALOG_LINK, **kw: str) -> etree.Element:
        cl = link_cls()
        if self.is_acquisition_feed:
            cl.catalog_type = 'acquisition'
        return cl(**kw)

    def __init__(
        self,
        id_: str,
        updated: datetime.datetime,
        request_context: RequestContext,
        subtitle: str | None = None,
        title: str | None = None,
        up_link: str | None = None,
        first_link: str | None = None,
        last_link: str | None = None,
        next_link: str | None = None,
        previous_link: str | None = None,
        full_text_search: bool = False,
    ) -> None:
        self.base_href = request_context.url_for('/opds')
        full_text_search = full_text_search or request_context.rd.query.get('full_text') == 'y'

        self.root = FEED(
            TITLE(title or default_feed_title),
            AUTHOR(__appname__, uri='https://calibre-ebook.com'),
            ID(id_),
            ICON(request_context.ctx.url_for('/favicon.png')),
            UPDATED(updated),
            SEARCH_LINK(request_context.url_for, full_text=full_text_search),
            START_LINK()(href=request_context.url_for('/opds')),
        )
        if up_link:
            self.root.append(UP_LINK()(href=up_link))
        if first_link:
            self.root.append(self.link(FIRST_LINK, href=first_link))
        if last_link:
            self.root.append(self.link(LAST_LINK, href=last_link))
        if next_link:
            self.root.append(self.link(NEXT_LINK, href=next_link))
        if previous_link:
            self.root.append(self.link(PREVIOUS_LINK, href=previous_link))
        if subtitle:
            self.root.insert(1, SUBTITLE(subtitle))


# }}}


class TopLevel(Feed):  # {{{
    def __init__(
        self,
        updated: datetime.datetime,  # datetime object in UTC
        categories: list[tuple[str, str, str]],
        request_context: RequestContext,
        id_: str = 'urn:calibre:main',
        subtitle: str = _('Books in your library'),
    ) -> None:
        Feed.__init__(self, id_, updated, request_context, subtitle=subtitle)

        subc = partial(NAVCATALOG_ENTRY, request_context.url_for, updated)
        subcatalogs = [subc(_('By ') + title, _('Books sorted by ') + desc, q) for title, desc, q in categories]
        for x in subcatalogs:
            self.root.append(x)
        if request_context.db.is_fts_enabled():
            self.root.append(
                E.entry(
                    TITLE(_('Search book contents')),
                    ID('calibre:full-text-search'),
                    UPDATED(updated),
                    self.link(href=request_context.url_for('/opds/fts')),
                )
            )
        for library_id, library_name in sorted(request_context.library_map.items(), key=lambda item: sort_key(item[1])):
            id_ = 'calibre-library:' + library_id
            self.root.append(
                E.entry(
                    TITLE(_('Library:') + ' ' + library_name),
                    ID(id_),
                    UPDATED(updated),
                    E.content(_('Change calibre library to:') + ' ' + library_name, type='text'),
                    self.link(href=request_context.url_for('/opds', library_id=library_id)),
                )
            )


# }}}


def pagination_links(offsets: Offsets, page_url: str, up_url: str) -> dict[str, str]:
    ans = {'up_link': up_url}
    ans['first_link'] = page_url
    ans['last_link'] = page_url + f'&offset={offsets.last_offset}'
    if offsets.offset > 0:
        ans['previous_link'] = page_url + f'&offset={offsets.previous_offset}'
    if offsets.next_offset > -1:
        ans['next_link'] = page_url + f'&offset={offsets.next_offset}'
    return ans


class NavFeed(Feed):
    def __init__(
        self,
        id_: str,
        updated: datetime.datetime,
        request_context: RequestContext,
        offsets: Offsets,
        page_url: str,
        up_url: str,
        title: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = pagination_links(offsets, page_url, up_url)
        if title:
            kwargs['title'] = title
        Feed.__init__(self, id_, updated, request_context, **kwargs)


class AcquisitionFeed(NavFeed):
    is_acquisition_feed = True

    def __init__(
        self,
        id_: str,
        updated: datetime.datetime,
        request_context: RequestContext,
        items: list[int],
        offsets: Offsets,
        page_url: str,
        up_url: str,
        title: str | None = None,
    ) -> None:
        NavFeed.__init__(self, id_, updated, request_context, offsets, page_url, up_url, title=title)
        for book_id in items:
            self.root.append(ACQUISITION_ENTRY(book_id, updated, request_context))


class CategoryFeed(NavFeed):
    def __init__(
        self,
        items: list[Tag],
        which: str,
        id_: str,
        updated: datetime.datetime,
        request_context: RequestContext,
        offsets: Offsets,
        page_url: str,
        up_url: str,
        title: str | None = None,
    ) -> None:
        NavFeed.__init__(self, id_, updated, request_context, offsets, page_url, up_url, title=title)
        ignore_count = False
        if which == 'search':
            ignore_count = True
        for item in items:
            self.root.append(
                CATALOG_ENTRY(
                    item,
                    item.category or '',
                    request_context,
                    updated,
                    which,
                    ignore_count=ignore_count,
                    add_kind=which != item.category,
                )
            )


class CategoryGroupFeed(NavFeed):
    def __init__(
        self,
        items: list[Group],
        which: str,
        id_: str,
        updated: datetime.datetime,
        request_context: RequestContext,
        offsets: Offsets,
        page_url: str,
        up_url: str,
        title: str | None = None,
    ) -> None:
        NavFeed.__init__(self, id_, updated, request_context, offsets, page_url, up_url, title=title)
        for item in items:
            self.root.append(CATALOG_GROUP_ENTRY(item, which, request_context, updated))


# OPDS 2.0 {{{
# The same feeds as above, as JSON, see https://specs.opds.io/opds-2.0 They are
# served at the same URLs, to clients that send Accept: application/opds+json


def opds2_link(href: str, rel: str = '', title: str = '', **kwargs: Any) -> dict[str, Any]:
    ans: dict[str, Any] = {'href': href, 'type': OPDS2_MIME}
    if rel:
        ans['rel'] = rel
    if title:
        ans['title'] = title
    ans.update(kwargs)
    return ans


def opds2_feed(
    request_context: RequestContext,
    self_url: str,
    title: str | None = None,
    subtitle: str | None = None,
    offsets: Offsets | None = None,
    page_url: str = '',
    up_url: str = '',
    full_text_search: bool = False,
) -> dict[str, Any]:
    metadata = {'title': title or default_feed_title}
    full_text_search = full_text_search or request_context.rd.query.get('full_text') == 'y'
    if subtitle:
        metadata['subtitle'] = subtitle
    links = [
        opds2_link(self_url, rel='self'),
        opds2_link(request_context.url_for('/opds'), rel='start'),
        opds2_link(search_url(request_context.url_for, '{query}', full_text=full_text_search), rel='search', templated=True),
    ]
    if offsets is not None:
        for name, href in pagination_links(offsets, page_url, up_url).items():
            rel = name.partition('_')[0]
            links.append(opds2_link(href, rel=rel, title=rel_title_map().get(rel, '')))
    return {'metadata': metadata, 'links': links}


def opds2_self_url(page_url: str, offsets: Offsets) -> str:
    return page_url + (f'&offset={offsets.offset}' if offsets.offset else '')


def opds2_top_level(categories: list[tuple[str, str, str]], request_context: RequestContext, subtitle: str = _('Books in your library')) -> dict[str, Any]:
    url_for = request_context.url_for
    ans = opds2_feed(request_context, url_for('/opds'), subtitle=subtitle)
    navigation = [opds2_link(navcatalog_url(url_for, q), title=_('By ') + title) for title, desc, q in categories]
    for library_id, library_name in sorted(request_context.library_map.items(), key=lambda item: sort_key(item[1])):
        navigation.append(opds2_link(url_for('/opds', library_id=library_id), title=_('Library:') + ' ' + library_name))
    if request_context.db.is_fts_enabled():
        navigation.append(opds2_link(url_for('/opds/fts'), title=_('Search book contents')))
    ans['navigation'] = navigation
    return ans


def opds2_category_feed(
    items: list[Tag], which: str, request_context: RequestContext, offsets: Offsets, page_url: str, up_url: str, title: str | None = None
) -> dict[str, Any]:
    ans = opds2_feed(request_context, opds2_self_url(page_url, offsets), title=title, offsets=offsets, page_url=page_url, up_url=up_url)
    navigation = []
    for item in items:
        item_kind = item.category or ''
        item_title, href = catalog_entry_data(item, item_kind, request_context, which, add_kind=which != item_kind)
        link = opds2_link(href, title=item_title)
        if which != 'search':
            link['properties'] = {'numberOfItems': item.count}
        navigation.append(link)
    ans['navigation'] = navigation
    return ans


def opds2_category_group_feed(
    items: list[Group], which: str, request_context: RequestContext, offsets: Offsets, page_url: str, up_url: str, title: str | None = None
) -> dict[str, Any]:
    ans = opds2_feed(request_context, opds2_self_url(page_url, offsets), title=title, offsets=offsets, page_url=page_url, up_url=up_url)
    ans['navigation'] = [
        opds2_link(category_group_url(item, which, request_context), title=item.text, properties={'numberOfItems': item.count}) for item in items
    ]
    return ans


def opds2_metadata(mi: Metadata, request_context: RequestContext) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        '@type': 'http://schema.org/Book',
        'title': mi.title,
        'author': list(mi.authors),
        'modified': as_utc(mi.last_modified).isoformat(),
    }
    if mi.uuid:
        metadata['identifier'] = 'urn:uuid:' + mi.uuid
    if mi.pubdate and not is_date_undefined(mi.pubdate):
        metadata['published'] = mi.pubdate.isoformat()
    if mi.languages:
        # OPDS 2.0 uses BCP 47 language tags, which use the two letter code when there is one
        metadata['language'] = [lang_as_iso639_1(x) or x for x in mi.languages]
    if mi.tags:
        metadata['subject'] = sorted(mi.tags, key=sort_key)
    if mi.series:
        metadata['belongsTo'] = {'series': {'name': mi.series, 'position': mi.series_index}}
    if extra := acquisition_extra(mi, request_context):
        metadata['description'] = '\n'.join(extra)
    return metadata


def opds2_publication(book_id: int, request_context: RequestContext) -> dict[str, Any]:
    mi = request_context.db.get_metadata(book_id)

    def get(**kwargs: Any) -> str:
        return request_context.ctx.url_for('/get', book_id=book_id, library_id=request_context.library_id, **kwargs)

    links = []
    for fmt in mi.formats or ():
        fmt = fmt.lower()
        if mt := format_mime_type(fmt):
            links.append({'rel': 'http://opds-spec.org/acquisition', 'href': get(what=fmt), 'type': mt})
    if 'CBZ' in (mi.formats or ()):
        # Only link to the manifest here. Listing a feed must not open archives
        # to find page counts or image formats.
        links.append({
            'rel': 'http://opds-spec.org/acquisition',
            'href': request_context.url_for('/comic-manifest', book_id=book_id),
            'type': DIVINA_MIME,
        })
    ans: dict[str, Any] = {'metadata': opds2_metadata(mi, request_context), 'links': links}
    if mi.has_cover:
        ans['images'] = [{'href': get(what='cover'), 'type': 'image/jpeg'}, {'href': get(what='thumb'), 'type': 'image/jpeg'}]
    return ans


def format_mime_type(fmt: str) -> str | None:
    return guess_type('a.' + fmt.lower())[0]


def opds2_has_acquisition_links(rc: RequestContext, ids: frozenset[int]) -> frozenset[int]:
    """
    The books that have at least one format that can be downloaded, as OPDS 2.0
    requires every publication to have an acquisition link
    """
    formats = rc.db.all_field_for('formats', ids, default_value=())
    return frozenset(book_id for book_id, fmts in formats.items() if any(map(format_mime_type, fmts or ())))


def opds2_acquisition_feed(
    request_context: RequestContext, items: list[int], offsets: Offsets, page_url: str, up_url: str, title: str | None = None
) -> dict[str, Any]:
    ans = opds2_feed(request_context, opds2_self_url(page_url, offsets), title=title, offsets=offsets, page_url=page_url, up_url=up_url)
    ans['publications'] = [opds2_publication(book_id, request_context) for book_id in items]
    return ans


# }}}


class RequestContext:
    db: Cache
    library_id: str
    library_map: dict[str, str]
    default_library: str
    ctx: Context
    rd: RequestData
    is_opds2: bool

    def __init__(self, ctx: Context, rd: RequestData, strict_library_id: bool = False) -> None:
        self.db, self.library_id, self.library_map, self.default_library = get_library_data(ctx, rd, strict_library_id=strict_library_id)
        self.ctx, self.rd = ctx, rd
        self.is_opds2 = accepts_opds2(rd)

    def url_for(self, route: str | None, **kwargs: Any) -> str:
        lid = kwargs.pop('library_id', self.library_id)
        assert self.ctx.url_for is not None
        ans = self.ctx.url_for(route, **kwargs)
        q = {'library_id': lid}
        ans += '?' + urlencode(q)
        return ans

    def allowed_book_ids(self) -> frozenset[int]:
        return self.ctx.allowed_book_ids(self.rd, self.db)

    @property
    def outheaders(self) -> MultiDict:
        return self.rd.outheaders

    @property
    def opts(self) -> Options:
        return self.ctx.opts

    def last_modified(self) -> datetime.datetime:
        return self.db.last_modified()

    def get_categories(self, report_parse_errors: bool = False) -> dict[str, list[Tag]]:
        return self.ctx.get_categories(self.rd, self.db, report_parse_errors=report_parse_errors)

    def search(self, query: str) -> frozenset[int]:
        return self.ctx.search(self.rd, self.db, query)


def get_acquisition_feed(
    rc: RequestContext,
    ids: frozenset[int],
    offset: int,
    page_url: str,
    up_url: str,
    id_: str,
    sort_by: str = 'title',
    ascending: bool = True,
    feed_title: str | None = None,
) -> etree.Element | dict[str, Any]:
    if rc.is_opds2:
        ids = opds2_has_acquisition_links(rc, ids)
    if not ids:
        raise HTTPNotFound('No books found')
    with rc.db.safe_read_lock:
        sort_by = sanitize_sort_field_name(rc.db.field_metadata, sort_by)
        items = rc.db.multisort([(sort_by, ascending)], ids)
        max_items = rc.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = items[offsets.offset : offsets.offset + max_items]
        lm = rc.last_modified()
        rc.outheaders['Last-Modified'] = http_date(timestampfromdt(lm))
        if rc.is_opds2:
            return opds2_acquisition_feed(rc, items, offsets, page_url, up_url, title=feed_title)
        return AcquisitionFeed(id_, lm, rc, items, offsets, page_url, up_url, title=feed_title).root


def get_all_books(rc: RequestContext, which: str, page_url: str, up_url: str, offset: int = 0) -> etree.Element | dict[str, Any]:
    try:
        offset = int(offset)
    except Exception:
        raise HTTPNotFound('Not found')
    if which not in ('title', 'newest'):
        raise HTTPNotFound('Not found')
    sort = 'timestamp' if which == 'newest' else 'title'
    ascending = which == 'title'
    feed_title = {'newest': _('Newest'), 'title': _('Title')}.get(which, which)
    feed_title = default_feed_title + ' :: ' + _('By %s') % feed_title
    ids = rc.allowed_book_ids()
    return get_acquisition_feed(
        rc,
        ids,
        offset,
        page_url,
        up_url,
        id_='calibre-all:' + sort,
        sort_by=sort,
        ascending=ascending,
        feed_title=feed_title,
    )


def get_navcatalog(request_context: RequestContext, which: str, page_url: str, up_url: str, offset: int = 0) -> etree.Element | dict[str, Any]:
    categories = request_context.get_categories()
    if which not in categories:
        raise HTTPNotFound(f'Category {which!r} not found')

    items = categories[which]
    updated = request_context.last_modified()
    category_meta = request_context.db.field_metadata
    meta = category_meta.get(which, {})
    category_name = meta.get('name', which)
    feed_title = default_feed_title + ' :: ' + _('By %s') % category_name

    id_ = 'calibre-category-feed:' + which

    MAX_ITEMS = request_context.opts.max_opds_ungrouped_items

    if MAX_ITEMS > 0 and len(items) <= MAX_ITEMS:
        max_items = request_context.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = list(items)[offsets.offset : offsets.offset + max_items]
        if request_context.is_opds2:
            ans = opds2_category_feed(items, which, request_context, offsets, page_url, up_url, title=feed_title)
        else:
            ans = CategoryFeed(items, which, id_, updated, request_context, offsets, page_url, up_url, title=feed_title).root
    else:
        starts = set()
        for x in items:
            val = getattr(x, 'sort', x.name)
            if not val:
                val = 'A'
            starts.add(val[0].upper())
        category_groups = OrderedDict()
        for x in sorted(starts, key=sort_key):
            category_groups[x] = len([y for y in items if getattr(y, 'sort', y.name).upper().startswith(x)])
        items = [Group(x, y) for x, y in category_groups.items()]
        max_items = request_context.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = items[offsets.offset : offsets.offset + max_items]
        if request_context.is_opds2:
            ans = opds2_category_group_feed(items, which, request_context, offsets, page_url, up_url, title=feed_title)
        else:
            ans = CategoryGroupFeed(items, which, id_, updated, request_context, offsets, page_url, up_url, title=feed_title).root

    request_context.outheaders['Last-Modified'] = http_date(timestampfromdt(updated))

    return ans


@endpoint('/opds', postprocess=atom)
def opds(ctx: Context, rd: RequestData) -> etree.Element | dict[str, Any]:
    rc = RequestContext(ctx, rd)
    db = rc.db
    try:
        categories = rc.get_categories(report_parse_errors=True)
    except ParseException as p:
        raise HTTPInternalServerError(p.msg)

    category_meta = db.field_metadata
    cats = [
        (_('Newest'), _('Date'), 'Onewest'),
        (_('Title'), _('Title'), 'Otitle'),
    ]

    def getter(x: str) -> str:
        try:
            return category_meta[x]['name'].lower()
        except KeyError:
            return x

    fm = rc.db.field_metadata
    for category in sorted(categories, key=lambda x: sort_key(getter(x))):
        if fm.is_ignorable_field(category) and not rc.ctx.is_field_displayable(category):
            continue
        if len(categories[category]) == 0:
            continue
        if category in ('formats', 'identifiers'):
            continue
        meta = category_meta.get(category, None)
        if meta is None:
            continue
        cats.append((meta['name'], meta['name'], 'N' + category))
    last_modified = db.last_modified()
    rd.outheaders['Last-Modified'] = http_date(timestampfromdt(last_modified))
    if rc.is_opds2:
        return opds2_top_level(cats, rc)
    return TopLevel(last_modified, cats, rc).root


@endpoint('/opds/navcatalog/{which}', postprocess=atom)
def opds_navcatalog(ctx: Context, rd: RequestData, which: str) -> etree.Element | dict[str, Any]:
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')
    rc = RequestContext(ctx, rd)

    page_url = rc.url_for('/opds/navcatalog', which=which)
    up_url = rc.url_for('/opds')
    try:
        which = from_hex_unicode(which)
    except ValueError:
        raise HTTPNotFound('Not found')
    type_ = which[0]
    which = which[1:]
    if type_ == 'O':
        return get_all_books(rc, which, page_url, up_url, offset=offset)
    elif type_ == 'N':
        return get_navcatalog(rc, which, page_url, up_url, offset=offset)
    raise HTTPNotFound('Not found')


@endpoint('/opds/category/{category}/{which}', postprocess=atom)
def opds_category(ctx: Context, rd: RequestData, category: str, which: str) -> etree.Element | dict[str, Any]:
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')

    if not which or not category:
        raise HTTPNotFound('Not found')
    rc = RequestContext(ctx, rd)
    page_url = rc.url_for('/opds/category', which=which, category=category)
    up_url = rc.url_for('/opds/navcatalog', which=category)

    try:
        which, category = from_hex_unicode(which), from_hex_unicode(category)
    except ValueError:
        raise HTTPNotFound('Not found')
    type_ = which[0]
    which = which[1:]
    if type_ == 'I':
        try:
            p = which.rindex(':')
            category = which[p + 1 :]
            which = which[:p]
            # This line will toss an exception for composite columns
            which = str(int(which[:p]))
        except Exception:
            # Might be a composite column, where we have the lookup key
            if not (category in rc.db.field_metadata and rc.db.field_metadata[category]['datatype'] == 'composite'):
                raise HTTPNotFound(f'Tag {which!r} not found')

    categories = rc.get_categories()
    if category not in categories:
        raise HTTPNotFound(f'Category {which!r} not found')

    if category == 'search':
        try:
            ids = rc.search(f'search:"{which}"')
        except Exception:
            raise HTTPNotFound(f'Search: {which!r} not understood')
        return get_acquisition_feed(rc, ids, offset, page_url, up_url, 'calibre-search:' + which)

    if type_ != 'I':
        raise HTTPNotFound('Non id categories not supported')

    q = category
    if q == 'news':
        q = 'tags'
    ids = rc.db.get_books_for_category(q, which) & rc.allowed_book_ids()
    sort_by = 'series' if category == 'series' else 'title'

    return get_acquisition_feed(rc, ids, offset, page_url, up_url, 'calibre-category:' + category + ':' + str(which), sort_by=sort_by)


@endpoint('/opds/categorygroup/{category}/{which}', postprocess=atom)
def opds_categorygroup(ctx: Context, rd: RequestData, category: str, which: str) -> etree.Element | dict[str, Any]:
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')

    if not which or not category:
        raise HTTPNotFound('Not found')

    rc = RequestContext(ctx, rd)
    categories = rc.get_categories()
    page_url = rc.url_for('/opds/categorygroup', category=category, which=which)

    try:
        category = from_hex_unicode(category)
    except ValueError:
        raise HTTPNotFound('Not found')
    if category not in categories:
        raise HTTPNotFound(f'Category {which!r} not found')
    category_meta = rc.db.field_metadata
    meta = category_meta.get(category, {})
    category_name = meta.get('name', which)
    try:
        which = from_hex_unicode(which)
    except ValueError:
        raise HTTPNotFound('Not found')
    feed_title = default_feed_title + ' :: ' + (_('By {0} :: {1}').format(category_name, which))
    owhich = as_hex_unicode('N' + category)
    up_url = rc.url_for('/opds/navcatalog', which=owhich)
    items = categories[category]

    def belongs(x: Tag, which: str) -> bool:
        return getattr(x, 'sort', x.name).lower().startswith(which.lower())

    items = [x for x in items if belongs(x, which)]
    if not items:
        raise HTTPNotFound(f'No items in group {category!r}:{which!r}')
    updated = rc.last_modified()

    id_ = 'calibre-category-group-feed:' + category + ':' + which

    max_items = rc.opts.max_opds_items
    offsets = Offsets(offset, max_items, len(items))
    items = list(items)[offsets.offset : offsets.offset + max_items]

    rc.outheaders['Last-Modified'] = http_date(timestampfromdt(updated))

    if rc.is_opds2:
        return opds2_category_feed(items, category, rc, offsets, page_url, up_url, title=feed_title)
    return CategoryFeed(items, category, id_, updated, rc, offsets, page_url, up_url, title=feed_title).root


@endpoint('/opds/fts', postprocess=atom)
def opds_full_text_catalog(ctx: Context, rd: RequestData) -> etree.Element | dict[str, Any]:
    rc = RequestContext(ctx, rd, strict_library_id=True)
    if not rc.db.is_fts_enabled():
        raise HTTPPreconditionRequired('Full text searching is not enabled on this library')
    title = _('Search book contents')
    if rc.is_opds2:
        ans = opds2_feed(rc, rc.url_for('/opds/fts'), title=title, full_text_search=True)
        ans['navigation'] = [opds2_link(rc.url_for('/opds'), title=_('Books in your library'))]
        return ans
    updated = rc.last_modified()
    ans = Feed('calibre:full-text-search', updated, rc, title=title, full_text_search=True).root
    ans.append(
        E.entry(
            TITLE(_('Books in your library')),
            ID('calibre:main'),
            UPDATED(updated),
            CATALOG_LINK()(href=rc.url_for('/opds')),
        )
    )
    return ans


@endpoint('/opds/search/{query=""}', postprocess=atom)
def opds_search(ctx: Context, rd: RequestData, query: str) -> etree.Element | dict[str, Any]:
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')

    mode = rd.query.get('full_text', 'n')
    if mode not in ('y', 'n'):
        raise HTTPBadRequest('full_text must be y or n')
    full_text = mode == 'y'
    rc = RequestContext(ctx, rd, strict_library_id=full_text)
    if query:
        path = parse_uri(rd.request_original_uri, parse_query=False, unquote_func=unquote_plus)[1]
        query = path[-1]
        if isinstance(query, bytes):
            query = query.decode('utf-8')
    else:
        query = rd.query.get('query', '')
    page_url = rc.url_for('/opds/search', query=query)
    if full_text:
        if not rc.db.is_fts_enabled():
            raise HTTPPreconditionRequired('Full text searching is not enabled on this library')
        if not query.strip():
            raise HTTPBadRequest('No full text search query specified')
        try:
            # Restrict before searching and do not fetch excerpts. Multiple
            # matching formats of the same book produce only one publication.
            ids = frozenset(
                x['book_id'] for x in rc.db.fts_search(query, return_text=False, restrict_to_book_ids=book_ids_from_user_restriction(ctx, rd, rc.db))
            )
        except FTSQueryError as err:
            raise HTTPUnprocessableEntity(str(err))
        page_url += '&full_text=y'
        return get_acquisition_feed(
            rc,
            ids,
            offset,
            page_url,
            rc.url_for('/opds'),
            'calibre-full-text-search:' + query,
            feed_title=default_feed_title + ' :: ' + _('Search book contents') + ': ' + query,
        )
    try:
        ids = rc.search(query)
    except Exception:
        raise HTTPNotFound(f'Search: {query!r} not understood')
    return get_acquisition_feed(rc, ids, offset, page_url, rc.url_for('/opds'), 'calibre-search:' + query)
