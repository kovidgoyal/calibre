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


def setenv(key, val):
    os.environ[key] = os.path.expandvars(val)


if isosx:

    SWBASE = '/Users/kovid'
    SW = SWBASE + '/sw'

    def install_env():
        # On OS X the frameworks/dylibs contain hard coded paths, so we have to re-create the paths in the VM exactly
        setenv('SWBASE', SWBASE)
        setenv('SW', SW)
        setenv(
            'PATH',
            '$SW/bin:$SW/qt/bin:$SW/python/Python.framework/Versions/2.7/bin:$PWD/node_modules/.bin:$PATH'
        )
        setenv('CFLAGS', '-I$SW/include')
        setenv('LDFLAGS', '-L$SW/lib')
        setenv('QMAKE', '$SW/qt/bin/qmake')
        setenv('QT_PLUGIN_PATH', '$SW/qt/plugins')
else:

    def install_env():
        setenv('SW', '$HOME/sw')
        setenv('PATH', '$SW/bin:$PATH')
        setenv('CFLAGS', '-I$SW/include')
        setenv('LDFLAGS', '-L$SW/lib')
        setenv('LD_LIBRARY_PATH', '$SW/qt/lib:$SW/lib')
        setenv('PKG_CONFIG_PATH', '$SW/lib/pkgconfig')
        setenv('QMAKE', '$SW/qt/bin/qmake')
        setenv('QT_PLUGIN_PATH', '$SW/qt/plugins')


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


def run_python(*args):
    python = os.path.expandvars('$SW/bin/python')
    if len(args) == 1:
        args = shlex.split(args[0])
    args = [python] + list(args)
    return run(*args)


def main():
    action = sys.argv[1]
    if action == 'install':
        if isosx:
            run('sudo', 'mkdir', '-p', SWBASE)
            run('sudo', 'chown', os.environ['USER'], SWBASE)
            download_and_decompress(
                'https://download.calibre-ebook.com/travis/sw-osx.tar.bz2',
                SWBASE
            )
        else:
            download_and_decompress(
                'https://download.calibre-ebook.com/travis/sw-linux.tar.xz',
                os.path.expanduser('~')
            )

        run('npm install --no-optional rapydscript-ng')
        print(os.environ['PATH'])
        run('which rapydscript')
        run('rapydscript --version')

    elif action == 'bootstrap':
        install_env()
        run_python('setup.py bootstrap --ephemeral')

    elif action == 'test':
        if isosx:
            os.environ['SSL_CERT_FILE'
                       ] = os.path.abspath('resources/mozilla-ca-certs.pem')

        install_env()
        run_python('setup.py test')
    else:
        raise SystemExit('Unknown action: {}'.format(action))


if __name__ == '__main__':
    main()
