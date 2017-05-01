#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json, base64
from functools import partial
from datetime import datetime

import msgpack

from calibre.utils.iso8601 import parse_iso8601

MSGPACK_MIME = 'application/x-msgpack'
CANARY = 'jPoAv3zOyHvQ5JFNYg4hJ9'


def encoded(typ, data, for_json):
    if for_json:
        return {CANARY: typ, 'v': data}
    return msgpack.ExtType(typ, msgpack_dumps(data))


def encoder(obj, for_json=False):
    if isinstance(obj, datetime):
        return encoded(0, unicode(obj.isoformat()), for_json)
    if isinstance(obj, (set, frozenset)):
        return encoded(1, tuple(obj), for_json)
    if hasattr(obj, '__calibre_serializable__'):
        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.library.field_metadata import FieldMetadata, fm_as_dict
        if isinstance(obj, Metadata):
            from calibre.ebooks.metadata.book.serialize import metadata_as_dict
            return encoded(
                2, metadata_as_dict(obj, encode_cover_data=for_json), for_json
            )
        elif isinstance(obj, FieldMetadata):
            return encoded(3, fm_as_dict(obj), for_json)
    raise TypeError('Cannot serialize objects of type {}'.format(type(obj)))


msgpack_dumps = partial(msgpack.packb, default=encoder, use_bin_type=True)


def json_dumps(data, **kw):
    kw['default'] = partial(encoder, for_json=True)
    kw['ensure_ascii'] = False
    ans = json.dumps(data, **kw)
    if not isinstance(ans, bytes):
        ans = ans.encode('utf-8')
    return ans


def decode_metadata(x, for_json):
    from calibre.ebooks.metadata.book.serialize import metadata_from_dict
    obj = metadata_from_dict(x)
    if for_json and obj.cover_data and obj.cover_data[1]:
        obj.cover_data = obj.cover_data[0], base64.standard_b64decode(
            obj.cover_data[1]
        )
    return obj


def decode_field_metadata(x, for_json):
    from calibre.library.field_metadata import fm_from_dict
    return fm_from_dict(x)


decoders = (
    lambda x, fj: parse_iso8601(x, assume_utc=True), lambda x, fj: set(x),
    decode_metadata, decode_field_metadata,
)


def json_decoder(obj):
    typ = obj.get(CANARY)
    if typ is None:
        return obj
    return decoders[typ](obj['v'], True)


def msgpack_decoder(code, data):
    return decoders[code](msgpack_loads(data), False)


msgpack_loads = partial(msgpack.unpackb, encoding='utf-8', ext_hook=msgpack_decoder)


def json_loads(data):
    return json.loads(data, object_hook=json_decoder)
