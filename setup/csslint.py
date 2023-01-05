#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
import subprocess

from setup import Command


class CSSLint(Command):
    description = 'Update the bundled copy of stylelint'
    NAME = 'stylelint-bundle.min.js'
    DOWNLOAD_URL = 'https://github.com/openstyles/stylelint-bundle.git'

    @property
    def vendored_file(self):
        return os.path.join(self.RESOURCES, self.NAME)

    def run(self, opts):
        self.clean()

        with self.temp_dir() as dl_src:
            subprocess.check_call(['git', 'clone', '--depth=1', self.DOWNLOAD_URL], cwd=dl_src)
            src = self.j(dl_src, 'stylelint-bundle')
            subprocess.check_call(['npm', 'install'], cwd=src)
            subprocess.check_call(['npm', 'run', 'build'], cwd=src)
            shutil.copyfile(self.j(src, 'dist', self.NAME), self.vendored_file)

    def clean(self):
        if os.path.exists(self.vendored_file):
            os.remove(self.vendored_file)
