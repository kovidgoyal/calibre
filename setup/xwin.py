#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import os
import runpy
import shutil

from setup import Command


class XWin(Command):
    description = 'Install the Windows headers for cross compilation'

    def run(self, opts):
        if not shutil.which('msiextract'):
            raise SystemExit('No msiextract found in PATH you may need to install msitools')
        base = os.path.dirname(self.SRC)
        m = runpy.run_path(os.path.join(base, 'setup', 'wincross.py'))
        cache_dir = os.path.join(base, '.build-cache', 'xwin')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        os.makedirs(cache_dir)
        m['main'](['--dest', cache_dir])
        for x in os.listdir(cache_dir):
            if x != 'root':
                shutil.rmtree(os.path.join(cache_dir, x))
