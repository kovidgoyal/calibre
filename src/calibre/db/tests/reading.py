#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import os, shutil#, unittest

def create_db(library_path):
    from calibre.library.database2 import LibraryDatabase2
    if LibraryDatabase2.exists_at(library_path):
        raise ValueError('A library already exists at %r'%library_path)
    src = os.path.join(os.path.dirname(__file__), 'metadata.db')
    db = os.path.join(library_path, 'metadata.db')
    shutil.copyfile(src, db)
    db = LibraryDatabase2(library_path)

