#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks import DRMError as _DRMError


class InvalidBook(ValueError):
    pass


class DRMError(_DRMError):

    def __init__(self):
        super().__init__(_('This file is locked with DRM. It cannot be edited.'))


class MalformedMarkup(ValueError):
    pass
