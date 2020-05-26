#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import re

from polyglot.functools import lru_cache


@lru_cache(maxsize=2)
def get_book_library_details(absolute_path_to_ebook):
    absolute_path_to_ebook = os.path.abspath(os.path.expanduser(absolute_path_to_ebook))
    base = os.path.dirname(absolute_path_to_ebook)
    m = re.search(r' \((\d+)\)$', os.path.basename(base))
    if m is None:
        return
    book_id = int(m.group(1))
    library_dir = os.path.dirname(os.path.dirname(base))
    dbpath = os.path.join(library_dir, 'metadata.db')
    dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH') or dbpath
    if not os.path.exists(dbpath):
        return None
    return {'dbpath': dbpath, 'book_id': book_id, 'fmt': absolute_path_to_ebook.rpartition('.')[-1].upper()}
