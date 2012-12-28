#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.ebooks.pdf.render.common import Array, Name

class Destination(Array):

    def __init__(self, start_page, pos):
        super(Destination, self).__init__(
            [start_page + pos['column'], Name('FitH'), pos['y']])

class Links(object):

    def __init__(self):
        self.anchors = {}

    def add(self, base_path, start_page, links, anchors):
        path = os.path.normcase(os.path.abspath(base_path))
        self.anchors[path] = a = {}
        a[None] = Destination(start_page, {'y':0, 'column':0})
        for anchor, pos in anchors.iteritems():
            a[anchor] = Destination(start_page, pos)


