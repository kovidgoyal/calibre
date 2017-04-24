#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial
from future_builtins import zip
from itertools import cycle

from calibre import force_unicode
from calibre.library.field_metadata import category_icon_map
from calibre.db.view import sanitize_sort_field_name
from calibre.ebooks.metadata import title_sort
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.content import get as get_content, icon as get_icon
from calibre.srv.utils import http_date, custom_fields_to_display, encode_name, decode_name, get_db
from calibre.utils.config import prefs, tweaks
from calibre.utils.date import isoformat, timestampfromdt
from calibre.utils.icu import numeric_sort_key as sort_key


def ensure_val(x, *allowed):
    if x not in allowed:
        x = allowed[0]
    return x


def get_pagination(query, num=100, offset=0):
    try:
        num = int(query.get('num', num))
    except:
        raise HTTPNotFound("Invalid num")
    try:
        offset = int(query.get('offset', offset))
    except:
        raise HTTPNotFound("Invalid offset")
    return num, offset


def category_icon(category, meta):  # {{{
    if category in category_icon_map:
        icon = category_icon_map[category]
    elif meta['is_custom']:
        icon = category_icon_map['custom:']
    elif meta['kind'] == 'user':
        icon = category_icon_map['user:']
    else:
        icon = 'blank.png'
    return icon
# }}}

# Book metadata {{{


def book_to_json(ctx, rd, db, book_id,
                 get_category_urls=True, device_compatible=False, device_for_template=None):
    mi = db.get_metadata(book_id, get_cover=False)
    codec = JsonCodec(db.field_metadata)
    if not device_compatible:
        try:
            mi.rating = mi.rating/2.
        except Exception:
            mi.rating = 0.0
    data = codec.encode_book_metadata(mi)
    for x in ('publication_type', 'size', 'db_id', 'lpath', 'mime',
            'rights', 'book_producer'):
        data.pop(x, None)

    get = partial(ctx.url_for, get_content, book_id=book_id, library_id=db.server_library_id)
    data['cover'] = get(what='cover')
    data['thumbnail'] = get(what='thumb')

    if not device_compatible:
        mi.format_metadata = {k.lower():dict(v) for k, v in
                mi.format_metadata.iteritems()}
        for v in mi.format_metadata.itervalues():
            mtime = v.get('mtime', None)
            if mtime is not None:
                v['mtime'] = isoformat(mtime, as_utc=True)
        data['format_metadata'] = mi.format_metadata
        fmts = set(x.lower() for x in mi.format_metadata.iterkeys())
        pf = prefs['output_format'].lower()
        other_fmts = list(fmts)
        try:
            fmt = pf if pf in fmts else other_fmts[0]
        except:
            fmt = None
        if fmts and fmt:
            other_fmts = [x for x in fmts if x != fmt]
        data['formats'] = sorted(fmts)
        if fmt:
            data['main_format'] = {fmt:get(what=fmt)}
        else:
            data['main_format'] = None
        data['other_formats'] = {fmt:get(what=fmt) for fmt in other_fmts}

        if get_category_urls:
            category_urls = data['category_urls'] = {}
            all_cats = ctx.get_categories(rd, db)
            for key in mi.all_field_keys():
                fm = mi.metadata_for_field(key)
                if (fm and fm['is_category'] and not fm['is_csp'] and
                        key != 'formats' and fm['datatype'] != 'rating'):
                    categories = mi.get(key) or []
                    if isinstance(categories, basestring):
                        categories = [categories]
                    category_urls[key] = dbtags = {}
                    for category in categories:
                        for tag in all_cats.get(key, ()):
                            if tag.original_name == category:
                                dbtags[category] = ctx.url_for(
                                    books_in,
                                    encoded_category=encode_name(tag.category if tag.category else key),
                                    encoded_item=encode_name(tag.original_name if tag.id is None else unicode(tag.id)),
                                    library_id=db.server_library_id
                                )
                                break
    else:
        series = data.get('series', None) or ''
        if series:
            tsorder = tweaks['save_template_title_series_sorting']
            series = title_sort(series, order=tsorder)
        data['_series_sort_'] = series
        if device_for_template:
            import posixpath
            from calibre.devices.utils import create_upload_path
            from calibre.utils.filenames import ascii_filename as sanitize
            from calibre.customize.ui import device_plugins

            for device_class in device_plugins():
                if device_class.__class__.__name__ == device_for_template:
                    template = device_class.save_template()
                    data['_filename_'] = create_upload_path(mi, book_id,
                            template, sanitize, path_type=posixpath)
                    break

    return data, mi.last_modified


@endpoint('/ajax/book/{book_id}/{library_id=None}', postprocess=json)
def book(ctx, rd, book_id, library_id):
    '''
    Return the metadata of the book as a JSON dictionary.

    Query parameters: ?category_urls=true&id_is_uuid=false&device_for_template=None

    If category_urls is true the returned dictionary also contains a
    mapping of category (field) names to URLs that return the list of books in the
    given category.

    If id_is_uuid is true then the book_id is assumed to be a book uuid instead.
    '''
    db = get_db(ctx, rd, library_id)
    with db.safe_read_lock:
        id_is_uuid = rd.query.get('id_is_uuid', 'false')
        oid = book_id
        if id_is_uuid == 'true':
            book_id = db.lookup_by_uuid(book_id)
        else:
            try:
                book_id = int(book_id)
                if not db.has_id(book_id):
                    book_id = None
            except Exception:
                book_id = None
        if book_id is None or not db.has_id(book_id):
            raise HTTPNotFound('Book with id %r does not exist' % oid)
        category_urls = rd.query.get('category_urls', 'true').lower()
        device_compatible = rd.query.get('device_compatible', 'false').lower()
        device_for_template = rd.query.get('device_for_template', None)

        data, last_modified = book_to_json(ctx, rd, db, book_id,
                get_category_urls=category_urls == 'true',
                device_compatible=device_compatible == 'true',
                device_for_template=device_for_template)
    rd.outheaders['Last-Modified'] = http_date(timestampfromdt(last_modified))
    return data


@endpoint('/ajax/books/{library_id=None}', postprocess=json)
def books(ctx, rd, library_id):
    '''
    Return the metadata for the books as a JSON dictionary.

    Query parameters: ?ids=all&category_urls=true&id_is_uuid=false&device_for_template=None

    If category_urls is true the returned dictionary also contains a
    mapping of category (field) names to URLs that return the list of books in the
    given category.

    If id_is_uuid is true then the book_id is assumed to be a book uuid instead.
    '''
    db = get_db(ctx, rd, library_id)
    with db.safe_read_lock:
        id_is_uuid = rd.query.get('id_is_uuid', 'false')
        ids = rd.query.get('ids')
        if ids is None or ids == 'all':
            ids = db.all_book_ids()
        else:
            ids = ids.split(',')
            if id_is_uuid == 'true':
                ids = {db.lookup_by_uuid(x) for x in ids}
                ids.discard(None)
            else:
                try:
                    ids = {int(x) for x in ids}
                except Exception:
                    raise HTTPNotFound('ids must a comma separated list of integers')
        last_modified = None
        category_urls = rd.query.get('category_urls', 'true').lower() == 'true'
        device_compatible = rd.query.get('device_compatible', 'false').lower() == 'true'
        device_for_template = rd.query.get('device_for_template', None)
        ans = {}
        for book_id in ids:
            if not db.has_id(book_id):
                ans[book_id] = None
                continue
            data, lm = book_to_json(
                ctx, rd, db, book_id, get_category_urls=category_urls,
                device_compatible=device_compatible, device_for_template=device_for_template)
            last_modified = lm if last_modified is None else max(lm, last_modified)
            ans[book_id] = data
    if last_modified is not None:
        rd.outheaders['Last-Modified'] = http_date(timestampfromdt(last_modified))
    return ans

# }}}

# Categories (Tag Browser)  {{{


@endpoint('/ajax/categories/{library_id=None}', postprocess=json)
def categories(ctx, rd, library_id):
    '''
    Return the list of top-level categories as a list of dictionaries. Each
    dictionary is of the form::
        {
        'name': Display Name,
        'url':URL that gives the JSON object corresponding to all entries in this category,
        'icon': URL to icon of this category,
        'is_category': False for the All Books and Newest categories, True for everything else
        }

    '''
    db = get_db(ctx, rd, library_id)
    with db.safe_read_lock:
        ans = {}
        categories = ctx.get_categories(rd, db, vl=rd.query.get('vl') or '')
        category_meta = db.field_metadata
        library_id = db.server_library_id

        def getter(x):
            return category_meta[x]['name']

        displayed_custom_fields = custom_fields_to_display(db)

        for category in sorted(categories, key=lambda x: sort_key(getter(x))):
            if len(categories[category]) == 0:
                continue
            if category in ('formats', 'identifiers'):
                continue
            meta = category_meta.get(category, None)
            if meta is None:
                continue
            if category_meta.is_ignorable_field(category) and \
                        category not in displayed_custom_fields:
                continue
            display_name = meta['name']
            if category.startswith('@'):
                category = category.partition('.')[0]
                display_name = category[1:]
            url = force_unicode(category)
            icon = category_icon(category, meta)
            ans[url] = (display_name, icon)

        ans = [{'url':k, 'name':v[0], 'icon':v[1], 'is_category':True}
                for k, v in ans.iteritems()]
        ans.sort(key=lambda x: sort_key(x['name']))
        for name, url, icon in [
                (_('All books'), 'allbooks', 'book.png'),
                (_('Newest'), 'newest', 'forward.png'),
                ]:
            ans.insert(0, {'name':name, 'url':url, 'icon':icon,
                'is_category':False})

        for c in ans:
            c['url'] = ctx.url_for(globals()['category'], encoded_name=encode_name(c['url']), library_id=library_id)
            c['icon'] = ctx.url_for(get_icon, which=c['icon'])

        return ans


@endpoint('/ajax/category/{encoded_name}/{library_id=None}', postprocess=json)
def category(ctx, rd, encoded_name, library_id):
    '''
    Return a dictionary describing the category specified by name. The

    Optional: ?num=100&offset=0&sort=name&sort_order=asc

    The dictionary looks like::

        {
            'category_name': Category display name,
            'base_url': Base URL for this category,
            'total_num': Total numberof items in this category,
            'offset': The offset for the items returned in this result,
            'num': The number of items returned in this result,
            'sort': How the returned items are sorted,
            'sort_order': asc or desc
            'subcategories': List of sub categories of this category.
            'items': List of items in this category,
        }

    Each subcategory is a dictionary of the same form as those returned by
    /ajax/categories

    Each  item is a dictionary of the form::

        {
            'name': Display name,
            'average_rating': Average rating for books in this item,
            'count': Number of books in this item,
            'url': URL to get list of books in this item,
            'has_children': If True this item contains sub categories, look
            for an entry corresponding to this item in subcategories int he
            main dictionary,
        }

    :param sort: How to sort the returned items. Choices are: name, rating,
                    popularity
    :param sort_order: asc or desc

    To learn how to create subcategories see
    https://manual.calibre-ebook.com/sub_groups.html
    '''

    db = get_db(ctx, rd, library_id)
    with db.safe_read_lock:
        num, offset = get_pagination(rd.query)
        sort, sort_order = rd.query.get('sort'), rd.query.get('sort_order')
        sort = ensure_val(sort, 'name', 'rating', 'popularity')
        sort_order = ensure_val(sort_order, 'asc', 'desc')
        try:
            dname = decode_name(encoded_name)
        except:
            raise HTTPNotFound('Invalid encoding of category name %r'%encoded_name)
        base_url = ctx.url_for(globals()['category'], encoded_name=encoded_name, library_id=db.server_library_id)

        if dname in ('newest', 'allbooks'):
            sort, sort_order = 'timestamp', 'desc'
            rd.query['sort'], rd.query['sort_order'] = sort, sort_order
            return books_in(ctx, rd, encoded_name, encode_name('0'), library_id)

        fm = db.field_metadata
        categories = ctx.get_categories(rd, db)
        hierarchical_categories = db.pref('categories_using_hierarchy', ())

        subcategory = dname
        toplevel = subcategory.partition('.')[0]
        if toplevel == subcategory:
            subcategory = None
        if toplevel not in categories or toplevel not in fm:
            raise HTTPNotFound('Category %r not found'%toplevel)

        # Find items and sub categories
        subcategories = []
        meta = fm[toplevel]
        item_names = {}
        children = set()

        if meta['kind'] == 'user':
            fullname = ((toplevel + '.' + subcategory) if subcategory is not
                                None else toplevel)
            try:
                # User categories cannot be applied to books, so this is the
                # complete set of items, no need to consider sub categories
                items = categories[fullname]
            except:
                raise HTTPNotFound('User category %r not found'%fullname)

            parts = fullname.split('.')
            for candidate in categories:
                cparts = candidate.split('.')
                if len(cparts) == len(parts)+1 and cparts[:-1] == parts:
                    subcategories.append({'name':cparts[-1],
                        'url':candidate,
                        'icon':category_icon(toplevel, meta)})

            category_name = toplevel[1:].split('.')
            # When browsing by user categories we ignore hierarchical normal
            # columns, so children can be empty

        elif toplevel in hierarchical_categories:
            items = []

            category_names = [x.original_name.split('.') for x in categories[toplevel] if
                    '.' in x.original_name]

            if subcategory is None:
                children = set(x[0] for x in category_names)
                category_name = [meta['name']]
                items = [x for x in categories[toplevel] if '.' not in x.original_name]
            else:
                subcategory_parts = subcategory.split('.')[1:]
                category_name = [meta['name']] + subcategory_parts

                lsp = len(subcategory_parts)
                children = set('.'.join(x) for x in category_names if len(x) ==
                        lsp+1 and x[:lsp] == subcategory_parts)
                items = [x for x in categories[toplevel] if x.original_name in
                        children]
                item_names = {x:x.original_name.rpartition('.')[-1] for x in
                        items}
                # Only mark the subcategories that have children themselves as
                # subcategories
                children = set('.'.join(x[:lsp+1]) for x in category_names if len(x) >
                        lsp+1 and x[:lsp] == subcategory_parts)
            subcategories = [{'name':x.rpartition('.')[-1],
                'url':toplevel+'.'+x,
                'icon':category_icon(toplevel, meta)} for x in children]
        else:
            items = categories[toplevel]
            category_name = meta['name']

        for x in subcategories:
            x['url'] = ctx.url_for(globals()['category'], encoded_name=encode_name(x['url']), library_id=db.server_library_id)
            x['icon'] = ctx.url_for(get_icon, which=x['icon'])
            x['is_category'] = True

        sort_keygen = {
                'name': lambda x: sort_key(x.sort if x.sort else x.original_name),
                'popularity': lambda x: x.count,
                'rating': lambda x: x.avg_rating
        }
        items.sort(key=sort_keygen[sort], reverse=sort_order == 'desc')
        total_num = len(items)
        items = items[offset:offset+num]
        items = [{
            'name':item_names.get(x, x.original_name),
            'average_rating': x.avg_rating,
            'count': x.count,
            'url': ctx.url_for(books_in, encoded_category=encode_name(x.category if x.category else toplevel),
                               encoded_item=encode_name(x.original_name if x.id is None else unicode(x.id)),
                               library_id=db.server_library_id
                               ),
            'has_children': x.original_name in children,
            } for x in items]

        return {
                'category_name': category_name,
                'base_url': base_url,
                'total_num': total_num,
                'offset':offset, 'num':len(items), 'sort':sort,
                'sort_order':sort_order,
                'subcategories':subcategories,
                'items':items,
        }


@endpoint('/ajax/books_in/{encoded_category}/{encoded_item}/{library_id=None}', postprocess=json)
def books_in(ctx, rd, encoded_category, encoded_item, library_id):
    '''
    Return the books (as list of ids) present in the specified category.

    Optional: ?num=100&offset=0&sort=title&sort_order=asc&get_additional_fields=
    '''
    db = get_db(ctx, rd, library_id)
    with db.safe_read_lock:
        try:
            dname, ditem = map(decode_name, (encoded_category, encoded_item))
        except:
            raise HTTPNotFound('Invalid encoded param: %r' % (encoded_category, encoded_item))
        num, offset = get_pagination(rd.query)
        sort, sort_order = rd.query.get('sort', 'title'), rd.query.get('sort_order')
        sort_order = ensure_val(sort_order, 'asc', 'desc')
        sfield = sanitize_sort_field_name(db.field_metadata, sort)
        if sfield not in db.field_metadata.sortable_field_keys():
            raise HTTPNotFound('%s is not a valid sort field'%sort)

        if dname in ('allbooks', 'newest'):
            ids = db.all_book_ids()
        elif dname == 'search':
            try:
                ids = ctx.search(rd, db, 'search:"%s"'%ditem)
            except Exception:
                raise HTTPNotFound('Search: %r not understood'%ditem)
        else:
            try:
                cid = int(ditem)
            except Exception:
                raise HTTPNotFound('Category id %r not an integer'%ditem)

            if dname == 'news':
                dname = 'tags'
            ids = db.get_books_for_category(dname, cid)

        ids = db.multisort(fields=[(sfield, sort_order == 'asc')], ids_to_sort=ids)
        total_num = len(ids)
        ids = ids[offset:offset+num]

        result = {
                'total_num': total_num, 'sort_order':sort_order,
                'offset':offset, 'num':len(ids), 'sort':sort,
                'base_url':ctx.url_for(books_in, encoded_category=encoded_category, encoded_item=encoded_item, library_id=db.server_library_id),
                'book_ids':ids
        }

        get_additional_fields = rd.query.get('get_additional_fields')
        if get_additional_fields:
            additional_fields = {}
            for field in get_additional_fields.split(','):
                field = field.strip()
                if field:
                    flist = additional_fields[field] = []
                    for id_ in ids:
                        flist.append(db.field_for(field, id_, default_value=None))
            if additional_fields:
                result['additional_fields'] = additional_fields
        return result
# }}}

# Search {{{


def search_result(ctx, rd, db, query, num, offset, sort, sort_order, vl=''):
    multisort = [(sanitize_sort_field_name(db.field_metadata, s), ensure_val(o, 'asc', 'desc') == 'asc')
                 for s, o in zip(sort.split(','), cycle(sort_order.split(',')))]
    skeys = db.field_metadata.sortable_field_keys()
    for sfield, sorder in multisort:
        if sfield not in skeys:
            raise HTTPNotFound('%s is not a valid sort field'%sort)

    ids = ctx.search(rd, db, query, vl=vl)
    ids = db.multisort(fields=multisort, ids_to_sort=ids)
    total_num = len(ids)
    ids = ids[offset:offset+num]
    return {
        'total_num': total_num, 'sort_order':sort_order,
        'offset':offset, 'num':len(ids), 'sort':sort,
        'base_url':ctx.url_for(search, library_id=db.server_library_id),
        'query': query,
        'library_id': db.server_library_id,
        'book_ids':ids,
        'vl': vl,
    }


@endpoint('/ajax/search/{library_id=None}', postprocess=json)
def search(ctx, rd, library_id):
    '''
    Return the books (as list of ids) matching the specified search query.

    Optional: ?num=100&offset=0&sort=title&sort_order=asc&query=&vl=
    '''
    db = get_db(ctx, rd, library_id)
    query = rd.query.get('query')
    num, offset = get_pagination(rd.query)
    with db.safe_read_lock:
        return search_result(ctx, rd, db, query, num, offset, rd.query.get('sort', 'title'), rd.query.get('sort_order', 'asc'), rd.query.get('vl') or '')

# }}}


@endpoint('/ajax/library-info', postprocess=json)
def library_info(ctx, rd):
    ' Return info about available libraries '
    library_map, default_library = ctx.library_info(rd)
    return {'library_map':library_map, 'default_library':default_library}
