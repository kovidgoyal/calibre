#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, platform, subprocess, stat, py_compile, glob, \
        textwrap, tarfile, re

from setup import Command, modules, basenames, functions, __version__, \
    __appname__

SITE_PACKAGES = ['PIL', 'dateutil', 'dns', 'PyQt4', 'mechanize',
        'sip.so', 'BeautifulSoup.py', 'cssutils', 'encutils', 'lxml',
        'sipconfig.py', 'xdg', 'dbus', '_dbus_bindings.so', 'dbus_bindings.py',
        '_dbus_glib_bindings.so', 'netifaces.so', '_psutil_posix.so',
        '_psutil_linux.so', 'psutil', 'cssselect']

QTDIR          = '/usr/lib/qt4'
QTDLLS         = ('QtCore', 'QtGui', 'QtNetwork', 'QtSvg', 'QtXml', 'QtWebKit', 'QtDBus')
MAGICK_PREFIX = '/usr'
binary_includes = [
                '/usr/bin/pdftohtml',
                '/usr/bin/pdfinfo',
                '/usr/lib/libusb-1.0.so.0',
                '/usr/lib/libmtp.so.9',
                '/usr/lib/libglib-2.0.so.0',
                '/usr/bin/pdftoppm',
                '/usr/lib/libwmflite-0.2.so.7',
                '/usr/lib/liblcms.so.1',
                '/usr/lib/liblzma.so.0',
                '/usr/lib/libexpat.so.1',
                '/usr/lib/libsqlite3.so.0',
                '/usr/lib/libmng.so.1',
                '/usr/lib/libpodofo.so.0.9.1',
                '/lib/libz.so.1',
                '/usr/lib/libtiff.so.5',
                '/lib/libbz2.so.1',
                '/usr/lib/libpoppler.so.28',
                '/usr/lib/libxml2.so.2',
                '/usr/lib/libopenjpeg.so.2',
                '/usr/lib/libxslt.so.1',
                '/usr/lib/libjpeg.so.8',
                '/usr/lib/libxslt.so.1',
                '/usr/lib/libgthread-2.0.so.0',
                '/usr/lib/libpng14.so.14',
                '/usr/lib/libexslt.so.0',
                # Ensure that libimobiledevice is compiled against openssl, not gnutls
                '/usr/lib/libimobiledevice.so.4',
                '/usr/lib/libusbmuxd.so.2',
                '/usr/lib/libplist.so.1',
                MAGICK_PREFIX+'/lib/libMagickWand.so.5',
                MAGICK_PREFIX+'/lib/libMagickCore.so.5',
                '/usr/lib/libgcrypt.so.11',
                '/usr/lib/libgpg-error.so.0',
                '/usr/lib/libphonon.so.4',
                '/usr/lib/libssl.so.1.0.0',
                '/usr/lib/libcrypto.so.1.0.0',
                '/lib/libreadline.so.6',
                '/usr/lib/libchm.so.0',
                '/usr/lib/liblcms2.so.2',
                '/usr/lib/libicudata.so.49',
                '/usr/lib/libicui18n.so.49',
                '/usr/lib/libicuuc.so.49',
                '/usr/lib/libicuio.so.49',
                ]
binary_includes += [os.path.join(QTDIR, 'lib%s.so.4'%x) for x in QTDLLS]

is64bit = platform.architecture()[0] == '64bit'
arch = 'x86_64' if is64bit else 'i686'


class LinuxFreeze(Command):

    def run(self, opts):
        self.drop_privileges()
        self.opts = opts
        self.src_root = self.d(self.SRC)
        self.base = self.j(self.src_root, 'build', 'linfrozen')
        self.py_ver = '.'.join(map(str, sys.version_info[:2]))
        self.lib_dir = self.j(self.base, 'lib')
        self.bin_dir = self.j(self.base, 'bin')

        self.initbase()
        self.copy_libs()
        self.copy_python()
        self.compile_mount_helper()
        self.build_launchers()
        self.create_tarfile()

    def initbase(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)
        os.makedirs(self.base)

    def copy_libs(self):
        self.info('Copying libs...')
        os.mkdir(self.lib_dir)
        os.mkdir(self.bin_dir)

        gcc = subprocess.Popen(["gcc-config", "-c"], stdout=subprocess.PIPE).communicate()[0]
        chost, _, gcc = gcc.rpartition('-')
        gcc_lib = '/usr/lib/gcc/%s/%s/'%(chost.strip(), gcc.strip())
        stdcpp = gcc_lib+'libstdc++.so.?'
        stdcpp = glob.glob(stdcpp)[-1]
        ffi = gcc_lib+'libffi.so.?'
        ffi = glob.glob(ffi)
        if ffi:
            ffi = ffi[-1]
        else:
            ffi = glob.glob('/usr/lib/libffi.so.?')[-1]

        for x in binary_includes + [stdcpp, ffi]:
            dest = self.bin_dir if '/bin/' in x else self.lib_dir
            shutil.copy2(x, dest)
        shutil.copy2('/usr/lib/libpython%s.so.1.0'%self.py_ver, dest)

        base = self.j(QTDIR, 'plugins')
        dest = self.j(self.lib_dir, 'qt_plugins')
        os.mkdir(dest)
        for x in os.listdir(base):
            y = self.j(base, x)
            if x not in ('designer', 'sqldrivers', 'codecs'):
                shutil.copytree(y, self.j(dest, x))

        im = glob.glob(MAGICK_PREFIX + '/lib/ImageMagick-*')[-1]
        self.magick_base = os.path.basename(im)
        dest = self.j(self.lib_dir, self.magick_base)
        shutil.copytree(im, dest, ignore=shutil.ignore_patterns('*.a'))
        from calibre import walk
        for x in walk(dest):
            if x.endswith('.la'):
                raw = open(x).read()
                raw = re.sub('libdir=.*', '', raw)
                open(x, 'wb').write(raw)

        dest = self.j(dest, 'config')
        src = self.j(MAGICK_PREFIX, 'share', self.magick_base, 'config')
        for x in glob.glob(src+'/*'):
            d = self.j(dest, os.path.basename(x))
            if os.path.isdir(x):
                shutil.copytree(x, d)
            else:
                shutil.copyfile(x, d)

    def compile_mount_helper(self):
        self.info('Compiling mount helper...')
        dest = self.j(self.bin_dir, 'calibre-mount-helper')
        subprocess.check_call(['gcc', '-Wall', '-pedantic',
            self.j(self.SRC, 'calibre', 'devices',
                'linux_mount_helper.c'), '-o', dest])

    def copy_python(self):
        self.info('Copying python...')

        def ignore_in_lib(base, items):
            ans = []
            for y in items:
                x = os.path.join(base, y)
                if (os.path.isfile(x) and os.path.splitext(x)[1] in ('.so',
                        '.py')) or \
                   (os.path.isdir(x) and x not in ('.svn', '.bzr', 'test', 'tests',
                       'testing')):
                    continue
                ans.append(y)
            return ans

        srcdir = self.j('/usr/lib/python'+self.py_ver)
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
            if os.path.isfile(y) and ext in ('.py', '.so') and \
                    self.b(y) not in ('pdflib_py.so',):
                shutil.copy2(y, self.py_dir)

        srcdir = self.j(srcdir, 'site-packages')
        dest = self.j(self.py_dir, 'site-packages')
        os.mkdir(dest)
        for x in SITE_PACKAGES:
            x = self.j(srcdir, x)
            ext = os.path.splitext(x)[1]
            if os.path.isdir(x):
                shutil.copytree(x, self.j(dest, self.b(x)),
                        ignore=ignore_in_lib)
            if os.path.isfile(x) and ext in ('.py', '.so'):
                shutil.copy2(x, dest)

        for x in os.listdir(self.SRC):
            shutil.copytree(self.j(self.SRC, x), self.j(dest, x),
                    ignore=ignore_in_lib)
        for x in ('trac',):
            x = self.j(dest, 'calibre', x)
            if os.path.exists(x):
                shutil.rmtree(x)

        for x in glob.glob(self.j(dest, 'calibre', 'translations', '*.po')):
            os.remove(x)

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
        dist = os.path.join(self.d(self.SRC), 'dist',
            '%s-%s-%s.tar.bz2'%(__appname__, __version__, arch))
        with tarfile.open(dist, mode='w:bz2',
                    format=tarfile.PAX_FORMAT) as tf:
            cwd = os.getcwd()
            os.chdir(self.base)
            try:
                for x in os.listdir('.'):
                    tf.add(x)
            finally:
                os.chdir(cwd)
        self.info('Archive %s created: %.2f MB'%(dist,
            os.stat(dist).st_size/(1024.**2)))

    def build_launchers(self):
        self.obj_dir = self.j(self.src_root, 'build', 'launcher')
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        base = self.j(self.src_root, 'setup', 'installer', 'linux')
        sources = [self.j(base, x) for x in ['util.c']]
        headers = [self.j(base, x) for x in ['util.h']]
        objects = [self.j(self.obj_dir, self.b(x)+'.o') for x in sources]
        cflags  = '-fno-strict-aliasing -W -Wall -c -O2 -pipe -DPYTHON_VER="python%s"'%self.py_ver
        cflags  = cflags.split() + ['-I/usr/include/python'+self.py_ver]
        for src, obj in zip(sources, objects):
            if not self.newer(obj, headers+[src, __file__]):
                continue
            cmd = ['gcc'] + cflags + ['-fPIC', '-o', obj, src]
            self.run_builder(cmd)

        dll = self.j(self.lib_dir, 'libcalibre-launcher.so')
        if self.newer(dll, objects):
            cmd = ['gcc', '-O2', '-Wl,--rpath=$ORIGIN/../lib', '-fPIC', '-o', dll, '-shared'] + objects + \
                    ['-lpython'+self.py_ver]
            self.info('Linking libcalibre-launcher.so')
            self.run_builder(cmd)

        src = self.j(base, 'main.c')

        modules['console'].append('calibre.linux')
        basenames['console'].append('calibre_postinstall')
        functions['console'].append('main')
        for typ in ('console', 'gui', ):
            self.info('Processing %s launchers'%typ)
            for mod, bname, func in zip(modules[typ], basenames[typ],
                    functions[typ]):
                xflags = list(cflags)
                xflags += ['-DGUI_APP='+('1' if typ == 'gui' else '0')]
                xflags += ['-DMODULE="%s"'%mod, '-DBASENAME="%s"'%bname,
                    '-DFUNCTION="%s"'%func]

                launcher = textwrap.dedent('''\
                #!/bin/sh
                path=`readlink -f $0`
                base=`dirname $path`
                lib=$base/lib
                export QT_ACCESSIBILITY=0 # qt-at-spi causes crashes and performance issues in various distros, so disable it
                export LD_LIBRARY_PATH=$lib:$LD_LIBRARY_PATH
                export MAGICK_HOME=$base
                export MAGICK_CONFIGURE_PATH=$lib/{1}/config
                export MAGICK_CODER_MODULE_PATH=$lib/{1}/modules-Q16/coders
                export MAGICK_CODER_FILTER_PATH=$lib/{1}/modules-Q16/filters
                exec $base/bin/{0} "$@"
                ''')

                dest = self.j(self.obj_dir, bname+'.o')
                if self.newer(dest, [src, __file__]+headers):
                    self.info('Compiling', bname)
                    cmd = ['gcc'] + xflags + [src, '-o', dest]
                    self.run_builder(cmd, verbose=False)
                exe = self.j(self.bin_dir, bname)
                sh = self.j(self.base, bname)
                with open(sh, 'wb') as f:
                    f.write(launcher.format(bname, self.magick_base))
                os.chmod(sh,
                    stat.S_IREAD|stat.S_IEXEC|stat.S_IWRITE|stat.S_IRGRP|stat.S_IXGRP|stat.S_IROTH|stat.S_IXOTH)

                if self.newer(exe, [dest, __file__]):
                    self.info('Linking', bname)
                    cmd = ['gcc', '-O2',
                            '-o', exe,
                            dest,
                            '-L'+self.lib_dir,
                            '-lcalibre-launcher',
                            ]

                    self.run_builder(cmd, verbose=False)

    def create_site_py(self):  # {{{
        with open(self.j(self.py_dir, 'site.py'), 'wb') as f:
            f.write(textwrap.dedent('''\
            import sys
            import encodings
            import __builtin__
            import locale
            import os
            import codecs

            def set_default_encoding():
                try:
                    locale.setlocale(locale.LC_ALL, '')
                except:
                    print 'WARNING: Failed to set default libc locale, using en_US.UTF-8'
                    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
                enc = locale.getdefaultlocale()[1]
                if not enc:
                    enc = locale.nl_langinfo(locale.CODESET)
                if not enc or enc.lower() == 'ascii':
                    enc = 'UTF-8'
                enc = codecs.lookup(enc).name
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

            def set_qt_plugin_path():
                import uuid
                uuid.uuid4() # Workaround for libuuid/PyQt conflict
                from PyQt4.Qt import QCoreApplication
                paths = list(map(unicode, QCoreApplication.libraryPaths()))
                paths.insert(0, sys.frozen_path + '/lib/qt_plugins')
                QCoreApplication.setLibraryPaths(paths)


            def main():
                try:
                    sys.argv[0] = sys.calibre_basename
                    dfv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
                    if dfv and os.path.exists(dfv):
                        sys.path.insert(0, os.path.abspath(dfv))
                    set_default_encoding()
                    set_helper()
                    set_qt_plugin_path()
                    mod = __import__(sys.calibre_module, fromlist=[1])
                    func = getattr(mod, sys.calibre_function)
                    return func()
                except SystemExit:
                    raise
                except:
                    import traceback
                    traceback.print_exc()
                return 1
            '''))
    # }}}


