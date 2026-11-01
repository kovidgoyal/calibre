#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>

import random
from collections import OrderedDict
from io import BytesIO
from struct import pack
from typing import ClassVar

from calibre.ebooks.mobi.utils import align_block
from polyglot.builtins import as_bytes

NULL = 0xFFFFFFFF

type HeaderValue = int | bytes | None


def zeroes(x: int) -> bytes:
    return b'\x00' * x


def nulls(x: int) -> bytes:
    return b'\xff' * x


def short(x: int) -> bytes:
    return pack(b'>H', x)


class Header(OrderedDict[str, HeaderValue]):
    HEADER_NAME = b''

    DEFINITION = '''
    '''

    ALIGN_BLOCK = False
    POSITIONS: ClassVar[dict[str, str]] = {}  # Mapping of position field to field whose position should
    # be stored in the position field
    SHORT_FIELDS: ClassVar[set[str]] = set()

    def __init__(self) -> None:
        OrderedDict.__init__(self)

        for line in self.DEFINITION.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, val = (x.strip() for x in line.partition('=')[0::2])
            if val:
                val = eval(val, {'zeroes': zeroes, 'NULL': NULL, 'DYN': None, 'nulls': nulls, 'short': short, 'random': random})
            else:
                val = 0
            if name in self:
                raise ValueError(f'Duplicate field in definition: {name!r}')
            self[name] = val

    @property
    def dynamic_fields(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.items() if v is None)

    def __call__(self, **kwargs: HeaderValue) -> bytes:
        positions = {}
        for name, val in kwargs.items():
            if name not in self:
                raise KeyError(f'Not a valid header field: {name!r}')
            self[name] = val

        buf = BytesIO()
        buf.write(as_bytes(self.HEADER_NAME))
        for name, val in self.items():
            val = self.format_value(name, val)
            positions[name] = buf.tell()
            if val is None:
                raise ValueError(f'Dynamic field {name!r} not set')
            if isinstance(val, int):
                fmt = b'H' if name in self.SHORT_FIELDS else b'I'
                val = pack(b'>' + fmt, val)
            buf.write(val)

        for pos_field, field in self.POSITIONS.items():
            buf.seek(positions[pos_field])
            buf.write(pack(b'>I', positions[field]))

        ans = buf.getvalue()
        if self.ALIGN_BLOCK:
            ans = align_block(ans)
        return ans

    def format_value(self, name: str, val: HeaderValue) -> HeaderValue:
        return val
