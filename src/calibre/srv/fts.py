#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.srv.errors import (
    HTTPBadRequest, HTTPPreconditionRequired, HTTPUnprocessableEntity,
)
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data


@endpoint('/fts/search', postprocess=json)
def fts_search(ctx, rd):
    '''
    Perform the specified full text query.

    Optional: ?query=<search query>&library_id=<default library>&use_stemming=<y or n>&query_id=arbitrary
    '''

    db = get_library_data(ctx, rd)[0]
    if not db.is_fts_enabled():
        raise HTTPPreconditionRequired('Full text searching is not enabled on this library')
    metadata_cache = {}
    l, t = db.fts_indexing_progress()[:2]
    ans = {'metadata': metadata_cache, 'left': l, 'total': t}

    use_stemming = rd.query.get('use_stemming', 'y') == 'y'
    query = rd.query.get('query' '')
    if not query:
        raise HTTPBadRequest('No search query specified')
    qid = rd.query.get('query_id')
    if qid:
        ans['query_id'] = qid

    def add_metadata(result):
        result.pop('id', None)
        result.pop('text', None)
        bid = result['book_id']
        if bid not in metadata_cache:
            with db.safe_read_lock:
                metadata_cache[bid] = {'title': db._field_for('title', bid), 'authors': db._field_for('authors', bid)}
        return result

    from calibre.db import FTSQueryError
    try:
        ans['results'] = tuple(db.fts_search(
            query, use_stemming=use_stemming, return_text=False, result_type=lambda x: x, process_each_result=add_metadata,
        ))
    except FTSQueryError as e:
        raise HTTPUnprocessableEntity(str(e))
    return ans
