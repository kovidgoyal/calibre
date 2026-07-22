#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import hashlib
import random
import shutil
import sys
import zipfile
from json import load as load_json_file
from json import loads as json_loads
from threading import Lock
from typing import Any

from calibre import as_unicode
from calibre.constants import in_develop_mode
from calibre.customize.ui import available_input_formats
from calibre.db.categories import category_display_order
from calibre.db.view import sanitize_sort_field_name
from calibre.ebooks.metadata.book.render import resolve_default_author_link
from calibre.srv.ajax import search_result
from calibre.srv.errors import BookNotFound, HTTPBadRequest, HTTPForbidden, HTTPNotFound, HTTPRedirect, HTTPTempRedirect
from calibre.srv.handler import Context
from calibre.srv.http_response import RequestData
from calibre.srv.last_read import last_read_cache
from calibre.srv.metadata import book_as_json, categories_as_json, categories_settings, get_gpref, icon_map, web_search_link
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data, get_use_roman
from calibre.utils.config import prefs, tweaks
from calibre.utils.icu import numeric_sort_key, sort_key
from calibre.utils.localization import _, get_lang, lang_code_for_user_manual, lang_map_for_ui, localize_website_link
from calibre.utils.resources import get_path as P
from calibre.utils.search_query_parser import ParseException
from calibre.utils.serialize import json_dumps

POSTABLE = frozenset({'GET', 'POST', 'HEAD'})


@endpoint('', auth_required=False)
def index(ctx: Context, rd: RequestData) -> Any:
    if rd.opts.url_prefix and rd.request_original_uri:
        # We need a trailing slash for relative URLs to resolve correctly, for
        # example the link to the mobile page in index.html
        from urllib.parse import urlparse, urlunparse

        p = urlparse(rd.request_original_uri)
        if not p.path.endswith(b'/'):
            p = p._replace(path=p.path + b'/')
            raise HTTPRedirect(urlunparse(p).decode('utf-8'))
    # allow serving the data via sendfile() for performance
    return open(P('content-server/index-generated.html'), 'rb')


@endpoint('/index.js.map', auth_required=False)
def index_js_map(ctx, rd):
    rd.outheaders['Content-Type'] = 'application/json'
    # allow serving the data via sendfile() for performance
    return open(P('content-server/index.js.map'), 'rb')


@endpoint('/robots.txt', auth_required=False)
def robots(ctx, rd):
    return b'User-agent: *\nDisallow: /'


@endpoint('/service_worker.js', auth_required=False, cache_control='no-cache')
def service_worker_js(ctx, rd):
    rd.outheaders['Content-Type'] = 'application/javascript; charset=UTF-8'
    return open(P('content-server/service_worker.js', allow_user_override=False), 'rb')


@endpoint('/manifest.json', auth_required=False, cache_control='no-cache')
def manifest_json(ctx, rd):
    rd.outheaders['Content-Type'] = 'application/manifest+json; charset=UTF-8'
    manifest = {
        'name': 'calibre Content Server',
        'short_name': 'calibre',
        'start_url': ctx.url_for(None),
        'display': 'standalone',
        'display_override': ['window-controls-overlay'],
        'icons': [
            {
                'src': ctx.url_for('/favicon.svg'),
                'sizes': 'any',
                'type': 'image/svg+xml',
                'purpose': 'any',
            },
            {
                'src': ctx.url_for('/favicon-192.png'),
                'sizes': '192x192',
                'type': 'image/png',
            },
            {
                'src': ctx.url_for('/favicon.png'),
                'sizes': '512x512',
                'type': 'image/png',
            },
        ],
    }
    return json_dumps(manifest)


# auth_required=True needed for Chrome: https://bugs.launchpad.net/calibre/+bug/1982060
@endpoint('/ajax-setup', auth_required=True, cache_control='no-cache', postprocess=json)
def ajax_setup(ctx, rd):
    auto_reload_port = getattr(rd.opts, 'auto_reload_port', 0)
    return {
        'auto_reload_port': max(0, auto_reload_port),
        'allow_console_print': bool(getattr(rd.opts, 'allow_console_print', False)),
        'ajax_timeout': rd.opts.ajax_timeout,
        'in_develop_mode': bool(in_develop_mode),
    }


print_lock = Lock()


@endpoint('/console-print', methods=('POST',))
def console_print(ctx, rd):
    if not getattr(rd.opts, 'allow_console_print', False):
        raise HTTPForbidden('console printing is not allowed')
    with print_lock:
        print(rd.remote_addr, end=' ')
        stdout = getattr(sys.stdout, 'buffer', sys.stdout)
        shutil.copyfileobj(rd.request_body_file, stdout)
        stdout.flush()
    return ''


def get_basic_query_data(ctx, rd):
    db, library_id, library_map, default_library = get_library_data(ctx, rd)
    skeys = db.field_metadata.sortable_field_keys()
    sorts, orders = [], []
    for x in rd.query.get('sort', '').split(','):
        if x:
            s, o = x.rpartition('.')[::2]
            if o and not s:
                s, o = o, ''
            if o not in ('asc', 'desc'):
                o = 'asc'
            if s.startswith('_'):
                s = '#' + s[1:]
            s = sanitize_sort_field_name(db.field_metadata, s)
            if s in skeys:
                sorts.append(s), orders.append(o)
    if not sorts:
        sorts, orders = ['timestamp'], ['desc']
    return library_id, db, sorts, orders, rd.query.get('vl') or ''


def get_translations_data() -> bytes | None:
    with zipfile.ZipFile(P('content-server/locales.zip', allow_user_override=False), 'r') as zf:
        names = set(zf.namelist())
        lang = get_lang()
        if lang not in names:
            xlang = lang.split('_')[0].lower()
            if xlang in names:
                lang = xlang
        if lang in names:
            return zf.open(lang, 'r').read()


_translations_cache: dict | bool | None = None


def get_translations():
    global _translations_cache
    if _translations_cache is None:
        _translations_cache = False
        data = get_translations_data()
        if data:
            _translations_cache = json_loads(data)
    return _translations_cache


_custom_list_template_cache: dict | None = None


def custom_list_template():
    global _custom_list_template_cache
    if _custom_list_template_cache is None:
        _custom_list_template_cache = {
            'thumbnail': True,
            'thumbnail_height': 140,
            'height': 'auto',
            'comments_fields': ['comments'],
            'lines': [
                _('<b>{title}</b> by {authors}'),
                _('{series_index} of <i>{series}</i>') + '|||{rating}',
                '{tags}',
                _('Date: {timestamp}') + '|||' + _('Published: {pubdate}') + '|||' + _('Publisher: {publisher}'),
                '',
            ],
        }
    return _custom_list_template_cache


def book_exists(x, ctx, rd):
    try:
        db = ctx.get_library(rd, x['library_id'])
        if db is None:
            raise Exception('')
    except Exception:
        return False
    return bool(db.new_api.has_format(x['book_id'], x['format']))


def basic_interface_data(ctx, rd):
    ans = {
        'username': rd.username,
        'output_format': prefs['output_format'].upper(),
        'input_formats': {x.upper(): True for x in available_input_formats()},
        'gui_pubdate_display_format': tweaks['gui_pubdate_display_format'],
        'gui_timestamp_display_format': tweaks['gui_timestamp_display_format'],
        'gui_last_modified_display_format': tweaks['gui_last_modified_display_format'],
        'completion_mode': tweaks['completion_mode'],
        'use_roman_numerals_for_series_number': get_use_roman(),
        'translations': get_translations(),
        'icon_map': icon_map(),
        'icon_path': ctx.url_for('/icon', which=''),
        'custom_list_template': getattr(ctx, 'custom_list_template', None) or custom_list_template(),
        'search_the_net_urls': getattr(ctx, 'search_the_net_urls', None) or [],
        'num_per_page': rd.opts.num_per_page,
        'default_book_list_mode': rd.opts.book_list_mode,
        'donate_link': localize_website_link('https://calibre-ebook.com/donate'),
        'lang_code_for_user_manual': lang_code_for_user_manual(),
        'default_author_link': resolve_default_author_link(get_gpref('default_author_link')),
    }
    ans['library_map'], ans['default_library_id'] = ctx.library_info(rd)
    if ans['username']:
        ans['recently_read_by_user'] = tuple(
            x for x in last_read_cache().get_recently_read(ans['username']) if x['library_id'] in ans['library_map'] and book_exists(x, ctx, rd)
        )
    return ans


@endpoint('/interface-data/update/{translations_hash=None}', postprocess=json)
def update_interface_data(ctx, rd, translations_hash):
    """
    Return the interface data needed for the server UI
    """
    ans = basic_interface_data(ctx, rd)
    t = ans['translations']
    if t and (t.get('hash') or translations_hash) and t.get('hash') == translations_hash:
        del ans['translations']
    return ans


def get_field_list(db):
    fieldlist = list(db.pref('book_display_fields', ()))
    names = frozenset(x[0] for x in fieldlist)
    available = frozenset(db.field_metadata.displayable_field_keys())
    for field in available:
        if field not in names:
            fieldlist.append((field, True))
    return [f for f, d in fieldlist if d and f in available]


BROWSE_FIELD_ORDER = ('series', 'authors', 'publisher', 'tags', 'formats', 'rating', 'pubdate')
BROWSE_FIELD_ICONS = {
    'series': 'book',
    'authors': 'user',
    'publisher': 'library',
    'tags': 'tags',
    'formats': 'convert',
    'rating': 'star',
    'pubdate': 'date',
}
BROWSE_FIELD_DESCRIPTIONS = {
    'series': _('Browse all series'),
    'authors': _('Browse all authors'),
    'publisher': _('Browse all publishers'),
    'tags': _('Browse all tags'),
    'formats': _('Browse all formats'),
    'rating': _('Browse by rating'),
    'pubdate': _('Browse by published date'),
}
BROWSE_IGNORED_CATEGORIES = frozenset({'identifiers', 'news', 'search'})


def browse_field_kind(key, metadata):
    if metadata is None or metadata.get('kind') != 'field':
        return ''
    if key == 'pubdate' or (metadata.get('is_custom') and metadata.get('datatype') == 'datetime'):
        return 'date'
    if metadata.get('is_category') and key not in BROWSE_IGNORED_CATEGORIES:
        return 'category'
    return ''


def browse_field_custom_icon_url(ctx, key):
    icon = icon_map().get(key)
    if icon and icon.startswith('_'):
        # icon_map() returns custom icon names with the leading _ already URL quoted.
        return ctx.url_for('/icon', which='') + '/' + icon
    return ''


def browse_field_entry(ctx, key, metadata, kind, hidden_categories):
    name = metadata.get('name') or key
    return {
        'key': key,
        'name': name,
        'description': BROWSE_FIELD_DESCRIPTIONS.get(key) or _('Browse {0}').format(name),
        'kind': kind,
        'icon': BROWSE_FIELD_ICONS.get(key) or ('date' if kind == 'date' else 'tags'),
        'custom_icon_url': browse_field_custom_icon_url(ctx, key),
        'is_custom': bool(metadata.get('is_custom')),
        'datatype': metadata.get('datatype') or '',
        'default_visible': key not in hidden_categories,
    }


def browse_field_map(ctx, db):
    fm = db.field_metadata
    hidden_categories = frozenset(db.pref('tag_browser_hidden_categories', set()))
    ans = {}
    for key in BROWSE_FIELD_ORDER:
        metadata = fm.get(key)
        kind = browse_field_kind(key, metadata)
        if kind:
            ans[key] = browse_field_entry(ctx, key, metadata, kind, hidden_categories)
    custom_fields = []
    for key, metadata in fm.custom_field_metadata(include_composites=False).items():
        kind = browse_field_kind(key, metadata)
        if kind and key not in ans:
            custom_fields.append((sort_key(metadata.get('name') or key), key, metadata, kind))
    for unused_sort_key, key, metadata, kind in sorted(custom_fields):
        ans[key] = browse_field_entry(ctx, key, metadata, kind, hidden_categories)
    return ans


def get_browse_fields(ctx, db):
    fields = browse_field_map(ctx, db)
    return tuple(fields[key] for key in category_display_order(db.pref('tag_browser_category_order', ()), tuple(fields)))


def escape_search_value(x):
    return str(x or '').replace('\\', '\\\\').replace('"', '\\"')


def category_browse_search_expression(field, item):
    search = item.get('search_expression')
    if search:
        return search
    search_name = item.get('original_name') or item.get('name') or ''
    if field == 'rating':
        stars = str(search_name).count('★')
        if 1 <= stars <= 5:
            return f'rating:{stars}'
    if item.get('is_hierarchical'):
        # Use prefix match so an intermediate node (e.g. "History") matches both
        # "History" and its children such as "History.Military".
        return f'{field}:"=.{escape_search_value(search_name)}"'
    # Use exact (=) match to avoid a CONTAINS match where one series/tag name
    # is a prefix of another (e.g. "Awakening" matching "Awakening Lands").
    return f'{field}:"={escape_search_value(search_name)}"'


def category_browse_items(ctx, rd, db, field, vl):
    opts = categories_settings(rd.query, db, gst_container=tuple)
    categories = json_loads(categories_as_json(ctx, rd, db, opts, vl))
    root = categories.get('root') or {}
    item_map = categories.get('item_map') or {}
    category_node = None
    for child in root.get('children', ()):
        item = item_map.get(child.get('id')) or {}
        if item.get('is_category') and item.get('category') == field:
            category_node = child
            break
    if category_node is None:
        return ()
    ans, seen = [], set()

    def walk(node):
        for child in node.get('children', ()):
            item = item_map.get(child.get('id')) or {}
            name = item.get('name') or ''
            if name and not item.get('is_category') and name not in seen:
                seen.add(name)
                search_name = item.get('original_name') or name
                ans.append({
                    'name': name,
                    'count': item.get('count'),
                    'avg_rating': item.get('avg_rating'),
                    'search_name': search_name,
                    'search': category_browse_search_expression(field, item),
                })
            walk(child)

    walk(category_node)
    return tuple(ans)


def next_month(year, month):
    month += 1
    if month > 12:
        return year + 1, 1
    return year, month


def date_browse_items(ctx, rd, db, field, vl):
    from calibre.db.search import TemplatesNotAllowed

    try:
        book_ids, parse_error = ctx.search(rd, db, rd.query.get('search') or '', vl=vl, report_restriction_errors=True)
    except TemplatesNotAllowed:
        raise HTTPBadRequest(_('templates are not allowed in search expressions'))
    if parse_error is not None:
        raise HTTPBadRequest(str(parse_error))
    group = rd.query.get('date_group') or 'y'
    if group == 'ym':
        groups = db.books_by_month(field=field, restrict_to_books=book_ids)
        items = sorted(groups, reverse=True)
        return tuple(
            {
                'name': f'{year:04d}-{month:02d}',
                'count': len(groups[year, month]),
                'avg_rating': None,
                'search': '{}:>={:04d}-{:02d}-01 and {}:<{:04d}-{:02d}-01'.format(field, year, month, field, *next_month(year, month)),
            }
            for year, month in items
            if groups[year, month]
        )
    groups = db.books_by_year(field=field, restrict_to_books=book_ids)
    return tuple(
        {
            'name': f'{year:04d}',
            'count': len(groups[year]),
            'avg_rating': None,
            'search': f'{field}:>={year:04d}-01-01 and {field}:<{year + 1:04d}-01-01',
        }
        for year in sorted(groups, reverse=True)
        if groups[year]
    )


def get_library_init_data(ctx, rd, db, num, sorts, orders, vl):
    ans = {}
    with db.safe_read_lock:
        try:
            ans['search_result'] = search_result(ctx, rd, db, rd.query.get('search', ''), num, 0, ','.join(sorts), ','.join(orders), vl)
        except ParseException:
            ans['search_result'] = search_result(ctx, rd, db, '', num, 0, ','.join(sorts), ','.join(orders), vl)
        sf = db.field_metadata.ui_sortable_field_keys()
        sf.pop('ondevice', None)
        ans['sortable_fields'] = sorted(
            ((sanitize_sort_field_name(db.field_metadata, k), v) for k, v in sf.items()),
            key=lambda field_name: sort_key(field_name[1]),
        )
        ans['field_metadata'] = db.field_metadata.all_metadata()
        ans['virtual_libraries'] = db._pref('virtual_libraries', {})
        ans['bools_are_tristate'] = db._pref('bools_are_tristate', True)
        ans['book_display_fields'] = get_field_list(db)
        ans['browse_fields'] = get_browse_fields(ctx, db)
        ans['fts_enabled'] = db.is_fts_enabled()
        ans['book_details_vertical_categories'] = db._pref('book_details_vertical_categories', ())
        ans['fields_that_support_notes'] = tuple(db._field_supports_notes())
        ans['categories_using_hierarchy'] = db._pref('categories_using_hierarchy', ())
        mdata = ans['metadata'] = {}
        try:
            extra_books = {int(x) for x in rd.query.get('extra_books', '').split(',')}
        except Exception:
            extra_books = ()
        for coll in (ans['search_result']['book_ids'], extra_books):
            for book_id in coll:
                if book_id not in mdata:
                    data = book_as_json(db, book_id)
                    if data is not None:
                        mdata[book_id] = data
    return ans


@endpoint('/interface-data/books-init', postprocess=json)
def books(ctx, rd):
    """
    Get data to create list of books

    Optional: ?num=50&sort=timestamp.desc&library_id=<default library>
              &search=''&extra_books=''&vl=''
    """
    ans = {}
    try:
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: {!r}'.format(rd.query.get('num')))
    library_id, db, sorts, orders, vl = get_basic_query_data(ctx, rd)
    ans = get_library_init_data(ctx, rd, db, num, sorts, orders, vl)
    ans['library_id'] = library_id
    return ans


@endpoint('/interface-data/init', postprocess=json)
def interface_data(ctx, rd):
    """
    Return the data needed to create the server UI as well as a list of books.

    Optional: ?num=50&sort=timestamp.desc&library_id=<default library>
              &search=''&extra_books=''&vl=''
    """
    ans = basic_interface_data(ctx, rd)
    ud = {}
    if rd.username:
        # Override session data with stored values for the authenticated user,
        # if any
        ud = ctx.user_manager.get_session_data(rd.username)
        lid = ud.get('library_id')
        if lid and lid in ans['library_map']:
            rd.query.set('library_id', lid)
        usort = ud.get('sort')
        if usort:
            rd.query.set('sort', usort)
    ans['library_id'], db, sorts, orders, vl = get_basic_query_data(ctx, rd)
    ans['user_session_data'] = ud
    try:
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: {!r}'.format(rd.query.get('num')))
    ans.update(get_library_init_data(ctx, rd, db, num, sorts, orders, vl))
    return ans


@endpoint('/interface-data/newly-added', postprocess=json)
def newly_added(ctx, rd):
    """
    Get newly added books.

    Optional: ?num=3&library_id=<default library>
    """
    db, library_id = get_library_data(ctx, rd)[:2]
    count = int(rd.query.get('num', 3))
    nbids = ctx.newest_book_ids(rd, db, count=count)
    with db.safe_read_lock:
        titles = db._all_field_for('title', nbids)
        authors = db._all_field_for('authors', nbids)
    return {'library_id': library_id, 'books': nbids, 'titles': titles, 'authors': authors}


@endpoint('/interface-data/more-books', postprocess=json, methods=POSTABLE)
def more_books(ctx, rd):
    """
    Get more results from the specified search-query, which must
    be specified as JSON in the request body.

    Optional: ?num=50&library_id=<default library>
    """
    db, library_id = get_library_data(ctx, rd)[:2]

    try:
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: {!r}'.format(rd.query.get('num')))
    try:
        search_query = load_json_file(rd.request_body_file)
        query, offset, sorts, orders, vl = (
            search_query['query'],
            search_query['offset'],
            search_query['sort'],
            search_query['sort_order'],
            search_query['vl'],
        )
    except KeyError as err:
        raise HTTPBadRequest(f'Search query missing key: {as_unicode(err)}')
    except Exception as err:
        raise HTTPBadRequest(f'Invalid query: {as_unicode(err)}')
    ans = {}
    with db.safe_read_lock:
        ans['search_result'] = search_result(ctx, rd, db, query, num, offset, sorts, orders, vl)
        mdata = ans['metadata'] = {}
        for book_id in ans['search_result']['book_ids']:
            data = book_as_json(db, book_id)
            if data is not None:
                mdata[book_id] = data

    return ans


@endpoint('/interface-data/set-session-data', postprocess=json, methods=POSTABLE)
def set_session_data(ctx, rd):
    """
    Store session data persistently so that it is propagated automatically to
    new logged in clients
    """
    if rd.username:
        try:
            new_data = load_json_file(rd.request_body_file)
            if not isinstance(new_data, dict):
                raise Exception('session data must be a dict')
        except Exception as err:
            raise HTTPBadRequest(f'Invalid data: {as_unicode(err)}')
        ud = ctx.user_manager.get_session_data(rd.username)
        ud.update(new_data)
        ctx.user_manager.set_session_data(rd.username, ud)


@endpoint('/interface-data/get-books', postprocess=json)
def get_books(ctx, rd):
    """
    Get books for the specified query

    Optional: ?library_id=<default library>&num=50&sort=timestamp.desc&search=''&vl=''
    """
    library_id, db, sorts, orders, vl = get_basic_query_data(ctx, rd)
    try:
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: {!r}'.format(rd.query.get('num')))
    searchq = rd.query.get('search', '')
    db = get_library_data(ctx, rd)[0]
    ans = {}
    mdata = ans['metadata'] = {}
    with db.safe_read_lock:
        try:
            ans['search_result'] = search_result(ctx, rd, db, searchq, num, 0, ','.join(sorts), ','.join(orders), vl)
        except ParseException as err:
            # This must not be translated as it is used by the front end to
            # detect invalid search expressions
            raise HTTPBadRequest(f'Invalid search expression: {as_unicode(err)}')
        for book_id in ans['search_result']['book_ids']:
            data = book_as_json(db, book_id)
            if data is not None:
                mdata[book_id] = data
    return ans


@endpoint('/interface-data/book-metadata/{book_id=0}', postprocess=json)
def book_metadata(ctx, rd, book_id):
    """
    Get metadata for the specified book. If no book_id is specified, return metadata for a random book.

    Optional: ?library_id=<default library>&vl=<virtual library>
    """
    library_id, db, sorts, orders, vl = get_basic_query_data(ctx, rd)

    if not book_id:
        all_ids = ctx.allowed_book_ids(rd, db)
        book_id = random.choice(tuple(all_ids))
    elif not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    data = book_as_json(db, book_id)
    if data is None:
        raise BookNotFound(book_id, db)
    data['id'] = book_id  # needed for random book view (when book_id=0)
    return data


@endpoint('/web-search/{book_id}/{field}/{item_val}', postprocess=json)
def web_search(ctx, rd, book_id, field, item_val):
    """
    Redirect to a web search URL for the specified item.
    Optional: ?library_id=<default library>
    """
    db, library_id = get_library_data(ctx, rd)[:2]
    try:
        book_id = int(book_id)
    except Exception:
        raise HTTPNotFound(f'Book with id {book_id!r} does not exist')
    if db is None:
        raise HTTPNotFound(f'Library {library_id!r} not found')
    with db.safe_read_lock:
        if not ctx.has_id(rd, db, book_id):
            raise BookNotFound(book_id, db)
        url, tooltip = web_search_link(db, book_id, field, item_val)
        if url:
            raise HTTPTempRedirect(url)
    raise HTTPNotFound(f'No web search URL for {field} {item_val}')


@endpoint('/interface-data/tag-browser')
def tag_browser(ctx, rd):
    """
    Get the Tag Browser serialized as JSON
    Optional: ?library_id=<default library>&sort_tags_by=name&partition_method=first letter
              &collapse_at=25&dont_collapse=&hide_empty_categories=&vl=''
    """
    db, library_id = get_library_data(ctx, rd)[:2]
    opts = categories_settings(rd.query, db, gst_container=tuple)
    vl = rd.query.get('vl') or ''
    etag = json_dumps([db.last_modified().isoformat(), rd.username, library_id, vl, list(opts)])
    etag = hashlib.sha256(etag).hexdigest()

    def generate():
        return json(ctx, rd, tag_browser, categories_as_json(ctx, rd, db, opts, vl))

    return rd.etagged_dynamic_response(etag, generate)


@endpoint('/interface-data/browse-field/{field}', postprocess=json)
def browse_field(ctx, rd, field):
    """
    Get browse-list items for the specified metadata field.
    Optional: ?library_id=<default library>&vl=&date_group=y
    """
    db = get_library_data(ctx, rd)[0]
    fields = browse_field_map(ctx, db)
    field_data = fields.get(field)
    if field_data is None:
        raise HTTPNotFound(f'{field} is not a browse field')
    vl = rd.query.get('vl') or ''
    if field_data['kind'] == 'date':
        items = date_browse_items(ctx, rd, db, field, vl)
    else:
        items = category_browse_items(ctx, rd, db, field, vl)
    return {'field': field, 'items': items}


_all_lang_names_cache: tuple | None = None


def all_lang_names():
    global _all_lang_names_cache
    if _all_lang_names_cache is None:
        _all_lang_names_cache = tuple(sorted(lang_map_for_ui().values(), key=numeric_sort_key))
    return _all_lang_names_cache


@endpoint('/interface-data/field-names/{field}', postprocess=json)
def field_names(ctx, rd, field):
    """
    Get a list of all names for the specified field
    Optional: ?library_id=<default library>
    """
    if field == 'languages':
        ans = all_lang_names()
    else:
        db, library_id = get_library_data(ctx, rd)[:2]
        try:
            ans = tuple(sorted(db.all_field_names(field), key=numeric_sort_key))
        except ValueError:
            raise HTTPNotFound(f'{field} is not a one-one or many-one field')
    return ans


@endpoint('/interface-data/field-id-map/{field}', postprocess=json)
def field_id_map(ctx, rd, field):
    """
    Get a map of all ids:names for the specified field
    Optional: ?library_id=<default library>
    """
    db, library_id = get_library_data(ctx, rd)[:2]
    try:
        return db.get_id_map(field)
    except ValueError:
        raise HTTPNotFound(f'{field} is not a one-one or many-one field')
