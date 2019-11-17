#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.constants import plugins

lzma = plugins['lzma_binding'][0]
if not lzma:
    raise RuntimeError('Failed to load lzma_binding module with error: %s' % plugins['lzma_binding'][1])

LzmaError = lzma.error

class NotXZ(LzmaError):
    pass

class InvalidXZ(LzmaError):
    pass

class NotLzma(LzmaError):
    pass

