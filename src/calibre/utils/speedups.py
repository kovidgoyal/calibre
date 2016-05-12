#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

import os

class ReadOnlyFileBuffer(object):

    ''' A zero copy implementation of a file like object. Uses memoryviews for efficiency. '''

    def __init__(self, raw):
        self.sz, self.mv = len(raw), (raw if isinstance(raw, memoryview) else memoryview(raw))
        self.pos = 0

    def tell(self):
        return self.pos

    def read(self, n=None):
        if n is None:
            ans = self.mv[self.pos:]
            self.pos = self.sz
            return ans
        ans = self.mv[self.pos:self.pos+n]
        self.pos = min(self.pos + n, self.sz)
        return ans

    def seek(self, pos, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self.pos = pos
        elif whence == os.SEEK_END:
            self.pos = self.sz + pos
        else:
            self.pos += pos
        self.pos = max(0, min(self.pos, self.sz))
        return self.pos

    def getvalue(self):
        return self.mv

    def close(self):
        pass


