#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, json
from io import BytesIO
from zipfile import ZipFile
from hashlib import sha1
from tempfile import mkdtemp


from setup import Command, download_securely


class MathJax(Command):

    description = 'Create the MathJax bundle'
    MATH_JAX_VERSION = '2.7.5'
    MATH_JAX_URL = 'https://github.com/mathjax/MathJax/archive/%s.zip' % MATH_JAX_VERSION
    FONT_FAMILY = 'TeX'

    def add_options(self, parser):
        parser.add_option('--path-to-mathjax', help='Path to the MathJax source code')
        parser.add_option('--mathjax-url', default=self.MATH_JAX_URL, help='URL to MathJax source archive in zip format')

    def download_mathjax_release(self, tdir, url):
        self.info('Downloading MathJax:', url)
        raw = download_securely(url)
        with ZipFile(BytesIO(raw)) as zf:
            zf.extractall(tdir)
            return os.path.join(tdir, 'MathJax-' + self.MATH_JAX_VERSION)

    def add_file(self, path, name):
        with open(path, 'rb') as f:
            raw = f.read()
        self.h.update(raw)
        self.mathjax_files[name] = len(raw)
        dest = self.j(self.mathjax_dir, *name.split('/'))
        base = os.path.dirname(dest)
        if not os.path.exists(base):
            os.makedirs(base)
        with open(dest, 'wb') as f:
            f.write(raw)

    def add_tree(self, base, prefix):
        for dirpath, dirnames, filenames in os.walk(base):
            for fname in filenames:
                f = os.path.join(dirpath, fname)
                name = prefix + '/' + os.path.relpath(f, base).replace(os.sep, '/')
                self.add_file(f, name)

    def clean(self):
        self.mathjax_dir = self.j(self.RESOURCES, 'mathjax')
        if os.path.exists(self.mathjax_dir):
            shutil.rmtree(self.mathjax_dir)

    def run(self, opts):
        self.h = sha1()
        self.mathjax_files = {}
        self.clean()
        os.mkdir(self.mathjax_dir)
        tdir = mkdtemp('calibre-mathjax-build')
        try:
            src = opts.path_to_mathjax or self.download_mathjax_release(tdir, opts.mathjax_url)
            self.info('Adding MathJax...')
            self.add_file(self.j(src, 'unpacked', 'MathJax.js'), 'MathJax.js')
            self.add_tree(self.j(src, 'fonts', 'HTML-CSS', self.FONT_FAMILY, 'woff'), 'fonts/HTML-CSS/%s/woff' % self.FONT_FAMILY)
            for d in 'extensions jax/element jax/input jax/output/CommonHTML'.split():
                self.add_tree(self.j(src, 'unpacked', *d.split('/')), d)
            etag = self.h.hexdigest()
            with open(self.j(self.RESOURCES, 'mathjax', 'manifest.json'), 'wb') as f:
                f.write(json.dumps({'etag': etag, 'files': self.mathjax_files}, indent=2).encode('utf-8'))
        finally:
            shutil.rmtree(tdir)
