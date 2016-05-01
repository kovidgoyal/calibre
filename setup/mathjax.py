#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from urllib import urlretrieve
from zipfile import ZipFile, ZIP_STORED, ZipInfo
from hashlib import sha1

from lzma.xz import compress

from setup import Command

class MathJax(Command):

    description = 'Create the MathJax bundle'
    MATH_JAX_VERSION = '2.6.1'
    MATH_JAX_URL = 'https://github.com/mathjax/MathJax/archive/%s.zip' % MATH_JAX_VERSION
    FONT_FAMILY = 'STIX-Web'

    def add_options(self, parser):
        parser.add_option('--path-to-mathjax', help='Path to the MathJax source code')

    def download_mathjax_release(self):
        from calibre.ptempfile import TemporaryDirectory
        self.info('Downloading MathJax:', self.MATH_JAX_URL)
        filename = urlretrieve(self.MATH_JAX_URL)[0]
        with ZipFile(filename) as zf, TemporaryDirectory() as tdir:
            zf.extractall(tdir)
            for d in os.listdir(tdir):
                q = os.path.join(tdir, d)
                if os.path.isdir(q):
                    return q

    def patch_jax(self, raw):
        self.info('Patching HTML-CSS jax web font loader...')
        nraw = raw.replace(b'dir+"/"+fullname', b'AJAX.fileURL(dir+"/"+fullname)')
        if nraw == raw:
            raise SystemExit('Failed to path the HTML-CSS jax font loading code')
        return nraw

    def add_file(self, zf, path, name):
        with open(path, 'rb') as f:
            raw = f.read()
        if name == 'jax/output/HTML-CSS/jax.js':
            raw = self.patch_jax(raw)
        self.h.update(raw)
        zi = ZipInfo(name)
        zi.external_attr = 0o444 << 16L
        zf.writestr(zi, raw)

    def add_tree(self, zf, base, prefix, ignore=lambda n:False):
        from calibre import walk
        for f in walk(base):
            name = prefix + '/' + os.path.relpath(f, base).replace(os.sep, '/')
            if not ignore(name):
                self.add_file(zf, f, name)

    def ignore_fonts(self, name):
        return '/fonts/' in name and self.FONT_FAMILY not in name

    def run(self, opts):
        self.h = sha1()
        src = opts.path_to_mathjax or self.download_mathjax_release()
        self.info('Compressing MathJax...')
        from calibre.ptempfile import SpooledTemporaryFile
        t = SpooledTemporaryFile()
        with ZipFile(t, 'w', ZIP_STORED) as zf:
            self.add_tree(zf, self.j(src, 'fonts', 'HTML-CSS', self.FONT_FAMILY, 'woff'), 'fonts/HTML-CSS/STIX-Web/woff')
            self.add_tree(zf, self.j(src, 'unpacked', 'extensions'), 'extensions')
            self.add_tree(zf, self.j(src, 'unpacked', 'jax', 'element'), 'jax/element')
            self.add_tree(zf, self.j(src, 'unpacked', 'jax', 'input'), 'jax/input')
            self.add_tree(zf, self.j(src, 'unpacked', 'jax', 'output', 'HTML-CSS'), 'jax/output/HTML-CSS', ignore=self.ignore_fonts)
            self.add_file(zf, self.j(src, 'unpacked', 'MathJax.js'), 'MathJax.js')

            zf.comment = self.h.hexdigest()
        t.seek(0)
        with open(self.j(self.RESOURCES, 'content-server', 'mathjax.zip.xz'), 'wb') as f:
            compress(t, f, level=9)
