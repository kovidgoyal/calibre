#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json

from calibre import prints
from calibre.db.cli.utils import args_to_action
from calibre.srv.changes import virtual_libraries
from calibre.utils.localization import _, ngettext

readonly = False
version = 0  # change this if you change signature of implementation()
ACTIONS = ('list', 'add', 'rename', 'remove')
ACTION_DEFAULT = 'list'


def implementation(db, notify_changes, action, *args):
    from calibre.utils.search_query_parser import ParseException

    is_remote = notify_changes is not None

    def parse_error(expr, e):
        return False, _('Failed to parse search query: ({0}) with error: {1}').format(expr, e)

    if action == 'list':
        with db.safe_read_lock:
            ans = {}
            for name, expr in db._pref('virtual_libraries', {}).items():
                try:
                    count = len(db._search(expr, allow_templates=not is_remote))
                except ParseException:
                    count = None
                ans[name] = (expr, count)
            return True, ans
    with db.write_lock:
        # Change a copy, so the cached preference is unchanged if anything fails
        orig_vls = db._pref('virtual_libraries', {})
        vls = dict(orig_vls)
        if action == 'add':
            name, expr, replace = args
            if name in vls and not replace:
                return False, _('A Virtual library named {} already exists').format(name)
            try:
                # Virtual libraries are evaluated with templates allowed, so remote clients must not be able to store
                # templates in them. Searching is not enough to check that, as it skips templates in parts of the
                # search that match no books.
                if is_remote and db._search_uses_templates(expr):
                    return False, _('Templates are not allowed in search expressions')
            except ParseException as e:
                return parse_error(expr, e)
            vls[name] = expr
            db._set_pref('virtual_libraries', vls)
            try:
                # Search once the Virtual library is stored, to catch searches that use it
                count = len(db._search(expr, allow_templates=not is_remote))
            except ParseException as e:
                db._set_pref('virtual_libraries', orig_vls)
                return parse_error(expr, e)
            if is_remote:
                notify_changes(virtual_libraries(added=(name,)))
            return True, count
        if action == 'rename':
            old, new = args
            if old not in vls:
                return False, _('No Virtual library named: {}').format(old)
            if new == old:
                return True, None
            if new in vls:
                return False, _('A Virtual library named {} already exists').format(new)
            db._set_pref('virtual_libraries', {(new if k == old else k): v for k, v in vls.items()})
            if db._pref('virtual_lib_on_startup') == old:
                db._set_pref('virtual_lib_on_startup', new)
            if is_remote:
                notify_changes(virtual_libraries(renamed=((old, new),)))
            return True, None
        if action == 'remove':
            names = tuple(dict.fromkeys(args))
            if missing := [x for x in names if x not in vls]:
                return False, _('No Virtual libraries named: {}').format(', '.join(missing))
            for name in names:
                del vls[name]
            db._set_pref('virtual_libraries', vls)
            if db._pref('virtual_lib_on_startup') in names:
                db._set_pref('virtual_lib_on_startup', '')
            if is_remote:
                notify_changes(virtual_libraries(removed=names))
            return True, len(names)
    return False, _('Unknown action: {}').format(action)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog virtual_libraries [options] [list|add|rename|remove]

Manage the Virtual libraries of this library. A Virtual library is a search
that behaves as though the library contains only the books it matches. To list
or search the books in a Virtual library, use: calibredb search 'vl:"name"'

List the Virtual libraries, with their searches and number of books. This is the
default action:

%prog virtual_libraries list

Create a Virtual library from a search:

%prog virtual_libraries add name search_expression

Rename a Virtual library:

%prog virtual_libraries rename name new_name

Remove Virtual libraries, the books in them are not changed:

%prog virtual_libraries remove name ...
'''
        )
    )
    parser.add_option(
        '--replace',
        default=False,
        action='store_true',
        help=_('Replace the search of an existing Virtual library with the same name when adding'),
    )
    parser.add_option(
        '--for-machine',
        default=False,
        action='store_true',
        help=_('Generate output in JSON format, which is more suitable for machine parsing'),
    )
    return parser


def run(dbctx, *args):
    ok, ans = dbctx.run('virtual_libraries', *args)
    if not ok:
        raise SystemExit(ans)
    return ans


def check_name(name: str) -> None:
    # Names starting with * are used by the GUI for temporary Virtual libraries made from the current search
    if name.startswith('*'):
        raise SystemExit(_('Error: A Virtual library name cannot begin with "*"'))


def main(opts, args, dbctx) -> int:
    from calibre.utils.icu import sort_key

    action, args = args_to_action(args, ACTIONS, default_action=ACTION_DEFAULT)
    if action == 'list':
        if args:
            raise SystemExit(_('Error: Too many arguments: {}').format(' '.join(args)))
        vls = run(dbctx, 'list')
        names = sorted(vls, key=sort_key)
        if opts.for_machine:
            prints(json.dumps([{'name': n, 'search': vls[n][0], 'count': vls[n][1]} for n in names], ensure_ascii=False, indent=2))
        else:
            for n in names:
                expr, count = vls[n]
                prints(f'{n}\t{expr}\t{_("invalid search") if count is None else count}')
    elif action == 'add':
        if len(args) != 2:
            raise SystemExit(_('Error: You must specify a name and a search expression'))
        name, expr = args[0].strip(), args[1].strip()
        if not name or not expr:
            raise SystemExit(_('Error: The name and search expression must not be empty'))
        check_name(name)
        count = run(dbctx, 'add', name, expr, opts.replace)
        prints(ngettext('Virtual library {0} added, with one book', 'Virtual library {0} added, with {1} books', count).format(name, count))
    elif action == 'rename':
        if len(args) != 2:
            raise SystemExit(_('Error: You must specify the name of the Virtual library and its new name'))
        new = args[1].strip()
        if not new:
            raise SystemExit(_('Error: The new name must not be empty'))
        check_name(new)
        run(dbctx, 'rename', args[0], new)
    else:
        if not args:
            raise SystemExit(_('Error: You must specify the names of the Virtual libraries to remove'))
        count = run(dbctx, 'remove', *args)
        prints(ngettext('One Virtual library removed', '{} Virtual libraries removed', count).format(count))
    return 0
