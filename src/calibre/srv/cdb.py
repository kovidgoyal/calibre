#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import os
import shutil
import time
from functools import partial
from io import BytesIO

from calibre import as_unicode, sanitize_file_name
from calibre.db.cli import module_for_cmd
from calibre.ebooks.metadata.meta import get_metadata
from calibre.srv.changes import books_added, books_deleted, metadata
from calibre.srv.errors import HTTPBadRequest, HTTPForbidden, HTTPNotFound
from calibre.srv.metadata import book_as_json
from calibre.srv.routes import endpoint, json, msgpack_or_json
from calibre.srv.utils import get_db, get_library_data
from calibre.utils.imghdr import what
from calibre.utils.serialize import MSGPACK_MIME, json_loads, msgpack_loads
from calibre.utils.speedups import ReadOnlyFileBuffer
from polyglot.binary import from_base64_bytes
from polyglot.builtins import iteritems

receive_data_methods = {'GET', 'POST'}


@endpoint('/cdb/cmd/{which}/{version=0}', postprocess=msgpack_or_json, methods=receive_data_methods, cache_control='no-cache')
def cdb_run(ctx, rd, which, version):
    try:
        m = module_for_cmd(which)
    except ImportError:
        raise HTTPNotFound(f'No module named: {which}')
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
        tb = ''
        if not getattr(err, 'suppress_traceback', False):
            import traceback
            tb = traceback.format_exc()
        return {'err': as_unicode(err), 'tb': tb}
    return {'result': result}


@endpoint('/cdb/add-book/{job_id}/{add_duplicates}/{filename}/{library_id=None}',
          needs_db_write=True, postprocess=json, methods=receive_data_methods, cache_control='no-cache')
def cdb_add_book(ctx, rd, job_id, add_duplicates, filename, library_id):
    '''
    Add a file as a new book. The file contents must be in the body of the request.

    The response will also have the title/authors/languages read from the
    metadata of the file/filename. It will contain a `book_id` field specifying
    the id of the newly added book, or if add_duplicates is not specified and a
    duplicate was found, no book_id will be present, instead there will be a
    `duplicates` field specifying the title and authors for all duplicate
    matches. It will also return the value of `job_id` as the `id` field and
    `filename` as the `filename` field.
    '''
    db = get_db(ctx, rd, library_id)
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot use the add book interface with a user who has per library restrictions')
    if not filename:
        raise HTTPBadRequest('An empty filename is not allowed')
    sfilename = sanitize_file_name(filename)
    fmt = os.path.splitext(sfilename)[1]
    fmt = fmt[1:] if fmt else None
    if not fmt:
        raise HTTPBadRequest('An filename with no extension is not allowed')
    if isinstance(rd.request_body_file, BytesIO):
        raise HTTPBadRequest('A request body containing the file data must be specified')
    add_duplicates = add_duplicates in ('y', '1')
    path = os.path.join(rd.tdir, sfilename)
    rd.request_body_file.seek(0)
    with open(path, 'wb') as f:
        shutil.copyfileobj(rd.request_body_file, f)
    from calibre.ebooks.metadata.worker import run_import_plugins
    path = run_import_plugins((path,), time.monotonic_ns(), rd.tdir)[0]
    with open(path, 'rb') as f:
        mi = get_metadata(f, stream_type=os.path.splitext(path)[1][1:], use_libprs_metadata=True)
        f.seek(0)
        nfmt = os.path.splitext(path)[1]
        fmt = nfmt[1:] if nfmt else fmt
        ids, duplicates = db.add_books([(mi, {fmt: f})], add_duplicates=add_duplicates)
    ans = {'title': mi.title, 'authors': mi.authors, 'languages': mi.languages, 'filename': filename, 'id': job_id}
    if ids:
        ans['book_id'] = ids[0]
        ctx.notify_changes(db.backend.library_path, books_added(ids))
    else:
        ans['duplicates'] = [{'title': m.title, 'authors': m.authors} for m, _ in duplicates]
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
        raise HTTPBadRequest(f'invalid book_ids: {book_ids}')
    db.remove_books(ids)
    ctx.notify_changes(db.backend.library_path, books_deleted(ids))
    return {}


@endpoint('/cdb/set-cover/{book_id}/{library_id=None}', types={'book_id': int},
            needs_db_write=True, postprocess=json, methods=receive_data_methods, cache_control='no-cache')
def cdb_set_cover(ctx, rd, book_id, library_id):
    db = get_db(ctx, rd, library_id)
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot use the add book interface with a user who has per library restrictions')
    rd.request_body_file.seek(0)
    dirtied = db.set_cover({book_id: rd.request_body_file})
    ctx.notify_changes(db.backend.library_path, metadata(dirtied))
    return tuple(dirtied)


def load_payload_data(rd):
    raw = rd.read()
    ct = rd.inheaders.get('Content-Type', all=True)
    ct = {x.lower().partition(';')[0] for x in ct}
    try:
        if MSGPACK_MIME in ct:
            return msgpack_loads(raw)
        elif 'application/json' in ct:
            return json_loads(raw)
        else:
            raise HTTPBadRequest('Only JSON or msgpack requests are supported')
    except Exception:
        raise HTTPBadRequest('Invalid encoded data')


@endpoint('/cdb/set-fields/{book_id}/{library_id=None}', types={'book_id': int},
          needs_db_write=True, postprocess=msgpack_or_json, methods=receive_data_methods, cache_control='no-cache')
def cdb_set_fields(ctx, rd, book_id, library_id):
    db = get_db(ctx, rd, library_id)
    if ctx.restriction_for(rd, db):
        raise HTTPForbidden('Cannot use the set fields interface with a user who has per library restrictions')
    data = load_payload_data(rd)
    try:
        changes, loaded_book_ids = data['changes'], frozenset(map(int, data.get('loaded_book_ids', ())))
        all_dirtied = bool(data.get('all_dirtied'))
        if not isinstance(changes, dict):
            raise TypeError('changes must be a dict')
    except Exception:
        raise HTTPBadRequest(
        '''Data must be of the form {'changes': {'title': 'New Title', ...}, 'loaded_book_ids':[book_id1, book_id2, ...]'}''')
    dirtied = set()
    cdata = changes.pop('cover', False)
    if cdata is not False:
        if cdata is not None:
            try:
                cdata = from_base64_bytes(cdata.split(',', 1)[-1])
            except Exception:
                raise HTTPBadRequest('Cover data is not valid base64 encoded data')
            try:
                fmt = what(None, cdata)
            except Exception:
                fmt = None
            if fmt not in ('jpeg', 'png'):
                raise HTTPBadRequest('Cover data must be either JPEG or PNG')
        dirtied |= db.set_cover({book_id: cdata})

    added_formats = changes.pop('added_formats', False)
    if added_formats:
        for data in added_formats:
            try:
                fmt = data['ext'].upper()
            except Exception:
                raise HTTPBadRequest('Format has no extension')
            if fmt:
                try:
                    fmt_data = from_base64_bytes(data['data_url'].split(',', 1)[-1])
                except Exception:
                    raise HTTPBadRequest('Format data is not valid base64 encoded data')
                if db.add_format(book_id, fmt, ReadOnlyFileBuffer(fmt_data)):
                    dirtied.add(book_id)
    removed_formats = changes.pop('removed_formats', False)
    if removed_formats:
        db.remove_formats({book_id: list(removed_formats)})
        dirtied.add(book_id)

    for field, value in iteritems(changes):
        dirtied |= db.set_field(field, {book_id: value})
    ctx.notify_changes(db.backend.library_path, metadata(dirtied))
    all_ids = dirtied if all_dirtied else (dirtied & loaded_book_ids)
    all_ids |= {book_id}
    return {bid: book_as_json(db, bid) for bid in all_ids}


@endpoint('/cdb/copy-to-library/{target_library_id}/{library_id=None}', needs_db_write=True,
        postprocess=msgpack_or_json, methods=receive_data_methods, cache_control='no-cache')
def cdb_copy_to_library(ctx, rd, target_library_id, library_id):
    db_src = get_db(ctx, rd, library_id)
    db_dest = get_db(ctx, rd, target_library_id)
    if ctx.restriction_for(rd, db_src) or ctx.restriction_for(rd, db_dest):
        raise HTTPForbidden('Cannot use the copy to library interface with a user who has per library restrictions')
    data = load_payload_data(rd)
    try:
        book_ids = {int(x) for x in data['book_ids']}
        move_books = bool(data.get('move', False))
        preserve_date = bool(data.get('preserve_date', True))
        duplicate_action = data.get('duplicate_action') or 'add'
        automerge_action = data.get('automerge_action') or 'overwrite'
    except Exception:
        raise HTTPBadRequest('Invalid encoded data, must be of the form: {book_ids: [id1, id2, ..]}')
    if duplicate_action not in ('add', 'add_formats_to_existing', 'ignore'):
        raise HTTPBadRequest('duplicate_action must be one of: add, add_formats_to_existing, ignore')
    if automerge_action not in ('overwrite', 'ignore', 'new record'):
        raise HTTPBadRequest('automerge_action must be one of: overwrite, ignore, new record')
    response = {}
    identical_books_data = None
    if duplicate_action != 'add':
        identical_books_data = db_dest.data_for_find_identical_books()
    to_remove = set()
    from calibre.db.copy_to_library import copy_one_book
    for book_id in book_ids:
        try:
            rdata = copy_one_book(
                    book_id, db_src, db_dest, duplicate_action=duplicate_action, automerge_action=automerge_action,
                    preserve_uuid=move_books, preserve_date=preserve_date, identical_books_data=identical_books_data)
            if move_books:
                to_remove.add(book_id)
            response[book_id] = {'ok': True, 'payload': rdata}
        except Exception:
            import traceback
            response[book_id] = {'ok': False, 'payload': traceback.format_exc()}

    if to_remove:
        db_src.remove_books(to_remove, permanent=True)

    return response
