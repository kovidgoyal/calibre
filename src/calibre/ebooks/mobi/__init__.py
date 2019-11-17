#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import absolute_import, division, print_function, unicode_literals

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


class MobiError(Exception):
    pass


# That might be a bit small on the PW, but Amazon/KG 2.5 still uses these values, even when delivered to a PW
MAX_THUMB_SIZE = 16 * 1024
MAX_THUMB_DIMEN = (180, 240)
