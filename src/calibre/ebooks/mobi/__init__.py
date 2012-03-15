#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

class MobiError(Exception):
    pass

MAX_THUMB_SIZE = 16 * 1024
MAX_THUMB_DIMEN = (180, 240)


