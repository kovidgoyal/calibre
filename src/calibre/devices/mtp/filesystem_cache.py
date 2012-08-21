#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

class FilesystemCache(object):

    def __init__(self, storage_map):
        self.tree = {}
        for storage_id, id_map in storage_map.iteritems():
            self.tree[storage_id] = self.build_tree(id_map)

