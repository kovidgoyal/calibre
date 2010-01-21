#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import __builtin__, sys, os

_dev_path = os.environ.get('CALIBRE_DEVELOP_FROM', None)
if _dev_path is not None:
    _dev_path = os.path.join(os.path.abspath(os.path.dirname(_dev_path)), 'resources')
    if not os.path.exists(_dev_path):
        _dev_path = None

def get_path(path, data=False):
    global _dev_path
    path = path.replace(os.sep, '/')
    base = None
    if _dev_path is not None:
        if os.path.exists(os.path.join(_dev_path, *path.split('/'))):
            base = _dev_path
    if base is None:
        base = sys.resources_location
    path = os.path.join(base, *path.split('/'))
    if data:
        return open(path, 'rb').read()
    return path

def get_image_path(path, data=False):
    return get_path('images/'+path, data=data)

__builtin__.__dict__['P'] = get_path
__builtin__.__dict__['I'] = get_image_path
