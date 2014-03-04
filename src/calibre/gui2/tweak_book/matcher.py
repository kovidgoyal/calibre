#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from unicodedata import normalize

from future_builtins import map

from calibre.constants import plugins
from calibre.utils.icu import primary_sort_key

class Matcher(object):

    def __init__(self, items):
        items = map(lambda x: normalize('NFC', unicode(x)), filter(None, items))
        items = tuple(map(lambda x: x.encode('utf-8'), items))
        sort_keys = tuple(map(primary_sort_key, items))

        speedup, err = plugins['matcher']
        if speedup is None:
            raise RuntimeError('Failed to load the matcher plugin with error: %s' % err)
        self.m = speedup.Matcher(items, sort_keys)

    def __call__(self, query):
        query = normalize('NFC', unicode(query)).encode('utf-8')
        return self.m.get_matches(query)

def test_mem():
    from calibre.utils.mem import gc_histogram, diff_hists
    m = Matcher([])
    del m
    def doit(c):
        m = Matcher([c+'im/one.gif', c+'im/two.gif', c+'text/one.html',])
        m('one')
    import gc
    gc.collect()
    h1 = gc_histogram()
    for i in xrange(100):
        doit(str(i))
    h2 = gc_histogram()
    diff_hists(h1, h2)

if __name__ == '__main__':
    test_mem()
