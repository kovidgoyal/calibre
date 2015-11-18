#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from datetime import datetime, time

from calibre.utils.date import isoformat, UNDEFINED_DATE, local_tz
from calibre.utils.icu import sort_key, collation_order

IGNORED_FIELDS = frozenset('cover ondevice path marked id au_map'.split())

def encode_datetime(dateval):
    if dateval is None:
        return "None"
    if not isinstance(dateval, datetime):
        dateval = datetime.combine(dateval, time())
    if hasattr(dateval, 'tzinfo') and dateval.tzinfo is None:
        dateval = dateval.replace(tzinfo=local_tz)
    if dateval <= UNDEFINED_DATE:
        return None
    return isoformat(dateval)

def add_field(field, db, book_id, ans, field_metadata):
    datatype = field_metadata.get('datatype')
    if datatype is not None:
        val = db._field_for(field, book_id)
        if val is not None and val != ():
            if datatype == 'datetime':
                val = encode_datetime(val)
                if val is None:
                    return
            ans[field] = val

def book_as_json(db, book_id):
    db = db.new_api
    with db.safe_read_lock:
        ans = {'formats':db._formats(book_id)}
        fm = db.field_metadata
        for field in fm.all_field_keys():
            if field not in IGNORED_FIELDS:
                add_field(field, db, book_id, ans, fm[field])
    return ans

def category_item_as_json(x):
    sname = x.sort or x.name
    ans = {'sort_key': tuple(bytearray(sort_key(sname))), 'first_letter_sort_key': collation_order(icu_upper(sname or ' '))}
    for k in x.__slots__:
        if k != 'state':
            val = getattr(x, k)
            if isinstance(val, set):
                val = tuple(val)
            if val is not None:
                ans[k] = val
    if ans.get('sort', False) == ans['name']:
        del ans['sort']
    return ans

def categories_as_json(categories):
    ans = []
    f = category_item_as_json
    for category in sorted(categories, key=sort_key):
        items = tuple(f(x) for x in categories[category])
        ans.append((category, items))
    return ans
