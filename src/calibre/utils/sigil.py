#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.utils.filenames import find_executable_in_path
from calibre.constants import iswindows

def find_executable():
    name = 'sigil' + ('.exe' if iswindows else '')
    find_executable_in_path(name)
    #if path is None and iswindows:
    #    path = search_program_files()

