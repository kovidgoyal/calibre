#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, shutil, time, httplib
from functools import partial
from threading import Thread

rmtree = partial(shutil.rmtree, ignore_errors=True)

class BaseTest(unittest.TestCase):

    longMessage = True
    maxDiff = None

    ae = unittest.TestCase.assertEqual


class TestServer(Thread):

    daemon = True

    def __init__(self, handler):
        Thread.__init__(self, name='ServerMain')
        from calibre.srv.opts import Options
        from calibre.srv.loop import ServerLoop
        from calibre.srv.http import create_http_handler
        from calibre.utils.logging import ThreadSafeLog
        self.loop = ServerLoop(
            opts=Options(shutdown_timeout=0.1),
            bind_address=('localhost', 0), http_handler=create_http_handler(handler),
            log=ThreadSafeLog(level=ThreadSafeLog.WARN),
        )

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

    def connect(self):
        return httplib.HTTPConnection(self.address[0], self.address[1], strict=True, timeout=0.1)
