#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import errno

from calibre import sanitize_file_name2
from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint

@endpoint('', auth_required=False)
def index(ctx, rd):
    return lopen(P('content-server/index.html'), 'rb')

@endpoint('/js/{which}', auth_required=False)
def js(ctx, rd, which):
    try:
        return lopen(P('content-server/' + sanitize_file_name2(which)), 'rb')
    except EnvironmentError as e:
        if e.errno == errno.ENOENT:
            raise HTTPNotFound('No js with name: %r' % which)
        raise
