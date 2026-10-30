#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json

from calibre import prints
from calibre.db import FTSQueryError
from calibre.db.cli.utils import for_terminal
from calibre.utils.localization import _

readonly = False
version = 0  # change this if you change signature of implementation()
ANNOTATION_TYPES = ('highlight', 'bookmark')
EXPORT_FORMATS = ('text', 'markdown', 'json')


def implementation(db, notify_changes, action, *args):
    from calibre.utils.search_query_parser import ParseException

    is_remote = notify_changes is not None
    if action == 'remove':
        annot_ids = {int(x) for x in args[0]}
        with db.quiet_write_lock:
            book_map = db._book_ids_for_annotations(annot_ids, ignore_removed=True)
            if missing := annot_ids - set(book_map):
                return False, _('No annotations with the ids: {}').format(', '.join(map(str, sorted(missing))))
            db._delete_annotations(tuple(book_map))
        if is_remote:
            from calibre.srv.changes import metadata

            notify_changes(metadata(set(book_map.values())))
        return True, len(book_map)
    if action not in ('get', 'search'):
        return False, _('Unknown action: {}').format(action)
    search, annotation_type = args[:2]
    book_ids = None
    if search:
        try:
            book_ids = db.search(search, allow_templates=not is_remote)
        except ParseException as e:
            return False, _('Failed to parse search query: ({0}) with error: {1}').format(search, e)
    with db.safe_read_lock:
        if action == 'search':
            query, use_stemming = args[2:]
            if not isinstance(query, str) or not query.strip():
                return False, _('You must specify a non-empty annotation search expression')
            try:
                annots = db._search_annotations(
                    query,
                    use_stemming=use_stemming,
                    highlight_start='',
                    highlight_end='',
                    snippet_size=32,
                    annotation_type=annotation_type or None,
                    ignore_removed=True,
                    restrict_to_book_ids=book_ids,
                )
            except FTSQueryError as err:
                return False, str(err)
        else:
            annots = db._all_annotations(annotation_type=annotation_type or None, ignore_removed=True, restrict_to_book_ids=book_ids)
        titles = {book_id: db._field_for('title', book_id) for book_id in {a['book_id'] for a in annots}}
    return True, (annots, titles)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog annotations [options] (list|search|export|remove)

Manage the annotations, that is the highlights and bookmarks, of books, as
created in the calibre E-book viewer or synced from other applications.

List the annotations, with their ids:

%prog annotations list

Search highlighted text, annotation notes and bookmark titles using the same
SQLite full text search syntax as the Browse annotations tool. Results are
ordered by relevance and include annotation ids, book titles and matching
excerpts. Use --search to restrict the books, --type to restrict the annotation
type, --no-stemming to match exact word forms, or --format json for a JSON array
of results including the annotation data and excerpts:

%prog annotations search "search expression"

Export the annotations as plain text, Markdown or JSON, grouped by book. The
JSON is the same calibre annotation collection as created by the Export
button in the Browse annotations tool:

%prog annotations export

Permanently remove the annotations with the specified ids, as shown by list:

%prog annotations remove ID ...
'''
        )
    )
    parser.add_option(
        '-s',
        '--search',
        default=None,
        help=_('Only list, search or export the annotations of books matching the specified book search query, for example: --search "series:Foundation"'),
    )
    parser.add_option(
        '-t',
        '--type',
        default=None,
        choices=ANNOTATION_TYPES,
        help=_('Only list, search or export annotations of the specified type, one of: {}').format(', '.join(ANNOTATION_TYPES)),
    )
    parser.add_option(
        '-f',
        '--format',
        default='text',
        choices=EXPORT_FORMATS,
        help=_('The export format, one of: {}. For search, text or json. Default is: %default').format(', '.join(EXPORT_FORMATS)),
    )
    parser.add_option(
        '--no-stemming', dest='use_stemming', default=True, action='store_false', help=_('For search, match exact word forms instead of word stems')
    )
    return parser


def run(dbctx, *args):
    ok, ans = dbctx.run('annotations', *args)
    if not ok:
        raise SystemExit(ans)
    return ans


def render_as_text(annots: list[dict], titles: dict[int, str], as_markdown: bool) -> str:
    from calibre.db.annotations import ChapterGroup, sort_annot_list_by_position_in_book

    lines = []
    by_book: dict[int, list[dict]] = {}
    for a in annots:
        by_book.setdefault(a['book_id'], []).append(a)
    for book_id, group in sorted(by_book.items(), key=lambda x: (titles.get(x[0]) or '').lower()):
        root = ChapterGroup(level=1)
        # Highlights before bookmarks, each in the order they appear in the book
        for atype in ANNOTATION_TYPES:
            of_type = [a['annotation'] for a in group if a['annotation']['type'] == atype]
            sort_annot_list_by_position_in_book(of_type, atype)
            for annot in of_type:
                root.add_annot(annot)
        lines.extend(('# ' + (titles.get(book_id) or _('Unknown')), ''))
        root.render_as_text(lines, as_markdown, None)
        lines.append('')
    return '\n'.join(lines).strip()


def main(opts, args, dbctx):
    if not args:
        raise SystemExit(_('Error: You must specify an action, one of: (list|search|export|remove)'))
    action, args = args[0], args[1:]
    if action != 'search' and not opts.use_stemming:
        raise SystemExit(_('Error: The --no-stemming option can only be used with search'))
    if action == 'remove':
        if opts.search or opts.type:
            raise SystemExit(_('Error: The --search and --type options cannot be used with remove, specify the ids of the annotations instead'))
        if not args:
            raise SystemExit(_('Error: You must specify the ids of the annotations to remove'))
        try:
            annot_ids = [int(x) for x in args]
        except ValueError:
            raise SystemExit(_('Error: Annotation ids must be numbers'))
        count = run(dbctx, 'remove', annot_ids)
        prints(_('{} annotations removed').format(count))
        return 0
    if action not in ('list', 'search', 'export'):
        raise SystemExit(_('Error: Action {} not recognized, must be one of: (list|search|export|remove)').format(action))
    if action == 'search':
        if len(args) != 1 or not args[0].strip():
            raise SystemExit(_('Error: You must specify one non-empty annotation search expression'))
        if opts.format not in ('text', 'json'):
            raise SystemExit(_('Error: The search output format must be text or json'))
        annots, titles = run(dbctx, 'search', opts.search, opts.type, args[0], opts.use_stemming)
    elif args:
        raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
    else:
        annots, titles = run(dbctx, 'get', opts.search, opts.type)
    # Book ids are sent as strings when using a remote library
    titles = {int(k): v for k, v in titles.items()}
    if action == 'search' and opts.format == 'json':
        prints(json.dumps([dict(a, title=titles.get(a['book_id'], '')) for a in annots], ensure_ascii=False, indent=2))
        return 0
    if action in ('list', 'search'):
        for a in annots if action == 'search' else sorted(annots, key=lambda a: a['id']):
            text = ' '.join((a['text'] or '').split())
            fields = (str(a['id']), titles.get(a['book_id'], ''), a['annotation']['type'], a['format'], f"{a['user_type']}:{a['user']}", text)
            prints(for_terminal('\t'.join(' '.join(x.split()) for x in fields) if action == 'search' else '\t'.join(fields)))
        return 0
    if opts.format == 'json':
        # The same calibre annotation collection as exported by the Browse annotations tool
        collection = []
        for a in annots:
            x = a['annotation'].copy()
            x['book_id'], x['format'] = a['book_id'], a['format']
            collection.append(x)
        data = json.dumps({'version': 1, 'type': 'calibre_annotation_collection', 'annotations': collection}, ensure_ascii=False, sort_keys=True, indent=2)
    else:
        data = for_terminal(render_as_text(annots, titles, opts.format == 'markdown'))
    if data:
        prints(data)
    return 0
