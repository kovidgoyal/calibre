#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, time, httplib
from threading import Thread

from calibre.srv.utils import ServerLog

class BaseTest(unittest.TestCase):

    longMessage = True
    maxDiff = None

    ae = unittest.TestCase.assertEqual

class TestServer(Thread):

    daemon = True

    def __init__(self, handler, plugins=(), **kwargs):
        Thread.__init__(self, name='ServerMain')
        from calibre.srv.opts import Options
        from calibre.srv.loop import ServerLoop
        from calibre.srv.http_response import create_http_handler
        kwargs['shutdown_timeout'] = kwargs.get('shutdown_timeout', 0.1)
        kwargs['listen_on'] = kwargs.get('listen_on', 'localhost')
        kwargs['port'] = kwargs.get('port', 0)
        self.loop = ServerLoop(
            create_http_handler(handler),
            opts=Options(**kwargs),
            plugins=plugins,
            log=ServerLog(level=ServerLog.WARN),
        )
        self.log = self.loop.log

    def run(self):
        try:
            self.loop.serve_forever()
        except KeyboardInterrupt:
            pass

    def __enter__(self):
        self.start()
        while not self.loop.ready and self.is_alive():
            time.sleep(0.01)
        self.address = self.loop.bound_address[:2]
        return self

    def __exit__(self, *args):
        self.loop.stop()

    def connect(self, timeout=None):
        if timeout is None:
            timeout = self.loop.opts.timeout
        return httplib.HTTPConnection(self.address[0], self.address[1], strict=True, timeout=timeout)

    def change_handler(self, handler):
        from calibre.srv.http_response import create_http_handler
        self.loop.handler = create_http_handler(handler)
