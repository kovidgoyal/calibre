#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
from datetime import datetime
from calibre.utils.iso8601 import parse_iso8601


MSGPACK_MIME = 'application/x-msgpack'


def encoder(obj):
    if isinstance(obj, datetime):
        return {'__datetime__': obj.isoformat()}
    return obj


def msgpack_dumps(data):
    import msgpack
    return msgpack.packb(data, use_bin_type=True, default=encoder)


def json_dumps(data, **kw):
    kw['default'] = encoder
    kw['ensure_ascii'] = False
    ans = json.dumps(data, **kw)
    if not isinstance(ans, bytes):
        ans = ans.encode('utf-8')
    return ans


def decoder(obj):
    dt = obj.get('__datetime__')
    if dt is not None:
        obj = parse_iso8601(dt, assume_utc=True)
    return obj


def msgpack_loads(data):
    import msgpack
    return msgpack.unpackb(
        data, encoding='utf-8', use_list=False, object_hook=decoder
    )


def json_loads(data):
    return json.loads(data, object_hook=decoder)
