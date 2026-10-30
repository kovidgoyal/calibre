#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import sys

from calibre import prints
from calibre.db.cli.utils import for_terminal
from calibre.utils.localization import _

readonly = False
version = 0  # change this if you change signature of implementation()
ANNOTATION_TYPES = ('highlight', 'bookmark')
EXPORT_FORMATS = ('text', 'markdown', 'json')


def annotations_to_import(data, fmt):
    from calibre.utils.iso8601 import parse_iso8601

    if not isinstance(data, dict) or data.get('type') != 'calibre_annotation_collection' or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError(_('Not a supported calibre annotation collection'))
    annotations = data.get('annotations')
    if not isinstance(annotations, list):
        raise TypeError(_('The annotation collection must contain a list of annotations'))
    book_ids, ans = set(), []
    for i, a in enumerate(annotations, 1):
        try:
            if not isinstance(a, dict) or a.get('type') not in ANNOTATION_TYPES or a.get('removed'):
                raise ValueError(_('Expected a highlight or bookmark'))
            if type(a.get('book_id')) is not int or a['book_id'] <= 0:
                raise ValueError(_('Missing or invalid source book id'))
            book_ids.add(a['book_id'])
            if len(book_ids) > 1:
                raise ValueError(_('The collection contains more than one book; export one book at a time'))
            if not isinstance(a.get('format'), str) or a['format'].upper() != fmt:
                raise ValueError(_('The source and destination formats must match'))
            field = 'uuid' if a['type'] == 'highlight' else 'title'
            if not isinstance(a.get(field), str) or (field == 'uuid' and not a[field]):
                raise ValueError(_('Missing or invalid annotation identity: {}').format(field))
            if not isinstance(a.get('timestamp'), str) or not a['timestamp']:
                raise ValueError(_('Missing annotation timestamp'))
            parse_iso8601(a['timestamp'], assume_utc=True)
            for key in ('highlighted_text', 'notes', 'start_cfi', 'end_cfi', 'spine_name', 'pos', 'pos_type'):
                if a.get(key) is not None and not isinstance(a[key], str):
                    raise ValueError(_('Invalid annotation field: {}').format(key))
            if a.get('spine_index') is not None and (type(a['spine_index']) is not int or a['spine_index'] < 0):
                raise ValueError(_('Invalid spine index'))
            if a.get('style') is not None and not isinstance(a['style'], dict):
                raise ValueError(_('Invalid annotation style'))
            if a.get('toc_family_titles') is not None and (
                not isinstance(a['toc_family_titles'], list) or not all(isinstance(x, str) for x in a['toc_family_titles'])
            ):
                raise ValueError(_('Invalid annotation chapter titles'))
        except (ValueError, TypeError, OverflowError) as err:
            raise ValueError(_('Invalid annotation {0}: {1}').format(i, err)) from err
        # Source book ids are only used to detect mixed collections. They must
        # never determine where annotations are stored in the target library.
        ans.append({k: v for k, v in a.items() if k not in ('book_id', 'format')})
    return ans


def implementation(db, notify_changes, action, *args):
    from calibre.utils.search_query_parser import ParseException

    is_remote = notify_changes is not None
    if action == 'import':
        book_id, fmt, data, user_type, user = args
        if user_type not in ('local', 'web') or not isinstance(user, str) or not user.strip():
            return False, _('Invalid annotation user')
        try:
            annots = annotations_to_import(data, fmt)
        except (ValueError, TypeError) as err:
            return False, str(err)
        with db.quiet_write_lock:
            if not db._has_id(book_id):
                return False, _('No book with id: {}').format(book_id)
            if fmt not in db._formats(book_id):
                return False, _('Book {0} has no {1} format').format(book_id, fmt)
            if annots:
                db._merge_annotations_for_book(book_id, fmt, annots, user_type=user_type, user=user)
        if is_remote and annots:
            from calibre.srv.changes import metadata

            notify_changes(metadata((book_id,)))
        return True, len(annots)
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
        titles = {book_id: db._field_for('title', book_id) for book_id in {a['book_id'] for a in annots}}
    return True, (annots, titles)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog annotations [options] (list|export|import|remove)

Manage the annotations, that is the highlights and bookmarks, of books, as
created in the calibre E-book viewer or synced from other applications.

List the annotations, with their ids:

%prog annotations list

Export the annotations as plain text, Markdown or JSON, grouped by book. The
JSON is the same calibre annotation collection as created by the Export
button in the Browse annotations tool:

%prog annotations export

Import a calibre annotation collection exported as JSON by this command or
the Browse annotations tool. The collection must contain annotations from
only one book and format. BOOK_ID is the destination book id, not the id
stored in the file. FORMAT must match the source format and must exist in
the destination book. Use the same edition of the book so positions match:

%prog annotations import BOOK_ID FORMAT FILE

Use - for FILE to read from standard input. The entire collection is
validated before importing. Annotations are merged with existing ones using
the viewer's rules: highlights are matched by UUID and bookmarks by title,
and the newer timestamp wins. Repeated imports do not create duplicates.
Unrelated annotations and reading positions are preserved.

By default import into the desktop viewer's local:viewer annotations.
Use --user-type web --annotation-user USER to import into a Content server
reader account instead. Both local and remote libraries are supported.

Permanently remove the annotations with the specified ids, as shown by list:

%prog annotations remove ID ...
'''
        )
    )
    parser.add_option(
        '--user-type',
        default='local',
        choices=('local', 'web'),
        help=_('For import, select desktop viewer annotations (local) or Content server reader annotations (web). Default: %default'),
    )
    parser.add_option(
        '--annotation-user',
        default=None,
        help=_('For import, the owner of the annotations. Defaults to viewer for local annotations; required for web annotations'),
    )
    parser.add_option(
        '-s',
        '--search',
        default=None,
        help=_('Only list or export the annotations of books matching the specified search query, for example: --search "series:Foundation"'),
    )
    parser.add_option(
        '-t',
        '--type',
        default=None,
        choices=ANNOTATION_TYPES,
        help=_('Only list or export annotations of the specified type, one of: {}').format(', '.join(ANNOTATION_TYPES)),
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
        raise SystemExit(_('Error: You must specify an action, one of: (list|export|import|remove)'))
    action, args = args[0], args[1:]
    if action != 'import' and (opts.user_type != 'local' or opts.annotation_user is not None):
        raise SystemExit(_('Error: The --user-type and --annotation-user options can only be used with import'))
    if action == 'import':
        if opts.search or opts.type or opts.format != 'text':
            raise SystemExit(_('Error: The --search, --type and --format options cannot be used with import'))
        if len(args) != 3:
            raise SystemExit(_('Error: Specify a destination book id, format and annotation collection file'))
        try:
            book_id = int(args[0])
        except ValueError:
            raise SystemExit(_('Error: The destination book id must be a number'))
        if opts.user_type == 'web' and not opts.annotation_user:
            raise SystemExit(_('Error: Specify --annotation-user for web annotations'))
        try:
            if args[2] == '-':
                data = json.loads(sys.stdin.buffer.read().decode('utf-8-sig'))
            else:
                with open(args[2], encoding='utf-8-sig') as f:
                    data = json.load(f)
        except (OSError, ValueError) as err:
            raise SystemExit(_('Error: Failed to read annotation collection: {}').format(err))
        count = run(dbctx, 'import', book_id, args[1].upper(), data, opts.user_type, opts.annotation_user if opts.annotation_user is not None else 'viewer')
        prints(_('{} annotations imported').format(count))
        return 0
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
    if action not in ('list', 'export'):
        raise SystemExit(_('Error: Action {} not recognized, must be one of: (list|export|import|remove)').format(action))
    if args:
        raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
    annots, titles = run(dbctx, 'get', opts.search, opts.type)
    # Book ids are sent as strings when using a remote library
    titles = {int(k): v for k, v in titles.items()}
    if action == 'list':
        for a in sorted(annots, key=lambda a: a['id']):
            text = ' '.join((a['text'] or '').split())
            fields = (str(a['id']), titles.get(a['book_id'], ''), a['annotation']['type'], a['format'], f"{a['user_type']}:{a['user']}", text)
            prints(for_terminal('\t'.join(fields)))
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
