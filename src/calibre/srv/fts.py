#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import re

from calibre.ebooks.metadata import authors_to_string
from calibre.srv.errors import (
    HTTPBadRequest, HTTPPreconditionRequired, HTTPUnprocessableEntity,
)
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data


@endpoint('/fts/search', postprocess=json)
def fts_search(ctx, rd):
    '''
    Perform the specified full text query.

    Optional: ?query=<search query>&library_id=<default library>&use_stemming=<y or n>&query_id=arbitrary&restriction=arbitrary
    '''

    db = get_library_data(ctx, rd)[0]
    if not db.is_fts_enabled():
        raise HTTPPreconditionRequired('Full text searching is not enabled on this library')
    metadata_cache = {}
    l, t = db.fts_indexing_progress()[:2]
    ans = {'metadata': metadata_cache, 'indexing_status': {'left': l, 'total': t}}

    use_stemming = rd.query.get('use_stemming', 'y') == 'y'
    query = rd.query.get('query' '')
    if not query:
        raise HTTPBadRequest('No search query specified')
    qid = rd.query.get('query_id')
    if qid:
        ans['query_id'] = qid
    book_ids = None
    if rd.query.get('restriction'):
        book_ids = db.search('', restriction=rd.query.get('restriction'))

    def add_metadata(result):
        result.pop('id', None)
        result.pop('text', None)
        bid = result['book_id']
        if bid not in metadata_cache:
            with db.safe_read_lock:
                metadata_cache[bid] = {'title': db._field_for('title', bid), 'authors': authors_to_string(db._field_for('authors', bid))}
        return result

    from calibre.db import FTSQueryError
    try:
        ans['results'] = tuple(db.fts_search(
            query, use_stemming=use_stemming, return_text=False, process_each_result=add_metadata, restrict_to_book_ids=book_ids,
        ))
    except FTSQueryError as e:
        raise HTTPUnprocessableEntity(str(e))
    return ans


@endpoint('/fts/disable', needs_db_write=True)
def fts_disable(ctx, rd):
    db = get_library_data(ctx, rd)[0]
    if db.is_fts_enabled():
        db.enable_fts(enabled=False)
    return ''


@endpoint('/fts/reindex', needs_db_write=True, methods=('POST',))
def fts_reindex(ctx, rd):
    db = get_library_data(ctx, rd)[0]
    if not db.is_fts_enabled():
        raise HTTPPreconditionRequired('Full text searching is not enabled on this library')
    data = rd.request_body_file.read()
    try:
        book_ids = json.loads(data)
    except Exception:
        raise HTTPBadRequest('Invalid book ids')
    if book_ids == 'all':
        db.reindex_fts()
    else:
        for book_id, fmts in book_ids.items():
            db.reindex_fts_book(int(book_id), *fmts)
    return ''


@endpoint('/fts/indexing', needs_db_write=True, methods=('POST',))
def fts_indexing(ctx, rd):
    data = rd.request_body_file.read()
    try:
        enable = json.loads(data)
    except Exception:
        raise HTTPBadRequest('Invalid boolean')
    if not isinstance(enable, bool):
        raise HTTPBadRequest('Invalid boolean')
    db = get_library_data(ctx, rd)[0]
    db.enable_fts(enable)
    return ''


@endpoint('/fts/snippets/{book_ids}', postprocess=json)
def fts_snippets(ctx, rd, book_ids):
    '''
    Perform the specified full text query and return the results with snippets restricted to the specified book ids.

    Optional: ?query=<search query>&library_id=<default library>&use_stemming=<y or n>
    &query_id=arbitrary&snippet_size=32&highlight_start=\x1c&highlight_end=\x1e
    '''
    db = get_library_data(ctx, rd)[0]
    if not db.is_fts_enabled():
        raise HTTPPreconditionRequired('Full text searching is not enabled on this library')

    use_stemming = rd.query.get('use_stemming', 'y') == 'y'
    query = rd.query.get('query' '')
    if not query:
        raise HTTPBadRequest('No search query specified')
    try:
        bids = frozenset(map(int, book_ids.split(',')))
    except Exception:
        raise HTTPBadRequest('Invalid list of book ids')
    try:
        ssz = int(rd.query.get('snippet_size', 32))
    except Exception:
        raise HTTPBadRequest('Invalid snippet size')
    snippets = {bid:{} for bid in bids}
    ans = {}
    qid = rd.query.get('query_id')
    if qid:
        ans['query_id'] = qid
    from calibre.db import FTSQueryError
    sanitize_pat = re.compile(r'\s+')
    try:
        for x in db.fts_search(
            query, use_stemming=use_stemming, return_text=True,
            highlight_start=rd.query.get('highlight_start', '\x1c'), highlight_end=rd.query.get('highlight_end', '\x1e'),
            restrict_to_book_ids=bids, snippet_size=ssz,
        ):
            r = snippets[x['book_id']]
            q = sanitize_pat.sub('', x['text'])
            r.setdefault(q, {'formats': [], 'text': x['text'],})['formats'].append(x['format'])
    except FTSQueryError as e:
        raise HTTPUnprocessableEntity(str(e))
    ans['snippets'] = {bid: tuple(v.values()) for bid, v in snippets.items()}
    return ans
