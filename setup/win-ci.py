#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import io
import os
import subprocess
import sys
import tarfile
import time


def printf(*args, **kw):
    print(*args, **kw)
    sys.stdout.flush()


def download_file(url):
    from urllib.request import urlopen
    count = 5
    while count > 0:
        count -= 1
        try:
            printf('Downloading', url)
            return urlopen(url).read()
        except Exception:
            if count <= 0:
                raise
            print('Download failed retrying...')
            time.sleep(1)


def sw():
    sw = os.environ['SW']
    os.chdir(sw)
    url = 'https://download.calibre-ebook.com/ci/calibre6/windows-64.tar.xz'
    tarball = download_file(url)
    with tarfile.open(fileobj=io.BytesIO(tarball)) as tf:
        tf.extractall()
    printf('Download complete')


def sanitize_path():
    needed_paths = []
    executables = 'git.exe curl.exe rapydscript.cmd node.exe'.split()
    for p in os.environ['PATH'].split(os.pathsep):
        for x in tuple(executables):
            if os.path.exists(os.path.join(p, x)):
                needed_paths.append(p)
                executables.remove(x)
    sw = os.environ['SW']
    paths = r'{0}\private\python\bin {0}\private\python\Lib\site-packages\pywin32_system32 {0}\bin {0}\qt\bin C:\Windows\System32'.format(
        sw
    ).split() + needed_paths
    os.environ['PATH'] = os.pathsep.join(paths)
    print('PATH:', os.environ['PATH'])


def python_exe():
    return os.path.join(os.environ['SW'], 'private', 'python', 'python.exe')


def build():
    sanitize_path()
    cmd = [python_exe(), 'setup.py', 'bootstrap', '--ephemeral']
    printf(*cmd)
    p = subprocess.Popen(cmd)
    raise SystemExit(p.wait())


def test():
    sanitize_path()
    for q in ('test', 'test_rs'):
        cmd = [python_exe(), 'setup.py', q]
        printf(*cmd)
        p = subprocess.Popen(cmd)
        if p.wait() != 0:
            raise SystemExit(p.returncode)


def setup_env():
    os.environ['SW'] = SW = r'C:\r\sw64\sw'
    os.makedirs(SW, exist_ok=True)
    os.environ['QMAKE'] = os.path.join(SW, r'qt\bin\qmake')
    os.environ['CALIBRE_QT_PREFIX'] = os.path.join(SW, r'qt')
    os.environ['CI'] = 'true'


def main():
    q = sys.argv[-1]
    setup_env()
    if q == 'bootstrap':
        build()
    elif q == 'test':
        test()
    elif q == 'install':
        sw()
    else:
        if len(sys.argv) == 1:
            raise SystemExit('Usage: win-ci.py sw|build|test')
        raise SystemExit('%r is not a valid action' % sys.argv[-1])


if __name__ == '__main__':
    main()
