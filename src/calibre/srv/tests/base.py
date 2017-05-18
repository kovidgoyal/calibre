#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, time, httplib, shutil, gc, tempfile, atexit, os
from io import BytesIO
from functools import partial
from threading import Thread

from calibre.srv.utils import ServerLog

rmtree = partial(shutil.rmtree, ignore_errors=True)


class BaseTest(unittest.TestCase):

    longMessage = True
    maxDiff = None

    ae = unittest.TestCase.assertEqual


class LibraryBaseTest(BaseTest):

    def setUp(self):
        from calibre.utils.recycle_bin import nuke_recycle
        nuke_recycle()
        self.library_path = self.mkdtemp()
        self.create_db(self.library_path)

    def tearDown(self):
        from calibre.utils.recycle_bin import restore_recyle
        restore_recyle()
        gc.collect(), gc.collect()
        try:
            shutil.rmtree(self.library_path)
        except EnvironmentError:
            # Try again in case something transient has a file lock on windows
            gc.collect(), gc.collect()
            time.sleep(2)
            shutil.rmtree(self.library_path)

    def mkdtemp(self):
        ans = tempfile.mkdtemp(prefix='db_test_')
        atexit.register(rmtree, ans)
        return ans

    def create_db(self, library_path):
        from calibre.db.legacy import create_backend
        from calibre.db.cache import Cache
        d = os.path.dirname
        src = os.path.join(d(d(d(os.path.abspath(__file__)))), 'db', 'tests', 'metadata.db')
        dest = os.path.join(library_path, 'metadata.db')
        shutil.copy2(src, dest)
        db = Cache(create_backend(library_path))
        db.init()
        db.set_cover({1:I('lt.png', data=True), 2:I('polish.png', data=True)})
        db.add_format(1, 'FMT1', BytesIO(b'book1fmt1'), run_hooks=False)
        db.add_format(1, 'EPUB', open(P('quick_start/eng.epub'), 'rb'), run_hooks=False)
        db.add_format(1, 'FMT2', BytesIO(b'book1fmt2'), run_hooks=False)
        db.add_format(2, 'FMT1', BytesIO(b'book2fmt1'), run_hooks=False)
        db.backend.conn.close()
        return dest

    def create_server(self, *args, **kwargs):
        args = (self.library_path ,) + args
        return LibraryServer(*args, **kwargs)


class TestServer(Thread):

    daemon = True

    def __init__(self, handler, plugins=(), specialize=lambda srv:None, **kwargs):
        Thread.__init__(self, name='ServerMain')
        from calibre.srv.opts import Options
        from calibre.srv.loop import ServerLoop
        from calibre.srv.http_response import create_http_handler
        self.setup_defaults(kwargs)
        self.loop = ServerLoop(
            create_http_handler(handler),
            opts=Options(**kwargs),
            plugins=plugins,
            log=ServerLog(level=ServerLog.WARN),
        )
        self.log = self.loop.log
        self.silence_log = self.log
        specialize(self)

    def setup_defaults(self, kwargs):
        kwargs['shutdown_timeout'] = kwargs.get('shutdown_timeout', 0.1)
        kwargs['listen_on'] = kwargs.get('listen_on', 'localhost')
        kwargs['port'] = kwargs.get('port', 0)
        kwargs['userdb'] = kwargs.get('userdb', ':memory:')

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
        self.join(self.loop.opts.shutdown_timeout)

    def connect(self, timeout=None):
        if timeout is None:
            timeout = self.loop.opts.timeout
        return httplib.HTTPConnection(self.address[0], self.address[1], strict=True, timeout=timeout)

    def change_handler(self, handler):
        from calibre.srv.http_response import create_http_handler
        self.loop.handler = create_http_handler(handler)


class LibraryServer(TestServer):

    def __init__(self, library_path, libraries=(), plugins=(), specialize=lambda x:None, **kwargs):
        Thread.__init__(self, name='ServerMain')
        from calibre.srv.opts import Options
        from calibre.srv.loop import ServerLoop
        from calibre.srv.handler import Handler
        from calibre.srv.http_response import create_http_handler
        self.setup_defaults(kwargs)
        opts = Options(**kwargs)
        self.libraries = libraries or (library_path,)
        self.handler = Handler(self.libraries, opts, testing=True)
        self.loop = ServerLoop(
            create_http_handler(self.handler.dispatch),
            opts=opts,
            plugins=plugins,
            log=ServerLog(level=ServerLog.WARN),
        )
        self.handler.set_log(self.loop.log)
        specialize(self)

    def __exit__(self, *args):
        self.loop.stop()
        self.handler.close()
        self.join(self.loop.opts.shutdown_timeout)
