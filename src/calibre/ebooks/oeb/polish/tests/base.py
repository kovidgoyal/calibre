#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, unittest, shutil

from calibre import CurrentDir
from calibre.ptempfile import TemporaryDirectory
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import DevNull
import calibre.ebooks.oeb.polish.container as pc
from polyglot.builtins import iteritems


def get_cache():
    from calibre.constants import cache_dir
    cache = os.path.join(cache_dir(), 'polish-test')
    if not os.path.exists(cache):
        os.mkdir(cache)
    return cache


def needs_recompile(obj, srcs):
    if isinstance(srcs, str):
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


def add_resources(raw, rmap):
    for placeholder, path in iteritems(rmap):
        fname = os.path.basename(path)
        shutil.copy2(path, '.')
        raw = raw.replace(placeholder, fname)
    return raw


def get_simple_book(fmt='epub'):
    cache = get_cache()
    ans = os.path.join(cache, 'simple.'+fmt)
    src = os.path.join(os.path.dirname(__file__), 'simple.html')
    if needs_recompile(ans, src):
        with TemporaryDirectory('bpt') as tdir:
            with CurrentDir(tdir):
                with lopen(src, 'rb') as sf:
                    raw = sf.read().decode('utf-8')
                raw = add_resources(raw, {
                    'LMONOI': P('fonts/liberation/LiberationMono-Italic.ttf'),
                    'LMONOR': P('fonts/liberation/LiberationMono-Regular.ttf'),
                    'IMAGE1': I('marked.png'),
                    'IMAGE2': I('textures/light_wood.png'),
                })
                shutil.copy2(I('lt.png'), '.')
                x = 'index.html'
                with lopen(x, 'wb') as f:
                    f.write(raw.encode('utf-8'))
                build_book(x, ans, args=[
                    '--level1-toc=//h:h2', '--language=en', '--authors=Kovid Goyal', '--cover=lt.png'])
    return ans


def get_split_book(fmt='epub'):
    cache = get_cache()
    ans = os.path.join(cache, 'split.'+fmt)
    src = os.path.join(os.path.dirname(__file__), 'split.html')
    if needs_recompile(ans, src):
        x = src.replace('split.html', 'index.html')
        raw = lopen(src, 'rb').read().decode('utf-8')
        try:
            with lopen(x, 'wb') as f:
                f.write(raw.encode('utf-8'))
            build_book(x, ans, args=['--level1-toc=//h:h2', '--language=en', '--authors=Kovid Goyal',
                                        '--cover=' + I('lt.png')])
        finally:
            os.remove(x)
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

    def check_links(self, container):
        for name in container.name_path_map:
            for link in container.iterlinks(name, get_line_numbers=False):
                dest = container.href_to_name(link, name)
                if dest:
                    self.assertTrue(container.exists(dest), f'The link {link} in {name} does not exist')
