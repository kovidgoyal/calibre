#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.constants import preferred_encoding
from calibre.ebooks.metadata.book import SERIALIZABLE_FIELDS
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.imghdr import what
from polyglot.builtins import iteritems
from polyglot.binary import as_base64_unicode


def ensure_unicode(obj, enc=preferred_encoding):
    if isinstance(obj, str):
        return obj
    if isinstance(obj, bytes):
        return obj.decode(enc, 'replace')
    if isinstance(obj, (list, tuple)):
        return [ensure_unicode(x) for x in obj]
    if isinstance(obj, dict):
        return {ensure_unicode(k): ensure_unicode(v) for k, v in iteritems(obj)}
    return obj


def serialize_cover(path):
    with lopen(path, 'rb') as f:
        cd = f.read()
    return what(None, cd), cd


def read_cover(mi):
    if mi.cover_data and mi.cover_data[1]:
        return mi
    if mi.cover:
        try:
            mi.cover_data = serialize_cover(mi.cover)
        except OSError:
            pass
    return mi


def metadata_as_dict(mi, encode_cover_data=False):
    if hasattr(mi, 'to_book_metadata'):
        mi = mi.to_book_metadata()
    ans = {}
    for field in SERIALIZABLE_FIELDS:
        if field != 'cover' and not mi.is_null(field):
            val = getattr(mi, field)
            ans[field] = ensure_unicode(val)
    if mi.cover_data and mi.cover_data[1]:
        if encode_cover_data:
            ans['cover_data'] = [mi.cover_data[0], as_base64_unicode(mi.cover_data[1])]
        else:
            ans['cover_data'] = mi.cover_data
    um = mi.get_all_user_metadata(False)
    if um:
        ans['user_metadata'] = um
    return ans


def metadata_from_dict(src):
    ans = Metadata('Unknown')
    for key, value in iteritems(src):
        if key == 'user_metadata':
            ans.set_all_user_metadata(value)
        else:
            setattr(ans, key, value)
    return ans
