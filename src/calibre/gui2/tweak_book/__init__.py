#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.utils.config import JSONConfig
tprefs = JSONConfig('tweak_book_gui')

_current_container = None

def current_container():
    return _current_container

def set_current_container(container):
    global _current_container
    _current_container = container
