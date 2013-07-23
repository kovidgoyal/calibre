#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, cProfile
from tempfile import gettempdir

from calibre.db.legacy import LibraryDatabase

db = None
def initdb(path):
    global db
    db = LibraryDatabase(os.path.expanduser(path))

def show_stats(path):
    from pstats import Stats
    s = Stats(path)
    s.sort_stats('cumulative')
    s.print_stats(30)

def main():
    stats = os.path.join(gettempdir(), 'read_db.stats')
    pr = cProfile.Profile()
    pr.enable()
    initdb('~/documents/largelib')
    pr.disable()
    pr.dump_stats(stats)
    show_stats(stats)
    print ('Stats saved to', stats)

if __name__ == '__main__':
    main()
