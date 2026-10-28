#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# An OPDS 2.0 catalog, see https://specs.opds.io/opds-2.0 Comics are also
# offered as Divina publications, see
# https://readium.org/webpub-manifest/profiles/divina so that they can be read
# page by page, without downloading the whole comic first. Their pages are
# only listed when a comic is opened, and each page is offered in several
# image formats, so that applications can use the best one they support.

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from calibre import guess_type
from calibre.db.cache import Cache
from calibre.srv.errors import HTTPNotFound
from calibre.srv.handler import Context
from calibre.srv.http_response import RequestData
from calibre.srv.routes import endpoint
from calibre.srv.utils import Offsets, get_db, http_date
from calibre.utils.date import is_date_undefined, timestampfromdt
from calibre.utils.icu import sort_key
from calibre.utils.localization import _, lang_as_iso639_1

OPDS_TYPE = 'application/opds+json'
PUBLICATION_TYPE = 'application/opds-publication+json'
DIVINA_TYPE = 'application/divina+json'
DIVINA_PROFILE = 'https://readium.org/webpub-manifest/profiles/divina'
ACQUISITION_REL = 'http://opds-spec.org/acquisition'
# Categories whose items are not stored in the database, so books cannot be
# listed by item
UNLISTABLE_CATEGORIES = frozenset(('formats', 'identifiers', 'search', 'news'))


def json_response(media_type: str) -> Callable[[Context, RequestData, Any, Any], bytes]:
    def postprocess(ctx: Context, rd: RequestData, endpoint: Any, output: Any) -> bytes:
        rd.outheaders.set('Content-Type', media_type + '; charset=UTF-8', replace_all=True)
        return json.dumps(output, ensure_ascii=False).encode('utf-8')

    return postprocess


opds_json = json_response(OPDS_TYPE)


def with_offset(url: str, offset: int) -> str:
    return url + ('&' if '?' in url else '?') + f'offset={offset}'


def iso_date(dt: Any) -> str | None:
    if dt is None or is_date_undefined(dt):
        return None
    return dt.isoformat()


class Catalog:
    "The library and the allowed books of a request, with helpers to create links"

    def __init__(self, ctx: Context, rd: RequestData, library_id: str | None) -> None:
        self.ctx, self.rd = ctx, rd
        self.library_map, default_library = ctx.library_info(rd)
        if not library_id:
            library_id = default_library
        elif library_id not in self.library_map:
            raise HTTPNotFound(f'No library with id: {library_id}')
        self.library_id = library_id
        self.db: Cache = get_db(ctx, rd, library_id)

    def url(self, route: str, **kwargs: Any) -> str:
        return self.ctx.url_for(route, library_id=self.library_id, **kwargs)

    def allowed_book_ids(self) -> frozenset[int]:
        return self.ctx.allowed_book_ids(self.rd, self.db)

    def set_last_modified(self) -> None:
        self.rd.outheaders['Last-Modified'] = http_date(timestampfromdt(self.db.last_modified()))

    def feed(self, title: str, self_url: str, **metadata: Any) -> dict[str, Any]:
        return {
            'metadata': {'title': title, **metadata},
            'links': [
                {'rel': 'self', 'href': self_url, 'type': OPDS_TYPE},
                {'rel': 'start', 'href': self.url('/opds2'), 'type': OPDS_TYPE},
                {'rel': 'search', 'href': self.url('/opds2/search') + '{?query}', 'type': OPDS_TYPE, 'templated': True},
            ],
        }

    def paginate(self, feed: dict[str, Any], page_url: str, offsets: Offsets, total: int) -> None:
        max_items = self.ctx.opts.max_opds_items
        feed['metadata'].update({'numberOfItems': total, 'itemsPerPage': max_items, 'currentPage': offsets.offset // max_items + 1})
        links = feed['links']
        links.append({'rel': 'first', 'href': page_url, 'type': OPDS_TYPE})
        links.append({'rel': 'last', 'href': with_offset(page_url, offsets.last_offset), 'type': OPDS_TYPE})
        if offsets.offset > 0:
            links.append({'rel': 'previous', 'href': with_offset(page_url, offsets.previous_offset), 'type': OPDS_TYPE})
        if offsets.next_offset > -1:
            links.append({'rel': 'next', 'href': with_offset(page_url, offsets.next_offset), 'type': OPDS_TYPE})

    def contributors(self, field: str, book_id: int) -> list[dict[str, Any]]:
        "The items in the field for the book, such as its authors, with links to their books"
        return [
            {
                'name': self.db.get_item_name(field, item_id),
                'links': [{'href': self.url('/opds2/category', category=field, item_id=item_id), 'type': OPDS_TYPE}],
            }
            for item_id in self.db.field_ids_for(field, book_id)
        ]

    def publication_metadata(self, book_id: int, mi: Any) -> dict[str, Any]:
        from calibre.library.comments import comments_to_html

        md: dict[str, Any] = {
            '@type': 'http://schema.org/Book',
            'title': mi.title,
            'identifier': 'urn:uuid:' + mi.uuid if mi.uuid else None,
            'modified': iso_date(mi.last_modified),
            'published': iso_date(mi.pubdate),
            'author': self.contributors('authors', book_id),
            'language': [x for x in (lang_as_iso639_1(lang) or lang for lang in mi.languages) if x],
            'publisher': self.contributors('publisher', book_id),
            'subject': list(mi.tags),
        }
        if mi.comments:
            md['description'] = comments_to_html(mi.comments)
        if series := self.contributors('series', book_id):
            series[0]['position'] = mi.series_index
            md['belongsTo'] = {'series': series[0]}
        # Metadata must not contain blank values
        return {k: v for k, v in md.items() if v}

    def publication(self, book_id: int) -> dict[str, Any]:
        from calibre.srv.comic_pages import COMIC_FORMATS

        def get(what: str) -> str:
            return self.ctx.url_for('/get', what=what, book_id=book_id, library_id=self.library_id)

        mi = self.db.get_metadata(book_id)
        formats = mi.formats or ()
        links: list[dict[str, Any]] = [{'rel': 'self', 'href': self.url('/opds2/publication', book_id=book_id), 'type': PUBLICATION_TYPE}]
        fm = mi.format_metadata
        for fmt in formats:
            if mt := guess_type('a.' + fmt.lower())[0]:
                link: dict[str, Any] = {'rel': ACQUISITION_REL, 'href': get(fmt.lower()), 'type': mt}
                if ffm := fm.get(fmt.upper()):
                    link['size'] = ffm['size']
                links.append(link)
        # Comics can also be read page by page, without downloading them first
        if fmt := next((x for x in COMIC_FORMATS if x in formats), None):
            links.append({'rel': ACQUISITION_REL, 'href': self.url('/opds2/divina', book_id=book_id, fmt=fmt.lower()), 'type': DIVINA_TYPE})

        return {
            'metadata': self.publication_metadata(book_id, mi),
            'links': links,
            'images': [
                {'href': get('cover'), 'type': 'image/jpeg'},
                {'href': get('thumb'), 'type': 'image/jpeg'},
            ],
        }

    def publications_feed(self, title: str, page_url: str, ids: frozenset[int], offset: int, sort_by: str = 'title', ascending: bool = True) -> dict[str, Any]:
        from calibre.db.view import sanitize_sort_field_name

        if not ids:
            raise HTTPNotFound('No books found')
        max_items = self.ctx.opts.max_opds_items
        with self.db.safe_read_lock:
            sort_by = sanitize_sort_field_name(self.db.field_metadata, sort_by)
            items = self.db.multisort([(sort_by, ascending)], ids)
            offsets = Offsets(offset, max_items, len(items))
            feed = self.feed(title, with_offset(page_url, offset) if offset else page_url)
            self.paginate(feed, page_url, offsets, len(items))
            feed['publications'] = [self.publication(book_id) for book_id in items[offsets.offset : offsets.offset + max_items]]
        self.set_last_modified()
        return feed

    def is_listable(self, category: str) -> bool:
        "Whether the items of the category, such as authors or tags, can be browsed"
        fm = self.db.field_metadata
        if category in UNLISTABLE_CATEGORIES or category.startswith('@') or category not in fm or fm[category]['datatype'] == 'composite':
            return False
        return not fm.is_ignorable_field(category) or self.ctx.is_field_displayable(category)

    def listable_categories(self) -> list[tuple[str, str]]:
        "The categories whose items can be browsed and that have items, as (key, name)"
        fm = self.db.field_metadata
        categories = self.ctx.get_categories(self.rd, self.db)
        ans = [(category, fm[category]['name']) for category, items in categories.items() if items and self.is_listable(category)]
        return sorted(ans, key=lambda x: sort_key(x[1]))


def offset_of(rd: RequestData) -> int:
    try:
        return max(0, int(rd.query.get('offset', 0)))
    except Exception:
        raise HTTPNotFound('Invalid offset')


@endpoint('/opds2/{library_id=None}', postprocess=opds_json)
def opds2(ctx: Context, rd: RequestData, library_id: str | None) -> dict[str, Any]:
    """
    The start of the OPDS 2.0 catalog, with links to browse the books in the
    library and to the other libraries.
    """
    c = Catalog(ctx, rd, library_id)
    feed = c.feed(_('{} library').format(c.library_map[c.library_id]), c.url('/opds2'))
    navigation = [
        {'href': c.url('/opds2/books', which='newest'), 'title': _('Newest'), 'type': OPDS_TYPE},
        {'href': c.url('/opds2/books', which='title'), 'title': _('Title'), 'type': OPDS_TYPE},
    ]
    navigation.extend({'href': c.url('/opds2/categories', category=key), 'title': name, 'type': OPDS_TYPE} for key, name in c.listable_categories())
    groups: list[dict[str, Any]] = [{'metadata': {'title': _('Browse')}, 'navigation': navigation}]
    others = sorted(((lid, name) for lid, name in c.library_map.items() if lid != c.library_id), key=lambda x: sort_key(x[1]))
    if others:
        groups.append({
            'metadata': {'title': _('Libraries')},
            'navigation': [{'href': ctx.url_for('/opds2', library_id=lid), 'title': name, 'type': OPDS_TYPE} for lid, name in others],
        })
    feed['groups'] = groups
    c.set_last_modified()
    return feed


@endpoint('/opds2/books/{library_id}/{which}', postprocess=opds_json)
def opds2_books(ctx: Context, rd: RequestData, library_id: str, which: str) -> dict[str, Any]:
    "All books, sorted by date added if which is newest or by title if which is title"
    if which not in ('newest', 'title'):
        raise HTTPNotFound(f'Unknown sort order: {which}')
    c = Catalog(ctx, rd, library_id)
    title = _('Newest') if which == 'newest' else _('Title')
    sort_by, ascending = ('timestamp', False) if which == 'newest' else ('title', True)
    return c.publications_feed(title, c.url('/opds2/books', which=which), c.allowed_book_ids(), offset_of(rd), sort_by, ascending)


@endpoint('/opds2/categories/{library_id}/{category}', postprocess=opds_json)
def opds2_categories(ctx: Context, rd: RequestData, library_id: str, category: str) -> dict[str, Any]:
    "The items in a category, such as authors or tags, with links to their books"
    c = Catalog(ctx, rd, library_id)
    if not c.is_listable(category):
        raise HTTPNotFound(f'Category {category!r} not found')
    items = [x for x in ctx.get_categories(rd, c.db).get(category, ()) if x.id is not None]
    if not items:
        raise HTTPNotFound(f'Category {category!r} has no items')
    page_url = c.url('/opds2/categories', category=category)
    offset = offset_of(rd)
    max_items = ctx.opts.max_opds_items
    offsets = Offsets(offset, max_items, len(items))
    feed = c.feed(c.db.field_metadata[category]['name'], with_offset(page_url, offset) if offset else page_url)
    c.paginate(feed, page_url, offsets, len(items))
    feed['navigation'] = [
        {
            'href': c.url('/opds2/category', category=category, item_id=item.id),
            'title': item.name,
            'type': OPDS_TYPE,
            'properties': {'numberOfItems': item.count},
        }
        for item in items[offsets.offset : offsets.offset + max_items]
    ]
    c.set_last_modified()
    return feed


@endpoint('/opds2/category/{library_id}/{category}/{item_id}', postprocess=opds_json, types={'item_id': int})
def opds2_category(ctx: Context, rd: RequestData, library_id: str, category: str, item_id: int) -> dict[str, Any]:
    "The books that have an item in a category, such as the books by an author"
    c = Catalog(ctx, rd, library_id)
    if not c.is_listable(category):
        raise HTTPNotFound(f'Category {category!r} not found')
    try:
        name = c.db.get_item_name(category, item_id)
    except Exception:
        name = None
    if name is None:
        raise HTTPNotFound(f'No item {item_id} in category {category!r}')
    ids = c.db.get_books_for_category(category, item_id) & c.allowed_book_ids()
    sort_by = 'series' if c.db.field_metadata[category]['datatype'] == 'series' else 'title'
    return c.publications_feed(name, c.url('/opds2/category', category=category, item_id=item_id), ids, offset_of(rd), sort_by)


@endpoint('/opds2/search/{library_id}', postprocess=opds_json)
def opds2_search(ctx: Context, rd: RequestData, library_id: str) -> dict[str, Any]:
    "Search for books with the query in the query parameter, using the calibre search syntax"
    c = Catalog(ctx, rd, library_id)
    query = rd.query.get('query', '')
    try:
        ids = ctx.search(rd, c.db, query)
    except Exception:
        raise HTTPNotFound(f'Search: {query!r} not understood')
    page_url = c.url('/opds2/search') + '?query=' + quote(query)
    return c.publications_feed(_('Search results'), page_url, ids, offset_of(rd))


@endpoint('/opds2/publication/{library_id}/{book_id}', postprocess=json_response(PUBLICATION_TYPE), types={'book_id': int})
def opds2_publication(ctx: Context, rd: RequestData, library_id: str, book_id: int) -> dict[str, Any]:
    "A single book, as an OPDS publication"
    c = Catalog(ctx, rd, library_id)
    with c.db.safe_read_lock:
        if not ctx.has_id(rd, c.db, book_id):
            raise HTTPNotFound(f'Book with id {book_id!r} does not exist')
        return c.publication(book_id)


def comic_path(c: Catalog, book_id: int, fmt: str) -> str:
    from calibre.srv.comic_pages import COMIC_FORMATS

    fmt = fmt.upper()
    with c.db.safe_read_lock:
        if not c.ctx.has_id(c.rd, c.db, book_id):
            raise HTTPNotFound(f'Book with id {book_id!r} does not exist')
        path = c.db.format_abspath(book_id, fmt) if fmt in COMIC_FORMATS else None
    if not path:
        raise HTTPNotFound(f'Book with id {book_id!r} has no {fmt} comic')
    return path


@endpoint('/opds2/divina/{library_id}/{book_id}/{fmt}', postprocess=json_response(DIVINA_TYPE), types={'book_id': int})
def opds2_divina(ctx: Context, rd: RequestData, library_id: str, book_id: int, fmt: str) -> dict[str, Any]:
    """
    The Divina manifest of a comic, listing its pages. Each page is offered in
    the format it is stored in, or as JPEG if that is not widely supported,
    with alternate versions in other formats.
    """
    from calibre.srv.comic_pages import page_names, page_types

    c = Catalog(ctx, rd, library_id)
    names = page_names(comic_path(c, book_id, fmt))
    if not names:
        raise HTTPNotFound('The comic has no pages')
    mi = c.db.get_metadata(book_id)
    metadata = c.publication_metadata(book_id, mi)
    metadata.pop('@type', None)
    metadata['conformsTo'] = DIVINA_PROFILE
    metadata['numberOfPages'] = len(names)
    reading_order = []
    for i, name in enumerate(names):
        native, types = page_types(name)

        def page_url(media_type: str, i: int = i, native: str = native) -> str:
            ans = c.url('/opds2/page', book_id=book_id, fmt=fmt.lower(), page=i)
            return ans if media_type == native else ans + '?type=' + media_type

        page: dict[str, Any] = {'href': page_url(types[0]), 'type': types[0]}
        if len(types) > 1:
            page['alternate'] = [{'href': page_url(t), 'type': t} for t in types[1:]]
        reading_order.append(page)
    rd.outheaders['Cache-Control'] = 'private, max-age=3600'
    return {
        '@context': 'https://readium.org/webpub-manifest/context.jsonld',
        'metadata': metadata,
        'links': [{'rel': 'self', 'href': c.url('/opds2/divina', book_id=book_id, fmt=fmt.lower()), 'type': DIVINA_TYPE}],
        'readingOrder': reading_order,
    }


@endpoint('/opds2/page/{library_id}/{book_id}/{fmt}/{page}', types={'book_id': int, 'page': int})
def opds2_page(ctx: Context, rd: RequestData, library_id: str, book_id: int, fmt: str, page: int) -> bytes:
    """
    A page of a comic, starting at zero, as listed in its Divina manifest. The
    page is in the format it is stored in, unless another format is specified
    with the type query parameter.
    """
    from calibre.srv.comic_pages import MEDIA_TYPES, convert_page, page_names, page_types, read_page
    from calibre.utils.imghdr import identify

    c = Catalog(ctx, rd, library_id)
    path = comic_path(c, book_id, fmt)
    names = page_names(path)
    if not 0 <= page < len(names):
        raise HTTPNotFound(f'Page {page} does not exist')
    native, types = page_types(names[page])
    media_type = rd.query.get('type') or native
    if media_type not in types:
        raise HTTPNotFound(f'Page {page} is not available as {media_type}')
    data = read_page(path, names[page])
    if media_type == native:
        # Use the actual type, as pages can have the wrong file extension
        media_type = MEDIA_TYPES.get(identify(data)[0] or '', native)
    else:
        data = convert_page(data, media_type)
    rd.outheaders['Content-Type'] = media_type
    rd.outheaders['Cache-Control'] = 'private, max-age=3600'
    return data
