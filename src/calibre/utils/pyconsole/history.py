#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import deque

class History(object): # {{{

    def __init__(self, current, entries):
        self.entries = deque(entries, maxlen=max(2000, len(entries)))
        self.index = len(self.entries) - 1
        self.current = self.default = current
        self.last_was_back = False

    def back(self, amt=1):
        if self.entries:
            oidx = self.index
            ans = self.entries[self.index]
            self.index = max(0, self.index - amt)
            self.last_was_back = self.index != oidx
            return ans

    def forward(self, amt=1):
        if self.entries:
            d = self.index
            if self.last_was_back:
                d += 1
            if d >= len(self.entries) - 1:
                self.index = len(self.entries) - 1
                self.last_was_back = False
                return self.current
            if self.last_was_back:
                amt += 1
            self.index = min(len(self.entries)-1, self.index + amt)
            self.last_was_back = False
            return self.entries[self.index]

    def enter(self, x):
        try:
            self.entries.remove(x)
        except ValueError:
            pass
        self.entries.append(x)
        self.index = len(self.entries) - 1
        self.current = self.default
        self.last_was_back = False

    def serialize(self):
        return list(self.entries)

# }}}


