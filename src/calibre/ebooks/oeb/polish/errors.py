#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from contextlib import contextmanager
from typing import TYPE_CHECKING

from calibre.ebooks import DRMError as _DRMError
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Generator


class InvalidBook(ValueError):
    pass


_drm_message = ''


@contextmanager
def drm_message(msg: str) -> Generator[None]:
    global _drm_message
    orig, _drm_message = _drm_message, msg
    try:
        yield
    finally:
        _drm_message = orig


class DRMError(_DRMError):
    def __init__(self) -> None:
        super().__init__(_drm_message or _('This file is locked with DRM. It cannot be edited.'))


class MalformedMarkup(ValueError):
    pass


class UnsupportedContainerType(Exception):
    pass
