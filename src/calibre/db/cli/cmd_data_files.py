#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
import shutil
import stat
from io import BytesIO

from calibre import as_unicode, prints
from calibre.db.cli.utils import for_terminal
from calibre.db.constants import DATA_DIR_NAME, DATA_FILE_PATTERN
from calibre.ptempfile import SpooledTemporaryFile
from calibre.utils.filenames import is_path_inside, is_windows_reserved_filename, path_from_root
from calibre.utils.localization import _

readonly = False
version = 0  # change this if you change signature of implementation()
# Action with the argument numbers and their types
# The types of the arguments of each action after the book id. The data for
# add and the destination for get are checked separately as they differ for
# local and remote libraries.
ACTIONS = {
    'list': (1, ()),
    'add': (2, (str, object, bool)),
    'get': (2, (str, object)),
    'rename': (3, (str, str, bool)),
    'remove': (2, (str, bool)),
}
# Characters that are not allowed in file names on at least one supported
# platform, : is rejected by path_from_root()
INVALID_NAME_CHARS = frozenset('<>"|?*' + ''.join(map(chr, range(32))))


def data_root(db, book_id):
    book_dir = os.path.join(db.backend.library_path, db._field_for('path', book_id))
    root = os.path.join(book_dir, DATA_DIR_NAME)
    if not is_path_inside(os.path.realpath(book_dir), os.path.realpath(root)):
        raise ValueError(_('The data directory of the book with id {} is outside the book directory').format(book_id))
    return root


def resolves_inside(root, path):
    return is_path_inside(os.path.realpath(root), os.path.realpath(path))


def data_files(db, book_id):
    # Map of names relative to data/ to ExtraFile, omitting symlinks that
    # resolve to somewhere outside the data directory and anything that is not
    # a regular file, such as FIFOs, which could block reads indefinitely
    root = data_root(db, book_id)
    return {
        ef.relpath[len(DATA_DIR_NAME) + 1 :]: ef
        for ef in db._list_extra_files(book_id, pattern=DATA_FILE_PATTERN)
        if stat.S_ISREG(ef.stat_result.st_mode) and resolves_inside(root, ef.file_path)
    }


def existing_data_file(db, book_id, name):
    # Look for the exact name first, so that existing files can be used even
    # if their names would not be accepted for new files, then with \ as a
    # separator.
    files = data_files(db, book_id)
    ef = files.get(name) or files.get(name.replace('\\', '/'))
    if ef is None and not db.backend.is_case_sensitive:
        # Names that differ only in case refer to the same file
        key = name.replace('\\', '/').lower()
        ef = next((x for n, x in files.items() if n.lower() == key), None)
    if ef is None:
        raise ValueError(_('No data file named: {}').format(name))
    if '\\' in ef.relpath:
        # The backend treats \ as a separator on all platforms
        raise ValueError(_('Data files with a backslash in their names are not supported: {}').format(name))
    return ef.relpath


def new_data_file(db, book_id, name):
    # Names are relative to data/, never to the book or library directory.
    try:
        for component in name.replace('\\', '/').split('/'):
            if INVALID_NAME_CHARS.intersection(component):
                raise ValueError('invalid character in path')
            if component.endswith(('.', ' ')) and component not in ('.', '..'):
                # Windows silently strips these, changing the name
                raise ValueError('path components cannot end with a period or space')
            if is_windows_reserved_filename(component):
                raise ValueError('reserved name not allowed in path')
        root = data_root(db, book_id)
        path = path_from_root(root, name, reject_colon=True, case_sensitive=db.backend.is_case_sensitive)
        if not resolves_inside(root, path):
            raise ValueError('path resolves to outside the data directory')
    except ValueError as err:
        raise ValueError(_('Invalid data file name: {0} ({1})').format(name, err))
    return DATA_DIR_NAME + '/' + name.replace('\\', '/')


def remove_empty_parents(db, book_id, relpath):
    # Remove directories left empty by moving a file out of them, but not the
    # data directory itself
    root = data_root(db, book_id)
    parent = os.path.dirname(path_from_root(root, relpath[len(DATA_DIR_NAME) + 1 :]))
    while is_path_inside(root, parent):
        try:
            os.rmdir(parent)
        except OSError:
            break
        parent = os.path.dirname(parent)


def implementation(db, notify_changes, action, book_id, *args):
    if action not in ACTIONS:
        return False, _('Unknown action: {}').format(action)
    is_remote = notify_changes is not None
    # Remote requests can contain arbitrary data, so check it before use
    types = ACTIONS[action][1]
    if not isinstance(book_id, int) or len(args) != len(types) or not all(isinstance(x, t) for x, t in zip(args, types)):
        return False, _('Invalid arguments for: {}').format(action)
    if is_remote and action == 'add' and not (isinstance(args[1], (list, tuple)) and len(args[1]) == 2 and isinstance(args[1][1], bytes)):
        return False, _('Invalid arguments for: {}').format(action)
    lock = db.quiet_write_lock if action in ('add', 'rename', 'remove') else db.safe_read_lock
    try:
        with lock:
            if not db._has_id(book_id):
                return False, _('No book with id: {}').format(book_id)
            if action == 'list':
                return True, [
                    {'name': name, 'size': ef.stat_result.st_size, 'mtime': ef.stat_result.st_mtime} for name, ef in sorted(data_files(db, book_id).items())
                ]
            if action == 'add':
                name, data, replace = args
                relpath = new_data_file(db, book_id, name)
                if is_remote:
                    # The data is always uploaded by the client, never a
                    # path on the server
                    data = BytesIO(data[1])
                if not db._add_extra_files(book_id, {relpath: data}, replace=replace)[relpath]:
                    return False, _('Cannot add data file (it may already exist): {}').format(name)
                return True, None
            if action == 'get':
                name, dest = args
                relpath = existing_data_file(db, book_id, name)
                # A remote destination is always on the client, never a path
                # for the server to write to. Local copies need no buffering.
                if is_remote:
                    dest = BytesIO()
                db._copy_extra_file_to(book_id, relpath, dest)
                return True, dest.getvalue() if is_remote else None
            if action == 'rename':
                name, new_name, replace = args
                relpath = existing_data_file(db, book_id, name)
                newpath = new_data_file(db, book_id, new_name)
                if newpath == relpath:
                    return True, None
                if relpath not in db._rename_extra_files(book_id, {relpath: newpath}, replace=replace):
                    return False, _('Cannot rename data file (the destination may already exist): {}').format(new_name)
                remove_empty_parents(db, book_id, relpath)
                return True, None
            name, permanent = args
            relpath = existing_data_file(db, book_id, name)
            errors = db._remove_extra_files(book_id, (relpath,), permanent=permanent)
            if err := errors.get(relpath):
                return False, str(err)
            remove_empty_parents(db, book_id, relpath)
            return True, None
    except (OSError, ValueError) as err:
        return False, str(err)


def option_parser(get_parser, args):
    parser = get_parser(
        _('''\
%prog data_files [options] (list|add|get|rename|remove) BOOK_ID ...

Manage the extra data files associated with a book, in local or remote libraries.
Names are relative to the book's data directory. Use / for subdirectories,
\\ is also accepted. Files whose names contain a \\ are listed, but cannot
otherwise be managed.
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

Directories left empty by rename and remove are deleted. With remote
libraries, each file is transferred in a single request, so very large files
need enough memory on both the client and the server, and uploads are limited
by the maximum request size of the server.
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


def download(dbctx, book_id, name, output, replace):
    output = os.path.abspath(output)
    if os.path.isdir(output):
        raise SystemExit(_('The output must be a file, not a directory: {}').format(output))

    def save_to(dest):
        data = run(dbctx, 'get', book_id, name, None if dbctx.is_remote else dest)
        if dbctx.is_remote:
            dest.write(data)

    try:
        if replace:
            # Finish downloading before writing to the destination. In
            # particular, a missing remote file must not truncate an existing
            # local file. Overwriting the destination rather than replacing it
            # keeps its permissions, ownership and any symlinks, and fails if
            # it is read-only, as with other programs.
            with SpooledTemporaryFile(max_size=32 * 1024 * 1024) as buf:
                save_to(buf)
                buf.seek(0)
                with open(output, 'wb') as dest:
                    shutil.copyfileobj(buf, dest)
        else:
            # Create the output exclusively, so that a file created after any
            # earlier check is never replaced
            with open(output, 'xb') as dest:
                try:
                    save_to(dest)
                except BaseException:
                    dest.close()
                    os.remove(output)
                    raise
    except FileExistsError:
        raise SystemExit(_('The output file already exists: {}').format(output))
    except OSError as err:
        raise SystemExit(_('Failed to save to {0} with error: {1}').format(output, as_unicode(err)))


def main(opts, args, dbctx):
    if not args:
        raise SystemExit(_('Error: You must specify an action, one of: {}').format(', '.join(ACTIONS)))
    action, args = args[0], args[1:]
    if action not in ACTIONS:
        raise SystemExit(_('Error: Action {0} not recognized, must be one of: {1}').format(action, ', '.join(ACTIONS)))
    count = ACTIONS[action][0]
    if len(args) != count:
        raise SystemExit(_('Error: Incorrect number of arguments for: {}').format(action))
    try:
        book_id = int(args[0])
    except ValueError:
        raise SystemExit(_('Error: The book id must be a number'))
    for option, invalid in (
        ('--for-machine', opts.for_machine and action != 'list'),
        ('--name', opts.name is not None and action != 'add'),
        ('--output', opts.output is not None and action != 'get'),
        ('--replace', opts.replace and action not in ('add', 'get', 'rename')),
        ('--permanent', opts.permanent and action != 'remove'),
    ):
        if invalid:
            raise SystemExit(_('Error: The option {0} cannot be used with {1}').format(option, action))
    if action == 'list':
        entries = run(dbctx, action, book_id)
        if opts.for_machine:
            prints(json.dumps(entries, ensure_ascii=False, indent=2))
        else:
            for entry in entries:
                prints('{}\t{}\t{}'.format(for_terminal(entry['name']).replace('\t', ' ').replace('\n', ' '), entry['size'], entry['mtime']))
    if action == 'add':
        run(dbctx, action, book_id, opts.name if opts.name is not None else os.path.basename(args[1]), dbctx.path(args[1]), opts.replace)
    if action == 'rename':
        run(dbctx, action, book_id, args[1], args[2], opts.replace)
    if action == 'remove':
        run(dbctx, action, book_id, args[1], opts.permanent)
    if action == 'get':
        if not opts.output:
            raise SystemExit(_('Error: You must specify --output for the get action'))
        download(dbctx, book_id, args[1], opts.output, opts.replace)
    return 0
