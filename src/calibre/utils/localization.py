#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

_available_translations = None

def available_translations():
    global _available_translations
    if _available_translations is None:
        base = P('resources/localization/locales')
        _available_translations = os.listdir(base)
    return _available_translations
