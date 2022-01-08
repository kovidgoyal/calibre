#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from functools import partial
from datetime import datetime
from polyglot.builtins import iteritems, itervalues

from calibre.constants import preferred_encoding
from calibre.ebooks.metadata import author_to_author_sort, title_sort
from calibre.utils.date import (
    parse_only_date, parse_date, UNDEFINED_DATE, isoformat, is_date_undefined)
from calibre.utils.localization import canonicalize_lang
from calibre.utils.icu import strcmp

missing = object()

# Convert data into values suitable for the db {{{


def sqlite_datetime(x):
    return isoformat(x, sep=' ') if isinstance(x, datetime) else x


def single_text(x):
    if x is None:
        return x
    if not isinstance(x, str):
        x = x.decode(preferred_encoding, 'replace')
    x = x.strip()
    return x if x else None


series_index_pat = re.compile(r'(.*)\s+\[([.0-9]+)\]$')


def get_series_values(val):
    if not val:
        return (val, None)
    match = series_index_pat.match(val.strip())
    if match is not None:
        idx = match.group(2)
        try:
            idx = float(idx)
            return (match.group(1).strip(), idx)
        except:
            pass
    return (val, None)


def multiple_text(sep, ui_sep, x):
    if not x:
        return ()
    if isinstance(x, bytes):
        x = x.decode(preferred_encoding, 'replace')
    if isinstance(x, str):
        x = x.split(sep)
    else:
        x = (y.decode(preferred_encoding, 'replace') if isinstance(y, bytes)
             else y for y in x)
    ui_sep = ui_sep.strip()
    repsep = ',' if ui_sep == ';' else ';'
    x = (y.strip().replace(ui_sep, repsep) for y in x if y.strip())
    return tuple(' '.join(y.split()) for y in x if y)


def adapt_datetime(x):
    if isinstance(x, (str, bytes)):
        x = parse_date(x, assume_utc=False, as_utc=False)
    if x and is_date_undefined(x):
        x = UNDEFINED_DATE
    return x


def adapt_date(x):
    if isinstance(x, (str, bytes)):
        x = parse_only_date(x)
    if x is None or is_date_undefined(x):
        x = UNDEFINED_DATE
    return x


def adapt_number(typ, x):
    if x is None:
        return None
    if isinstance(x, (str, bytes)):
        if isinstance(x, bytes):
            x = x.decode(preferred_encoding, 'replace')
        if not x or x.lower() == 'none':
            return None
    return typ(x)


def adapt_bool(x):
    if isinstance(x, (str, bytes)):
        if isinstance(x, bytes):
            x = x.decode(preferred_encoding, 'replace')
        x = x.lower()
        if x == 'true':
            x = True
        elif x == 'false':
            x = False
        elif x == 'none' or x == '':
            x = None
        else:
            x = bool(int(x))
    return x if x is None else bool(x)


def adapt_languages(to_tuple, x):
    ans = []
    for lang in to_tuple(x):
        lc = canonicalize_lang(lang)
        if not lc or lc in ans or lc in ('und', 'zxx', 'mis', 'mul'):
            continue
        ans.append(lc)
    return tuple(ans)


def clean_identifier(typ, val):
    typ = icu_lower(typ or '').strip().replace(':', '').replace(',', '')
    val = (val or '').strip().replace(',', '|')
    return typ, val


def adapt_identifiers(to_tuple, x):
    if not isinstance(x, dict):
        x = {k:v for k, v in (y.partition(':')[0::2] for y in to_tuple(x))}
    ans = {}
    for k, v in iteritems(x):
        k, v = clean_identifier(k, v)
        if k and v:
            ans[k] = v
    return ans


def adapt_series_index(x):
    ret = adapt_number(float, x)
    return 1.0 if ret is None else ret


def get_adapter(name, metadata):
    dt = metadata['datatype']
    if dt == 'text':
        if metadata['is_multiple']:
            m = metadata['is_multiple']
            ans = partial(multiple_text, m['ui_to_list'], m['list_to_ui'])
        else:
            ans = single_text
    elif dt == 'series':
        ans = single_text
    elif dt == 'datetime':
        ans = adapt_date if name == 'pubdate' else adapt_datetime
    elif dt == 'int':
        ans = partial(adapt_number, int)
    elif dt == 'float':
        ans = partial(adapt_number, float)
    elif dt == 'bool':
        ans = adapt_bool
    elif dt == 'comments':
        ans = single_text
    elif dt == 'rating':
        ans = lambda x: None if x in {None, 0} else min(10, max(0, adapt_number(int, x)))
    elif dt == 'enumeration':
        ans = single_text
    elif dt == 'composite':
        ans = lambda x: x

    if name == 'title':
        return lambda x: ans(x) or _('Unknown')
    if name == 'author_sort':
        return lambda x: ans(x) or ''
    if name == 'authors':
        return lambda x: tuple(y.replace('|', ',') for y in ans(x)) or (_('Unknown'),)
    if name in {'timestamp', 'last_modified'}:
        return lambda x: ans(x) or UNDEFINED_DATE
    if name == 'series_index':
        return adapt_series_index
    if name == 'languages':
        return partial(adapt_languages, ans)
    if name == 'identifiers':
        return partial(adapt_identifiers, ans)

    return ans
# }}}

# One-One fields {{{


def one_one_in_books(book_id_val_map, db, field, *args):
    'Set a one-one field in the books table'
    # Ignore those items whose value is the same as the current value
    # We can't do this for the cover because the file might change without
    # the presence-of-cover flag changing
    if field.name != 'cover':
        g = field.table.book_col_map.get
        book_id_val_map = {k:v for k, v in book_id_val_map.items() if v != g(k, missing)}
    if book_id_val_map:
        sequence = ((sqlite_datetime(v), k) for k, v in book_id_val_map.items())
        db.executemany(
            'UPDATE books SET %s=? WHERE id=?'%field.metadata['column'], sequence)
        field.table.book_col_map.update(book_id_val_map)
    return set(book_id_val_map)


def set_uuid(book_id_val_map, db, field, *args):
    field.table.update_uuid_cache(book_id_val_map)
    return one_one_in_books(book_id_val_map, db, field, *args)


def set_title(book_id_val_map, db, field, *args):
    ans = one_one_in_books(book_id_val_map, db, field, *args)
    # Set the title sort field if the title changed
    field.title_sort_field.writer.set_books(
        {k:title_sort(v) for k, v in book_id_val_map.items() if k in ans}, db)
    return ans


def one_one_in_other(book_id_val_map, db, field, *args):
    'Set a one-one field in the non-books table, like comments'
    # Ignore those items whose value is the same as the current value
    g = field.table.book_col_map.get
    book_id_val_map = {k:v for k, v in iteritems(book_id_val_map) if v != g(k, missing)}
    deleted = tuple((k,) for k, v in iteritems(book_id_val_map) if v is None)
    if deleted:
        db.executemany('DELETE FROM %s WHERE book=?'%field.metadata['table'],
                        deleted)
        for book_id in deleted:
            field.table.book_col_map.pop(book_id[0], None)
    updated = {k:v for k, v in iteritems(book_id_val_map) if v is not None}
    if updated:
        db.executemany('INSERT OR REPLACE INTO %s(book,%s) VALUES (?,?)'%(
            field.metadata['table'], field.metadata['column']),
            ((k, sqlite_datetime(v)) for k, v in iteritems(updated)))
        field.table.book_col_map.update(updated)
    return set(book_id_val_map)


def custom_series_index(book_id_val_map, db, field, *args):
    series_field = field.series_field
    sequence = []
    for book_id, sidx in book_id_val_map.items():
        ids = series_field.ids_for_book(book_id)
        if sidx is None:
            sidx = 1.0
        if ids:
            if field.table.book_col_map.get(book_id, missing) != sidx:
                sequence.append((sidx, book_id, ids[0]))
                field.table.book_col_map[book_id] = sidx
        else:
            # the series has been deleted from the book, which means no row for
            # it exists in the series table. The series_index value should be
            # removed from the in-memory table as well, to ensure this book
            # sorts the same as other books with no series.
            field.table.remove_books((book_id,), db)
    if sequence:
        db.executemany('UPDATE %s SET %s=? WHERE book=? AND value=?'%(
                field.metadata['table'], field.metadata['column']), sequence)
    return {s[1] for s in sequence}
# }}}

# Many-One fields {{{


def safe_lower(x):
    try:
        return icu_lower(x)
    except (TypeError, ValueError, KeyError, AttributeError):
        return x


def get_db_id(val, db, m, table, kmap, rid_map, allow_case_change,
              case_changes, val_map, is_authors=False):
    ''' Get the db id for the value val. If val does not exist in the db it is
    inserted into the db. '''
    kval = kmap(val)
    item_id = rid_map.get(kval, None)
    if item_id is None:
        if is_authors:
            aus = author_to_author_sort(val)
            db.execute('INSERT INTO authors(name,sort) VALUES (?,?)',
                            (val.replace(',', '|'), aus))
        else:
            db.execute('INSERT INTO %s(%s) VALUES (?)'%(
                m['table'], m['column']), (val,))
        item_id = rid_map[kval] = db.last_insert_rowid()
        table.id_map[item_id] = val
        table.col_book_map[item_id] = set()
        if is_authors:
            table.asort_map[item_id] = aus
            table.alink_map[item_id] = ''
    elif allow_case_change and val != table.id_map[item_id]:
        case_changes[item_id] = val
    val_map[val] = item_id


def change_case(case_changes, dirtied, db, table, m, is_authors=False):
    if is_authors:
        vals = ((val.replace(',', '|'), item_id) for item_id, val in
                iteritems(case_changes))
    else:
        vals = ((val, item_id) for item_id, val in iteritems(case_changes))
    db.executemany(
        'UPDATE %s SET %s=? WHERE id=?'%(m['table'], m['column']), vals)
    for item_id, val in iteritems(case_changes):
        table.id_map[item_id] = val
        dirtied.update(table.col_book_map[item_id])
        if is_authors:
            table.asort_map[item_id] = author_to_author_sort(val)


def many_one(book_id_val_map, db, field, allow_case_change, *args):
    dirtied = set()
    m = field.metadata
    table = field.table
    dt = m['datatype']
    is_custom_series = dt == 'series' and table.name.startswith('#')

    # Map values to db ids, including any new values
    kmap = safe_lower if dt in {'text', 'series'} else lambda x:x
    rid_map = {kmap(item):item_id for item_id, item in iteritems(table.id_map)}
    if len(rid_map) != len(table.id_map):
        # table has some entries that differ only in case, fix it
        table.fix_case_duplicates(db)
        rid_map = {kmap(item):item_id for item_id, item in iteritems(table.id_map)}
    val_map = {None:None}
    case_changes = {}
    for val in itervalues(book_id_val_map):
        if val is not None:
            get_db_id(val, db, m, table, kmap, rid_map, allow_case_change,
                    case_changes, val_map)

    if case_changes:
        change_case(case_changes, dirtied, db, table, m)

    book_id_item_id_map = {k:val_map[v] for k, v in iteritems(book_id_val_map)}

    # Ignore those items whose value is the same as the current value
    book_id_item_id_map = {k:v for k, v in iteritems(book_id_item_id_map)
        if v != table.book_col_map.get(k, None)}
    dirtied |= set(book_id_item_id_map)

    # Update the book->col and col->book maps
    deleted = set()
    updated = {}
    for book_id, item_id in iteritems(book_id_item_id_map):
        old_item_id = table.book_col_map.get(book_id, None)
        if old_item_id is not None:
            table.col_book_map[old_item_id].discard(book_id)
        if item_id is None:
            table.book_col_map.pop(book_id, None)
            deleted.add(book_id)
        else:
            table.book_col_map[book_id] = item_id
            table.col_book_map[item_id].add(book_id)
            updated[book_id] = item_id

    # Update the db link table
    if deleted:
        db.executemany('DELETE FROM %s WHERE book=?'%table.link_table,
                            ((k,) for k in deleted))
    if updated:
        sql = (
            'DELETE FROM {0} WHERE book=?; INSERT INTO {0}(book,{1},extra) VALUES(?, ?, 1.0)'
            if is_custom_series else
            'DELETE FROM {0} WHERE book=?; INSERT INTO {0}(book,{1}) VALUES(?, ?)'
        )
        db.executemany(sql.format(table.link_table, m['link_column']),
            ((book_id, book_id, item_id) for book_id, item_id in
                    iteritems(updated)))

    # Remove no longer used items
    remove = {item_id for item_id in table.id_map if not
              table.col_book_map.get(item_id, False)}
    if remove:
        db.executemany('DELETE FROM %s WHERE id=?'%m['table'],
            ((item_id,) for item_id in remove))
        for item_id in remove:
            del table.id_map[item_id]
            table.col_book_map.pop(item_id, None)

    return dirtied
# }}}

# Many-Many fields {{{


def uniq(vals, kmap=lambda x:x):
    ''' Remove all duplicates from vals, while preserving order. kmap must be a
    callable that returns a hashable value for every item in vals '''
    vals = vals or ()
    lvals = (kmap(x) for x in vals)
    seen = set()
    seen_add = seen.add
    return tuple(x for x, k in zip(vals, lvals) if k not in seen and not seen_add(k))


def many_many(book_id_val_map, db, field, allow_case_change, *args):
    dirtied = set()
    m = field.metadata
    table = field.table
    dt = m['datatype']
    is_authors = field.name == 'authors'

    # Map values to db ids, including any new values
    kmap = safe_lower if dt == 'text' else lambda x:x
    rid_map = {kmap(item):item_id for item_id, item in iteritems(table.id_map)}
    if len(rid_map) != len(table.id_map):
        # table has some entries that differ only in case, fix it
        table.fix_case_duplicates(db)
        rid_map = {kmap(item):item_id for item_id, item in iteritems(table.id_map)}
    val_map = {}
    case_changes = {}
    book_id_val_map = {k:uniq(vals, kmap) for k, vals in iteritems(book_id_val_map)}
    for vals in itervalues(book_id_val_map):
        for val in vals:
            get_db_id(val, db, m, table, kmap, rid_map, allow_case_change,
                      case_changes, val_map, is_authors=is_authors)

    if case_changes:
        change_case(case_changes, dirtied, db, table, m, is_authors=is_authors)
        if is_authors:
            for item_id, val in iteritems(case_changes):
                for book_id in table.col_book_map[item_id]:
                    current_sort = field.db_author_sort_for_book(book_id)
                    new_sort = field.author_sort_for_book(book_id)
                    if strcmp(current_sort, new_sort) == 0:
                        # The sort strings differ only by case, update the db
                        # sort
                        field.author_sort_field.writer.set_books({book_id:new_sort}, db)

    book_id_item_id_map = {k:tuple(val_map[v] for v in vals)
                           for k, vals in book_id_val_map.items()}

    # Ignore those items whose value is the same as the current value
    g = table.book_col_map.get
    not_set = ()
    book_id_item_id_map = {k:v for k, v in book_id_item_id_map.items() if v != g(k, not_set)}
    dirtied |= set(book_id_item_id_map)

    # Update the book->col and col->book maps
    deleted = set()
    updated = {}
    for book_id, item_ids in iteritems(book_id_item_id_map):
        old_item_ids = table.book_col_map.get(book_id, None)
        if old_item_ids:
            for old_item_id in old_item_ids:
                table.col_book_map[old_item_id].discard(book_id)
        if item_ids:
            table.book_col_map[book_id] = item_ids
            for item_id in item_ids:
                table.col_book_map[item_id].add(book_id)
            updated[book_id] = item_ids
        else:
            table.book_col_map.pop(book_id, None)
            deleted.add(book_id)

    # Update the db link table
    if deleted:
        db.executemany('DELETE FROM %s WHERE book=?'%table.link_table,
                            ((k,) for k in deleted))
    if updated:
        vals = (
            (book_id, val) for book_id, vals in iteritems(updated)
            for val in vals
        )
        db.executemany('DELETE FROM %s WHERE book=?'%table.link_table,
                            ((k,) for k in updated))
        db.executemany('INSERT INTO {}(book,{}) VALUES(?, ?)'.format(
            table.link_table, m['link_column']), vals)
        if is_authors:
            aus_map = {book_id:field.author_sort_for_book(book_id) for book_id
                       in updated}
            field.author_sort_field.writer.set_books(aus_map, db)

    # Remove no longer used items
    remove = {item_id for item_id in table.id_map if not
              table.col_book_map.get(item_id, False)}
    if remove:
        db.executemany('DELETE FROM %s WHERE id=?'%m['table'],
            ((item_id,) for item_id in remove))
        for item_id in remove:
            del table.id_map[item_id]
            table.col_book_map.pop(item_id, None)
            if is_authors:
                table.asort_map.pop(item_id, None)
                table.alink_map.pop(item_id, None)

    return dirtied

# }}}


def identifiers(book_id_val_map, db, field, *args):  # {{{
    # Ignore those items whose value is the same as the current value
    g = field.table.book_col_map.get
    book_id_val_map = {k:v for k, v in book_id_val_map.items() if v != g(k, missing)}

    table = field.table
    updates = set()
    for book_id, identifiers in iteritems(book_id_val_map):
        if book_id not in table.book_col_map:
            table.book_col_map[book_id] = {}
        current_ids = table.book_col_map[book_id]
        remove_keys = set(current_ids) - set(identifiers)
        for key in remove_keys:
            table.col_book_map.get(key, set()).discard(book_id)
            current_ids.pop(key, None)
        current_ids.update(identifiers)
        for key, val in iteritems(identifiers):
            if key not in table.col_book_map:
                table.col_book_map[key] = set()
            table.col_book_map[key].add(book_id)
            updates.add((book_id, key, val))
    db.executemany('DELETE FROM identifiers WHERE book=?',
                        ((x,) for x in book_id_val_map))
    if updates:
        db.executemany('INSERT OR REPLACE INTO identifiers (book, type, val) VALUES (?, ?, ?)',
                            tuple(updates))
    return set(book_id_val_map)
# }}}


def dummy(book_id_val_map, *args):
    return set()


class Writer:

    def __init__(self, field):
        self.adapter = get_adapter(field.name, field.metadata)
        self.name = field.name
        self.field = field
        dt = field.metadata['datatype']
        self.accept_vals = lambda x: True
        if dt == 'composite' or field.name in {
            'id', 'size', 'path', 'formats', 'news'}:
            self.set_books_func = dummy
        elif self.name[0] == '#' and self.name.endswith('_index'):
            self.set_books_func = custom_series_index
        elif self.name == 'identifiers':
            self.set_books_func = identifiers
        elif self.name == 'uuid':
            self.set_books_func = set_uuid
        elif self.name == 'title':
            self.set_books_func = set_title
        elif field.is_many_many:
            self.set_books_func = many_many
        elif field.is_many:
            self.set_books_func = (self.set_books_for_enum if dt == 'enumeration' else many_one)
        else:
            self.set_books_func = (one_one_in_books if field.metadata['table'] == 'books' else one_one_in_other)
            if self.name in {'timestamp', 'uuid', 'sort'}:
                self.accept_vals = bool

    def set_books(self, book_id_val_map, db, allow_case_change=True):
        book_id_val_map = {k:self.adapter(v) for k, v in
                           iteritems(book_id_val_map) if self.accept_vals(v)}
        if not book_id_val_map:
            return set()
        dirtied = self.set_books_func(book_id_val_map, db, self.field,
                                      allow_case_change)
        return dirtied

    def set_books_for_enum(self, book_id_val_map, db, field,
                           allow_case_change):
        allowed = set(field.metadata['display']['enum_values'])
        book_id_val_map = {k:v for k, v in iteritems(book_id_val_map) if v is
                           None or v in allowed}
        if not book_id_val_map:
            return set()
        return many_one(book_id_val_map, db, field, False)
