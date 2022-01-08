#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import json
from functools import partial
from importlib import import_module
from threading import Lock

from calibre.srv.auth import AuthController
from calibre.srv.errors import HTTPForbidden
from calibre.srv.library_broker import LibraryBroker, path_for_db
from calibre.srv.routes import Router
from calibre.srv.users import UserManager
from calibre.utils.date import utcnow
from calibre.utils.search_query_parser import ParseException
from polyglot.builtins import itervalues


class Context:

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

    def abort_job(self, job_id):
        return self.jobs_manager.abort_job(job_id)

    def is_field_displayable(self, field):
        if self.displayed_fields and field not in self.displayed_fields:
            return False
        return field not in self.ignored_fields

    def init_session(self, endpoint, data):
        pass

    def finalize_session(self, endpoint, data, output):
        pass

    def get_library(self, request_data, library_id=None):
        if not request_data.username:
            return self.library_broker.get(library_id)
        lf = partial(self.user_manager.allowed_library_names, request_data.username)
        allowed_libraries = self.library_broker.allowed_libraries(lf)
        if not allowed_libraries:
            raise HTTPForbidden(f'The user {request_data.username} is not allowed to access any libraries on this server')
        library_id = library_id or next(iter(allowed_libraries))
        if library_id in allowed_libraries:
            return self.library_broker.get(library_id)
        raise HTTPForbidden(f'The user {request_data.username} is not allowed to access the library {library_id}')

    def library_info(self, request_data):
        if not request_data.username:
            return self.library_broker.library_map, self.library_broker.default_library
        lf = partial(self.user_manager.allowed_library_names, request_data.username)
        allowed_libraries = self.library_broker.allowed_libraries(lf)
        if not allowed_libraries:
            raise HTTPForbidden(f'The user {request_data.username} is not allowed to access any libraries on this server')
        return dict(allowed_libraries), next(iter(allowed_libraries))

    def restriction_for(self, request_data, db):
        return self.user_manager.library_restriction(request_data.username, path_for_db(db))

    def has_id(self, request_data, db, book_id):
        restriction = self.restriction_for(request_data, db)
        if restriction:
            try:
                return book_id in db.search('', restriction=restriction)
            except ParseException:
                return False
        return db.has_id(book_id)

    def get_allowed_book_ids_from_restriction(self, request_data, db):
        restriction = self.restriction_for(request_data, db)
        return frozenset(db.search('', restriction=restriction)) if restriction else None

    def allowed_book_ids(self, request_data, db):
        try:
            ans = self.get_allowed_book_ids_from_restriction(request_data, db)
        except ParseException:
            return frozenset()
        if ans is None:
            ans = db.all_book_ids()
        return ans

    def check_for_write_access(self, request_data):
        if not request_data.username:
            if request_data.is_trusted_ip:
                return
            raise HTTPForbidden('Anonymous users are not allowed to make changes')
        if self.user_manager.is_readonly(request_data.username):
            raise HTTPForbidden(f'The user {request_data.username} does not have permission to make changes')

    def get_effective_book_ids(self, db, request_data, vl, report_parse_errors=False):
        try:
            return db.books_in_virtual_library(vl, self.restriction_for(request_data, db))
        except ParseException:
            if report_parse_errors:
                raise
            return frozenset()

    def get_categories(self, request_data, db, sort='name', first_letter_sort=True,
                       vl='', report_parse_errors=False):
        restrict_to_ids = self.get_effective_book_ids(db, request_data, vl,
                                          report_parse_errors=report_parse_errors)
        key = restrict_to_ids, sort, first_letter_sort
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

    def get_tag_browser(self, request_data, db, opts, render, vl=''):
        restrict_to_ids = self.get_effective_book_ids(db, request_data, vl)
        key = restrict_to_ids, opts
        with self.lock:
            cache = self.library_broker.category_caches[db.server_library_id]
            old = cache.pop(key, None)
            if old is None or old[0] <= db.last_modified():
                categories = db.get_categories(book_ids=restrict_to_ids, sort=opts.sort_by, first_letter_sort=opts.collapse_model == 'first letter')
                data = json.dumps(render(db, categories), ensure_ascii=False)
                if isinstance(data, str):
                    data = data.encode('utf-8')
                cache[key] = old = (utcnow(), data)
                if len(cache) > self.CATEGORY_CACHE_SIZE:
                    cache.popitem(last=False)
            else:
                cache[key] = old
            return old[1]

    def search(self, request_data, db, query, vl='', report_restriction_errors=False):
        try:
            restrict_to_ids = self.get_effective_book_ids(db, request_data, vl, report_parse_errors=report_restriction_errors)
        except ParseException:
            try:
                self.get_allowed_book_ids_from_restriction(request_data, db)
            except ParseException as e:
                return frozenset(), e
            return frozenset(), None
        query = query or ''
        key = query, restrict_to_ids
        with self.lock:
            cache = self.library_broker.search_caches[db.server_library_id]
            old = cache.pop(key, None)
            if old is None or old[0] < db.clear_search_cache_count:
                matches = db.search(query, book_ids=restrict_to_ids)
                cache[key] = old = (db.clear_search_cache_count, matches)
                if len(cache) > self.SEARCH_CACHE_SIZE:
                    cache.popitem(last=False)
            else:
                cache[key] = old
            if report_restriction_errors:
                return old[1], None
            return old[1]


SRV_MODULES = ('ajax', 'books', 'cdb', 'code', 'content', 'legacy', 'opds', 'users_api', 'convert')


class Handler:

    def __init__(self, libraries, opts, testing=False, notify_changes=None):
        ctx = Context(libraries, opts, testing=testing, notify_changes=notify_changes)
        self.auth_controller = None
        if opts.auth:
            has_ssl = opts.ssl_certfile is not None and opts.ssl_keyfile is not None
            prefer_basic_auth = {'auto':has_ssl, 'basic':True}.get(opts.auth_mode, False)
            self.auth_controller = AuthController(
                user_credentials=ctx.user_manager, prefer_basic_auth=prefer_basic_auth, ban_time_in_minutes=opts.ban_for, ban_after=opts.ban_after)
        self.router = Router(ctx=ctx, url_prefix=opts.url_prefix, auth_controller=self.auth_controller)
        for module in SRV_MODULES:
            module = import_module('calibre.srv.' + module)
            self.router.load_routes(itervalues(vars(module)))
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

    @property
    def ctx(self):
        return self.router.ctx
