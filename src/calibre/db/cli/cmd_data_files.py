#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
from io import BytesIO
from tempfile import NamedTemporaryFile

from calibre import prints
from calibre.db.cli.utils import for_terminal
from calibre.db.constants import DATA_DIR_NAME, DATA_FILE_PATTERN
from calibre.utils.filenames import is_path_inside, path_from_root
from calibre.utils.localization import _

readonly = False
version = 0  # change this if you change signature of implementation()
ACTIONS = ('list', 'add', 'get', 'rename', 'remove')


def data_path(db, book_id, name):
    # Names are relative to data/, never to the book or library directory.
    book_dir = os.path.join(db.backend.library_path, db._field_for('path', book_id))
    root = os.path.join(book_dir, DATA_DIR_NAME)
    path = path_from_root(root, name, reject_colon=True)
    if (
        '\0' in name
        or not is_path_inside(os.path.realpath(book_dir), os.path.realpath(root))
        or not is_path_inside(os.path.realpath(root), os.path.realpath(path))
    ):
        raise ValueError(_('Invalid data file name: {}').format(name))
    return DATA_DIR_NAME + '/' + name.replace('\\', '/')


def implementation(db, notify_changes, action, book_id, *args):
    if action not in ACTIONS:
        return False, _('Unknown action: {}').format(action)
    is_remote = notify_changes is not None
    lock = db.quiet_write_lock if action in ('add', 'rename', 'remove') else db.safe_read_lock
    try:
        with lock:
            if not db._has_id(book_id):
                return False, _('No book with id: {}').format(book_id)
            if action == 'list':
                entries = []
                for ef in sorted(db._list_extra_files(book_id, pattern=DATA_FILE_PATTERN), key=lambda x: x.relpath):
                    name = ef.relpath[len(DATA_DIR_NAME) + 1 :]
                    data_path(db, book_id, name)
                    entries.append({'name': name, 'size': ef.stat_result.st_size, 'mtime': ef.stat_result.st_mtime})
                return True, entries
            relpath = data_path(db, book_id, args[0])
            if action == 'add':
                data, replace = args[1:]
                if is_remote:
                    data = BytesIO(data[1])
                if not db._add_extra_files(book_id, {relpath: data}, replace=replace)[relpath]:
                    return False, _('Cannot add data file (it may already exist): {}').format(args[0])
                return True, None
            files = {ef.relpath for ef in db._list_extra_files(book_id, pattern=DATA_FILE_PATTERN)}
            if relpath not in files:
                return False, _('No data file named: {}').format(args[0])
            if action == 'get':
                # A remote destination is always on the client, never a path
                # for the server to write to. Local copies need no buffering.
                dest = BytesIO() if is_remote else args[1]
                db._copy_extra_file_to(book_id, relpath, dest)
                return True, dest.getvalue() if is_remote else None
            if action == 'rename':
                newpath = data_path(db, book_id, args[1])
                if newpath == relpath:
                    return True, None
                if relpath not in db._rename_extra_files(book_id, {relpath: newpath}, replace=args[2]):
                    return False, _('Cannot rename data file (the destination may already exist): {}').format(args[1])
                return True, None
            errors = db._remove_extra_files(book_id, (relpath,), permanent=args[1])
            if err := errors.get(relpath):
                return False, str(err)
            return True, None
    except (OSError, ValueError) as err:
        return False, str(err)


def option_parser(get_parser, args):
    parser = get_parser(
        _('''\
%prog data_files [options] (list|add|get|rename|remove) BOOK_ID ...

Manage the extra data files associated with a book, in local or remote libraries.
Names are relative to the book's data directory. Use / for subdirectories.
E-book formats, covers and metadata.opf cannot be accessed with this command.
Remote libraries require an account with write access, as for other management
commands, and do not support accounts with per-library search restrictions.

List file names, sizes in bytes and modification times (seconds since the Unix
epoch). Use --for-machine for JSON output:

%prog data_files list BOOK_ID

Add a file, using its basename, or --name to specify a name or subdirectory.
Existing files are not replaced unless --replace is specified. This is also
available through add_format --as-extra-data-file:

%prog data_files add BOOK_ID FILE

Save one data file to --output on the local machine. Existing output files
are not replaced unless --replace is specified:

%prog data_files get BOOK_ID NAME --output FILE

Rename a file. Existing destinations are not replaced unless --replace is set:

%prog data_files rename BOOK_ID NAME NEW_NAME

Remove a file to the operating system's recycle bin. With --permanent, delete
it permanently instead. For remote libraries this happens on the server:

%prog data_files remove BOOK_ID NAME
''')
    )
    parser.add_option('--for-machine', action='store_true', default=False, help=_('Output the list of files as JSON'))
    parser.add_option('--name', default=None, help=_('Name to use for the added file, relative to the data directory'))
    parser.add_option('--output', default=None, help=_('Local destination for the get action'))
    parser.add_option('--replace', action='store_true', default=False, help=_('Allow replacing existing files when adding, getting or renaming'))
    parser.add_option('--permanent', action='store_true', default=False, help=_('Permanently delete the data file instead of using the recycle bin'))
    return parser


def run(dbctx, *args):
    ok, ans = dbctx.run('data_files', *args)
    if not ok:
        raise SystemExit(ans)
    return ans


def main(opts, args, dbctx):
    if not args or args[0] not in ACTIONS:
        raise SystemExit(_('You must specify an action, one of: {}').format(', '.join(ACTIONS)))
    action, args = args[0], args[1:]
    count = {'list': 1, 'add': 2, 'get': 2, 'rename': 3, 'remove': 2}[action]
    if len(args) != count:
        raise SystemExit(_('Incorrect number of arguments for: {}').format(action))
    try:
        book_id = int(args[0])
    except ValueError:
        raise SystemExit(_('The book id must be a number'))
    for option, invalid in (
        ('--for-machine', opts.for_machine and action != 'list'),
        ('--name', opts.name is not None and action != 'add'),
        ('--output', opts.output is not None and action != 'get'),
        ('--replace', opts.replace and action not in ('add', 'get', 'rename')),
        ('--permanent', opts.permanent and action != 'remove'),
    ):
        if invalid:
            raise SystemExit(_('The option {0} cannot be used with {1}').format(option, action))
    if action == 'list':
        entries = run(dbctx, action, book_id)
        if opts.for_machine:
            prints(json.dumps(entries, ensure_ascii=False, indent=2))
        else:
            for entry in entries:
                prints('{}\t{}\t{}'.format(for_terminal(entry['name']).replace('\t', ' ').replace('\n', ' '), entry['size'], entry['mtime']))
    elif action == 'add':
        run(dbctx, action, book_id, opts.name if opts.name is not None else os.path.basename(args[1]), dbctx.path(args[1]), opts.replace)
    elif action == 'rename':
        run(dbctx, action, book_id, args[1], args[2], opts.replace)
    elif action == 'remove':
        run(dbctx, action, book_id, args[1], opts.permanent)
    else:
        if not opts.output:
            raise SystemExit(_('You must specify --output for the get action'))
        if not opts.replace and os.path.lexists(opts.output):
            raise SystemExit(_('The output file already exists: {}').format(opts.output))
        # Finish downloading before replacing the destination. In particular,
        # a missing remote file must not truncate an existing local file.
        path = None
        try:
            with NamedTemporaryFile(dir=os.path.dirname(os.path.abspath(opts.output)), delete=False) as dest:
                path = dest.name
                data = run(dbctx, action, book_id, args[1], None if dbctx.is_remote else dest)
                if dbctx.is_remote:
                    dest.write(data)
            os.replace(path, opts.output)
        finally:
            if path is not None and os.path.exists(path):
                os.remove(path)
    return 0
