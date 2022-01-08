#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, json
from hashlib import sha1


from setup.revendor import ReVendor


class MathJax(ReVendor):

    description = 'Create the MathJax bundle'
    NAME = 'mathjax'
    TAR_NAME = 'MathJax'
    VERSION = '3.1.4'
    DOWNLOAD_URL = 'https://github.com/mathjax/MathJax/archive/%s.tar.gz' % VERSION

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
            if os.path.isdir(os.path.join(src, 'es5')):
                src = os.path.join(src, 'es5')
            self.info('Adding MathJax...')
            for x in 'core loader startup input/tex-full input/asciimath input/mml input/mml/entities output/chtml'.split():
                self.add_file(self.j(src, x + '.js'), x + '.js')
            self.add_tree(
                self.j(src, 'output', 'chtml'), 'output/chtml')
            etag = self.h.hexdigest()
            with open(self.j(self.RESOURCES, 'mathjax', 'manifest.json'), 'wb') as f:
                f.write(json.dumps({'etag': etag, 'files': self.mathjax_files, 'version': self.VERSION}, indent=2).encode('utf-8'))
