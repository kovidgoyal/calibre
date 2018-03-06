#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from functools import partial
from io import BytesIO

from calibre import as_unicode, sanitize_file_name_unicode
from calibre.db.cli import module_for_cmd
from calibre.ebooks.metadata.meta import get_metadata
from calibre.srv.changes import books_added, books_deleted
from calibre.srv.errors import HTTPBadRequest, HTTPForbidden, HTTPNotFound
from calibre.srv.routes import endpoint, json, msgpack_or_json
from calibre.srv.utils import get_db, get_library_data
from calibre.utils.serialize import MSGPACK_MIME, json_loads, msgpack_loads
from calibre.srv.metadata import book_as_json

receive_data_methods = {'GET', 'POST'}


@endpoint('/cdb/cmd/{which}/{version=0}', postprocess=msgpack_or_json, methods=receive_data_methods, cache_control='no-cache')
def cdb_run(ctx, rd, which, version):
    try:
        m = module_for_cmd(which)
    except ImportError:
        raise HTTPNotFound('No module named: {}'.format(which))
    if not getattr(m, 'readonly', False):
        ctx.check_for_write_access(rd)
    if getattr(m, 'version', 0) != int(version):
        raise HTTPNotFound(('The module {} is not available in version: {}.'
                           'Make sure the version of calibre used for the'
                            ' server and calibredb match').format(which, version))
    db = get_library_data(ctx, rd, strict_library_id=True)[0]
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot use the command-line db interface with a user who has per library restrictions')
    raw = rd.read()
    ct = rd.inheaders.get('Content-Type', all=True)
    ct = {x.lower().partition(';')[0] for x in ct}
    try:
        if MSGPACK_MIME in ct:
            args = msgpack_loads(raw)
        elif 'application/json' in ct:
            args = json_loads(raw)
        else:
            raise HTTPBadRequest('Only JSON or msgpack requests are supported')
    except Exception:
        raise HTTPBadRequest('args are not valid encoded data')
    if getattr(m, 'needs_srv_ctx', False):
        args = [ctx] + list(args)
    try:
        result = m.implementation(db, partial(ctx.notify_changes, db.backend.library_path), *args)
    except Exception as err:
        import traceback
        return {'err': as_unicode(err), 'tb': traceback.format_exc()}
    return {'result': result}


@endpoint('/cdb/add-book/{job_id}/{add_duplicates}/{filename}/{library_id=None}',
          needs_db_write=True, postprocess=json, methods=receive_data_methods, cache_control='no-cache')
def cdb_add_book(ctx, rd, job_id, add_duplicates, filename, library_id):
    '''
    Add a file as a new book. The file contents must be in the body of the request.

    The response will also have the title/authors/languages read from the
    metadata of the file/filename. It will contain a `book_id` field specifying the id of the newly added book,
    or if add_duplicates is not specified and a duplicate was found, no book_id will be present. It will also
    return the value of `job_id` as the `id` field and `filename` as the `filename` field.
    '''
    db = get_db(ctx, rd, library_id)
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot use the add book interface with a user who has per library restrictions')
    if not filename:
        raise HTTPBadRequest('An empty filename is not allowed')
    sfilename = sanitize_file_name_unicode(filename)
    fmt = os.path.splitext(sfilename)[1]
    fmt = fmt[1:] if fmt else None
    if not fmt:
        raise HTTPBadRequest('An filename with no extension is not allowed')
    if isinstance(rd.request_body_file, BytesIO):
        raise HTTPBadRequest('A request body containing the file data must be specified')
    add_duplicates = add_duplicates in ('y', '1')
    path = os.path.join(rd.tdir, sfilename)
    rd.request_body_file.name = path
    rd.request_body_file.seek(0)
    mi = get_metadata(rd.request_body_file, stream_type=fmt, use_libprs_metadata=True)
    rd.request_body_file.seek(0)
    ids, duplicates = db.add_books([(mi, {fmt: rd.request_body_file})], add_duplicates=add_duplicates)
    ans = {'title': mi.title, 'authors': mi.authors, 'languages': mi.languages, 'filename': filename, 'id': job_id}
    if ids:
        ans['book_id'] = ids[0]
        books_added(ids)
    return ans


@endpoint('/cdb/delete-books/{book_ids}/{library_id=None}',
          needs_db_write=True, postprocess=json, methods=receive_data_methods, cache_control='no-cache')
def cdb_delete_book(ctx, rd, book_ids, library_id):
    db = get_db(ctx, rd, library_id)
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot use the delete book interface with a user who has per library restrictions')
    try:
        ids = {int(x) for x in book_ids.split(',')}
    except Exception:
        raise HTTPBadRequest('invalid book_ids: {}'.format(book_ids))
    db.remove_books(ids)
    books_deleted(ids)
    return {}


@endpoint('/cdb/set-fields/{book_id}/{library_id=None}', types={'book_id': int},
          needs_db_write=True, postprocess=msgpack_or_json, methods=receive_data_methods, cache_control='no-cache')
def cdb_set_fields(ctx, rd, book_id, library_id):
    db = get_db(ctx, rd, library_id)
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot use the set fields interface with a user who has per library restrictions')
    raw = rd.read()
    ct = rd.inheaders.get('Content-Type', all=True)
    ct = {x.lower().partition(';')[0] for x in ct}
    try:
        if MSGPACK_MIME in ct:
            data = msgpack_loads(raw)
        elif 'application/json' in ct:
            data = json_loads(raw)
        else:
            raise HTTPBadRequest('Only JSON or msgpack requests are supported')
        changes, loaded_book_ids = data['changes'], frozenset(map(int, data['loaded_book_ids']))
    except Exception:
        raise HTTPBadRequest('Invalid encoded data')
    dirtied = set()
    for field, value in changes.iteritems():
        dirtied |= db.set_field(field, {book_id: value})
    return {bid: book_as_json(db, book_id) for bid in (dirtied & loaded_book_ids) | {book_id}}
