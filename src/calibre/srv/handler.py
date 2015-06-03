#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import binascii, os, random

from calibre.srv.routes import Router

class LibraryBroker(object):

    def __init__(self, libraries):
        self.libraries = libraries

class Context(object):

    log = None
    url_for = None

    def __init__(self, libraries, opts):
        self.opts = opts
        self.library_broker = LibraryBroker(libraries)
        self.secret = bytes(binascii.hexlify(os.urandom(random.randint(20, 30))))
        self.key_order = random.choice(('{0}:{1}', '{1}:{0}'))

    def init_session(self, endpoint, data):
        cval = data.inheaders.get('Cookie') or ''
        if isinstance(cval, bytes):
            cval = cval.decode('utf-8', 'replace')
        data.cookies = c = {}
        for x in cval.split(';'):
            x = x.strip()
            if x:
                k, v = x.partition('=')[::2]
                c[k] = v

    def finalize_session(self, endpoint, data, output):
        pass

class Handler(object):

    def __init__(self, libraries, opts):
        self.router = Router(ctx=Context(libraries, opts), url_prefix=opts.url_prefix)
        self.router.ctx.url_for = self.router.url_for
        self.dispatch = self.router.dispatch

    def set_log(self, log):
        self.router.ctx.log = log

