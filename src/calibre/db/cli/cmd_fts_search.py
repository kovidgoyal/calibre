#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import re

readonly = True
version = 0  # change this if you change signature of implementation()


def implementation(db, notify_changes, query, adata):
    rto = adata['restrict_to']
    restrict_to = None
    if not db.is_fts_enabled():
        err = Exception(_('Full text searching is not enabled on this library. Use the calibredb fts_index enable --wait-until-complete command to enable it'))
        err.suppress_traceback = True
        raise err
    l, t = db.fts_indexing_progress()[:2]
    if l/t > (1 - adata['threshold']):
        err = Exception(_('{0} files out of {1} are not yet indexed, searching is disabled').format(l, t))
        err.suppress_traceback = True
        raise err
    if rto:
        if isinstance(rto, str):
            restrict_to = db.search(rto)
        else:
            restrict_to = set(rto)

    metadata_cache = {}
    include_snippets = adata['include_snippets']

    def add_metadata(result):
        result.pop('id', None)
        if not include_snippets:
            result.pop('text', None)
        bid = result['book_id']
        if bid not in metadata_cache:
            with db.safe_read_lock:
                metadata_cache[bid] = {'title': db._field_for('title', bid), 'authors': db._field_for('authors', bid)}
        return result

    from calibre.db import FTSQueryError
    try:
        return db.fts_search(
            query, use_stemming=adata['use_stemming'], highlight_start=adata['start_marker'], highlight_end=adata['end_marker'],
            return_text=include_snippets, restrict_to_book_ids=restrict_to, result_type=tuple if adata['as_tuple'] else lambda x: x,
            process_each_result=add_metadata, snippet_size=64
        ), metadata_cache
    except FTSQueryError as e:
        e.suppress_traceback = True
        raise e


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog fts_search [options] search expression

Do a full text search on the entire library or a subset of it.

'''
    ))
    parser.add_option(
        '--include-snippets',
        default=False,
        action='store_true',
        help=_('Include snippets of the text surrounding each match. Note that this makes searching much slower.')
    )
    parser.add_option(
        '--match-start-marker',
        default='\x1b[31m',
        help=_('The marker used to indicate the start of a matched word inside a snippet')
    )
    parser.add_option(
        '--match-end-marker',
        default='\x1b[m',
        help=_('The marker used to indicate the end of a matched word inside a snippet')
    )
    parser.add_option(
        '--do-not-match-on-related-words',
        default=True,
        dest='use_stemming',
        action='store_false',
        help=_('Only match on exact words not related words. So correction will not match correcting.')
    )
    parser.add_option(
        '--restrict-to',
        default='',
        help=_('Restrict the searched books, either using a search expression or ids.'
               ' For example: ids:1,2,3 to restrict by ids or search:tag:foo to restrict to books having the tag foo.')
    )
    parser.add_option(
        '--output-format', default='text', choices=('text', 'json'),
        help=_('The format to output the search results in. Either "text" for plain text or "json" for JSON output.')
    )

    parser.add_option(
        '--indexing-threshold', type=float, default=90.,
        help=_('How much of the library must be indexed before searching is allowed, as a percentage. Defaults to 90')
    )
    return parser


def output_results_as_text(results, metadata_cache, include_snippets):
    from calibre.utils.terminal import geometry
    from calibre.ebooks.metadata import authors_to_string
    width = max(5, geometry()[0])
    separator = '─' * width
    if not include_snippets:
        bids = {}
        for result in results:
            bids.setdefault(result['book_id'], []).append(result['format'])
        for bid, fmts in bids.items():
            m = metadata_cache[bid]
            print(_('{0} by {1}').format(m['title'], authors_to_string(m['authors'])))
            print(f'Book id: {bid} Formats: {", ".join(fmts)}')
            print(separator)
        return

    current_text_q = ''
    current_id = -1
    current_formats = []
    pat = re.compile(r'\s+')

    def print_result():
        m = metadata_cache[current_id]
        print(_('{0} by {1}').format(m['title'], authors_to_string(m['authors'])))
        print(f'Book id: {current_id} Formats: {", ".join(current_formats)}')
        print(current_text_q)
        print(separator)

    for result in results:
        textq = pat.sub(' ', result['text'])
        if result['book_id'] == current_id and textq == current_text_q:
            current_formats.append(result['format'])
        else:
            if current_id > -1:
                print_result()
            current_id, current_text_q, current_formats = result['book_id'], textq, [result['format']]

    if current_id > -1:
        print_result()


def main(opts, args, dbctx):
    if len(args) < 1:
        dbctx.option_parser.print_help()
        raise SystemExit(_('Error: You must specify the search expression'))
    search_expression = ' '.join(args)
    restrict_to = ''
    if opts.restrict_to:
        q, v = opts.restrict_to.partition(':')[::2]
        if q == 'ids':
            restrict_to = tuple(set(map(int, v.split(','))))
        elif q == 'search':
            restrict_to = v
        else:
            raise SystemExit('The --restrict-to option must start with either ids: or search:')
    from calibre.db import FTSQueryError
    try:
        results, metadata_cache = dbctx.run('fts_search', search_expression, {
            'start_marker': opts.match_start_marker, 'end_marker': opts.match_end_marker, 'use_stemming': opts.use_stemming,
            'include_snippets': opts.include_snippets, 'restrict_to': restrict_to, 'as_tuple': dbctx.is_remote,
            'threshold': max(0, min(opts.indexing_threshold, 100)) / 100
        })
        if opts.output_format == 'json':
            if not dbctx.is_remote:
                results = tuple(results)
            for r in results:
                m = metadata_cache[r['book_id']]
                r['title'], r['authors'] = m['title'], m['authors']
            import json
            print(json.dumps(results, sort_keys=True, indent='  '))
        else:
            output_results_as_text(results, metadata_cache, opts.include_snippets)
    except FTSQueryError as e:
        raise SystemExit(str(e))
    except Exception as e:
        if getattr(e, 'suppress_traceback', False):
            raise SystemExit(str(e))
        raise
    return 0
