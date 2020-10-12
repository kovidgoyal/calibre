#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import hashlib
import random
import shutil
import sys
import zipfile
from json import load as load_json_file, loads as json_loads
from threading import Lock

from calibre import as_unicode
from calibre.constants import in_develop_mode
from calibre.customize.ui import available_input_formats
from calibre.db.view import sanitize_sort_field_name
from calibre.srv.ajax import search_result
from calibre.srv.errors import (
    BookNotFound, HTTPBadRequest, HTTPForbidden, HTTPNotFound
)
from calibre.srv.metadata import (
    book_as_json, categories_as_json, categories_settings, icon_map
)
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data, get_use_roman
from calibre.utils.config import prefs, tweaks
from calibre.utils.icu import numeric_sort_key, sort_key
from calibre.utils.localization import (
    get_lang, lang_map_for_ui, localize_website_link
)
from calibre.utils.search_query_parser import ParseException
from calibre.utils.serialize import json_dumps
from polyglot.builtins import iteritems, itervalues

POSTABLE = frozenset({'GET', 'POST', 'HEAD'})


@endpoint('', auth_required=False)
def index(ctx, rd):
    ans_file = lopen(P('content-server/index-generated.html'), 'rb')
    if not in_develop_mode:
        return ans_file
    return ans_file.read().replace(b'__IN_DEVELOP_MODE__', b'1')


@endpoint('/robots.txt', auth_required=False)
def robots(ctx, rd):
    return b'User-agent: *\nDisallow: /'


@endpoint('/ajax-setup', auth_required=False, cache_control='no-cache', postprocess=json)
def ajax_setup(ctx, rd):
    auto_reload_port = getattr(rd.opts, 'auto_reload_port', 0)
    return {
        'auto_reload_port': max(0, auto_reload_port),
        'allow_console_print': bool(getattr(rd.opts, 'allow_console_print', False)),
        'ajax_timeout': rd.opts.ajax_timeout,
    }


print_lock = Lock()


@endpoint('/console-print', methods=('POST', ))
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


def get_translations_data():
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
            return zf.open(lang, 'r').read()


def get_translations():
    if not hasattr(get_translations, 'cached'):
        get_translations.cached = False
        data = get_translations_data()
        if data:
            get_translations.cached = json_loads(data)
    return get_translations.cached


def custom_list_template():
    ans = getattr(custom_list_template, 'ans', None)
    if ans is None:
        ans = {
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
            ]
        }
        custom_list_template.ans = ans
    return ans


def basic_interface_data(ctx, rd):
    ans = {
        'username': rd.username,
        'output_format': prefs['output_format'].upper(),
        'input_formats': {x.upper(): True
                          for x in available_input_formats()},
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
        'donate_link': localize_website_link('https://calibre-ebook.com/donate')
    }
    ans['library_map'], ans['default_library_id'] = ctx.library_info(rd)
    return ans


@endpoint('/interface-data/update/{translations_hash=None}', postprocess=json)
def update_interface_data(ctx, rd, translations_hash):
    '''
    Return the interface data needed for the server UI
    '''
    ans = basic_interface_data(ctx, rd)
    t = ans['translations']
    if t and (t.get('hash') or translations_hash) and t.get('hash') == translations_hash:
        del ans['translations']
    return ans


def get_field_list(db):
    fieldlist = list(db.pref('book_display_fields', ()))
    names = frozenset([x[0] for x in fieldlist])
    available = frozenset(db.field_metadata.displayable_field_keys())
    for field in available:
        if field not in names:
            fieldlist.append((field, True))
    return [f for f, d in fieldlist if d and f in available]


def get_library_init_data(ctx, rd, db, num, sorts, orders, vl):
    ans = {}
    with db.safe_read_lock:
        try:
            ans['search_result'] = search_result(
                ctx, rd, db,
                rd.query.get('search', ''), num, 0, ','.join(sorts),
                ','.join(orders), vl
            )
        except ParseException:
            ans['search_result'] = search_result(
                ctx, rd, db, '', num, 0, ','.join(sorts), ','.join(orders), vl
            )
        sf = db.field_metadata.ui_sortable_field_keys()
        sf.pop('ondevice', None)
        ans['sortable_fields'] = sorted(
            ((sanitize_sort_field_name(db.field_metadata, k), v)
             for k, v in iteritems(sf)),
            key=lambda field_name: sort_key(field_name[1])
        )
        ans['field_metadata'] = db.field_metadata.all_metadata()
        ans['virtual_libraries'] = db._pref('virtual_libraries', {})
        ans['book_display_fields'] = get_field_list(db)
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
              &search=''&extra_books=''&vl=''
    '''
    ans = {}
    try:
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    library_id, db, sorts, orders, vl = get_basic_query_data(ctx, rd)
    ans = get_library_init_data(ctx, rd, db, num, sorts, orders, vl)
    ans['library_id'] = library_id
    return ans


@endpoint('/interface-data/init', postprocess=json)
def interface_data(ctx, rd):
    '''
    Return the data needed to create the server UI as well as a list of books.

    Optional: ?num=50&sort=timestamp.desc&library_id=<default library>
              &search=''&extra_books=''&vl=''
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
    ans['library_id'], db, sorts, orders, vl = get_basic_query_data(ctx, rd)
    ans['user_session_data'] = ud
    try:
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    ans.update(get_library_init_data(ctx, rd, db, num, sorts, orders, vl))
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
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    try:
        search_query = load_json_file(rd.request_body_file)
        query, offset, sorts, orders, vl = search_query['query'], search_query[
            'offset'
        ], search_query['sort'], search_query['sort_order'], search_query['vl']
    except KeyError as err:
        raise HTTPBadRequest('Search query missing key: %s' % as_unicode(err))
    except Exception as err:
        raise HTTPBadRequest('Invalid query: %s' % as_unicode(err))
    ans = {}
    with db.safe_read_lock:
        ans['search_result'] = search_result(
            ctx, rd, db, query, num, offset, sorts, orders, vl
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

    Optional: ?library_id=<default library>&num=50&sort=timestamp.desc&search=''&vl=''
    '''
    library_id, db, sorts, orders, vl = get_basic_query_data(ctx, rd)
    try:
        num = int(rd.query.get('num', rd.opts.num_per_page))
    except Exception:
        raise HTTPNotFound('Invalid number of books: %r' % rd.query.get('num'))
    searchq = rd.query.get('search', '')
    db = get_library_data(ctx, rd)[0]
    ans = {}
    mdata = ans['metadata'] = {}
    with db.safe_read_lock:
        try:
            ans['search_result'] = search_result(
                ctx, rd, db, searchq, num, 0, ','.join(sorts), ','.join(orders), vl
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

    Optional: ?library_id=<default library>&vl=<virtual library>
    '''
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


@endpoint('/interface-data/tag-browser')
def tag_browser(ctx, rd):
    '''
    Get the Tag Browser serialized as JSON
    Optional: ?library_id=<default library>&sort_tags_by=name&partition_method=first letter
              &collapse_at=25&dont_collapse=&hide_empty_categories=&vl=''
    '''
    db, library_id = get_library_data(ctx, rd)[:2]
    opts = categories_settings(rd.query, db, gst_container=tuple)
    vl = rd.query.get('vl') or ''
    etag = json_dumps([db.last_modified().isoformat(), rd.username, library_id, vl, list(opts)])
    etag = hashlib.sha1(etag).hexdigest()

    def generate():
        return json(ctx, rd, tag_browser, categories_as_json(ctx, rd, db, opts, vl))

    return rd.etagged_dynamic_response(etag, generate)


def all_lang_names():
    ans = getattr(all_lang_names, 'ans', None)
    if ans is None:
        ans = all_lang_names.ans = tuple(sorted(itervalues(lang_map_for_ui()), key=numeric_sort_key))
    return ans


@endpoint('/interface-data/field-names/{field}', postprocess=json)
def field_names(ctx, rd, field):
    '''
    Get a list of all names for the specified field
    Optional: ?library_id=<default library>
    '''
    if field == 'languages':
        ans = all_lang_names()
    else:
        db, library_id = get_library_data(ctx, rd)[:2]
        ans = tuple(sorted(db.all_field_names(field), key=numeric_sort_key))
    return ans
