#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from importlib import import_module
from threading import Lock

from calibre import force_unicode
from calibre.db.cache import Cache
from calibre.db.legacy import create_backend, LibraryDatabase
from calibre.srv.routes import Router

def init_library(library_path):
    db = Cache(create_backend(library_path))
    db.init()
    return db

class LibraryBroker(object):

    def __init__(self, libraries):
        self.lock = Lock()
        self.lmap = {}
        for path in libraries:
            if not LibraryDatabase.exists_at(path):
                continue
            library_id = base = force_unicode(os.path.basename(path))
            c = 0
            while library_id in self.lmap:
                c += 1
                library_id = base + ' (1)'
            if path is libraries[0]:
                self.default_library = library_id
            self.lmap[library_id] = path

    def get(self, library_id=None):
        with self.lock:
            library_id = library_id or self.default_library
            ans = self.lmap.get(library_id)
            if ans is None:
                return
            if not callable(getattr(ans, 'init', None)):
                try:
                    self.lmap[library_id] = ans = init_library(ans)
                    ans.server_library_id = library_id
                except Exception:
                    self.lmap[library_id] = ans = None
                    raise
            return ans


class Context(object):

    log = None
    url_for = None

    def __init__(self, libraries, opts, testing=False):
        self.opts = opts
        self.library_broker = LibraryBroker(libraries)
        self.testing = testing

    def init_session(self, endpoint, data):
        pass

    def finalize_session(self, endpoint, data, output):
        pass

    def get_library(self, library_id=None):
        return self.library_broker.get(library_id)

class Handler(object):

    def __init__(self, libraries, opts, testing=False):
        self.router = Router(ctx=Context(libraries, opts, testing=testing), url_prefix=opts.url_prefix)
        for module in ('content', 'ajax'):
            module = import_module('calibre.srv.' + module)
            self.router.load_routes(vars(module).itervalues())
        self.router.finalize()
        self.router.ctx.url_for = self.router.url_for
        self.dispatch = self.router.dispatch

    def set_log(self, log):
        self.router.ctx.log = log

