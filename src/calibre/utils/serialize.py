#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from polyglot.builtins import unicode_type


MSGPACK_MIME = 'application/x-msgpack'
CANARY = 'jPoAv3zOyHvQ5JFNYg4hJ9'


def encoded(typ, data, ExtType):
    if ExtType is None:
        return {CANARY: typ, 'v': data}
    return ExtType(typ, msgpack_dumps(data))


def create_encoder(for_json=False):
    from datetime import datetime
    ExtType = None
    if not for_json:
        import msgpack
        ExtType = msgpack.ExtType

    def encoder(obj):
        if isinstance(obj, datetime):
            return encoded(0, unicode_type(obj.isoformat()), ExtType)
        if isinstance(obj, (set, frozenset)):
            return encoded(1, tuple(obj), ExtType)
        if getattr(obj, '__calibre_serializable__', False):
            from calibre.ebooks.metadata.book.base import Metadata
            from calibre.library.field_metadata import FieldMetadata, fm_as_dict
            from calibre.db.categories import Tag
            if isinstance(obj, Metadata):
                from calibre.ebooks.metadata.book.serialize import metadata_as_dict
                return encoded(
                    2, metadata_as_dict(obj, encode_cover_data=for_json), ExtType
                )
            elif isinstance(obj, FieldMetadata):
                return encoded(3, fm_as_dict(obj), ExtType)
            elif isinstance(obj, Tag):
                return encoded(4, obj.as_dict(), ExtType)
        if for_json and isinstance(obj, bytes):
            return obj.decode('utf-8')
        raise TypeError('Cannot serialize objects of type {}'.format(type(obj)))

    return encoder


def msgpack_dumps(obj):
    import msgpack
    return msgpack.packb(obj, default=create_encoder(), use_bin_type=True)


def json_dumps(data, **kw):
    import json
    kw['default'] = create_encoder(for_json=True)
    kw['ensure_ascii'] = False
    ans = json.dumps(data, **kw)
    if not isinstance(ans, bytes):
        ans = ans.encode('utf-8')
    return ans


def decode_metadata(x, for_json):
    from polyglot.binary import from_base64_bytes
    from calibre.ebooks.metadata.book.serialize import metadata_from_dict
    obj = metadata_from_dict(x)
    if for_json and obj.cover_data and obj.cover_data[1]:
        obj.cover_data = obj.cover_data[0], from_base64_bytes(obj.cover_data[1])
    return obj


def decode_field_metadata(x, for_json):
    from calibre.library.field_metadata import fm_from_dict
    return fm_from_dict(x)


def decode_category_tag(x, for_json):
    from calibre.db.categories import Tag
    return Tag.from_dict(x)


def decode_datetime(x, fj):
    from calibre.utils.iso8601 import parse_iso8601
    return parse_iso8601(x, assume_utc=True)


decoders = (
    decode_datetime,
    lambda x, fj: set(x),
    decode_metadata, decode_field_metadata, decode_category_tag
)


def json_decoder(obj):
    typ = obj.get(CANARY)
    if typ is None:
        return obj
    return decoders[typ](obj['v'], True)


def msgpack_decoder(code, data):
    return decoders[code](msgpack_loads(data), False)


def msgpack_loads(dump, use_list=True):
    # use_list controls whether msgpack arrays are unpacked as lists or tuples
    import msgpack
    return msgpack.unpackb(dump, ext_hook=msgpack_decoder, raw=False, use_list=use_list, strict_map_key=False)


def json_loads(data):
    import json
    return json.loads(data, object_hook=json_decoder)


def pickle_dumps(data):
    import pickle
    return pickle.dumps(data, -1)


def pickle_loads(dump):
    import pickle
    return pickle.loads(dump, encoding='utf-8')
