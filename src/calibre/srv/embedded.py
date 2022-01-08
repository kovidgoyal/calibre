#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import errno
import json
import os
from contextlib import suppress
from threading import Thread

from calibre import as_unicode
from calibre.constants import cache_dir, config_dir, is_running_from_develop
from calibre.srv.bonjour import BonJour
from calibre.srv.handler import Handler
from calibre.srv.http_response import create_http_handler
from calibre.srv.loop import ServerLoop
from calibre.srv.opts import server_config
from calibre.srv.utils import RotatingLog


def log_paths():
    return os.path.join(cache_dir(), 'server-log.txt'), os.path.join(
        cache_dir(), 'server-access-log.txt'
    )


def read_json(path):
    try:
        with lopen(path, 'rb') as f:
            raw = f.read()
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
        return
    with suppress(json.JSONDecodeError):
        return json.loads(raw)


def custom_list_template():
    return read_json(custom_list_template.path)


def search_the_net_urls():
    return read_json(search_the_net_urls.path)


custom_list_template.path = os.path.join(config_dir, 'server-custom-list-template.json')
search_the_net_urls.path = os.path.join(config_dir, 'server-search-the-net.json')


class Server:

    loop = current_thread = exception = None
    state_callback = start_failure_callback = None

    def __init__(self, library_broker, notify_changes):
        opts = server_config()
        lp, lap = log_paths()
        try:
            os.makedirs(cache_dir())
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        log_size = opts.max_log_size * 1024 * 1024
        log = RotatingLog(lp, max_size=log_size)
        access_log = RotatingLog(lap, max_size=log_size)
        self.handler = Handler(library_broker, opts, notify_changes=notify_changes)
        plugins = self.plugins = []
        if opts.use_bonjour:
            plugins.append(BonJour(wait_for_stop=max(0, opts.shutdown_timeout - 0.2)))
        self.opts = opts
        self.log, self.access_log = log, access_log
        self.handler.set_log(self.log)
        self.handler.router.ctx.custom_list_template = custom_list_template()
        self.handler.router.ctx.search_the_net_urls = search_the_net_urls()

    @property
    def ctx(self):
        return self.handler.router.ctx

    @property
    def user_manager(self):
        return self.handler.router.ctx.user_manager

    def start(self):
        if self.current_thread is None:
            try:
                self.loop = ServerLoop(
                    create_http_handler(self.handler.dispatch),
                    opts=self.opts,
                    log=self.log,
                    access_log=self.access_log,
                    plugins=self.plugins
                )
                self.loop.initialize_socket()
            except Exception as e:
                self.loop = None
                self.exception = e
                if self.start_failure_callback is not None:
                    try:
                        self.start_failure_callback(as_unicode(e))
                    except Exception:
                        pass
                return
            self.handler.set_jobs_manager(self.loop.jobs_manager)
            self.current_thread = t = Thread(
                name='EmbeddedServer', target=self.serve_forever
            )
            t.daemon = True
            t.start()

    def serve_forever(self):
        self.exception = None
        from calibre.srv.content import reset_caches
        try:
            if is_running_from_develop:
                from calibre.utils.rapydscript import compile_srv
                compile_srv()
        except BaseException as e:
            self.exception = e
            if self.start_failure_callback is not None:
                try:
                    self.start_failure_callback(as_unicode(e))
                except Exception:
                    pass
            return
        if self.state_callback is not None:
            try:
                self.state_callback(True)
            except Exception:
                pass
        reset_caches()  # we reset the cache as the server tdir has changed
        try:
            self.loop.serve_forever()
        except BaseException as e:
            self.exception = e
        if self.state_callback is not None:
            try:
                self.state_callback(False)
            except Exception:
                pass

    def stop(self):
        if self.loop is not None:
            self.loop.stop()
            self.loop = None

    def exit(self):
        if self.current_thread is not None:
            self.stop()
            self.current_thread.join()
            self.current_thread = None

    @property
    def is_running(self):
        return self.current_thread is not None and self.current_thread.is_alive()
