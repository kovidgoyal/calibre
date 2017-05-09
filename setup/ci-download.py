#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import sys, subprocess
from tempfile import NamedTemporaryFile

url, compression, dest = sys.argv[-3:]


def decompress(path):
    raise SystemExit(
        subprocess.Popen(['tar', 'x' + compression + 'f', path, '-C', dest]).wait()
    )


if __name__ == '__main__':
    for i in range(5):
        if i:
            print('Failed to download', url, 'retrying...'.format(url))
        else:
            print('Downloading', url, '...')
        with NamedTemporaryFile() as f:
            ret = subprocess.Popen(['curl', url], stdout=f).wait()
            if ret == 0:
                decompress(f.name)
                break
