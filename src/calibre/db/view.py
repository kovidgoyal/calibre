#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


class View(object):

    def __init__(self, cache):
        self.cache = cache
        self._field_idx_map = {}
        for col, idx in cache.backend.FIELD_MAP.iteritems():
            if isinstance(col, int):
                pass # custom column
            else:
                self._field_idx_map[idx] = col

