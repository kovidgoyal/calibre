#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from bisect import bisect

class PositionFinder(object):

    def __init__(self, raw):
        pat = br'\n' if isinstance(raw, bytes) else r'\n'
        self.new_lines = tuple(m.start() + 1 for m in re.finditer(pat, raw))

    def __call__(self, pos):
        lnum = bisect(self.new_lines, pos)
        try:
            offset = abs(pos - self.new_lines[lnum - 1])
        except IndexError:
            offset = pos
        return (lnum + 1, offset)

class CommentFinder(object):

    def __init__(self, raw, pat=r'(?s)/\*.*?\*/'):
        self.starts, self.ends = [], []
        for m in re.finditer(pat, raw):
            start, end = m.span()
            self.starts.append(start), self.ends.append(end)

    def __call__(self, offset):
        if not self.starts:
            return False
        q = bisect(self.starts, offset) - 1
        return q >= 0 and self.starts[q] <= offset <= self.ends[q]

