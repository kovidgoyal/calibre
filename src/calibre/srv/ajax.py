#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial
from binascii import hexlify, unhexlify

from calibre.ebooks.metadata import title_sort
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import http_date
from calibre.utils.config import prefs, tweaks
from calibre.utils.date import isoformat, timestampfromdt

def encode_name(name):
    if isinstance(name, unicode):
        name = name.encode('utf-8')
    return hexlify(name)

def decode_name(name):
    return unhexlify(name).decode('utf-8')

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

    get = partial(ctx.url_for, '/get', book_id=book_id, library_id=db.server_library_id)
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
            for key in mi.all_field_keys():
                fm = mi.metadata_for_field(key)
                if (fm and fm['is_category'] and not fm['is_csp'] and
                        key != 'formats' and fm['datatype'] != 'rating'):
                    categories = mi.get(key) or []
                    if isinstance(categories, basestring):
                        categories = [categories]
                    idmap = db.get_item_ids(key, categories)
                    category_urls[key] = dbtags = {}
                    for category, category_id in idmap.iteritems():
                        if category_id is not None:
                            dbtags[category] = ctx.url_for(
                                '/ajax/books_in', category=encode_name(key), item=encode_name(str(category_id)))
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
    db = ctx.get_library(library_id)
    if db is None:
        raise HTTPNotFound('Library %r not found' % library_id)
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
        if book_id is None:
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
    db = ctx.get_library(library_id)
    if db is None:
        raise HTTPNotFound('Library %r not found' % library_id)
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
        restricted_to = ctx.restrict_to_ids(db, rd)
        for book_id in ids:
            if book_id not in restricted_to:
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

@endpoint('/ajax/books_in/{category}/{item}', postprocess=json)
def books_in(ctx, rd, category, item):
    raise NotImplementedError('TODO: Implement this')
