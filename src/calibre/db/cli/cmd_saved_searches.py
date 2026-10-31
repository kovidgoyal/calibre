#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING, cast

from calibre.db.cli.utils import args_to_action
from calibre.utils.localization import _

readonly = False
version = 0  # change this if you change signature of implementation()
ACTIONS = ('list', 'add', 'remove')
ACTION_DEFAULT = 'list'

from calibre import prints
from calibre.srv.changes import saved_searches

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from optparse import Values

    from calibre.db.cache import Cache
    from calibre.db.cli.main import DBCtx
    from calibre.srv.changes import ChangeEvent
    from calibre.utils.config import OptionParser


def check_no_templates(db: Cache, query: str) -> None:
    from calibre.utils.search_query_parser import ParseException

    try:
        uses_templates = db.search_uses_templates(query)
    except ParseException as err:
        e = ValueError(_('Failed to parse search query: ({0}) with error: {1}').format(query, err))
        setattr(e, 'suppress_traceback', True)
        raise e from err
    if uses_templates:
        e = ValueError(_('Templates are not allowed in search expressions'))
        setattr(e, 'suppress_traceback', True)
        raise e


def implementation(db: Cache, notify_changes: Callable[[ChangeEvent], None] | None, action: str, *args: object) -> dict[str, str | None] | None:
    if action == 'list':
        with db.safe_read_lock:
            names = db.saved_search_names()
            return {n: db.saved_search_lookup(n) for n in names}
    if action == 'add':
        name, val = cast('tuple[str, str]', args)
        if notify_changes is not None:
            # Saved searches are used in Virtual libraries and restrictions, which are evaluated with
            # templates allowed, so remote clients must not be able to store templates in them
            check_no_templates(db, val)
        db.saved_search_add(name, val)
        if notify_changes is not None:
            notify_changes(saved_searches(added=(name,)))
        return
    if action == 'remove':
        name = cast('str', args[0])
        db.saved_search_delete(name)
        if notify_changes is not None:
            notify_changes(saved_searches(removed=(name,)))
        return


def option_parser(get_parser: Callable[[str], OptionParser], args: Sequence[str]) -> OptionParser:
    parser = get_parser(
        _(
            '''\
%prog saved_searches [options] [list|add|remove]

Manage the saved searches stored in this database.
If you try to add a query with a name that already exists, it will be
replaced.

Syntax for listing, the default action:

%prog saved_searches list

Syntax for adding:

%prog saved_searches add search_name search_expression

Syntax for removing:

%prog saved_searches remove search_name
    '''
        )
    )
    return parser


def main(opts: Values, args: list[str], dbctx: DBCtx) -> int:
    action, args = args_to_action(args, ACTIONS, default_action=ACTION_DEFAULT)
    if action == 'list':
        for name, value in cast('dict[str, str | None]', dbctx.run('saved_searches', 'list')).items():
            prints(_('Name:'), name)
            prints(_('Search string:'), value)
            print()
    elif action == 'add':
        if len(args) < 2:
            raise SystemExit(_('Error: You must specify a name and a search string'))
        if '"' in args[0]:
            raise SystemExit(_('Error: Saved search names cannot contain " (quote) characters'))
        dbctx.run('saved_searches', 'add', args[0], args[1])
        prints(args[0], _('added'))
    else:
        if len(args) < 1:
            raise SystemExit(_('Error: You must specify a name'))
        dbctx.run('saved_searches', 'remove', args[0])
        prints(args[0], _('removed'))
    return 0
