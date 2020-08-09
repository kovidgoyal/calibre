#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
import subprocess

from setup import Command


class CSSLint(Command):
    # We cant use the released copy since it has not had a release in years and
    # there are several critical bug fixes we need

    description = 'Update the bundled copy of csslint'
    NAME = 'csslint.js'
    DOWNLOAD_URL = 'https://github.com/CSSLint/csslint.git'

    @property
    def vendored_file(self):
        return os.path.join(self.RESOURCES, self.NAME)

    def run(self, opts):
        self.clean()

        with self.temp_dir() as dl_src:
            subprocess.check_call(['git', 'clone', '--depth=1', self.DOWNLOAD_URL], cwd=dl_src)
            src = self.j(dl_src, 'csslint')
            subprocess.check_call(['npm', 'install'], cwd=src)
            shutil.copyfile(self.j(src, 'dist', self.NAME), self.vendored_file)

    def clean(self):
        if os.path.exists(self.vendored_file):
            os.remove(self.vendored_file)
