#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Setup instructions for linux build-system

Edit /etc/network/interfaces and add

iface eth1 inet static
        address 192.168.xxx.xxx

Also add eth1 to the auto line (use sudo ifup eth1 to start eth1 without rebooting)

sudo visudo (all no password actions for user)
sudo apt-get install build-essential module-assistant vim zsh vim-scripts rsync \
    htop nasm unzip libdbus-1-dev cmake libltdl-dev libudev-dev apt-file \
    libdbus-glib-1-dev libcups2-dev "^libxcb.*" libx11-xcb-dev libglu1-mesa-dev \
    libxrender-dev flex bison gperf libasound2-dev libgstreamer0.10-dev \
    libgstreamer-plugins-base0.10-dev libpulse-dev libgtk2.0-dev libffi-dev
apt-file update

# For recent enough version of debian (>= sid) also install libxkbcommon-dev

mkdir -p ~/bin ~/sw/sources ~/sw/build

chsh -s /bin/zsh

Edit /etc/default/grub and change the GRUB_TIMEOUT to 1, then run
sudo update-grub

Copy over authorized_keys, .vimrc and .zshrc

Create ~/.zshenv as

export SW=$HOME/sw
export MAKEOPTS="-j2"
export CFLAGS=-I$SW/include
export LDFLAGS=-L$SW/lib
export LD_LIBRARY_PATH=$SW/lib
export PKG_CONFIG_PATH=$SW/lib/pkgconfig:$PKG_CONFIG_PATH

typeset -U path
path=($SW/bin "$path[@]")
path=($SW/qt/bin "$path[@]")
path=(~/bin "$path[@]")

'''

import sys, os, shutil, platform, subprocess, stat, py_compile, glob, textwrap, tarfile
from functools import partial

from setup import Command, modules, basenames, functions, __version__,  __appname__
from setup.build_environment import QT_DLLS, QT_PLUGINS, qt, PYQT_MODULES, sw as SW

j = os.path.join
is64bit = platform.architecture()[0] == '64bit'
py_ver = '.'.join(map(str, sys.version_info[:2]))
arch = 'x86_64' if is64bit else 'i686'


def binary_includes():
    return [
    j(SW, 'bin', x) for x in ('pdftohtml', 'pdfinfo', 'pdftoppm')] + [

    j(SW, 'lib', 'lib' + x) for x in (
        'usb-1.0.so.0', 'mtp.so.9', 'expat.so.1', 'sqlite3.so.0',
        'podofo.so.0.9.1', 'z.so.1', 'bz2.so.1.0', 'poppler.so.46',
        'iconv.so.2', 'xml2.so.2', 'xslt.so.1', 'jpeg.so.8', 'png16.so.16',
        'exslt.so.0', 'imobiledevice.so.4', 'usbmuxd.so.2', 'plist.so.2',
        'MagickCore-6.Q16.so.2', 'MagickWand-6.Q16.so.2', 'ssl.so.1.0.0',
        'crypto.so.1.0.0', 'readline.so.6', 'chm.so.0', 'icudata.so.53',
        'icui18n.so.53', 'icuuc.so.53', 'icuio.so.53', 'python%s.so.1.0' % py_ver,
        'gcrypt.so.20', 'gpg-error.so.0', 'gobject-2.0.so.0', 'glib-2.0.so.0',
        'gthread-2.0.so.0', 'gmodule-2.0.so.0', 'gio-2.0.so.0',
    )] + [

    glob.glob('/lib/*/lib' + x)[-1] for x in (
        'dbus-1.so.3',  'pcre.so.3'
    )] + [

    glob.glob('/usr/lib/*/lib' + x)[-1] for x in (
        'gstreamer-0.10.so.0', 'gstbase-0.10.so.0', 'gstpbutils-0.10.so.0',
        'gstapp-0.10.so.0', 'gstinterfaces-0.10.so.0', 'gstvideo-0.10.so.0', 'orc-0.4.so.0',
        'ffi.so.5',
        # 'stdc++.so.6',
        # We dont include libstdc++.so as the OpenGL dlls on the target
        # computer fail to load in the QPA xcb plugin if they were compiled
        # with a newer version of gcc than the one on the build computer.
        # libstdc++, like glibc is forward compatible and I dont think any
        # distros do not have libstdc++.so.6, so it should be safe to leave it out.
        # https://gcc.gnu.org/onlinedocs/libstdc++/manual/abi.html (The current
        # debian stable libstdc++ is  libstdc++.so.6.0.17)
    )] + [
        j(qt['libs'], 'lib%s.so.5' % x) for x in QT_DLLS]


def ignore_in_lib(base, items, ignored_dirs=None):
    ans = []
    if ignored_dirs is None:
        ignored_dirs = {'.svn', '.bzr', '.git', 'test', 'tests', 'testing'}
    for name in items:
        path = os.path.join(base, name)
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

class LinuxFreeze(Command):

    def run(self, opts):
        self.drop_privileges()
        self.opts = opts
        self.src_root = self.d(self.SRC)
        self.base = self.j(self.src_root, 'build', 'linfrozen')
        self.lib_dir = self.j(self.base, 'lib')
        self.bin_dir = self.j(self.base, 'bin')

        self.initbase()
        self.copy_libs()
        self.copy_python()
        self.build_launchers()
        self.strip_files()
        self.create_tarfile()

    def initbase(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)
        os.makedirs(self.base)

    def copy_libs(self):
        self.info('Copying libs...')
        os.mkdir(self.lib_dir)
        os.mkdir(self.bin_dir)

        for x in binary_includes():
            dest = self.bin_dir if '/bin/' in x else self.lib_dir
            shutil.copy2(x, dest)

        base = qt['plugins']
        dest = self.j(self.lib_dir, 'qt_plugins')
        os.mkdir(dest)
        for x in QT_PLUGINS:
            shutil.copytree(self.j(base, x), self.j(dest, x))

        im = glob.glob(SW + '/lib/ImageMagick-*')[-1]
        self.magick_base = os.path.basename(im)
        dest = self.j(self.lib_dir, self.magick_base)
        shutil.copytree(im, dest, ignore=shutil.ignore_patterns('*.a'))

    def copy_python(self):
        self.info('Copying python...')

        srcdir = self.j(SW, 'lib/python'+py_ver)
        self.py_dir = self.j(self.lib_dir, self.b(srcdir))
        if not os.path.exists(self.py_dir):
            os.mkdir(self.py_dir)

        for x in os.listdir(srcdir):
            y = self.j(srcdir, x)
            ext = os.path.splitext(x)[1]
            if os.path.isdir(y) and x not in ('test', 'hotshot', 'distutils',
                    'site-packages', 'idlelib', 'lib2to3', 'dist-packages'):
                shutil.copytree(y, self.j(self.py_dir, x),
                        ignore=ignore_in_lib)
            if os.path.isfile(y) and ext in ('.py', '.so'):
                shutil.copy2(y, self.py_dir)

        srcdir = self.j(srcdir, 'site-packages')
        dest = self.j(self.py_dir, 'site-packages')
        import_site_packages(srcdir, dest)

        filter_pyqt = {x+'.so' for x in PYQT_MODULES}
        pyqt = self.j(dest, 'PyQt5')
        for x in os.listdir(pyqt):
            if x.endswith('.so') and x not in filter_pyqt:
                os.remove(self.j(pyqt, x))

        for x in os.listdir(self.SRC):
            c = self.j(self.SRC, x)
            if os.path.exists(self.j(c, '__init__.py')):
                shutil.copytree(c, self.j(dest, x), ignore=partial(ignore_in_lib, ignored_dirs={}))
            elif os.path.isfile(c):
                shutil.copy2(c, self.j(dest, x))

        shutil.copytree(self.j(self.src_root, 'resources'), self.j(self.base,
                'resources'))

        self.create_site_py()

        for x in os.walk(self.py_dir):
            for f in x[-1]:
                if f.endswith('.py'):
                    y = self.j(x[0], f)
                    rel = os.path.relpath(y, self.py_dir)
                    try:
                        py_compile.compile(y, dfile=rel, doraise=True)
                        os.remove(y)
                        z = y+'c'
                        if os.path.exists(z):
                            os.remove(z)
                    except:
                        if '/uic/port_v3/' not in y:
                            self.warn('Failed to byte-compile', y)

    def run_builder(self, cmd, verbose=True):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        if verbose:
            self.info(*cmd)
        x = p.stdout.read() + p.stderr.read()
        if x.strip():
            self.info(x.strip())

        if p.wait() != 0:
            self.info('Failed to run builder')
            sys.exit(1)

    def create_tarfile(self):
        self.info('Creating archive...')
        base = self.j(self.d(self.SRC), 'dist')
        if not os.path.exists(base):
            os.mkdir(base)
        dist = os.path.join(base, '%s-%s-%s.tar'%(__appname__, __version__, arch))
        with tarfile.open(dist, mode='w', format=tarfile.PAX_FORMAT) as tf:
            cwd = os.getcwd()
            os.chdir(self.base)
            try:
                for x in os.listdir('.'):
                    tf.add(x)
            finally:
                os.chdir(cwd)
        self.info('Compressing archive...')
        ans = dist.rpartition('.')[0] + '.txz'
        if False:
            os.rename(dist, ans)
        else:
            subprocess.check_call(['xz', '-f', '-9', dist])
            os.rename(dist + '.xz', ans)
        self.info('Archive %s created: %.2f MB'%(
            os.path.basename(ans), os.stat(ans).st_size/(1024.**2)))

    def build_launchers(self):
        self.obj_dir = self.j(self.src_root, 'build', 'launcher')
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        base = self.j(self.src_root, 'setup', 'installer', 'linux')
        sources = [self.j(base, x) for x in ['util.c']]
        headers = [self.j(base, x) for x in ['util.h']]
        objects = [self.j(self.obj_dir, self.b(x)+'.o') for x in sources]
        cflags  = '-fno-strict-aliasing -W -Wall -c -O2 -pipe -DPYTHON_VER="python%s"'%py_ver
        cflags  = cflags.split() + ['-I%s/include/python%s' % (SW, py_ver)]
        for src, obj in zip(sources, objects):
            if not self.newer(obj, headers+[src, __file__]):
                continue
            cmd = ['gcc'] + cflags + ['-fPIC', '-o', obj, src]
            self.run_builder(cmd)

        dll = self.j(self.lib_dir, 'libcalibre-launcher.so')
        if self.newer(dll, objects):
            cmd = ['gcc', '-O2', '-Wl,--rpath=$ORIGIN/../lib', '-fPIC', '-o', dll, '-shared'] + objects + \
                    ['-L%s/lib'%SW, '-lpython'+py_ver]
            self.info('Linking libcalibre-launcher.so')
            self.run_builder(cmd)

        src = self.j(base, 'main.c')

        modules['console'].append('calibre.linux')
        basenames['console'].append('calibre_postinstall')
        functions['console'].append('main')
        c_launcher = '/tmp/calibre-c-launcher'
        lsrc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'launcher.c')
        cmd = ['gcc', '-O2', '-DMAGICK_BASE="%s"' % self.magick_base, '-o', c_launcher, lsrc, ]
        self.info('Compiling launcher')
        self.run_builder(cmd, verbose=False)

        for typ in ('console', 'gui', ):
            self.info('Processing %s launchers'%typ)
            for mod, bname, func in zip(modules[typ], basenames[typ],
                    functions[typ]):
                xflags = list(cflags)
                xflags += ['-DGUI_APP='+('1' if typ == 'gui' else '0')]
                xflags += ['-DMODULE="%s"'%mod, '-DBASENAME="%s"'%bname,
                    '-DFUNCTION="%s"'%func]

                dest = self.j(self.obj_dir, bname+'.o')
                if self.newer(dest, [src, __file__]+headers):
                    cmd = ['gcc'] + xflags + [src, '-o', dest]
                    self.run_builder(cmd, verbose=False)
                exe = self.j(self.bin_dir, bname)
                sh = self.j(self.base, bname)
                shutil.copy2(c_launcher, sh)
                os.chmod(sh,
                    stat.S_IREAD|stat.S_IEXEC|stat.S_IWRITE|stat.S_IRGRP|stat.S_IXGRP|stat.S_IROTH|stat.S_IXOTH)

                if self.newer(exe, [dest, __file__]):
                    cmd = ['gcc', '-O2',
                            '-o', exe,
                            dest,
                            '-L'+self.lib_dir,
                            '-lcalibre-launcher',
                            ]

                    self.run_builder(cmd, verbose=False)

    def strip_files(self):
        from calibre import walk
        files = {self.j(self.bin_dir, x) for x in os.listdir(self.bin_dir)} | {
            x for x in {
            self.j(self.d(self.bin_dir), x) for x in os.listdir(self.bin_dir)} if os.path.exists(x)}
        for x in walk(self.lib_dir):
            x = os.path.realpath(x)
            if x not in files and is_elf(x):
                files.add(x)
        self.info('Stripping %d files...' % len(files))
        before = sum(os.path.getsize(x) for x in files)
        strip_files(files)
        after = sum(os.path.getsize(x) for x in files)
        self.info('Stripped %.1f MB' % ((before - after)/(1024*1024.)))

    def create_site_py(self):  # {{{
        with open(self.j(self.py_dir, 'site.py'), 'wb') as f:
            f.write(textwrap.dedent('''\
            import sys
            import encodings  # noqa
            import __builtin__
            import locale
            import os
            import codecs

            def set_default_encoding():
                try:
                    locale.setlocale(locale.LC_ALL, '')
                except:
                    print ('WARNING: Failed to set default libc locale, using en_US.UTF-8')
                    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
                enc = locale.getdefaultlocale()[1]
                if not enc:
                    enc = locale.nl_langinfo(locale.CODESET)
                if not enc or enc.lower() == 'ascii':
                    enc = 'UTF-8'
                try:
                    enc = codecs.lookup(enc).name
                except LookupError:
                    enc = 'UTF-8'
                sys.setdefaultencoding(enc)
                del sys.setdefaultencoding

            class _Helper(object):
                """Define the builtin 'help'.
                This is a wrapper around pydoc.help (with a twist).

                """

                def __repr__(self):
                    return "Type help() for interactive help, " \
                        "or help(object) for help about object."
                def __call__(self, *args, **kwds):
                    import pydoc
                    return pydoc.help(*args, **kwds)

            def set_helper():
                __builtin__.help = _Helper()

            def main():
                try:
                    sys.argv[0] = sys.calibre_basename
                    dfv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
                    if dfv and os.path.exists(dfv):
                        sys.path.insert(0, os.path.abspath(dfv))
                    set_default_encoding()
                    set_helper()
                    mod = __import__(sys.calibre_module, fromlist=[1])
                    func = getattr(mod, sys.calibre_function)
                    return func()
                except SystemExit as err:
                    if err.code is None:
                        return 0
                    if isinstance(err.code, int):
                        return err.code
                    print (err.code)
                    return 1
                except:
                    import traceback
                    traceback.print_exc()
                return 1
            '''))
    # }}}


