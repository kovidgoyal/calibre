#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import, print_function)
import hashlib, random, zipfile, shutil, sys
from json import load as load_json_file

from calibre import as_unicode
from calibre.customize.ui import available_input_formats
from calibre.db.view import sanitize_sort_field_name
from calibre.srv.ajax import search_result
from calibre.srv.errors import HTTPNotFound, HTTPBadRequest
from calibre.srv.metadata import book_as_json, categories_as_json, icon_map
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data, get_use_roman
from calibre.utils.config import prefs, tweaks
from calibre.utils.icu import sort_key
from calibre.utils.localization import get_lang
from calibre.utils.search_query_parser import ParseException

POSTABLE = frozenset({'GET', 'POST', 'HEAD'})


@endpoint('', auth_required=False)
def index(ctx, rd):
    return lopen(P('content-server/index-generated.html'), 'rb')


@endpoint('/calibre.appcache', auth_required=False, cache_control='no-cache')
def appcache(ctx, rd):
    return lopen(P('content-server/calibre.appcache'), 'rb')


@endpoint('/robots.txt', auth_required=False)
def robots(ctx, rd):
    return b'User-agent: *\nDisallow: /'


@endpoint('/auto-reload-port', auth_required=False, cache_control='no-cache')
def auto_reload(ctx, rd):
    auto_reload_port = getattr(rd.opts, 'auto_reload_port', 0)
    rd.outheaders.set('Content-Type', 'text/plain')
    return str(max(0, auto_reload_port))


@endpoint('/console-print', methods=('POST', ))
def console_print(ctx, rd):
    if not getattr(rd.opts, 'allow_console_print', False):
        raise HTTPNotFound('console printing is not allowed')
    shutil.copyfileobj(rd.request_body_file, sys.stdout)
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
    return library_id, db, sorts, orders


_cached_translations = None


def get_translations():
    global _cached_translations
    if _cached_translations is None:
        _cached_translations = False
        with zipfile.ZipFile(
            P('content-server/locales.zip', allow_user_override=False), 'r'
        ) as zf:
            names = set(zf.namelist())
            lang = get_lang()
            if lang not in names:
                xlang = lang.split('_')[0].lower()
                if xlang in names:
                    lang = xlang
            if lang in names:
                _cached_translations = load_json_file(zf.open(lang, 'r'))
    return _cached_translations


DEFAULT_NUMBER_OF_BOOKS = 50


def basic_interface_data(ctx, rd):
    ans = {
        'username': rd.username,
        'output_format': prefs['output_format'].upper(),
        'input_formats': {x.upper(): True
                          for x in available_input_formats()},
        'gui_pubdate_display_format': tweaks['gui_pubdate_display_format'],
        'gui_timestamp_display_format': tweaks['gui_timestamp_display_format'],
        'gui_last_modified_display_format':
        tweaks['gui_last_modified_display_format'],
        'use_roman_numerals_for_series_number': get_use_roman(),
        'translations': get_translations(),
        'allow_console_print': getattr(rd.opts, 'allow_console_print', False),
        'icon_map': icon_map(),
        'icon_path': ctx.url_for('/icon', which=''),
    }
    ans['library_map'], ans['default_library_id'] = ctx.library_info(rd)
    return ans


@endpoint('/interface-data/update', postprocess=json)
def update_interface_data(ctx, rd):
    '''
    Return the interface data needed for the server UI
    '''
    return basic_interface_data(ctx, rd)


def get_library_init_data(ctx, rd, db, num, sorts, orders):
    ans = {}
    with db.safe_read_lock:
        try:
            ans['search_result'] = search_result(
                ctx, rd, db,
                rd.query.get('search', ''), num, 0, ','.join(sorts),
                ','.join(orders)
            )
        except ParseException:
            ans['search_result'] = search_result(
                ctx, rd, db, '', num, 0, ','.join(sorts), ','.join(orders)
            )
        sf = db.field_metadata.ui_sortable_field_keys()
        sf.pop('ondevice', None)
        ans['sortable_fields'] = sorted(
            ((sanitize_sort_field_name(db.field_metadata, k), v)
             for k, v in sf.iteritems()),
            key=lambda (field, name): sort_key(name)
        )
        ans['field_metadata'] = db.field_metadata.all_metadata()
        mdata = ans['metadata'] = {}
        try:
            extra_books = set(
                int(x) for x in rd.query.get('extra_books', '').split(',')
            )
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
    '''
    Get data to create list of books

    Optional: ?num=50&sort=timestamp.desc&library_id=<default library>
              &search=''&extra_books=''
    '''
    ans = {}
    try:
        num = int(rd.query.get('num', DEFAULT_NUMBER_OF_BOOKS))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    library_id, db, sorts, orders = get_basic_query_data(ctx, rd)
    ans = get_library_init_data(ctx, rd, db, num, sorts, orders)
    ans['library_id'] = library_id
    return ans


@endpoint('/interface-data/init', postprocess=json)
def interface_data(ctx, rd):
    '''
    Return the data needed to create the server UI as well as a list of books.

    Optional: ?num=50&sort=timestamp.desc&library_id=<default library>
              &search=''&extra_books=''
    '''
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
    ans['library_id'], db, sorts, orders = get_basic_query_data(ctx, rd)
    ans['user_session_data'] = ud
    try:
        num = int(rd.query.get('num', DEFAULT_NUMBER_OF_BOOKS))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    ans.update(get_library_init_data(ctx, rd, db, num, sorts, orders))
    return ans


@endpoint('/interface-data/more-books', postprocess=json, methods=POSTABLE)
def more_books(ctx, rd):
    '''
    Get more results from the specified search-query, which must
    be specified as JSON in the request body.

    Optional: ?num=50&library_id=<default library>
    '''
    db, library_id = get_library_data(ctx, rd)[:2]

    try:
        num = int(rd.query.get('num', DEFAULT_NUMBER_OF_BOOKS))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    try:
        search_query = load_json_file(rd.request_body_file)
        query, offset, sorts, orders = search_query['query'], search_query[
            'offset'
        ], search_query['sort'], search_query['sort_order']
    except KeyError as err:
        raise HTTPBadRequest('Search query missing key: %s' % as_unicode(err))
    except Exception as err:
        raise HTTPBadRequest('Invalid query: %s' % as_unicode(err))
    ans = {}
    with db.safe_read_lock:
        ans['search_result'] = search_result(
            ctx, rd, db, query, num, offset, sorts, orders
        )
        mdata = ans['metadata'] = {}
        for book_id in ans['search_result']['book_ids']:
            data = book_as_json(db, book_id)
            if data is not None:
                mdata[book_id] = data

    return ans


@endpoint('/interface-data/set-session-data', postprocess=json, methods=POSTABLE)
def set_session_data(ctx, rd):
    '''
    Store session data persistently so that it is propagated automatically to
    new logged in clients
    '''
    if rd.username:
        try:
            new_data = load_json_file(rd.request_body_file)
            if not isinstance(new_data, dict):
                raise Exception('session data must be a dict')
        except Exception as err:
            raise HTTPBadRequest('Invalid data: %s' % as_unicode(err))
        ud = ctx.user_manager.get_session_data(rd.username)
        ud.update(new_data)
        ctx.user_manager.set_session_data(rd.username, ud)


@endpoint('/interface-data/get-books', postprocess=json)
def get_books(ctx, rd):
    '''
    Get books for the specified query

    Optional: ?library_id=<default library>&num=50&sort=timestamp.desc&search=''
    '''
    library_id, db, sorts, orders = get_basic_query_data(ctx, rd)
    try:
        num = int(rd.query.get('num', DEFAULT_NUMBER_OF_BOOKS))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    searchq = rd.query.get('search', '')
    db = get_library_data(ctx, rd)[0]
    ans = {}
    mdata = ans['metadata'] = {}
    with db.safe_read_lock:
        try:
            ans['search_result'] = search_result(
                ctx, rd, db, searchq, num, 0, ','.join(sorts), ','.join(orders)
            )
        except ParseException as err:
            # This must not be translated as it is used by the front end to
            # detect invalid search expressions
            raise HTTPBadRequest('Invalid search expression: %s' % as_unicode(err))
        for book_id in ans['search_result']['book_ids']:
            data = book_as_json(db, book_id)
            if data is not None:
                mdata[book_id] = data
    return ans


@endpoint('/interface-data/book-metadata/{book_id=0}', postprocess=json)
def book_metadata(ctx, rd, book_id):
    '''
    Get metadata for the specified book. If no book_id is specified, return metadata for a random book.

    Optional: ?library_id=<default library>
    '''
    library_id, db = get_basic_query_data(ctx, rd)[:2]
    book_ids = ctx.allowed_book_ids(rd, db)

    def notfound():
        raise HTTPNotFound(_('No book with id: %d in library') % book_id)

    if not book_ids:
        notfound()
    if not book_id:
        book_id = random.choice(tuple(book_ids))
    elif book_id not in book_ids:
        notfound()
    data = book_as_json(db, book_id)
    if data is None:
        notfound()
    data['id'] = book_id  # needed for random book view (when book_id=0)
    return data


@endpoint('/interface-data/tag-browser')
def tag_browser(ctx, rd):
    '''
    Get the Tag Browser serialized as JSON
    Optional: ?library_id=<default library>&sort_tags_by=name&partition_method=first letter
              &collapse_at=25&dont_collapse=&hide_empty_categories=
    '''
    db, library_id = get_library_data(ctx, rd)[:2]
    etag = '%s||%s||%s' % (db.last_modified(), rd.username, library_id)
    etag = hashlib.sha1(etag.encode('utf-8')).hexdigest()

    def generate():
        db, library_id = get_library_data(ctx, rd)[:2]
        return json(ctx, rd, tag_browser, categories_as_json(ctx, rd, db))

    return rd.etagged_dynamic_response(etag, generate)
