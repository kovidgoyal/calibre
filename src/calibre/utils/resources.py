#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import __builtin__, sys, os

def get_path(path, data=False):
    path = path.replace(os.sep, '/')
    path = os.path.join(sys.resources_location, *path.split('/'))
    if data:
        return open(path, 'rb').read()
    return path

def get_image_path(path, data=False):
    return get_path('images/'+path, data=data)

__builtin__.__dict__['P'] = get_path
__builtin__.__dict__['I'] = get_image_path
