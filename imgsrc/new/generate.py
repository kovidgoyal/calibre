#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os

duplicates = {
    'character-set': ['languages'],
    'calibre': ['library', 'lt'],
    'format-text-color': 'lookfeel',
    'books_in_series': ['series'],
}

sizes = {
    'lt': '256',
    'default_cover': 'original',
    'viewer': '256',
    'tweak': '256',
}

skip = {'calibre'}

base = os.path.dirname(os.path.abspath(__file__))

for src in os.listdir(base):
    if src.endswith('.svg'):
        name = src.rpartition('.')[0]
        names = [name] + duplicates.get(name, [])
        for oname in names:
            if oname in skip:
                continue
        src = os.path.join(base, name + '.svg')
