#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, unittest, shutil

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import DevNull
import calibre.ebooks.oeb.polish.container as pc

def get_cache():
    from calibre.constants import cache_dir
    cache = os.path.join(cache_dir(), 'polish-test')
    if not os.path.exists(cache):
        os.mkdir(cache)
    return cache

def needs_recompile(obj, srcs):
    if isinstance(srcs, type('')):
        srcs = [srcs]
    try:
        obj_mtime = os.stat(obj).st_mtime
    except OSError:
        return True
    for src in srcs:
        if os.stat(src).st_mtime > obj_mtime:
            return True
    return False

def build_book(src, dest, args=()):
    from calibre.ebooks.conversion.cli import main
    main(['ebook-convert', src, dest] + list(args))

def get_simple_book(fmt='epub'):
    cache = get_cache()
    ans = os.path.join(cache, 'simple.'+fmt)
    src = os.path.join(os.path.dirname(__file__), 'simple.html')
    if needs_recompile(ans, src):
        x = src.replace('simple.html', 'index.html')
        raw = open(src, 'rb').read().decode('utf-8')
        raw = raw.replace('LMONOI', P('fonts/liberation/LiberationMono-Italic.ttf'))
        raw = raw.replace('LMONO', P('fonts/liberation/LiberationMono-Regular.ttf'))
        raw = raw.replace('IMAGE1', I('marked.png'))
        try:
            with open(x, 'wb') as f:
                f.write(raw.encode('utf-8'))
            build_book(x, ans, args=['--level1-toc=//h:h2', '--language=en', '--authors=Kovid Goyal',
                                        '--cover=' + I('lt.png')])
        finally:
            try:
                os.remove('index.html')
            except:
                pass
    return ans

devnull = DevNull()

class BaseTest(unittest.TestCase):

    longMessage = True
    maxDiff = None

    def setUp(self):
        pc.default_log = devnull
        self.tdir = PersistentTemporaryDirectory(suffix='-polish-test')

    def tearDown(self):
        shutil.rmtree(self.tdir, ignore_errors=True)
        del self.tdir

