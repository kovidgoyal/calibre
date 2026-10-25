#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import os
import sys

from calibre import prints
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.html2text import html2text
from calibre.utils.localization import _

readonly = False
version = 0  # change this if you change signature of implementation()


def unsupported_field_error(db, field):
    return _('The field {0} does not support notes. Fields that support notes are: {1}').format(field, ', '.join(sorted(db.field_supports_notes())))


def item_id_for(db, field, item_name):
    if not db.field_supports_notes(field):
        return None, unsupported_field_error(db, field)
    item_id = db.get_item_id(field, item_name)
    if item_id is None:
        return None, _('No item named {0} found in the field {1}').format(item_name, field)
    return item_id, ''


def import_note_data(db, field, item_id, html):
    # Import from an empty directory so that relative and file: image URLs in
    # the HTML cannot be used to read arbitrary files into the note
    with TemporaryDirectory() as tdir:
        path = os.path.join(tdir, 'note.html')
        with open(path, 'wb') as f:
            f.write(html.encode('utf-8') if isinstance(html, str) else html)
        db.import_note(field, item_id, path)


def implementation(db, notify_changes, action, *args):
    is_remote = notify_changes is not None
    if action == 'list':
        field = args[0] if args else None
        with db.safe_read_lock:
            if field is not None and not db.field_supports_notes(field):
                return False, unsupported_field_error(db, field)
            items = {field: db.get_all_items_that_have_notes(field)} if field else db.get_all_items_that_have_notes()
            ans = []
            for field_name, item_ids in items.items():
                id_map = db.get_id_map(field_name)
                ans.extend((field_name, id_map[item_id]) for item_id in item_ids if item_id in id_map)
        return True, sorted(ans)
    field, item_name = args[:2]
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
        html_or_path, is_path = args[2:4]
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


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog notes [options] (list|show|set|remove)

Manage the notes attached to items such as authors, series, tags and
publishers. FIELD is the lookup name of the field, for example: authors,
series, tags, publisher or #mycolumn. ITEM is the name of the item, for
example the name of an author. Items are matched case insensitively.

List the items that have notes, optionally only those in the specified field:

%prog notes list [FIELD]

Print the note for an item as Markdown formatted text, or with --as-html as
an HTML document with any images embedded, suitable for use with set:

%prog notes show FIELD ITEM

Replace the note for an item with the contents of an HTML file. Use - to
read the HTML from standard input. Images embedded as data: URLs are always
added to the note. When using a local library and reading from a file, images
referenced by paths relative to the file are added as well:

%prog notes set FIELD ITEM FILE

Remove the note for an item:

%prog notes remove FIELD ITEM
'''
        )
    )
    parser.add_option(
        '--as-html',
        default=False,
        action='store_true',
        help=_('When showing a note, output it as HTML instead of Markdown formatted text'),
    )
    return parser


def run(dbctx, *args):
    ok, ans = dbctx.run('notes', *args)
    if not ok:
        raise SystemExit(ans)
    return ans


def main(opts, args, dbctx):
    if not args:
        raise SystemExit(_('Error: You must specify an action, one of: (list|show|set|remove)'))
    action, args = args[0], args[1:]
    if action == 'list':
        if len(args) > 1:
            raise SystemExit(_('Error: You can specify at most one field to list'))
        for field, item_name in run(dbctx, 'list', *args):
            prints(f'{field}: {item_name}')
        return 0
    if action not in ('show', 'set', 'remove'):
        raise SystemExit(_('Error: Action {} not recognized, must be one of: (list|show|set|remove)').format(action))
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
