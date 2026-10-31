#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import sys
from typing import TYPE_CHECKING, cast

from calibre import prints
from calibre.db import FTSQueryError
from calibre.db.cli.utils import args_to_action, for_terminal
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from optparse import Values

    from calibre.db.backend import JSONDict
    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBCtx
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser

readonly = False
version = 1  # change this if you change signature of implementation()
ACTIONS = ('list', 'search', 'export', 'import', 'remove')
ACTION_DEFAULT = 'list'
ANNOTATION_TYPES = ('highlight', 'bookmark')
EXPORT_FORMATS = ('text', 'markdown', 'json')
USER_TYPES = ('local', 'web')
C1_ESCAPES = {c: f'\\u{c:04x}' for c in range(127, 160)}
# The text fields of the annotations created by the viewers, other fields are
# not imported
TEXT_FIELDS = {
    'highlight': ('highlighted_text', 'notes', 'start_cfi', 'end_cfi', 'spine_name'),
    'bookmark': ('pos', 'pos_type'),
}


def canonical_timestamp(ts: str) -> str:
    # Annotations are merged by comparing their timestamps as strings, so use
    # the UTC format created by the viewers, for example: 2026-01-01T00:00:00.000Z
    from calibre.utils.iso8601 import parse_iso8601

    return parse_iso8601(ts, assume_utc=True).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def annotations_to_import(data: object, fmt: str) -> tuple[list[dict], int]:
    """
    Validate the annotation collection, returning its annotations of the
    specified format, ready to be merged, and the number of annotations of
    other formats, which are skipped.
    """
    if not isinstance(data, dict) or data.get('type') != 'calibre_annotation_collection' or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError(_('Not a supported calibre annotation collection'))
    annotations = data.get('annotations')
    if not isinstance(annotations, list):
        raise TypeError(_('The annotation collection must contain a list of annotations'))
    book_ids, users, ans, skipped = set(), set(), [], 0
    for i, a in enumerate(annotations, 1):
        try:
            if not isinstance(a, dict) or a.get('type') not in ANNOTATION_TYPES or a.get('removed'):
                raise ValueError(_('Expected a highlight or bookmark'))
            if type(a.get('book_id')) is not int or a['book_id'] <= 0:
                raise ValueError(_('Missing or invalid source book id'))
            book_ids.add(a['book_id'])
            if len(book_ids) > 1:
                raise ValueError(_('The collection contains more than one book; export one book at a time'))
            if not isinstance(a.get('format'), str) or not a['format']:
                raise ValueError(_('Missing or invalid format'))
            # Collections exported by older versions of calibre do not record
            # the user
            user_type, user = a.get('user_type'), a.get('user')
            if (user_type, user) != (None, None) and (user_type not in USER_TYPES or not isinstance(user, str) or not user):
                raise ValueError(_('Invalid annotation user'))
            atype = a['type']
            field = 'uuid' if atype == 'highlight' else 'title'
            if not isinstance(a.get(field), str) or not a[field]:
                raise ValueError(_('Missing or invalid annotation identity: {}').format(field))
            if not isinstance(a.get('timestamp'), str) or not a['timestamp']:
                raise ValueError(_('Missing annotation timestamp'))
            # Source book ids and formats are only used to validate the
            # collection, they must never determine where annotations are
            # stored in the target library. Only known fields are imported.
            x = {'type': atype, field: a[field], 'timestamp': canonical_timestamp(a['timestamp'])}
            for key in TEXT_FIELDS[atype]:
                if (val := a.get(key)) is not None:
                    if not isinstance(val, str):
                        raise ValueError(_('Invalid annotation field: {}').format(key))
                    x[key] = val
            if atype == 'highlight':
                if (val := a.get('spine_index')) is not None:
                    if type(val) is not int or val < 0:
                        raise ValueError(_('Invalid spine index'))
                    x['spine_index'] = val
                if (val := a.get('style')) is not None:
                    if not isinstance(val, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in val.items()):
                        raise ValueError(_('Invalid annotation style'))
                    x['style'] = val
                if (val := a.get('toc_family_titles')) is not None:
                    if not isinstance(val, list) or not all(isinstance(t, str) for t in val):
                        raise ValueError(_('Invalid annotation chapter titles'))
                    x['toc_family_titles'] = val
        except (ValueError, TypeError, OverflowError) as err:
            raise ValueError(_('Invalid annotation {0}: {1}').format(i, err)) from err
        if a['format'].upper() != fmt:
            skipped += 1
            continue
        if user_type is not None:
            users.add((user_type, user))
        ans.append(x)
    if len(users) > 1:
        raise ValueError(
            _(
                'The collection contains annotations from more than one user; export the annotations of one user'
                ' at a time with the --user-type and --annotation-user options'
            )
        )
    return ans, skipped


def implementation(
    db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, action: str, *args: object
) -> tuple[bool, str | int | dict[str, int] | tuple[list[JSONDict], dict[int, object]]]:
    from calibre.utils.search_query_parser import ParseException

    is_remote = notify_changes is not None
    if action == 'import':
        book_id, fmt, data, user_type, user = cast('tuple[int, str, object, str, str]', args)
        if user_type not in USER_TYPES or not isinstance(user, str) or not user.strip() or (user_type == 'local' and user != 'viewer'):
            return False, _('Invalid annotation user')
        try:
            annots, skipped = annotations_to_import(data, fmt)
        except (ValueError, TypeError) as err:
            return False, str(err)

        def serialized(amap: dict[str, list[JSONDict]]) -> set[str]:
            return {json.dumps(x, sort_keys=True) for values in amap.values() for x in values}

        changed = 0
        with db.quiet_write_lock:
            if not db._has_id(book_id):
                return False, _('No book with id: {}').format(book_id)
            if fmt not in db._formats(book_id):
                return False, _('Book {0} has no {1} format').format(book_id, fmt)
            if annots:
                before = serialized(db._annotations_map_for_book(book_id, fmt, user_type=user_type, user=user))
                db._merge_annotations_for_book(book_id, fmt, annots, user_type=user_type, user=user)
                changed = len(serialized(db._annotations_map_for_book(book_id, fmt, user_type=user_type, user=user)) - before)
        if is_remote and changed:
            from calibre.srv.changes import metadata

            notify_changes(metadata((book_id,)))
        return True, {'imported': changed, 'unchanged': max(0, len(annots) - changed), 'skipped': skipped}
    if action == 'remove':
        annot_ids = {int(x) for x in cast('Iterable[int]', args[0])}
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
    search, annotation_type, user_type, user = cast('tuple[str | None, str | None, str | None, str | None]', args[:4])
    book_ids = None
    if search:
        try:
            book_ids = db.search(search, allow_templates=not is_remote)
        except ParseException as e:
            return False, _('Failed to parse search query: ({0}) with error: {1}').format(search, e)
    with db.safe_read_lock:
        if action == 'search':
            query, use_stemming = cast('tuple[object, bool]', args[4:])
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
            # The highlighted text and notes are separated by \x1f in the
            # full text search index
            annots = [dict(a, text=(a['text'] or '').replace('\x1f', ' ')) for a in annots]
        else:
            annots = db._all_annotations(annotation_type=annotation_type or None, ignore_removed=True, restrict_to_book_ids=book_ids)
        annots = [a for a in annots if (not user_type or a['user_type'] == user_type) and (not user or a['user'] == user)]
        titles = {book_id: db._field_for('title', book_id) for book_id in {a['book_id'] for a in annots}}  # ty: ignore[no-matching-overload]
    return True, (annots, titles)  # ty: ignore[invalid-return-type]


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''\
%prog annotations [options] [list|search|export|import|remove]

Manage the annotations, that is the highlights and bookmarks, of books, as
created in the calibre E-book viewer or synced from other applications.

List the annotations, with their ids. This is the default action:

%prog annotations list

Search highlighted text, annotation notes and bookmark titles using the same
SQLite full text search syntax as the Browse annotations tool. Results are
ordered by relevance and include annotation ids, book titles and matching
excerpts. Use --search to restrict the books, --type to restrict the annotation
type, --user-type and --annotation-user to restrict the user, --no-stemming to
match exact word forms, or --format json for a JSON array of results including
the annotation data and excerpts:

%prog annotations search "search expression"

Export the annotations as plain text, Markdown or JSON, grouped by book. The
JSON is the same calibre annotation collection as created by the Export
button in the Browse annotations tool:

%prog annotations export

Import a calibre annotation collection exported as JSON by this command or
the Browse annotations tool. The collection must contain annotations from
only one book. BOOK_ID is the destination book id, not the id stored in the
file. Only the annotations of the format FORMAT are imported, annotations of
other formats are skipped. FORMAT must exist in the destination book. Use the
same edition of the book so positions match:

%prog annotations import BOOK_ID FORMAT FILE

Use - for FILE to read from standard input. The entire collection is
validated before importing. Annotations are merged with existing ones using
the viewer's rules: highlights are matched by UUID and bookmarks by title,
and the newer timestamp wins. Repeated imports do not create duplicates.
Unrelated annotations and reading positions are preserved.

By default annotations are imported into those of the calibre E-book viewer.
Use --user-type web --annotation-user USER to import them into those of a
Content server user instead. Exported collections record the user the
annotations belong to, and if a collection contains annotations of more than
one user, it is rejected. Use the --user-type and --annotation-user
options when exporting, to export the annotations of a single user.

Permanently remove the annotations with the specified ids, as shown by list:

%prog annotations remove ID ...
'''
        )
    )
    parser.add_option(
        '--user-type',
        default=None,
        choices=USER_TYPES,
        help=_(
            'Only list, search or export the annotations of the specified type of user. For import, the type of user to import the'
            ' annotations for, the calibre E-book viewer (local) or a Content server user (web). Default for import is local.'
        ),
    )
    parser.add_option(
        '--annotation-user',
        default=None,
        help=_(
            'Only list, search or export the annotations of the specified user. For import, the Content server user to import the'
            ' annotations for, required with --user-type web. Note that this can be any user, not just the one used to'
            ' connect to a remote library.'
        ),
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


def json_for_terminal(data: object) -> str:
    # JSON only escapes C0 control characters, also escape DEL and the C1
    # control characters, which some terminals interpret. They can only occur
    # inside JSON strings, so escaping them keeps the JSON valid.
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).translate(C1_ESCAPES)


def run(dbctx: DBCtx, *args: object) -> object:
    ok, ans = cast('tuple[bool, object]', dbctx.run('annotations', *args))
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


def main(opts: Values, args: list[str], dbctx: DBCtx) -> int:
    action, args = args_to_action(args, ACTIONS, default_action=ACTION_DEFAULT)
    if action != 'search' and not opts.use_stemming:
        raise SystemExit(_('Error: The --no-stemming option can only be used with search'))
    if action == 'import':
        if opts.search or opts.type or opts.format != 'text':
            raise SystemExit(_('Error: The --search, --type and --format options cannot be used with import'))
        if len(args) != 3:
            raise SystemExit(_('Error: Specify a destination book id, format and annotation collection file'))
        try:
            book_id = int(args[0])
        except ValueError:
            raise SystemExit(_('Error: The destination book id must be a number'))
        user_type = opts.user_type or 'local'
        if user_type == 'web' and not opts.annotation_user:
            raise SystemExit(_('Error: Specify --annotation-user for web annotations'))
        user = opts.annotation_user or 'viewer'
        if user_type == 'local' and user != 'viewer':
            raise SystemExit(_('Error: Local annotations can only be imported for the calibre E-book viewer, use --user-type web for Content server users'))
        try:
            if args[2] == '-':
                data = json.loads(sys.stdin.buffer.read().decode('utf-8-sig'))
            else:
                with open(args[2], encoding='utf-8-sig') as f:
                    data = json.load(f)
        except (OSError, ValueError) as err:
            raise SystemExit(_('Error: Failed to read annotation collection: {}').format(err))
        counts = cast('dict[str, int]', run(dbctx, 'import', book_id, args[1].upper(), data, user_type, user))
        prints(_('{} annotations imported').format(counts['imported']))
        if counts['unchanged']:
            prints(_('{} annotations unchanged, as the library already has the same or newer versions').format(counts['unchanged']))
        if counts['skipped']:
            prints(_('{} annotations of other formats skipped').format(counts['skipped']))
        return 0
    if action == 'remove':
        if opts.search or opts.type:
            raise SystemExit(_('Error: The --search and --type options cannot be used with remove, specify the ids of the annotations instead'))
        if opts.user_type or opts.annotation_user:
            raise SystemExit(_('Error: The --user-type and --annotation-user options cannot be used with remove'))
        if not args:
            raise SystemExit(_('Error: You must specify the ids of the annotations to remove'))
        try:
            annot_ids = [int(x) for x in args]
        except ValueError:
            raise SystemExit(_('Error: Annotation ids must be numbers'))
        count = run(dbctx, 'remove', annot_ids)
        prints(_('{} annotations removed').format(count))
        return 0
    if action == 'search':
        if len(args) != 1 or not args[0].strip():
            raise SystemExit(_('Error: You must specify one non-empty annotation search expression'))
        if opts.format not in ('text', 'json'):
            raise SystemExit(_('Error: The search output format must be text or json'))
        annots, titles = cast(
            'tuple[list[JSONDict], dict[int | str, str]]',
            run(dbctx, 'search', opts.search, opts.type, opts.user_type, opts.annotation_user, args[0], opts.use_stemming),
        )
    elif args:
        raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
    else:
        annots, titles = cast('tuple[list[JSONDict], dict[int | str, str]]', run(dbctx, 'get', opts.search, opts.type, opts.user_type, opts.annotation_user))
    # Book ids are sent as strings when using a remote library
    titles = {int(k): v for k, v in titles.items()}
    if action == 'search' and opts.format == 'json':
        prints(json_for_terminal([dict(a, title=titles.get(a['book_id'], '')) for a in annots]))
        return 0
    if action in ('list', 'search'):
        if action == 'list':
            annots = sorted(annots, key=lambda a: a['id'])
        for a in annots:
            fields = (str(a['id']), titles.get(a['book_id'], ''), a['annotation']['type'], a['format'], f"{a['user_type']}:{a['user']}", a['text'] or '')
            # One annotation per line, with tab separated fields
            prints(for_terminal('\t'.join(' '.join(x.split()) for x in fields)))
    else:
        if opts.format == 'json':
            # The same calibre annotation collection as exported by the Browse annotations tool
            collection = []
            for a in annots:
                x = a['annotation'].copy()
                x['book_id'], x['format'], x['user_type'], x['user'] = a['book_id'], a['format'], a['user_type'], a['user']
                collection.append(x)
            data = json_for_terminal({'version': 1, 'type': 'calibre_annotation_collection', 'annotations': collection})
        else:
            data = for_terminal(render_as_text(annots, titles, opts.format == 'markdown'))
        if data:
            prints(data)
    return 0
