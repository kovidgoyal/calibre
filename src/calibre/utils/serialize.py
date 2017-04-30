#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json, base64
from functools import partial
from datetime import datetime

from calibre.utils.iso8601 import parse_iso8601

MSGPACK_MIME = 'application/x-msgpack'
CANARY = 'jPoAv3zOyHvQ5JFNYg4hJ9'


def encoded(typ, data):
    return {CANARY: typ, 'v': data}


def encoder(obj, for_json=False):
    if isinstance(obj, datetime):
        return encoded(0, unicode(obj.isoformat()))
    if isinstance(obj, (set, frozenset)):
        return encoded(1, tuple(obj))
    if obj.__class__.__name__ == 'Metadata':
        from calibre.ebooks.metadata.book.base import Metadata
        if isinstance(obj, Metadata):
            from calibre.ebooks.metadata.book.serialize import metadata_as_dict
            return encoded(2, metadata_as_dict(obj, encode_cover_data=for_json))
    raise TypeError('Cannot serialize objects of type {}'.format(type(obj)))


def msgpack_dumps(data):
    import msgpack
    return msgpack.packb(data, use_bin_type=True, default=encoder)


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


decoders = (
    lambda x, fj: parse_iso8601(x, assume_utc=True),
    lambda x, fj: set(x),
    decode_metadata,
)


def decoder(obj, for_json=False):
    typ = obj.get(CANARY)
    if typ is None:
        return obj
    return decoders[typ](obj['v'], for_json)


def msgpack_loads(data):
    import msgpack
    return msgpack.unpackb(data, encoding='utf-8', object_hook=decoder)


def json_loads(data):
    return json.loads(data, object_hook=partial(decoder, for_json=True))
