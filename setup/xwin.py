#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import shutil

from setup import Command


class XWin(Command):
    description = 'Install the Windows headers for cross compilation'

    def run(self, opts):
        import subprocess
        cache_dir = '.build-cache/xwin'
        output_dir = cache_dir + '/splat'
        cmd = f'xwin --include-atl --accept-license --cache-dir {cache_dir}'.split()
        for step in 'download unpack'.split():
            try:
                subprocess.check_call(cmd + [step])
            except FileNotFoundError:
                raise SystemExit('xwin not found install it from https://github.com/Jake-Shadle/xwin/releases')
        subprocess.check_call(cmd + ['splat', '--output', output_dir])
        shutil.rmtree(f'{cache_dir}/dl')
        shutil.rmtree(f'{cache_dir}/unpack')
