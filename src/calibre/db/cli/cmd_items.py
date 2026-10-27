#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

from calibre.db.tables import ManyToOneTable
from calibre.srv.changes import metadata
from calibre.utils.localization import _, ngettext

readonly = False
version = 0  # change this if you change signature of implementation()

# Fields whose items are numbers, languages or other data that cannot be
# meaningfully renamed or removed by name
UNSUPPORTED_FIELDS = frozenset({'formats', 'identifiers', 'languages', 'rating'})


def supported_fields(db):
    ans = set()
    for field in db.fields:
        f = db.fields[field]
        if field not in UNSUPPORTED_FIELDS and isinstance(getattr(f, 'table', None), ManyToOneTable) and f.metadata.get('datatype') in ('text', 'series'):
            ans.add(field)
    return ans


def item_ids_for(db, field, item_names):
    # Must be called with the write lock held
    ans = []
    for item_name in item_names:
        item_id = db._get_item_id(field, item_name)
        if item_id is None:
            return None, _('No item named {0} found in the field {1}').format(item_name, field)
        ans.append(item_id)
    return ans, ''


def check_args(action, field, new_name):
    if action == 'rename':
        if not new_name.strip():
            return _('The new name must not be empty')
    elif action == 'remove':
        if field == 'authors':
            return _('Authors cannot be removed, rename them instead')
    else:
        return _('Unknown action: {}').format(action)
    return ''


def implementation(db, notify_changes, action, field, item_names, new_name, search):
    from calibre.utils.search_query_parser import ParseException

    err = check_args(action, field, new_name)
    if err:
        return False, err
    fields = supported_fields(db)
    if field not in fields:
        return False, _('The field {0} is not supported. Supported fields are: {1}').format(field, ', '.join(sorted(fields)))
    is_remote = notify_changes is not None
    restrict_to_book_ids = None
    if search:
        # The search cannot be run with the write lock held as it uses the
        # public read API. A book changing in between is harmless, as the
        # rename and remove only act on books that currently have the item.
        try:
            restrict_to_book_ids = db.search(search, allow_templates=not is_remote)
        except ParseException as e:
            return False, _('Failed to parse search query: ({0}) with error: {1}').format(search, e)
    # Look up the items and change them under a single lock so that they
    # cannot be changed by another client in between
    with db.write_lock:
        item_ids, err = item_ids_for(db, field, item_names)
        if item_ids is None:
            return False, err
        if action == 'rename':
            affected_books = db._rename_items(field, {item_ids[0]: new_name}, restrict_to_book_ids=restrict_to_book_ids)[0]
        else:
            affected_books = db._remove_items(field, item_ids, restrict_to_book_ids=restrict_to_book_ids)
    if affected_books and notify_changes is not None:
        notify_changes(metadata(affected_books))
    return True, len(affected_books)


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog items [options] (rename|remove) FIELD ITEM ...

Rename or remove items such as authors, tags, series and publishers in all
books, the same as the Manage authors, tags, etc. actions in the calibre
interface. FIELD is the lookup name of the field, for example: authors, tags,
series, publisher or #mycolumn. Items are matched case insensitively.

Rename an item. If an item named NEW_NAME already exists, the two items are
merged. For fields that contain multiple values, NEW_NAME can contain more
than one value, separated by the separator for the field, for example a comma
for tags. The item is then replaced by all the values:

%prog items rename FIELD ITEM NEW_NAME

Remove one or more items from all books. Authors cannot be removed:

%prog items remove FIELD ITEM [ITEM ...]
'''
        )
    )
    parser.add_option(
        '-s',
        '--search',
        default=None,
        help=_('Only change books that match the specified search expression, for example: {}').format('tags:"=Fiction"'),
    )
    return parser


def main(opts, args, dbctx):
    if not args:
        raise SystemExit(_('Error: You must specify an action, one of: (rename|remove)'))
    action, args = args[0], args[1:]
    if action not in ('rename', 'remove'):
        raise SystemExit(_('Error: Action {} not recognized, must be one of: (rename|remove)').format(action))
    if action == 'rename':
        if len(args) != 3:
            raise SystemExit(_('Error: You must specify a field, the name of an item and its new name'))
        field, item_names, new_name = args[0], args[1:2], args[2]
    else:
        if len(args) < 2:
            raise SystemExit(_('Error: You must specify a field and the names of one or more items'))
        field, item_names, new_name = args[0], args[1:], ''
    err = check_args(action, field, new_name)
    if err:
        raise SystemExit(err)
    ok, ans = dbctx.run('items', action, field, item_names, new_name, opts.search)
    if not ok:
        raise SystemExit(ans)
    print(ngettext('One book changed', '{} books changed', ans).format(ans))
    return 0
