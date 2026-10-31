#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import os
import sys
from typing import TYPE_CHECKING, cast

from calibre import prints
from calibre.db import FTSQueryError
from calibre.db.cli.utils import args_to_action, for_terminal
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.html2text import html2text
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from optparse import Values

    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBContext
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser

readonly = False
version = 0  # change this if you change signature of implementation()
ACTIONS = ('list', 'search', 'show', 'set', 'remove')
ACTION_DEFAULT = 'list'


def unsupported_field_error(db: Cache, field: str) -> str:
    return _('The field {0} does not support notes. Fields that support notes are: {1}').format(field, ', '.join(sorted(db.field_supports_notes())))  # ty: ignore[invalid-argument-type]


def item_id_for(db: Cache, field: str, item_name: str) -> tuple[int, str] | tuple[None, str]:
    if not db.field_supports_notes(field):
        return None, unsupported_field_error(db, field)
    item_id = db.get_item_id(field, item_name)
    if item_id is None:
        return None, _('No item named {0} found in the field {1}').format(item_name, field)
    return item_id, ''


def import_note_data(db: Cache, field: str, item_id: int, html: str | bytes) -> None:
    # Import from an empty directory so that relative and file: image URLs in
    # the HTML cannot be used to read arbitrary files into the note
    with TemporaryDirectory() as tdir:
        path = os.path.join(tdir, 'note.html')
        with open(path, 'wb') as f:
            f.write(html.encode('utf-8') if isinstance(html, str) else html)
        db.import_note(field, item_id, path)


def implementation(
    db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, action: str, *args: object
) -> tuple[bool, str | list[tuple[str, str, str]] | list[tuple[str, str]]]:
    is_remote = notify_changes is not None
    if action == 'search':
        query, field = cast('tuple[str, str | None]', args)
        # Searching notes needs an exclusive lock. Keep it until the item names
        # are read as well, so that items cannot be renamed or removed in between.
        with db.quiet_write_lock:
            if field is not None and not db.field_supports_notes(field):
                return False, unsupported_field_error(db, field)
            try:
                results = db._search_notes(
                    query,
                    restrict_to_fields=(field,) if field is not None else (),
                    highlight_start='',
                    highlight_end='',
                    snippet_size=32,
                )
            except FTSQueryError as err:
                return False, str(err)
            ans = [(r['field'], db._get_item_name(r['field'], r['item_id']), r['text']) for r in results]
        return True, ans
    if action == 'list':
        field = cast('str | None', args[0]) if args else None
        with db.safe_read_lock:
            if field is not None and not db.field_supports_notes(field):
                return False, unsupported_field_error(db, field)
            items = {field: db.get_all_items_that_have_notes(field)} if field else db.get_all_items_that_have_notes()
            ans = []
            for field_name, item_ids in items.items():  # ty: ignore[unresolved-attribute]
                id_map = db.get_id_map(field_name)
                ans.extend((field_name, id_map[item_id]) for item_id in item_ids if item_id in id_map)
        return True, sorted(ans)
    field, item_name = cast('tuple[str, str]', args[:2])
    with db.safe_read_lock:
        item_id, err = item_id_for(db, field, item_name)
    if item_id is None:
        return False, err
    if action == 'show':
        as_html = args[2]
        if as_html:
            return True, db.export_note(field, item_id)
        doc = db.notes_for(field, item_id)
        return True, html2text(doc, default_image_alt=' ') if doc else ''
    if action == 'set':
        html_or_path, is_path = cast('tuple[str | bytes, bool]', args[2:4])
        if is_path:
            if is_remote:
                return False, _('Cannot import notes from files on the server, send the HTML instead')
            db.import_note(field, item_id, html_or_path)
        else:
            import_note_data(db, field, item_id, html_or_path)
        return True, ''
    if action == 'remove':
        db.set_notes_for(field, item_id, '')
        return True, ''
    return False, _('Unknown action: {}').format(action)


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''\
%prog notes [options] [list|search|show|set|remove]

Manage the notes attached to items such as authors, series, tags and
publishers. FIELD is the lookup name of the field, for example: authors,
series, tags, publisher or #mycolumn. ITEM is the name of the item, for
example the name of an author. Items are matched case insensitively.

List the items that have notes, optionally only those in the specified field.
This is the default action:

%prog notes list [FIELD]

Search the text of notes using the same SQLite full text search syntax as
the Browse notes tool in calibre. Print the field, item name and an excerpt
for each match. Use --field to search only the notes in a particular field:

%prog notes search "search expression"
%prog notes search --field authors "search expression"

Print the note for an item as Markdown formatted text, or with --as-html as
an HTML document with any images embedded, suitable for use with set:

%prog notes show FIELD ITEM

Replace the note for an item with the contents of an HTML file. Use - to
read the HTML from standard input. Images embedded as base64-encoded data:
URLs are added to the note for both local and remote libraries. When using a
local library and reading from a file, images referenced by paths relative to
the file are added as well:

%prog notes set FIELD ITEM FILE

Remove the note for an item:

%prog notes remove FIELD ITEM
'''
        )
    )
    parser.add_option(
        '--field',
        default=None,
        help=_('When searching notes, restrict the search to this field, for example: authors, tags or #mycolumn'),
    )
    parser.add_option(
        '--as-html',
        default=False,
        action='store_true',
        help=_('When showing a note, output it as HTML instead of Markdown formatted text'),
    )
    return parser


def run(dbctx: DBContext, *args: object) -> object:
    ok, ans = cast('tuple[bool, object]', dbctx.run('notes', *args))
    if not ok:
        raise SystemExit(ans)
    return ans


def main(opts: Values, args: list[str], dbctx: DBContext) -> int:
    action, args = args_to_action(args, ACTIONS, default_action=ACTION_DEFAULT)
    if opts.field is not None and action != 'search':
        raise SystemExit(_('Error: The --field option can only be used with search'))
    if action == 'search':
        if len(args) != 1 or not args[0].strip():
            raise SystemExit(_('Error: You must specify one non-empty search expression'))
        if opts.as_html:
            raise SystemExit(_('Error: The --as-html option cannot be used with search'))
        for field, item_name, text in cast('list[tuple[str, str, str]]', run(dbctx, 'search', args[0], opts.field)):
            # Keep each result on one line and remove terminal control characters.
            prints(for_terminal('\t'.join(' '.join(x.split()) for x in (field, item_name or '', text))))
        return 0
    if action == 'list':
        if len(args) > 1:
            raise SystemExit(_('Error: You can specify at most one field to list'))
        for field, item_name in cast('list[tuple[str, str]]', run(dbctx, 'list', *args)):
            prints(f'{field}: {item_name}')
        return 0
    if len(args) < 2:
        raise SystemExit(_('Error: You must specify a field and the name of an item'))
    if action == 'set' and len(args) < 3:
        raise SystemExit(_('Error: You must specify the file to read the note from'))
    if len(args) > (3 if action == 'set' else 2):
        raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
    field, item_name = args[:2]
    if action == 'show':
        text = run(dbctx, 'show', field, item_name, opts.as_html)
        if text:
            prints(text)
    elif action == 'set':
        path = args[2]
        if path == '-':
            run(dbctx, 'set', field, item_name, sys.stdin.buffer.read(), False)
            return 0
        try:
            with open(path, 'rb') as f:
                data = f.read() if dbctx.is_remote else b''
        except OSError as err:
            raise SystemExit(_('Error: Failed to read the note from {0} with error: {1}').format(path, err))
        if dbctx.is_remote:
            run(dbctx, 'set', field, item_name, data, False)
        else:
            run(dbctx, 'set', field, item_name, path, True)
    else:
        run(dbctx, 'remove', field, item_name)
    return 0
