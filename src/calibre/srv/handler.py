#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import json
from importlib import import_module
from threading import Lock

from calibre.srv.auth import AuthController
from calibre.srv.routes import Router
from calibre.srv.users import UserManager
from calibre.srv.library_broker import LibraryBroker
from calibre.utils.date import utcnow


class Context(object):

    log = None
    url_for = None
    jobs_manager = None
    CATEGORY_CACHE_SIZE = 25
    SEARCH_CACHE_SIZE = 100

    def __init__(self, libraries, opts, testing=False):
        self.opts = opts
        self.library_broker = libraries if isinstance(libraries, LibraryBroker) else LibraryBroker(libraries)
        self.testing = testing
        self.lock = Lock()
        self.user_manager = UserManager(opts.userdb)
        self.ignored_fields = frozenset(filter(None, (x.strip() for x in (opts.ignored_fields or '').split(','))))
        self.displayed_fields = frozenset(filter(None, (x.strip() for x in (opts.displayed_fields or '').split(','))))

    def start_job(self, name, module, func, args=(), kwargs=None, job_done_callback=None, job_data=None):
        return self.jobs_manager.start_job(name, module, func, args, kwargs, job_done_callback, job_data)

    def job_status(self, job_id):
        return self.jobs_manager.job_status(job_id)

    def is_field_displayable(self, field):
        if self.displayed_fields and field not in self.displayed_fields:
            return False
        return field not in self.ignored_fields

    def init_session(self, endpoint, data):
        pass

    def finalize_session(self, endpoint, data, output):
        pass

    def get_library(self, data, library_id=None):
        # TODO: Restrict the libraries based on data.username
        return self.library_broker.get(library_id)

    def library_info(self, data):
        # TODO: Restrict the libraries based on data.username
        return self.library_broker.library_map, self.library_broker.default_library

    def allowed_book_ids(self, data, db):
        with self.lock:
            ans = data.allowed_book_ids.get(db.server_library_id)
            if ans is None:
                ans = data.allowed_book_ids[db.server_library_id] = db.all_book_ids()
            return ans

    def get_categories(self, data, db, restrict_to_ids=None, sort='name', first_letter_sort=True):
        if restrict_to_ids is None:
            restrict_to_ids = self.allowed_book_ids(data, db)
        key = (restrict_to_ids, sort, first_letter_sort)
        with self.lock:
            cache = self.library_broker.category_caches[db.server_library_id]
            old = cache.pop(key, None)
            if old is None or old[0] <= db.last_modified():
                categories = db.get_categories(book_ids=restrict_to_ids, sort=sort, first_letter_sort=first_letter_sort)
                cache[key] = old = (utcnow(), categories)
                if len(cache) > self.CATEGORY_CACHE_SIZE:
                    cache.popitem(last=False)
            else:
                cache[key] = old
            return old[1]

    def get_tag_browser(self, data, db, opts, render, restrict_to_ids=None):
        if restrict_to_ids is None:
            restrict_to_ids = self.allowed_book_ids(data, db)
        key = (restrict_to_ids, opts)
        with self.lock:
            cache = self.library_broker.category_caches[db.server_library_id]
            old = cache.pop(key, None)
            if old is None or old[0] <= db.last_modified():
                categories = db.get_categories(book_ids=restrict_to_ids, sort=opts.sort_by, first_letter_sort=opts.collapse_model == 'first letter')
                data = json.dumps(render(db, categories), ensure_ascii=False)
                if isinstance(data, type('')):
                    data = data.encode('utf-8')
                cache[key] = old = (utcnow(), data)
                if len(cache) > self.CATEGORY_CACHE_SIZE:
                    cache.popitem(last=False)
            else:
                cache[key] = old
            return old[1]

    def search(self, data, db, query, restrict_to_ids=None):
        if restrict_to_ids is None:
            restrict_to_ids = self.allowed_book_ids(data, db)
        with self.lock:
            cache = self.library_broker.search_caches[db.server_library_id]
            key = (query, restrict_to_ids)
            old = cache.pop(key, None)
            if old is None or old[0] < db.clear_search_cache_count:
                matches = db.search(query, book_ids=restrict_to_ids)
                cache[key] = old = (db.clear_search_cache_count, matches)
                if len(cache) > self.SEARCH_CACHE_SIZE:
                    cache.popitem(last=False)
            else:
                cache[key] = old
            return old[1]


class Handler(object):

    def __init__(self, libraries, opts, testing=False):
        ctx = Context(libraries, opts, testing=testing)
        self.auth_controller = None
        if opts.auth:
            has_ssl = opts.ssl_certfile is not None and opts.ssl_keyfile is not None
            prefer_basic_auth = {'auto':has_ssl, 'basic':True}.get(opts.auth_mode, False)
            self.auth_controller = AuthController(user_credentials=ctx.user_manager, prefer_basic_auth=prefer_basic_auth)
        self.router = Router(ctx=ctx, url_prefix=opts.url_prefix, auth_controller=self.auth_controller)
        for module in ('content', 'ajax', 'code', 'legacy', 'opds', 'books'):
            module = import_module('calibre.srv.' + module)
            self.router.load_routes(vars(module).itervalues())
        self.router.finalize()
        self.router.ctx.url_for = self.router.url_for
        self.dispatch = self.router.dispatch

    def set_log(self, log):
        self.router.ctx.log = log
        if self.auth_controller is not None:
            self.auth_controller.log = log

    def set_jobs_manager(self, jobs_manager):
        self.router.ctx.jobs_manager = jobs_manager

    def close(self):
        self.router.ctx.library_broker.close()
