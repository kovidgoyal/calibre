#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.srv.routes import Router

class LibraryBroker(object):

    def __init__(self, libraries):
        self.libraries = libraries

class Context(object):

    def __init__(self, libraries):
        self.library_broker = LibraryBroker(libraries)

class Handler(object):

    def __init__(self, libraries, opts):
        self.router = Router(ctx=Context(libraries), url_prefix=opts.url_prefix)
        self.router.ctx.url_for = self.router.url_for
        self.dispatch = self.router.dispatch

