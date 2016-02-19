#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)


from calibre.srv.errors import HTTPRedirect
from calibre.srv.routes import endpoint

@endpoint('/browse/{+rest=""}')
def browse(ctx, rd, rest):
    raise HTTPRedirect(ctx.url_for('') or '/')

@endpoint('/mobile/{+rest=""}')
def mobile(ctx, rd, rest):
    raise HTTPRedirect(ctx.url_for('') or '/')

