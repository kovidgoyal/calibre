#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import re

from calibre import prints
from calibre.db.cli import integers_from_string
from calibre.db.cli.utils import args_to_action
from calibre.utils.localization import _, ngettext

readonly = False
version = 0  # change this if you change signature of implementation()
ACTIONS = ('list', 'restore', 'delete', 'empty')


def list_entries(db):
    books, formats = db.list_trash_entries()

    def as_list(entries):
        return [(e.book_id, e.title, e.author, e.mtime, sorted(e.formats), e.restorable) for e in sorted(entries, key=lambda e: -e.mtime)]

    return as_list(books), as_list(formats)


def delete_entries(db, entries, of_formats):
    count, errors = 0, []
    for book_id in sorted(entries):
        try:
            db.delete_trash_entry(book_id, 'f' if of_formats else 'b')
        except Exception as e:
            errors.append(f'{book_id}: {e}')
        else:
            count += 1
    return count, errors


def restore_entries(db, notify_changes, entries, of_formats):
    from calibre.srv.changes import books_added, formats_added

    # done is what has actually been restored, for notifying the Content server, count is the number of entries restored completely
    done, count, errors = {}, 0, []
    for book_id, entry in sorted(entries.items()):
        if not entry.restorable:
            errors.append(_('{}: The book no longer exists, its formats cannot be restored').format(book_id))
            continue
        try:
            if of_formats:
                for fmt in sorted(entry.formats):
                    db.move_format_from_trash(book_id, fmt)
                    done.setdefault(book_id, []).append(fmt)
            else:
                db.move_book_from_trash(book_id)
                done[book_id] = []
        except Exception as e:
            errors.append(f'{book_id}: {e}')
        else:
            count += 1
    if notify_changes is not None and done:
        notify_changes(formats_added(done) if of_formats else books_added(done))
    return count, errors


def implementation(db, notify_changes, action, *args):
    if action not in ACTIONS:
        return False, _('Unknown action: {}').format(action)
    if action == 'empty':
        db.clear_trash_bin()
        return True, None
    if action == 'list':
        return True, list_entries(db)
    book_ids, of_formats = set(args[0]), args[1]
    books, formats = db.list_trash_entries()
    entries = {e.book_id: e for e in (formats if of_formats else books)}
    if missing := book_ids - set(entries):
        return False, _('No entries in the trash bin for the books: {}').format(', '.join(map(str, sorted(missing))))
    entries = {book_id: entries[book_id] for book_id in book_ids}
    if action == 'delete':
        return True, delete_entries(db, entries, of_formats)
    return True, restore_entries(db, notify_changes, entries, of_formats)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog trash [options] (list|restore|delete|empty) [ids]

Manage the books and formats that have been removed and placed in the trash bin.
Entries in the trash bin are permanently deleted automatically after some days.
ids is a comma separated list of book ids, as for the remove command, for
example: 23,34,57-85 (when specifying a range, the last number in the range is
not included).

List the removed books and formats, most recently removed first, with the
times they were removed in local time. Removed formats of books that no longer
exist are marked as not restorable, they can only be deleted. With
--for-machine, the times are in UTC:

%prog trash list

Restore removed books, or with --formats, the removed formats of books:

%prog trash restore ids

Permanently delete entries from the trash bin:

%prog trash delete ids

Permanently delete everything in the trash bin:

%prog trash empty
'''
        )
    )
    parser.add_option(
        '--formats',
        default=False,
        action='store_true',
        help=_('Act on the removed formats of the specified books, instead of on removed books'),
    )
    parser.add_option(
        '--for-machine',
        default=False,
        action='store_true',
        help=_('Generate output for the list action in JSON format, which is more suitable for machine parsing'),
    )
    return parser


def run(dbctx, *args):
    ok, ans = dbctx.run('trash', *args)
    if not ok:
        raise SystemExit(ans)
    return ans


def main(opts, args, dbctx):
    from calibre.utils.date import as_local_time, utcfromtimestamp

    action, args = args_to_action(args, ACTIONS)
    if action in ('list', 'empty'):
        if args:
            raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
        if opts.formats:
            raise SystemExit(_('Error: The --formats option cannot be used with the {} action').format(action))
        if action == 'empty':
            run(dbctx, 'empty')
            prints(_('The trash bin has been emptied'))
            return 0
        books, formats = run(dbctx, 'list')
        if opts.for_machine:

            def as_dicts(entries):
                return [
                    {'id': i, 'title': t, 'author': a, 'removed': utcfromtimestamp(m).isoformat(), 'formats': f, 'restorable': r}
                    for i, t, a, m, f, r in entries
                ]

            prints(json.dumps({'books': as_dicts(books), 'formats': as_dicts(formats)}, ensure_ascii=False, indent=2))
            return 0

        def date(m):
            return as_local_time(utcfromtimestamp(m)).strftime('%Y-%m-%d %H:%M')

        def clean(x):
            # Tabs and newlines in titles or authors would break the columns
            return re.sub(r'\s+', ' ', x)

        for heading, entries in ((_('Books'), books), (_('Formats'), formats)):
            if not entries:
                continue
            prints(heading + ':')
            for book_id, title, author, mtime, fmts, restorable in entries:
                extra = '\t' + ', '.join(fmts) if fmts else ''
                if not restorable:
                    extra += '\t' + _('(not restorable)')
                prints(f'{book_id}\t{clean(title)}\t{clean(author)}\t{date(mtime)}{extra}')
        return 0
    if not args:
        raise SystemExit(_('Error: You must specify the ids of the books'))
    book_ids = set()
    try:
        for arg in args:
            book_ids |= set(integers_from_string(arg))
    except ValueError:
        raise SystemExit(_('Error: Book ids must be numbers'))
    count, errors = run(dbctx, action, sorted(book_ids), opts.formats)
    if action == 'delete':
        prints(ngettext('One entry permanently deleted', '{} entries permanently deleted', count).format(count))
        failed = _('Failed to delete:')
    else:
        if opts.formats:
            prints(ngettext('The formats of one book restored', 'The formats of {} books restored', count).format(count))
        else:
            prints(ngettext('One book restored', '{} books restored', count).format(count))
        failed = _('Failed to restore:')
    if errors:
        raise SystemExit(failed + '\n' + '\n'.join(errors))
    return 0
