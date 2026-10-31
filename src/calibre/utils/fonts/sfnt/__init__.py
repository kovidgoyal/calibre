#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

from datetime import datetime, timedelta
from typing import IO, TYPE_CHECKING

from calibre.utils.date import utc_tz

if TYPE_CHECKING:
    from calibre.utils.fonts.sfnt.container import Sfnt


def align_block(raw: bytes, multiple: int = 4, pad: bytes = b'\0') -> bytes:
    """
    Return raw with enough pad bytes append to ensure its length is a multiple
    of 4.
    """
    extra = len(raw) % multiple
    if extra == 0:
        return raw
    return raw + pad * (multiple - extra)


class UnknownTable:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __call__(self) -> bytes:
        return self.raw

    def __len__(self) -> int:
        return len(self.raw)


class DateTimeProperty:
    def __init__(self, name: str) -> None:
        self.name = name

    def __get__(self, obj: object, type: type | None = None) -> datetime:
        return datetime(1904, 1, 1, tzinfo=utc_tz) + timedelta(seconds=getattr(obj, self.name))

    def __set__(self, obj: object, val: datetime) -> None:
        td = val - datetime(1904, 1, 1, tzinfo=utc_tz)
        setattr(obj, self.name, int(td.total_seconds()))


class FixedProperty:
    def __init__(self, name: str) -> None:
        self.name = name

    def __get__(self, obj: object, type: type | None = None) -> float:
        val = getattr(obj, self.name)
        return val / 0x10000

    def __set__(self, obj: object, val: float) -> int:
        return round(val * (0x10000))


def max_power_of_two(x: int) -> int:
    """
    Return the highest exponent of two, so that
        (2 ** exponent) <= x
    """
    exponent = 0
    while x:
        x = x >> 1
        exponent += 1
    return max(exponent - 1, 0)


def load_font(stream_or_path: bytes | IO[bytes]) -> Sfnt:
    raw = stream_or_path
    if hasattr(raw, 'read'):
        raw = raw.read()  # ty: ignore[call-non-callable]
    from calibre.utils.fonts.sfnt.container import Sfnt

    return Sfnt(raw)
