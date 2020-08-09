#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Eli Schwartz <eschwartz@archlinux.org>

import os
import shutil
import tarfile
import time
from io import BytesIO

from setup import Command, download_securely

is_ci = os.environ.get('CI', '').lower() == 'true'


class ReVendor(Command):

    # NAME = TAR_NAME = VERSION = DOWNLOAD_URL = ''
    CAN_USE_SYSTEM_VERSION = True

    def add_options(self, parser):
        parser.add_option('--path-to-%s' % self.NAME, help='Path to the extracted %s source' % self.TAR_NAME)
        parser.add_option('--%s-url' % self.NAME, default=self.DOWNLOAD_URL,
                help='URL to %s source archive in tar.gz format' % self.TAR_NAME)
        if self.CAN_USE_SYSTEM_VERSION:
            parser.add_option('--system-%s' % self.NAME, default=False, action='store_true',
                    help='Treat %s as system copy and symlink instead of copy' % self.TAR_NAME)

    def download_vendor_release(self, tdir, url):
        self.info('Downloading %s:' % self.TAR_NAME, url)
        try:
            raw = download_securely(url)
        except Exception:
            if not is_ci:
                raise
            self.info('Download failed, sleeping and retrying...')
            time.sleep(2)
            raw = download_securely(url)
        with tarfile.open(fileobj=BytesIO(raw)) as tf:
            tf.extractall(tdir)
            if len(os.listdir(tdir)) == 1:
                return self.j(tdir, os.listdir(tdir)[0])
            else:
                return tdir

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
