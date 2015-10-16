#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from calibre.srv.routes import endpoint

@endpoint('', auth_required=False)
def index(ctx, rd):
    return lopen(P('content-server/index.html'), 'rb')
