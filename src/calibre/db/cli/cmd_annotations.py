#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json

from calibre import prints
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
        with db.write_lock:
            existing = {a['id'] for a in db._all_annotations(ignore_removed=True) if a['id'] in annot_ids}
            if missing := annot_ids - existing:
                return False, _('No annotations with the ids: {}').format(', '.join(map(str, sorted(missing))))
            db._delete_annotations(tuple(existing))
        return True, len(existing)
    if action != 'get':
        return False, _('Unknown action: {}').format(action)
    search, annotation_type = args[:2]
    book_ids = None
    if search:
        try:
            book_ids = db.search(search, allow_templates=not is_remote)
        except ParseException as e:
            return False, _('Failed to parse search query: ({0}) with error: {1}').format(search, e)
    with db.safe_read_lock:
        annots = db._all_annotations(annotation_type=annotation_type or None, ignore_removed=True, restrict_to_book_ids=book_ids)
        titles = {a['book_id']: db._field_for('title', a['book_id']) for a in annots}
    return True, (annots, titles)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog annotations [options] (list|export|remove)

Manage the annotations, that is the highlights and bookmarks, of books, as
created in the calibre E-book viewer or synced from other applications.

List the annotations, with their ids:

%prog annotations list

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
        help=_('Only use the annotations of books matching the specified search query, for example: --search "series:Foundation"'),
    )
    parser.add_option(
        '-t',
        '--type',
        default=None,
        choices=ANNOTATION_TYPES,
        help=_('Only use annotations of the specified type, one of: {}').format(', '.join(ANNOTATION_TYPES)),
    )
    parser.add_option(
        '-f',
        '--format',
        default='text',
        choices=EXPORT_FORMATS,
        help=_('The format to export the annotations in, one of: {}. Default is: %default').format(', '.join(EXPORT_FORMATS)),
    )
    return parser


def run(dbctx, *args):
    ok, ans = dbctx.run('annotations', *args)
    if not ok:
        raise SystemExit(ans)
    return ans


def render_timestamp(ts: str) -> str:
    from calibre.utils.date import as_local_time
    from calibre.utils.iso8601 import parse_iso8601

    try:
        return as_local_time(parse_iso8601(ts)).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ts or ''


def sorted_by_position(annots: list[dict]) -> list[dict]:
    "Sort the annotations of a book in the order they appear in it, highlights before bookmarks"
    from calibre.db.annotations import bookmark_sort_key, highlight_sort_key

    ans = []
    for atype, key in (('highlight', highlight_sort_key), ('bookmark', bookmark_sort_key)):
        of_type = [a for a in annots if a['annotation']['type'] == atype]
        try:
            of_type.sort(key=lambda a: key(a['annotation']))
        except Exception:
            pass  # Annotations from other applications may not have positions
        ans.extend(of_type)
    return ans


def render_as_text(annots: list[dict], titles: dict[int, str], as_markdown: bool) -> str:
    # Uses the same layout as the export in the Browse annotations tool
    lines = []
    by_book: dict[int, list[dict]] = {}
    for a in annots:
        by_book.setdefault(a['book_id'], []).append(a)
    separator = '-' * 20 if as_markdown else '───'
    for book_id, group in sorted(by_book.items(), key=lambda x: (titles.get(x[0]) or '').lower()):
        lines.extend(('# ' + (titles.get(book_id) or _('Unknown')), ''))
        current_chapter = None
        for a in sorted_by_position(group):
            annot = a['annotation']
            chapter = ' > '.join(annot.get('toc_family_titles') or ())
            if chapter and chapter != current_chapter:
                lines.extend(('## ' + chapter, ''))
            current_chapter = chapter
            date = render_timestamp(annot.get('timestamp', ''))
            if annot['type'] == 'bookmark':
                lines.append(annot.get('title') or '')
            else:
                lines.append(annot.get('highlighted_text') or '')
            lines.append(f'*{date}*' if as_markdown else date)
            if notes := annot.get('notes'):
                lines.extend(('', notes))
            lines.extend(('', separator, ''))
    return '\n'.join(lines).strip()


def main(opts, args, dbctx):
    if not args:
        raise SystemExit(_('Error: You must specify an action, one of: (list|export|remove)'))
    action, args = args[0], args[1:]
    if action == 'remove':
        if not args:
            raise SystemExit(_('Error: You must specify the ids of the annotations to remove'))
        try:
            annot_ids = [int(x) for x in args]
        except ValueError:
            raise SystemExit(_('Error: Annotation ids must be numbers'))
        count = run(dbctx, 'remove', annot_ids)
        prints(_('{} annotations removed').format(count))
        return 0
    if action not in ('list', 'export'):
        raise SystemExit(_('Error: Action {} not recognized, must be one of: (list|export|remove)').format(action))
    if args:
        raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
    annots, titles = run(dbctx, 'get', opts.search, opts.type)
    # Book ids are sent as strings when using a remote library
    titles = {int(k): v for k, v in titles.items()}
    if action == 'list':
        for a in sorted(annots, key=lambda a: a['id']):
            text = ' '.join((a['text'] or '').split())
            prints(f"{a['id']}\t{titles.get(a['book_id'], '')}\t{a['annotation']['type']}\t{text}")
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
        data = render_as_text(annots, titles, opts.format == 'markdown')
    if data:
        prints(data)
    return 0
