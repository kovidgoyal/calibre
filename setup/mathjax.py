#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil
from io import BytesIO
from zipfile import ZipFile, ZIP_STORED, ZipInfo
from hashlib import sha1
from tempfile import mkdtemp, SpooledTemporaryFile
is_ci = os.environ.get('CI', '').lower() == 'true'


from setup import Command, download_securely


class MathJax(Command):

    description = 'Create the MathJax bundle'
    MATH_JAX_URL = 'https://github.com/kovidgoyal/MathJax/archive/master.zip'
    FONT_FAMILY = 'TeX'

    def add_options(self, parser):
        parser.add_option('--path-to-mathjax', help='Path to the MathJax source code')
        parser.add_option('--mathjax-url', default=self.MATH_JAX_URL, help='URL to MathJax source archive in zip format')

    def download_mathjax_release(self, tdir, url):
        self.info('Downloading MathJax:', url)
        raw = download_securely(url)
        with ZipFile(BytesIO(raw)) as zf:
            zf.extractall(tdir)
            return os.path.join(tdir, 'MathJax-master')

    def add_file(self, zf, path, name):
        with open(path, 'rb') as f:
            raw = f.read()
        self.h.update(raw)
        zi = ZipInfo(name)
        zi.external_attr = 0o444 << 16L
        zf.writestr(zi, raw)

    def add_tree(self, zf, base, prefix, ignore=lambda n:False):
        for dirpath, dirnames, filenames in os.walk(base):
            for fname in filenames:
                f = os.path.join(dirpath, fname)
                name = prefix + '/' + os.path.relpath(f, base).replace(os.sep, '/')
                if not ignore(name):
                    self.add_file(zf, f, name)

    def ignore_fonts(self, name):
        return '/fonts/' in name and self.FONT_FAMILY not in name

    def run(self, opts):
        from lzma.xz import compress
        self.h = sha1()
        tdir = mkdtemp('calibre-mathjax-build')
        try:
            src = opts.path_to_mathjax or self.download_mathjax_release(tdir, opts.mathjax_url)
            self.info('Compressing MathJax...')
            t = SpooledTemporaryFile()
            with ZipFile(t, 'w', ZIP_STORED) as zf:
                self.add_file(zf, self.j(src, 'unpacked', 'MathJax.js'), 'MathJax.js')
                self.add_tree(zf, self.j(src, 'fonts', 'HTML-CSS', self.FONT_FAMILY, 'woff'), 'fonts/HTML-CSS/%s/woff' % self.FONT_FAMILY)
                for d in 'extensions jax/element jax/input jax/output/CommonHTML'.split():
                    self.add_tree(zf, self.j(src, 'unpacked', *d.split('/')), d)

                zf.comment = self.h.hexdigest()
            t.seek(0)
            with open(self.j(self.RESOURCES, 'content-server', 'mathjax.zip.xz'), 'wb') as f:
                compress(t, f, level=1 if is_ci else 9)
            with open(self.j(self.RESOURCES, 'content-server', 'mathjax.version'), 'wb') as f:
                f.write(zf.comment)
        finally:
            shutil.rmtree(tdir)
