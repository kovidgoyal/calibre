#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import os
from threading import Thread

from calibre import as_unicode
from calibre.constants import cache_dir
from calibre.srv.bonjour import BonJour
from calibre.srv.handler import Handler
from calibre.srv.http_response import create_http_handler
from calibre.srv.loop import ServerLoop
from calibre.srv.utils import RotatingLog
from calibre.srv.opts import server_config


def log_paths():
    return os.path.join(cache_dir(), 'server-log.txt'), os.path.join(
        cache_dir(), 'server-access-log.txt'
    )


class Server(object):

    loop = current_thread = exception = None
    state_callback = start_failure_callback = None

    def __init__(self, library_broker):
        opts = server_config()
        lp, lap = log_paths()
        log_size = opts.max_log_size * 1024 * 1024
        log = RotatingLog(lp, max_size=log_size)
        access_log = RotatingLog(lap, max_size=log_size)
        self.handler = Handler(library_broker, opts)
        plugins = self.plugins = []
        if opts.use_bonjour:
            plugins.append(BonJour())
        self.opts = opts
        self.log, self.access_log = log, access_log
        self.handler.set_log(self.log)
        _df = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        if _df and os.path.exists(_df):
            from calibre.utils.rapydscript import compile_srv
            compile_srv()

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
        if self.state_callback is not None:
            try:
                self.state_callback(True)
            except Exception:
                pass
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
