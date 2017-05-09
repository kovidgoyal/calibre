#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import shlex
import subprocess
import sys
import time
from tempfile import NamedTemporaryFile

_plat = sys.platform.lower()
isosx = 'darwin' in _plat


def run(*args):
    if len(args) == 1:
        args = shlex.split(args[0])
    print(' '.join(args))
    ret = subprocess.Popen(args).wait()
    if ret != 0:
        raise SystemExit(ret)


def decompress(path, dest, compression):
    run('tar', 'x' + compression + 'f', path, '-C', dest)


def download_and_decompress(url, dest, compression=None):
    if compression is None:
        compression = 'j' if url.endswith('.bz2') else 'J'
    for i in range(5):
        print('Downloading', url, '...')
        with NamedTemporaryFile() as f:
            ret = subprocess.Popen(['curl', '-fSsL', url], stdout=f).wait()
            if ret == 0:
                decompress(f.name, dest, compression)
                return
            time.sleep(1)
    raise SystemExit('Failed to download ' + url)


def main():
    action = sys.argv[1]
    if action == 'install':
        if isosx:
            os.makedirs(os.environ['SWBASE'])
            run('sudo', 'chown', os.environ['USER'], os.environ['SWBASE'])
            download_and_decompress('https://download.calibre-ebook.com/travis/sw-osx.tar.bz2', os.environ['SWBASE'])
        else:
            download_and_decompress('https://download.calibre-ebook.com/travis/sw-linux.tar.xz', os.path.expanduser('~'))

        run('npm install --no-optional rapydscript-ng')
        print(os.environ['PATH'])
        run('which rapydscript')
        run('rapydscript --version')

        run(sys.executable, 'setup.py', 'bootstrap', '--ephemeral')
    elif action == 'test':
        if isosx:
            os.environ['SSL_CERT_FILE'] = os.path.abspath('resources/mozilla-ca-certs.pem')
        run(sys.executable, 'setup.py', 'test')


if __name__ == '__main__':
    main()
