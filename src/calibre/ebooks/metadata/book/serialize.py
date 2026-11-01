#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING, cast

from calibre.constants import preferred_encoding
from calibre.ebooks.metadata.book import SERIALIZABLE_FIELDS
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.imghdr import what
from polyglot.binary import as_base64_unicode

if TYPE_CHECKING:
    from collections.abc import Mapping

    from calibre.ebooks.metadata.book.base import FieldMetadataDict


def ensure_unicode(obj: object, enc: str = preferred_encoding) -> object:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, bytes):
        return obj.decode(enc, 'replace')
    if isinstance(obj, (list, tuple)):
        return [ensure_unicode(x) for x in obj]
    if isinstance(obj, dict):
        return {ensure_unicode(k): ensure_unicode(v) for k, v in obj.items()}
    return obj


def serialize_cover(path: str) -> tuple[str | None, bytes]:
    with open(path, 'rb') as f:
        cd = f.read()
    return what(None, cd), cd


def read_cover(mi: Metadata) -> Metadata:
    if mi.cover_data[1]:
        return mi
    if mi.cover:
        try:
            mi.cover_data = serialize_cover(mi.cover)
        except OSError:
            pass
    return mi


def metadata_as_dict(mi: Metadata, encode_cover_data: bool = False) -> dict[str, object]:
    if callable(to_book_metadata := getattr(mi, 'to_book_metadata', None)):
        # mi is a duck typed OPF object
        mi = to_book_metadata()
        assert isinstance(mi, Metadata)
    ans: dict[str, object] = {}
    for field in SERIALIZABLE_FIELDS:
        if field != 'cover' and not mi.is_null(field):
            val = getattr(mi, field)
            ans[field] = ensure_unicode(val)
    if mi.cover_data[1]:
        if encode_cover_data:
            ans['cover_data'] = [mi.cover_data[0], as_base64_unicode(mi.cover_data[1])]
        else:
            ans['cover_data'] = mi.cover_data
    um = mi.get_all_user_metadata(False)
    if um:
        ans['user_metadata'] = um
    return ans


def metadata_from_dict(src: Mapping[str, object]) -> Metadata:
    ans = Metadata('Unknown')
    for key, value in src.items():
        if key == 'user_metadata':
            ans.set_all_user_metadata(cast('dict[str, FieldMetadataDict]', value))  # as created by metadata_as_dict()
        else:
            setattr(ans, key, value)
    return ans
