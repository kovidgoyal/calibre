#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from datetime import datetime

from calibre.constants import preferred_encoding, ispy3
from calibre.utils.date import (parse_only_date, parse_date, UNDEFINED_DATE,
                                isoformat)
if ispy3:
    unicode = str

# Convert data into values suitable for the db {{{

def sqlite_datetime(x):
    return isoformat(x, sep=' ') if isinstance(x, datetime) else x

def single_text(x):
    if x is None:
        return x
    if not isinstance(x, unicode):
        x = x.decode(preferred_encoding, 'replace')
    x = x.strip()
    return x if x else None

def multiple_text(sep, x):
    if x is None:
        return ()
    if isinstance(x, bytes):
        x = x.decode(preferred_encoding, 'replce')
    if isinstance(x, unicode):
        x = x.split(sep)
    x = (y.strip() for y in x if y.strip())
    return (' '.join(y.split()) for y in x if y)

def adapt_datetime(x):
    if isinstance(x, (unicode, bytes)):
        x = parse_date(x, assume_utc=False, as_utc=False)
    return x

def adapt_date(x):
    if isinstance(x, (unicode, bytes)):
        x = parse_only_date(x)
    if x is None:
        x = UNDEFINED_DATE
    return x

def adapt_number(typ, x):
    if x is None:
        return None
    if isinstance(x, (unicode, bytes)):
        if x.lower() == 'none':
            return None
    return typ(x)

def adapt_bool(x):
    if isinstance(x, (unicode, bytes)):
        x = x.lower()
        if x == 'true':
            x = True
        elif x == 'false':
            x = False
        elif x == 'none':
            x = None
        else:
            x = bool(int(x))
    return x if x is None else bool(x)

def get_adapter(name, metadata):
    dt = metadata['datatype']
    if dt == 'text':
        if metadata['is_multiple']:
            ans = partial(multiple_text, metadata['is_multiple']['ui_to_list'])
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
        ans = lambda x: x if x is None else min(10., max(0., adapt_number(float, x))),
    elif dt == 'enumeration':
        ans = single_text
    elif dt == 'composite':
        ans = lambda x: x

    if name == 'title':
        return lambda x: ans(x) or _('Unknown')
    if name == 'author_sort':
        return lambda x: ans(x) or ''
    if name == 'authors':
        return lambda x: ans(x) or (_('Unknown'),)
    if name in {'timestamp', 'last_modified'}:
        return lambda x: ans(x) or UNDEFINED_DATE
    if name == 'series_index':
        return lambda x: 1.0 if ans(x) is None else ans(x)

    return ans
# }}}

# One-One fields {{{
def one_one_in_books(book_id_val_map, db, field, *args):
    'Set a one-one field in the books table'
    if book_id_val_map:
        sequence = tuple((sqlite_datetime(v), k) for k, v in book_id_val_map.iteritems())
        db.conn.executemany(
            'UPDATE books SET %s=? WHERE id=?'%field.metadata['column'], sequence)
        field.table.book_col_map.update(book_id_val_map)
    return set(book_id_val_map)

def one_one_in_other(book_id_val_map, db, field, *args):
    'Set a one-one field in the non-books table, like comments'
    deleted = tuple((k,) for k, v in book_id_val_map.iteritems() if v is None)
    if deleted:
        db.conn.executemany('DELETE FROM %s WHERE book=?'%field.metadata['table'],
                        deleted)
        for book_id in deleted:
            field.table.book_col_map.pop(book_id[0], None)
    updated = {k:v for k, v in book_id_val_map.iteritems() if v is not None}
    if updated:
        db.conn.executemany('INSERT OR REPLACE INTO %s(book,%s) VALUES (?,?)'%(
            field.metadata['table'], field.metadata['column']),
            tuple((k, sqlite_datetime(v)) for k, v in updated.iteritems()))
        field.table.book_col_map.update(updated)
    return set(book_id_val_map)

def custom_series_index(book_id_val_map, db, field, *args):
    series_field = field.series_field
    sequence = []
    for book_id, sidx in book_id_val_map.iteritems():
        if sidx is None:
            sidx = 1.0
        ids = series_field.ids_for_book(book_id)
        if ids:
            sequence.append((sidx, book_id, ids[0]))
            field.table.book_col_map[book_id] = sidx
    if sequence:
        db.conn.executemany('UPDATE %s SET %s=? WHERE book=? AND value=?'%(
                field.metadata['table'], field.metadata['column']), sequence)
    return {s[0] for s in sequence}
# }}}

# Many-One fields {{{

def safe_lower(x):
    try:
        return icu_lower(x)
    except (TypeError, ValueError, KeyError, AttributeError):
        return x

def many_one(book_id_val_map, db, field, allow_case_change, *args):
    dirtied = set()
    m = field.metadata
    table = field.table
    dt = m['datatype']

    # Map values to their canonical form for later comparison
    kmap = safe_lower if dt == 'text' else lambda x:x

    # Ignore those items whose value is the same as the current value
    no_changes = {k:nval for k, nval in book_id_val_map.iteritems() if
                  kmap(nval) == kmap(field.for_book(k, default_value=None))}
    for book_id in no_changes:
        del book_id_val_map[book_id]

    # If we are allowed case changes check that none of the ignored items are
    # case changes. If they are, update the item's case in the db.
    if allow_case_change:
        for book_id, nval in no_changes.iteritems():
            if nval is not None and nval != field.for_book(
                book_id, default_value=None):
                # Change of case
                item_id = table.book_col_map[book_id]
                db.conn.execute('UPDATE %s SET %s=? WHERE id=?'%(
                    m['table'], m['column']), (nval, item_id))
                table.id_map[item_id] = nval
                dirtied |= table.col_book_map[item_id]

    deleted = {k:v for k, v in book_id_val_map.iteritems() if v is None}
    updated = {k:v for k, v in book_id_val_map.iteritems() if v is not None}
    link_table = table.link_table

    if deleted:
        db.conn.executemany('DELETE FROM %s WHERE book=?'%link_table,
            tuple((book_id,) for book_id in deleted))
        for book_id in deleted:
            item_id = table.book_col_map.pop(book_id, None)
            if item_id is not None:
                table.col_book_map[item_id].discard(book_id)
        dirtied |= set(deleted)

    if updated:
        rid_map = {kmap(v):k for k, v in table.id_map.iteritems()}
        book_id_item_id_map = {k:rid_map.get(kmap(v), None) for k, v in
                               book_id_val_map.iteritems()}

        # items that dont yet exist
        new_items = {k:v for k, v in updated.iteritems() if
                     book_id_item_id_map[k] is None}
        # items that already exist
        changed_items = {k:book_id_item_id_map[k] for k in updated if
                         book_id_item_id_map[k] is not None}
        def sql_update(imap):
            db.conn.executemany(
                'DELETE FROM {0} WHERE book=?; INSERT INTO {0}(book,{1}) VALUES(?, ?)'
                .format(link_table, m['link_column']),
                tuple((book_id, book_id, item_id) for book_id, item_id in
                       imap.iteritems()))

        if new_items:
            item_ids = {}
            val_map = {}
            for val in set(new_items.itervalues()):
                lval = kmap(val)
                if lval in val_map:
                    item_id = val_map[lval]
                else:
                    db.conn.execute('INSERT INTO %s(%s) VALUES (?)'%(
                        m['table'], m['column']), (val,))
                    item_id = val_map[lval] = db.conn.last_insert_rowid()
                item_ids[val] = item_id
                table.id_map[item_id] = val
            imap = {}
            for book_id, val in new_items.iteritems():
                item_id = item_ids[val]
                old_item_id = table.book_col_map.get(book_id, None)
                if old_item_id is not None:
                    table.col_book_map[old_item_id].discard(book_id)
                if item_id not in table.col_book_map:
                    table.col_book_map[item_id] = set()
                table.col_book_map[item_id].add(book_id)
                table.book_col_map[book_id] = imap[book_id] = item_id
            sql_update(imap)
            dirtied |= set(imap)

        if changed_items:
            imap = {}
            sql_update(changed_items)
            for book_id, item_id in changed_items.iteritems():
                old_item_id = table.book_col_map.get(book_id, None)
                if old_item_id != item_id:
                    table.book_col_map[book_id] = item_id
                    table.col_book_map[item_id].add(book_id)
                    if old_item_id is not None:
                        table.col_book_map[old_item_id].discard(book_id)
                    imap[book_id] = item_id
            sql_update(imap)
            dirtied |= set(imap)

    # Remove no longer used items
    remove = {item_id for item_id in table.id_map if not
              table.col_book_map.get(item_id, False)}
    if remove:
        db.conn.executemany('DELETE FROM %s WHERE id=?'%m['table'],
            tuple((item_id,) for item_id in remove))
        for item_id in remove:
            del table.id_map[item_id]
            table.col_book_map.pop(item_id, None)

    return dirtied
# }}}

def dummy(book_id_val_map, *args):
    return set()

class Writer(object):

    def __init__(self, field):
        self.adapter = get_adapter(field.name, field.metadata)
        self.name = field.name
        self.field = field
        dt = field.metadata['datatype']
        self.accept_vals = lambda x: True
        if dt == 'composite' or field.name in {
            'id', 'cover', 'size', 'path', 'formats', 'news'}:
            self.set_books_func = dummy
        elif self.name[0] == '#' and self.name.endswith('_index'):
            self.set_books_func = custom_series_index
        elif field.is_many_many:
            # TODO: Implement this
            pass
            # TODO: Remember to change commas to | when writing authors to sqlite
        elif field.is_many:
            self.set_books_func = many_one
        else:
            self.set_books_func = (one_one_in_books if field.metadata['table']
                                   == 'books' else one_one_in_other)
            if self.name in {'timestamp', 'uuid', 'sort'}:
                self.accept_vals = bool

    def set_books(self, book_id_val_map, db, allow_case_change=True):
        book_id_val_map = {k:self.adapter(v) for k, v in
                           book_id_val_map.iteritems() if self.accept_vals(v)}
        if not book_id_val_map:
            return set()
        dirtied = self.set_books_func(book_id_val_map, db, self.field,
                                      allow_case_change)
        return dirtied

