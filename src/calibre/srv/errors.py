#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'


class NonHTTPConnRequest(Exception):

    def __init__(self, data=None):
        Exception.__init__(self, '')
        self.data = data

class MaxSizeExceeded(Exception):

    def __init__(self, prefix, size, limit):
        Exception.__init__(self, prefix + (' %d > maximum %d' % (size, limit)))

class HTTP404(Exception):
    pass

class IfNoneMatch(Exception):
    def __init__(self, etag=None):
        Exception.__init__(self, '')
        self.etag = etag
