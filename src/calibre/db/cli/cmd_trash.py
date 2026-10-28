#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json

from calibre import prints
from calibre.constants import trash_name
from calibre.db.cli import integers_from_string
from calibre.utils.localization import _, ngettext

readonly = False
version = 0  # change this if you change signature of implementation()
ACTIONS = ('list', 'restore', 'delete', 'empty')


def implementation(db, notify_changes, action, *args):
    from calibre.srv.changes import books_added, formats_added

    is_remote = notify_changes is not None
    if action == 'empty':
        db.clear_trash_bin()
        return True, None
    books, formats = db.list_trash_entries()
    if action == 'list':

        def as_list(entries):
            return [(e.book_id, e.title, e.author, e.mtime, sorted(e.formats)) for e in sorted(entries, key=lambda e: -e.mtime)]

        return True, (as_list(books), as_list(formats))
    book_ids, of_formats = set(args[0]), args[1]
    entries = {e.book_id: e for e in (formats if of_formats else books)}
    if missing := book_ids - set(entries):
        return False, _('No entries in the {0} for the books: {1}').format(trash_name(), ', '.join(map(str, sorted(missing))))
    if action == 'delete':
        for book_id in book_ids:
            db.delete_trash_entry(book_id, 'f' if of_formats else 'b')
        return True, (len(book_ids), [])
    if action != 'restore':
        return False, _('Unknown action: {}').format(action)
    done, errors = {}, []
    for book_id in sorted(book_ids):
        try:
            if of_formats:
                for fmt in sorted(entries[book_id].formats):
                    db.move_format_from_trash(book_id, fmt)
                    done.setdefault(book_id, []).append(fmt)
            else:
                db.move_book_from_trash(book_id)
                done[book_id] = []
        except Exception as e:
            errors.append(f'{book_id}: {e}')
    if is_remote and done:
        notify_changes(formats_added(done) if of_formats else books_added(done))
    return True, (len(done), errors)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog trash [options] (list|restore|delete|empty) [ids]

Manage the books and formats that have been removed and placed in the {0}.
Entries in the {0} are permanently deleted automatically after some days.
ids is a comma separated list of book ids, as for the remove command, for
example: 23,34,57-85

List the removed books and formats, most recently removed first:

%prog trash list

Restore removed books, or with --formats, the removed formats of books:

%prog trash restore ids

Permanently delete entries from the {0}:

%prog trash delete ids

Permanently delete everything in the {0}:

%prog trash empty
'''
        ).format(trash_name())
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
        help=_('Generate output in JSON format, which is more suitable for machine parsing'),
    )
    return parser


def run(dbctx, *args):
    ok, ans = dbctx.run('trash', *args)
    if not ok:
        raise SystemExit(ans)
    return ans


def main(opts, args, dbctx):
    from calibre.utils.date import as_local_time, utcfromtimestamp

    if not args:
        raise SystemExit(_('Error: You must specify an action, one of: ({})').format('|'.join(ACTIONS)))
    action, args = args[0], args[1:]
    if action not in ACTIONS:
        raise SystemExit(_('Error: Action {0} not recognized, must be one of: ({1})').format(action, '|'.join(ACTIONS)))
    if action in ('list', 'empty'):
        if args:
            raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
        if action == 'empty':
            run(dbctx, 'empty')
            prints(_('The {} has been emptied').format(trash_name()))
            return 0
        books, formats = run(dbctx, 'list')
        if opts.for_machine:

            def as_dicts(entries):
                return [{'id': i, 'title': t, 'author': a, 'removed': utcfromtimestamp(m).isoformat(), 'formats': f} for i, t, a, m, f in entries]

            prints(json.dumps({'books': as_dicts(books), 'formats': as_dicts(formats)}, ensure_ascii=False, indent=2))
            return 0

        def date(m):
            return as_local_time(utcfromtimestamp(m)).strftime('%Y-%m-%d %H:%M')

        for heading, entries in ((_('Books'), books), (_('Formats'), formats)):
            if not entries:
                continue
            prints(heading + ':')
            for book_id, title, author, mtime, fmts in entries:
                extra = '\t' + ', '.join(fmts) if fmts else ''
                prints(f'{book_id}\t{title}\t{author}\t{date(mtime)}{extra}')
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
        return 0
    if opts.formats:
        prints(ngettext('The formats of one book restored', 'The formats of {} books restored', count).format(count))
    else:
        prints(ngettext('One book restored', '{} books restored', count).format(count))
    if errors:
        raise SystemExit(_('Failed to restore:') + '\n' + '\n'.join(errors))
    return 0
