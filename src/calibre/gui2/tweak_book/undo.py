#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'


class State(object):

    def __init__(self, container):
        self.container = container
        self.operation = None

class GlobalUndoHistory(object):

    def __init__(self):
        self.states = []

    def open_book(self, container):
        self.states = [State(container)]

