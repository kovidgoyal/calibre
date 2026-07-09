#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from contextlib import contextmanager

from calibre.ebooks import DRMError as _DRMError


class InvalidBook(ValueError):
    pass


_drm_message = ''


@contextmanager
def drm_message(msg: str) -> None:
    global _drm_message
    orig, _drm_message = _drm_message, msg
    try:
        yield
    finally:
        _drm_message = orig


class DRMError(_DRMError):

    def __init__(self):
        super().__init__(_drm_message or _('This file is locked with DRM. It cannot be edited.'))


class MalformedMarkup(ValueError):
    pass


class UnsupportedContainerType(Exception):
    pass
