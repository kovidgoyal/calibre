#!/usr/bin/env python
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


import sys
from time import monotonic_ns

from calibre.constants import DEBUG


def get_current_book_data(set_val=False):
    if set_val is not False:
        setattr(get_current_book_data, 'ans', set_val)
    return getattr(get_current_book_data, 'ans', {})


def get_boss(set_val=False):
    if set_val:
        get_boss.ans = set_val
    return get_boss.ans


def link_prefix_for_location_links(add_open_at=True):
    cbd = get_current_book_data()
    link_prefix = library_id = None
    if 'calibre_library_id' in cbd:
        library_id = cbd['calibre_library_id']
        book_id = cbd['calibre_book_id']
        book_fmt = cbd['calibre_book_fmt']
    elif cbd.get('book_library_details'):
        bld = cbd['book_library_details']
        book_id = bld['book_id']
        book_fmt = bld['fmt'].upper()
        library_id = bld['library_id']
    if library_id:
        library_id = '_hex_-' + library_id.encode('utf-8').hex()
        link_prefix = f'calibre://view-book/{library_id}/{book_id}/{book_fmt}'
        if add_open_at:
            link_prefix += '?open_at='
    return link_prefix


def url_for_book_in_library():
    cbd = get_current_book_data()
    ans = library_id = None
    if 'calibre_library_id' in cbd:
        library_id = cbd['calibre_library_id']
        book_id = cbd['calibre_book_id']
    elif cbd.get('book_library_details'):
        bld = cbd['book_library_details']
        book_id = bld['book_id']
        library_id = bld['library_id']
    if library_id:
        library_id = '_hex_-' + library_id.encode('utf-8').hex()
        ans = f'calibre://show-book/{library_id}/{book_id}'
    return ans



class PerformanceMonitor:

    def __init__(self):
        self.start_time = monotonic_ns()

    def __call__(self, desc='', reset=False):
        if DEBUG:
            at = monotonic_ns()
            if reset:
                self.start_time = at
            if desc:
                ts = (at - self.start_time) / 1e9
                print(f'[{ts:.3f}] {desc}', file=sys.stderr)


performance_monitor = PerformanceMonitor()
