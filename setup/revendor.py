#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, json
from io import BytesIO
import tarfile
from hashlib import sha1
from tempfile import mkdtemp


from setup import Command, download_securely


class ReVendor(Command):

    # NAME = TAR_NAME = VERSION = DOWNLOAD_URL = ''

    def add_options(self, parser):
        parser.add_option('--path-to-%s' % self.NAME, help='Path to the extracted %s source' % self.TAR_NAME)
        parser.add_option('--%s-url' % self.NAME, default=self.DOWNLOAD_URL,
                help='URL to %s source archive in zip format' % self.TAR_NAME)
        parser.add_option('--system-%s' % self.NAME, default=False, action='store_true',
                help='Treat %s as system copy and symlink instead of copy' % self.TAR_NAME)

    def download_vendor_release(self, tdir, url):
        self.info('Downloading %s:' % self.TAR_NAME, url)
        raw = download_securely(url)
        with tarfile.open(fileobj=BytesIO(raw)) as tf:
            tf.extractall(tdir)
            return os.path.join(tdir, '%s-%s' % (self.TAR_NAME, self.VERSION))

    def add_file_pre(self, name, raw):
        pass

    def add_file(self, path, name):
        with open(path, 'rb') as f:
            raw = f.read()
        self.add_file_pre(name, raw)
        dest = self.j(self.vendored_dir, *name.split('/'))
        base = os.path.dirname(dest)
        if not os.path.exists(base):
            os.makedirs(base)
        if self.use_symlinks:
            os.symlink(path, dest)
        else:
            with open(dest, 'wb') as f:
                f.write(raw)

    def add_tree(self, base, prefix, ignore=lambda n:False):
        for dirpath, dirnames, filenames in os.walk(base):
            for fname in filenames:
                f = os.path.join(dirpath, fname)
                name = prefix + '/' + os.path.relpath(f, base).replace(os.sep, '/')
                if not ignore(name):
                    self.add_file(f, name)


    @property
    def vendored_dir(self):
        return self.j(self.RESOURCES, self.NAME)

    def clean(self):
        if os.path.exists(self.vendored_dir):
            shutil.rmtree(self.vendored_dir)


class MathJax(ReVendor):

    description = 'Create the MathJax bundle'
    NAME = 'mathjax'
    TAR_NAME = 'MathJax'
    VERSION = '2.7.5'
    DOWNLOAD_URL = 'https://github.com/mathjax/MathJax/archive/%s.tar.gz' % VERSION
    FONT_FAMILY = 'TeX'

    def add_file_pre(self, name, raw):
        self.h.update(raw)
        self.mathjax_files[name] = len(raw)

    def already_present(self):
        manifest = self.j(self.vendored_dir, 'manifest.json')
        if os.path.exists(manifest):
            with open(manifest, 'rb') as f:
                return json.load(f).get('version') == self.VERSION
        return False

    def run(self, opts):
        if not opts.system_mathjax and self.already_present():
            self.info('MathJax already present in the resources directory, not downloading')
            return
        self.use_symlinks = opts.system_mathjax
        self.h = sha1()
        self.mathjax_files = {}
        self.clean()
        os.mkdir(self.vendored_dir)
        tdir = mkdtemp('calibre-mathjax-build')
        try:
            src = opts.path_to_mathjax or self.download_vendor_release(tdir, opts.mathjax_url)
            self.info('Adding MathJax...')
            unpacked = 'unpacked' if self.e(self.j(src, 'unpacked')) else ''
            self.add_file(self.j(src, unpacked, 'MathJax.js'), 'MathJax.js')
            self.add_tree(
                self.j(src, 'fonts', 'HTML-CSS', self.FONT_FAMILY, 'woff'),
                'fonts/HTML-CSS/%s/woff' % self.FONT_FAMILY,
                lambda x: not x.endswith('.woff'))
            for d in 'extensions jax/element jax/input jax/output/CommonHTML'.split():
                self.add_tree(self.j(src, unpacked, *d.split('/')), d)
            etag = self.h.hexdigest()
            with open(self.j(self.RESOURCES, 'mathjax', 'manifest.json'), 'wb') as f:
                f.write(json.dumps({'etag': etag, 'files': self.mathjax_files, 'version': self.VERSION}, indent=2).encode('utf-8'))
        finally:
            shutil.rmtree(tdir)
