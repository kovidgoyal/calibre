#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import print_function

import errno
import glob
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from functools import partial

from bypy.constants import (
    LIBDIR, PREFIX, PYTHON, SRC as CALIBRE_DIR, SW, build_dir, is64bit,
    python_major_minor_version, worker_env
)
from bypy.pkgs.qt import PYQT_MODULES, QT_DLLS, QT_PLUGINS
from bypy.utils import (
    create_job, get_dll_path, mkdtemp, parallel_build, py_compile, run, run_shell,
    walk
)

j = os.path.join
self_dir = os.path.dirname(os.path.abspath(__file__))
arch = 'x86_64' if is64bit else 'i686'

py_ver = '.'.join(map(str, python_major_minor_version()))
QT_PREFIX = os.path.join(PREFIX, 'qt')
calibre_constants = globals()['init_env']['calibre_constants']
qt_get_dll_path = partial(get_dll_path, loc=os.path.join(QT_PREFIX, 'lib'))


def binary_includes():
    return [
        j(PREFIX, 'bin', x) for x in ('pdftohtml', 'pdfinfo', 'pdftoppm', 'optipng', 'JxrDecApp')] + [

        j(PREFIX, 'private', 'mozjpeg', 'bin', x) for x in ('jpegtran', 'cjpeg')] + [
        ] + list(map(
            get_dll_path,
            ('usb-1.0 mtp expat sqlite3 ffi z poppler dbus-1 iconv xml2 xslt jpeg png16'
             ' webp exslt ncursesw readline chm icudata icui18n icuuc icuio gcrypt gpg-error'
             ' gobject-2.0 glib-2.0 gthread-2.0 gmodule-2.0 gio-2.0 dbus-glib-1').split()
        )) + [
            get_dll_path('podofo', 3), get_dll_path('bz2', 2), j(PREFIX, 'lib', 'libunrar.so'),
            get_dll_path('ssl', 3), get_dll_path('crypto', 3), get_dll_path('python' + py_ver, 2),
            # We dont include libstdc++.so as the OpenGL dlls on the target
            # computer fail to load in the QPA xcb plugin if they were compiled
            # with a newer version of gcc than the one on the build computer.
            # libstdc++, like glibc is forward compatible and I dont think any
            # distros do not have libstdc++.so.6, so it should be safe to leave it out.
            # https://gcc.gnu.org/onlinedocs/libstdc++/manual/abi.html (The current
            # debian stable libstdc++ is  libstdc++.so.6.0.17)
    ] + list(map(qt_get_dll_path, QT_DLLS))


class Env(object):

    def __init__(self):
        self.src_root = CALIBRE_DIR
        self.base = mkdtemp('frozen-')
        self.lib_dir = j(self.base, 'lib')
        self.py_dir = j(self.lib_dir, 'python' + py_ver)
        os.makedirs(self.py_dir)
        self.bin_dir = j(self.base, 'bin')
        os.mkdir(self.bin_dir)
        self.SRC = j(self.src_root, 'src')
        self.obj_dir = mkdtemp('launchers-')


def ignore_in_lib(base, items, ignored_dirs=None):
    ans = []
    if ignored_dirs is None:
        ignored_dirs = {'.svn', '.bzr', '.git', 'test', 'tests', 'testing'}
    for name in items:
        path = j(base, name)
        if os.path.isdir(path):
            if name in ignored_dirs or not os.path.exists(j(path, '__init__.py')):
                if name != 'plugins':
                    ans.append(name)
        else:
            if name.rpartition('.')[-1] not in ('so', 'py'):
                ans.append(name)
    return ans


def import_site_packages(srcdir, dest):
    if not os.path.exists(dest):
        os.mkdir(dest)
    for x in os.listdir(srcdir):
        ext = x.rpartition('.')[-1]
        f = j(srcdir, x)
        if ext in ('py', 'so'):
            shutil.copy2(f, dest)
        elif ext == 'pth' and x != 'setuptools.pth':
            for line in open(f, 'rb').read().splitlines():
                src = os.path.abspath(j(srcdir, line))
                if os.path.exists(src) and os.path.isdir(src):
                    import_site_packages(src, dest)
        elif os.path.exists(j(f, '__init__.py')):
            shutil.copytree(f, j(dest, x), ignore=ignore_in_lib)


def copy_libs(env):
    print('Copying libs...')

    for x in binary_includes():
        dest = env.bin_dir if '/bin/' in x else env.lib_dir
        shutil.copy2(x, dest)
        os.chmod(j(
            dest, os.path.basename(x)),
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

    base = j(QT_PREFIX, 'plugins')
    dest = j(env.lib_dir, 'qt_plugins')
    os.mkdir(dest)
    for x in QT_PLUGINS:
        if x not in ('audio', 'printsupport'):
            shutil.copytree(j(base, x), j(dest, x))


def copy_python(env, ext_dir):
    print('Copying python...')
    srcdir = j(PREFIX, 'lib/python' + py_ver)

    for x in os.listdir(srcdir):
        y = j(srcdir, x)
        ext = os.path.splitext(x)[1]
        if os.path.isdir(y) and x not in ('test', 'hotshot', 'distutils',
                                          'site-packages', 'idlelib', 'lib2to3', 'dist-packages'):
            shutil.copytree(y, j(env.py_dir, x), ignore=ignore_in_lib)
        if os.path.isfile(y) and ext in ('.py', '.so'):
            shutil.copy2(y, env.py_dir)

    srcdir = j(srcdir, 'site-packages')
    dest = j(env.py_dir, 'site-packages')
    import_site_packages(srcdir, dest)
    shutil.rmtree(j(dest, 'PyQt5/uic/port_v3'))

    filter_pyqt = {x + '.so' for x in PYQT_MODULES} | {'sip.so'}
    pyqt = j(dest, 'PyQt5')
    for x in os.listdir(pyqt):
        if x.endswith('.so') and x not in filter_pyqt:
            os.remove(j(pyqt, x))

    for x in os.listdir(env.SRC):
        c = j(env.SRC, x)
        if os.path.exists(j(c, '__init__.py')):
            shutil.copytree(c, j(dest, x), ignore=partial(ignore_in_lib, ignored_dirs={}))
        elif os.path.isfile(c):
            shutil.copy2(c, j(dest, x))
    pdir = j(dest, 'calibre', 'plugins')
    if not os.path.exists(pdir):
        os.mkdir(pdir)
    for x in glob.glob(j(ext_dir, '*.so')):
        shutil.copy2(x, j(pdir, os.path.basename(x)))

    shutil.copytree(j(env.src_root, 'resources'), j(env.base, 'resources'))
    sitepy = j(self_dir, 'site.py')
    shutil.copy2(sitepy, j(env.py_dir, 'site.py'))

    py_compile(env.py_dir)


def build_launchers(env):
    base = self_dir
    sources = [j(base, x) for x in ['util.c']]
    objects = [j(env.obj_dir, os.path.basename(x) + '.o') for x in sources]
    cflags = '-fno-strict-aliasing -W -Wall -c -O2 -pipe -DPYTHON_VER="python%s"' % py_ver
    cflags = cflags.split() + ['-I%s/include/python%s' % (PREFIX, py_ver)]
    for src, obj in zip(sources, objects):
        cmd = ['gcc'] + cflags + ['-fPIC', '-o', obj, src]
        run(*cmd)

    dll = j(env.lib_dir, 'libcalibre-launcher.so')
    cmd = ['gcc', '-O2', '-Wl,--rpath=$ORIGIN/../lib', '-fPIC', '-o', dll, '-shared'] + objects + \
        ['-L%s/lib' % PREFIX, '-lpython' + py_ver]
    run(*cmd)

    src = j(base, 'main.c')

    modules, basenames, functions = calibre_constants['modules'].copy(), calibre_constants['basenames'].copy(), calibre_constants['functions'].copy()
    modules['console'].append('calibre.linux')
    basenames['console'].append('calibre_postinstall')
    functions['console'].append('main')
    c_launcher = '/tmp/calibre-c-launcher'
    lsrc = os.path.join(base, 'launcher.c')
    cmd = ['gcc', '-O2', '-o', c_launcher, lsrc, ]
    run(*cmd)

    jobs = []
    for typ in ('console', 'gui', ):
        for mod, bname, func in zip(modules[typ], basenames[typ], functions[typ]):
            xflags = list(cflags)
            xflags.remove('-c')
            xflags += ['-DGUI_APP=' + ('1' if typ == 'gui' else '0')]
            xflags += ['-DMODULE="%s"' % mod, '-DBASENAME="%s"' % bname,
                       '-DFUNCTION="%s"' % func]

            exe = j(env.bin_dir, bname)
            cmd = ['gcc'] + xflags + [src, '-o', exe, '-L' + env.lib_dir, '-lcalibre-launcher']
            jobs.append(create_job(cmd))
            sh = j(env.base, bname)
            shutil.copy2(c_launcher, sh)
            os.chmod(sh,
                     stat.S_IREAD | stat.S_IEXEC | stat.S_IWRITE | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    if jobs:
        if not parallel_build(jobs, verbose=False):
            raise SystemExit(1)


def is_elf(path):
    with open(path, 'rb') as f:
        return f.read(4) == b'\x7fELF'


STRIPCMD = ['strip']


def strip_files(files, argv_max=(256 * 1024)):
    """ Strip a list of files """
    while files:
        cmd = list(STRIPCMD)
        pathlen = sum(len(s) + 1 for s in cmd)
        while pathlen < argv_max and files:
            f = files.pop()
            cmd.append(f)
            pathlen += len(f) + 1
        if len(cmd) > len(STRIPCMD):
            all_files = cmd[len(STRIPCMD):]
            unwritable_files = tuple(filter(None, (None if os.access(x, os.W_OK) else (x, os.stat(x).st_mode) for x in all_files)))
            [os.chmod(x, stat.S_IWRITE | old_mode) for x, old_mode in unwritable_files]
            subprocess.check_call(cmd)
            [os.chmod(x, old_mode) for x, old_mode in unwritable_files]


def strip_binaries(env):
    files = {j(env.bin_dir, x) for x in os.listdir(env.bin_dir)} | {
        x for x in {
            j(os.path.dirname(env.bin_dir), x) for x in os.listdir(env.bin_dir)} if os.path.exists(x)}
    for x in walk(env.lib_dir):
        x = os.path.realpath(x)
        if x not in files and is_elf(x):
            files.add(x)
    print('Stripping %d files...' % len(files))
    before = sum(os.path.getsize(x) for x in files)
    strip_files(files)
    after = sum(os.path.getsize(x) for x in files)
    print('Stripped %.1f MB' % ((before - after) / (1024 * 1024.)))


def create_tarfile(env, compression_level='9'):
    print('Creating archive...')
    base = os.path.join(SW, 'dist')
    try:
        shutil.rmtree(base)
    except EnvironmentError as err:
        if err.errno != errno.ENOENT:
            raise
    os.mkdir(base)
    dist = os.path.join(base, '%s-%s-%s.tar' % (calibre_constants['appname'], calibre_constants['version'], arch))
    with tarfile.open(dist, mode='w', format=tarfile.PAX_FORMAT) as tf:
        cwd = os.getcwd()
        os.chdir(env.base)
        try:
            for x in os.listdir('.'):
                tf.add(x)
        finally:
            os.chdir(cwd)
    print('Compressing archive...')
    ans = dist.rpartition('.')[0] + '.txz'
    start_time = time.time()
    subprocess.check_call(['xz', '--threads=0', '-f', '-' + compression_level, dist])
    secs = time.time() - start_time
    print('Compressed in %d minutes %d seconds' % (secs // 60, secs % 60))
    os.rename(dist + '.xz', ans)
    print('Archive %s created: %.2f MB' % (
        os.path.basename(ans), os.stat(ans).st_size / (1024.**2)))


def run_tests(path_to_calibre_debug, cwd_on_failure):
    p = subprocess.Popen([path_to_calibre_debug, '--test-build'])
    if p.wait() != 0:
        os.chdir(cwd_on_failure)
        print('running calibre build tests failed', file=sys.stderr)
        run_shell()
        raise SystemExit(p.wait())


def build_extensions(env, ext_dir):
    wenv = os.environ.copy()
    wenv.update(worker_env)
    wenv['LD_LIBRARY_PATH'] = LIBDIR
    wenv['QMAKE'] = os.path.join(QT_PREFIX, 'bin', 'qmake')
    wenv['SW'] = PREFIX
    wenv['SIP_BIN'] = os.path.join(PREFIX, 'bin', 'sip')
    p = subprocess.Popen([PYTHON, 'setup.py', 'build', '--build-dir=' + build_dir(), '--output-dir=' + ext_dir], env=wenv, cwd=CALIBRE_DIR)
    if p.wait() != 0:
        os.chdir(CALIBRE_DIR)
        print('building calibre extensions failed', file=sys.stderr)
        run_shell()
        raise SystemExit(p.returncode)


def main():
    args = globals()['args']
    ext_dir = globals()['ext_dir']
    env = Env()
    copy_libs(env)
    build_extensions(env, ext_dir)
    copy_python(env, ext_dir)
    build_launchers(env)
    if not args.skip_tests:
        run_tests(j(env.base, 'calibre-debug'), env.base)
    if not args.dont_strip:
        strip_binaries(env)
    create_tarfile(env, args.compression_level)


if __name__ == '__main__':
    main()
