#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import QListView

class AlternateViews(object):

    def __init__(self, main_view):
        self.views = {}
        self.current_view = self.main_view = main_view
        self.stack = None

    def set_stack(self, stack):
        self.stack = stack
        self.stack.addWidget(self.main_view)

    def add_view(self, key, view):
        self.views[key] = view
        self.stack.addWidget(view)
        self.stack.setCurrentIndex(0)

class GridView(QListView):
    pass

