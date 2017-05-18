#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import json
from functools import partial
from importlib import import_module
from threading import Lock

from calibre.srv.auth import AuthController
from calibre.srv.errors import HTTPForbidden
from calibre.srv.library_broker import LibraryBroker
from calibre.srv.routes import Router
from calibre.srv.users import UserManager
from calibre.utils.date import utcnow


class Context(object):

    log = None
    url_for = None
    jobs_manager = None
    CATEGORY_CACHE_SIZE = 25
    SEARCH_CACHE_SIZE = 100

    def __init__(self, libraries, opts, testing=False, notify_changes=None):
        self.opts = opts
        self.library_broker = libraries if isinstance(libraries, LibraryBroker) else LibraryBroker(libraries)
        self.testing = testing
        self.lock = Lock()
        self.user_manager = UserManager(opts.userdb)
        self.ignored_fields = frozenset(filter(None, (x.strip() for x in (opts.ignored_fields or '').split(','))))
        self.displayed_fields = frozenset(filter(None, (x.strip() for x in (opts.displayed_fields or '').split(','))))
        self._notify_changes = notify_changes

    def notify_changes(self, library_path, change_event):
        if self._notify_changes is not None:
            self._notify_changes(library_path, change_event)

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
        if not data.username:
            return self.library_broker.get(library_id)
        lf = partial(self.user_manager.allowed_library_names, data.username)
        allowed_libraries = self.library_broker.allowed_libraries(lf)
        if not allowed_libraries:
            raise HTTPForbidden('The user {} is not allowed to access any libraries on this server'.format(data.username))
        library_id = library_id or next(allowed_libraries.iterkeys())
        if library_id in allowed_libraries:
            return self.library_broker.get(library_id)
        raise HTTPForbidden('The user {} is not allowed to access the library {}'.format(data.username, library_id))

    def library_info(self, data):
        if not data.username:
            return self.library_broker.library_map, self.library_broker.default_library
        lf = partial(self.user_manager.allowed_library_names, data.username)
        allowed_libraries = self.library_broker.allowed_libraries(lf)
        if not allowed_libraries:
            raise HTTPForbidden('The user {} is not allowed to access any libraries on this server'.format(data.username))
        return dict(allowed_libraries), next(allowed_libraries.iterkeys())

    def check_for_write_access(self, data):
        if not data.username:
            if data.is_local_connection and self.opts.local_write:
                return
            raise HTTPForbidden('Anonymous users are not allowed to make changes')
        if self.user_manager.is_readonly(data.username):
            raise HTTPForbidden('The user {} does not have permission to make changes'.format(data.username))

    def get_categories(self, data, db, sort='name', first_letter_sort=True, vl=''):
        restrict_to_ids = db.books_in_virtual_library(vl)
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

    def get_tag_browser(self, data, db, opts, render, vl=''):
        restrict_to_ids = db.books_in_virtual_library(vl)
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

    def search(self, data, db, query, vl=''):
        with self.lock:
            cache = self.library_broker.search_caches[db.server_library_id]
            vl = db.pref('virtual_libraries', {}).get(vl) or ''
            key = query, vl
            old = cache.pop(key, None)
            if old is None or old[0] < db.clear_search_cache_count:
                matches = db.search(query, restriction=vl)
                cache[key] = old = (db.clear_search_cache_count, matches)
                if len(cache) > self.SEARCH_CACHE_SIZE:
                    cache.popitem(last=False)
            else:
                cache[key] = old
            return old[1]


class Handler(object):

    def __init__(self, libraries, opts, testing=False, notify_changes=None):
        ctx = Context(libraries, opts, testing=testing, notify_changes=notify_changes)
        self.auth_controller = None
        if opts.auth:
            has_ssl = opts.ssl_certfile is not None and opts.ssl_keyfile is not None
            prefer_basic_auth = {'auto':has_ssl, 'basic':True}.get(opts.auth_mode, False)
            self.auth_controller = AuthController(user_credentials=ctx.user_manager, prefer_basic_auth=prefer_basic_auth)
        self.router = Router(ctx=ctx, url_prefix=opts.url_prefix, auth_controller=self.auth_controller)
        for module in ('content', 'ajax', 'code', 'legacy', 'opds', 'books', 'cdb'):
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
