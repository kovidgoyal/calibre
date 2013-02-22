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

# Convert data into values suitable for the db {{{

if ispy3:
    unicode = str

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

def sqlite_datetime(x):
    return isoformat(x, sep=' ') if isinstance(x, datetime) else x

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
        for book_id in book_id_val_map:
            field.table.book_col_map.pop(book_id, None)
    updated = {k:v for k, v in book_id_val_map.iteritems() if v is not None}
    if updated:
        db.conn.executemany('INSERT OR REPLACE INTO %s(book,%s) VALUES (?,?)'%(
            field.metadata['table'], field.metadata['column']),
            tuple((k, sqlite_datetime(v)) for k, v in updated.iteritems()))
        field.table.book_col_map.update(updated)
    return set(book_id_val_map)

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
            # TODO: Implement this
            pass
        elif field.is_many:
            # TODO: Implement this
            pass
            # TODO: Remember to change commas to | when writing authors to sqlite
        else:
            self.set_books_func = (one_one_in_books if field.metadata['table']
                                   == 'books' else one_one_in_other)
            if self.name in {'timestamp', 'uuid', 'sort'}:
                self.accept_vals = bool

    def set_books(self, book_id_val_map, db):
        book_id_val_map = {k:self.adapter(v) for k, v in
                           book_id_val_map.iteritems() if self.accept_vals(v)}
        if not book_id_val_map:
            return set()
        dirtied = self.set_books_func(book_id_val_map, db, self.field)
        return dirtied

