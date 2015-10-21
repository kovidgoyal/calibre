#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from datetime import datetime, time

from calibre.utils.date import isoformat, UNDEFINED_DATE, local_tz

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
