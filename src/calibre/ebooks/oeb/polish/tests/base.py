#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import shutil
import unittest

import calibre.ebooks.oeb.polish.container as pc
from calibre import CurrentDir
from calibre.ptempfile import PersistentTemporaryDirectory, TemporaryDirectory
from calibre.utils.logging import DevNull
from calibre.utils.resources import get_image_path as I
from calibre.utils.resources import get_path as P


def get_cache():
    from calibre.constants import cache_dir
    cache = os.path.join(cache_dir(), 'polish-test')
    if not os.path.exists(cache):
        os.mkdir(cache)
    return cache


once_per_run = set()


def needs_recompile(obj, srcs):
    is_ci = os.environ.get('CI', '').lower() == 'true'
    if is_ci and obj not in once_per_run:
        once_per_run.add(obj)
        return True
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
    main(['ebook-convert', src, dest, '-vv'] + list(args))


def add_resources(raw, rmap):
    for placeholder, path in rmap.items():
        fname = os.path.basename(path)
        shutil.copy2(path, '.')
        raw = raw.replace(placeholder, fname)
    return raw


def setup_simple_book(src):
    with open(src, 'rb') as sf:
        raw = sf.read().decode('utf-8')
    raw = add_resources(raw, {
        'LMONOI': P('fonts/liberation/LiberationMono-Italic.ttf'),
        'LMONOR': P('fonts/liberation/LiberationMono-Regular.ttf'),
        'IMAGE1': I('marked.png'),
        'IMAGE2': I('textures/light_wood.png'),
    })
    shutil.copy2(I('lt.png'), '.')
    x = 'index.html'
    with open(x, 'wb') as f:
        f.write(raw.encode('utf-8'))
    return x


def get_simple_book(fmt='epub'):
    cache = get_cache()
    ans = os.path.join(cache, 'simple.'+fmt)
    src = os.path.join(os.path.dirname(__file__), 'simple.html')
    if needs_recompile(ans, src):
        with TemporaryDirectory('bpt') as tdir, CurrentDir(tdir):
            x = setup_simple_book(src)
            build_book(x, ans, args=[
                '--level1-toc=//h:h2', '--language=en', '--authors=Kovid Goyal', '--cover=lt.png'])
    return ans


def get_split_book(fmt='epub'):
    cache = get_cache()
    ans = os.path.join(cache, 'split.'+fmt)
    src = os.path.join(os.path.dirname(__file__), 'split.html')
    if needs_recompile(ans, src):
        x = src.replace('split.html', 'index.html')
        with open(src, 'rb') as sf:
            raw = sf.read().decode('utf-8')
        try:
            with open(x, 'wb') as f:
                f.write(raw.encode('utf-8'))
            build_book(x, ans, args=['--level1-toc=//h:h2', '--language=en', '--authors=Kovid Goyal',
                                        '--cover=' + I('lt.png')])
        finally:
            os.remove(x)
    return ans


def get_book_for_kepubify(has_cover=True, epub_version='3'):
    cache = get_cache()
    ans = os.path.join(cache, f'kepubify-{has_cover}-{epub_version}.epub')
    src = os.path.join(os.path.dirname(__file__), 'simple.html')
    if needs_recompile(ans, src):
        with TemporaryDirectory('bpt') as tdir, CurrentDir(tdir):
            index_html = setup_simple_book(src)
            args = ['--level1-toc=//h:h2', '--language=en', '--authors=Kovid Goyal', f'--epub-version={epub_version}']
            if has_cover:
                args.append('--cover=lt.png')
            else:
                args.append('--no-default-epub-cover')
            build_book(index_html, ans, args=args)
    c = pc.get_container(ans)
    with c.open('page_styles.css', 'r+') as f:
        css = f.read()
        css += '\n\ndiv { widows: 13; orphans: 12; color: red; }'
        f.seek(0), f.truncate(), f.write(css)
    c.commit()

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
