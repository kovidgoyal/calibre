#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable


def control[F: Callable[..., object]](func: F) -> F:
    setattr(func, 'function_type', 'control')
    return func


def data[F: Callable[..., object]](func: F) -> F:
    setattr(func, 'function_type', 'data')
    return func


class DataError(Exception):
    def __init__(self, tb: str, msg: str | None = None) -> None:
        Exception.__init__(self, msg or _('Failed to get completion data'))
        self.tb = tb

    def traceback(self) -> str:
        return str(self) + '\n' + self.tb
