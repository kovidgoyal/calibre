#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, errno

from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint

@endpoint('/static/{+what}', auth_required=False, cache_control=24)
def static(ctx, rd, what):
    base = P('content-server', allow_user_override=False)
    path = os.path.abspath(os.path.join(base, *what.split('/')))
    if not path.startswith(base) or ':' in what:
        raise HTTPNotFound('Naughty, naughty!')
    path = os.path.relpath(path, base).replace(os.sep, '/')
    path = P('content-server/' + path)
    try:
        return lopen(path, 'rb')
    except EnvironmentError as e:
        if e.errno == errno.EISDIR or os.path.isdir(path):
            raise HTTPNotFound('Cannot get a directory')
        raise HTTPNotFound()

@endpoint('/favicon.png', auth_required=False, cache_control=24)
def favicon(ctx, rd):
    return lopen(I('lt.png'), 'rb')
