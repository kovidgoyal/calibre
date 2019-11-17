#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, json
from io import BytesIO
from hashlib import sha1


from setup.revendor import ReVendor


class MathJax(ReVendor):

    description = 'Create the MathJax bundle'
    NAME = 'mathjax'
    TAR_NAME = 'MathJax'
    VERSION = '2.7.6'
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
        with self.temp_dir(suffix='-calibre-mathjax-build') as tdir:
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
