#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os, shlex, subprocess, glob, shutil
from distutils import sysconfig

from PyQt4.pyqtconfig import QtGuiModuleMakefile

from setup import Command, islinux, isosx, SRC, iswindows
from setup.build_environment import fc_inc, fc_lib, qt_inc, qt_lib, \
        fc_error, poppler_libs, poppler_lib, poppler_inc, podofo_inc, \
        podofo_lib, podofo_error, poppler_error, pyqt, OSX_SDK, NMAKE, \
        leopard_build, QMAKE, msvc, MT, win_inc, win_lib

isunix = islinux or isosx

make = 'make' if isunix else NMAKE

class Extension(object):

    def absolutize(self, paths):
        return [x if os.path.isabs(x) else os.path.join(SRC, x.replace('/',
            os.sep)) for x in paths]


    def __init__(self, name, sources, **kwargs):
        self.name = name
        self.needs_cxx = bool([1 for x in sources if os.path.splitext(x)[1] in
            ('.cpp', '.c++', '.cxx')])
        self.sources = self.absolutize(sources)
        self.headers = self.absolutize(kwargs.get('headers', []))
        self.sip_files = self.absolutize(kwargs.get('sip_files', []))
        self.inc_dirs = self.absolutize(kwargs.get('inc_dirs', []))
        self.lib_dirs = self.absolutize(kwargs.get('lib_dirs', []))
        self.error = kwargs.get('error', None)
        self.libraries = kwargs.get('libraries', [])
        self.cflags = kwargs.get('cflags', [])
        self.ldflags = kwargs.get('ldflags', [])
        self.optional = kwargs.get('optional', False)

extensions = [
    Extension('lzx',
            ['calibre/utils/lzx/lzxmodule.c',
                    'calibre/utils/lzx/compressor.c',
                    'calibre/utils/lzx/lzxd.c',
                    'calibre/utils/lzx/lzc.c',
                    'calibre/utils/lzx/lzxc.c'],
            headers=['calibre/utils/lzx/msstdint.h',
                    'calibre/utils/lzx/lzc.h',
                    'calibre/utils/lzx/lzxmodule.h',
                    'calibre/utils/lzx/system.h',
                    'calibre/utils/lzx/lzxc.h',
                    'calibre/utils/lzx/lzxd.h',
                    'calibre/utils/lzx/mspack.h'],
            inc_dirs=['calibre/utils/lzx']),

    Extension('fontconfig',
        ['calibre/utils/fonts/fontconfig.c'],
        inc_dirs = [fc_inc],
        libraries=['fontconfig'],
        lib_dirs=[fc_lib],
        error=fc_error),

    Extension('msdes',
                ['calibre/utils/msdes/msdesmodule.c',
                        'calibre/utils/msdes/des.c'],
                headers=['calibre/utils/msdes/spr.h',
                        'calibre/utils/msdes/d3des.h'],
                inc_dirs=['calibre/utils/msdes']),

    Extension('cPalmdoc',
        ['calibre/ebooks/compression/palmdoc.c']),

    Extension('calibre_poppler',
                ['calibre/utils/poppler/poppler.cpp'],
                libraries=(['poppler', 'poppler-qt4']+poppler_libs),
                lib_dirs=[os.environ.get('POPPLER_LIB_DIR',
                    poppler_lib), qt_lib],
                inc_dirs=[poppler_inc, qt_inc],
                error=poppler_error,
                optional=True),

    Extension('podofo',
                    ['calibre/utils/podofo/podofo.cpp'],
                    libraries=['podofo'],
                    lib_dirs=[podofo_lib],
                    inc_dirs=[podofo_inc],
                    error=podofo_error),

    Extension('pictureflow',
                ['calibre/gui2/pictureflow/pictureflow.cpp'],
                inc_dirs = ['calibre/gui2/pictureflow'],
                headers = ['calibre/gui2/pictureflow/pictureflow.h'],
                sip_files = ['calibre/gui2/pictureflow/pictureflow.sip']
                )

    ]

if iswindows:
    extensions.append(Extension('winutil',
                ['calibre/utils/windows/winutil.c'],
                libraries=['shell32', 'setupapi'],
                include_dirs=os.environ.get('INCLUDE',
                        'C:/WinDDK/6001.18001/inc/api/;'
                        'C:/WinDDK/6001.18001/inc/crt/').split(';'),
                cflags=['/X']
                ))
if isosx:
    extensions.append(Extension('usbobserver',
                ['calibre/devices/usbobserver/usbobserver.c'],
                ldflags=['-framework', 'IOKit'])
            )


if isunix:
    cc = os.environ.get('CC', 'gcc')
    cxx = os.environ.get('CXX', 'g++')
    cflags = '-O3 -Wall -DNDEBUG -fPIC -fno-strict-aliasing -pipe'.split()
    ldflags = ['-Wall']
    cflags += shlex.split(os.environ.get('CFLAGS', ''))
    ldflags += shlex.split(os.environ.get('LDFLAGS', ''))

if islinux:
    cflags.append('-pthread')
    ldflags.append('-shared')
    cflags.append('-I'+sysconfig.get_python_inc())
    ldflags.append('-lpython'+sysconfig.get_python_version())


if isosx:
    x, p = ('x86_64', 'ppc64') if leopard_build else ('i386', 'ppc')
    archs = ['-arch', x, '-arch', p, '-isysroot',
                OSX_SDK]
    cflags.extend(archs)
    ldflags.extend(archs)
    ldflags.extend('-bundle -undefined dynamic_lookup'.split())
    cflags.extend(['-fno-common', '-dynamic'])
    cflags.append('-I'+sysconfig.get_python_inc())


if iswindows:
    cc = cxx = msvc.cc
    cflags = '/c /nologo /Ox /MD /W3 /EHsc /DNDEBUG'.split()
    ldflags = '/DLL /nologo /INCREMENTAL:NO'.split()
    for p in win_inc:
        cflags.append('-I'+p)
    for p in win_lib:
        ldflags.append('/LIBPATH:'+p)
    cflags.append('-I%s'%sysconfig.get_python_inc())
    ldflags.append('/LIBPATH:'+os.path.join(sysconfig.PREFIX, 'libs'))


class Build(Command):

    description = textwrap.dedent('''\
        calibre depends on several python extensions written in C/C++.
        This command will compile them. You can influence the compile
        process by several environment variables, listed below:

           CC      - C Compiler defaults to gcc
           CXX     - C++ Compiler, defaults to g++
           CFLAGS  - Extra compiler flags
           LDFLAGS - Extra linker flags

           FC_INC_DIR - fontconfig header files
           FC_LIB_DIR - fontconfig library

           POPPLER_INC_DIR - poppler header files
           POPPLER_LIB_DIR - poppler-qt4 library

           PODOFO_INC_DIR - podofo header files
           PODOFO_LIB_DIR - podofo library files

           QMAKE          - Path to qmake
           VS90COMNTOOLS  - Location of Microsoft Visual Studio 9 Tools (windows only)

        ''')

    def add_options(self, parser):
        choices = [e.name for e in extensions]+['all']
        parser.add_option('-1', '--only', choices=choices, default='all',
                help=('Build only the named extension. Available: '+
                    ', '.join(choices)+'. Default:%default'))

    def run(self, opts):
        self.obj_dir = os.path.join(os.path.dirname(SRC), 'build', 'objects')
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        for ext in extensions:
            if opts.only != 'all' and opts.only != ext.name:
                continue
            if ext.error is not None:
                if ext.optional:
                    self.warn(ext.error)
                    continue
                else:
                    raise Exception(ext.error)
            dest = self.dest(ext)
            if not os.path.exists(self.d(dest)):
                os.makedirs(self.d(dest))
            self.info('\n####### Building extension', ext.name, '#'*7)
            self.build(ext, dest)

    def dest(self, ext):
        ex = '.pyd' if iswindows else '.so'
        return os.path.join(SRC, 'calibre', 'plugins', ext.name)+ex

    def inc_dirs_to_cflags(self, dirs):
        return ['-I'+x for x in dirs]

    def lib_dirs_to_ldflags(self, dirs):
        pref = '/LIBPATH:' if iswindows else '-L'
        return [pref+x for x in dirs]

    def libraries_to_ldflags(self, dirs):
        pref = '' if iswindows else '-l'
        suff = '.lib' if iswindows else ''
        return [pref+x+suff for x in dirs]

    def build(self, ext, dest):
        if ext.sip_files:
            return self.build_pyqt_extension(ext, dest)
        compiler = cxx if ext.needs_cxx else cc
        linker = msvc.linker if iswindows else compiler
        objects = []
        einc = self.inc_dirs_to_cflags(ext.inc_dirs)
        obj_dir = self.j(self.obj_dir, ext.name)
        if not os.path.exists(obj_dir):
            os.makedirs(obj_dir)
        for src in ext.sources:
            obj = self.j(obj_dir, os.path.splitext(self.b(src))[0]+'.o')
            objects.append(obj)
            if self.newer(obj, [src]+ext.headers):
                inf = '/Tp' if src.endswith('.cpp') else '/Tc'
                sinc = [inf+src] if iswindows else ['-c', src]
                oinc = ['/Fo'+obj] if iswindows else ['-o', obj]
                cmd = [compiler] + cflags + ext.cflags + einc + sinc + oinc
                self.info(' '.join(cmd))
                subprocess.check_call(cmd)

        dest = self.dest(ext)
        elib = self.lib_dirs_to_ldflags(ext.lib_dirs)
        xlib = self.libraries_to_ldflags(ext.libraries)
        if self.newer(dest, objects):
            print 'Linking', ext.name
            cmd = [linker]
            if iswindows:
                cmd += ldflags + ext.ldflags + elib + xlib + \
                    ['/EXPORT:init'+ext.name] + objects + ['/OUT:'+dest]
            else:
                cmd += objects + ['-o', dest] + ldflags + ext.ldflags + elib + xlib
            print ' '.join(cmd)
            subprocess.check_call(cmd)
            if iswindows:
                manifest = dest+'.manifest'
                cmd = [MT, '-manifest', manifest, '-outputresource:%s;2'%dest]
                self.info(*cmd)
                subprocess.check_call(cmd)
                os.remove(manifest)
                for x in ('.exp', '.lib'):
                    x = os.path.splitext(dest)[0]+x
                    if os.path.exists(x):
                        os.remove(x)

    def build_qt_objects(self, ext):
        obj_pat = 'release\\*.obj' if iswindows else '*.o'
        objects = glob.glob(obj_pat)
        if not objects or self.newer(objects, ext.sources+ext.headers):
            archs = 'x86_64 ppc64' if leopard_build else 'x86 ppc'
            pro = textwrap.dedent('''\
                TARGET   = %s
                TEMPLATE = lib
                HEADERS  = %s
                SOURCES  = %s
                VERSION  = 1.0.0
                CONFIG   += %s
            ''')%(ext.name, ' '.join(ext.headers), ' '.join(ext.sources), archs)
            open(ext.name+'.pro', 'wb').write(pro)
            subprocess.check_call([QMAKE, '-o', 'Makefile', ext.name+'.pro'])
            if leopard_build:
                raw = open('Makefile', 'rb').read()
                open('Makefile', 'wb').write(raw.replace('ppc64', 'x86_64'))
            subprocess.check_call([make, '-f', 'Makefile'])
            objects = glob.glob(obj_pat)
        return list(map(self.a, objects))

    def build_pyqt_extension(self, ext, dest):
        pyqt_dir = self.j(self.d(self.SRC), 'build', 'pyqt')
        src_dir = self.j(pyqt_dir, ext.name)
        qt_dir  = self.j(src_dir, 'qt')
        if not self.e(qt_dir):
            os.makedirs(qt_dir)
        cwd = os.getcwd()
        try:
            os.chdir(qt_dir)
            qt_objects = self.build_qt_objects(ext)
        finally:
            os.chdir(cwd)

        sip_files = ext.sip_files
        ext.sip_files = []
        sipf = sip_files[0]
        sbf = self.j(src_dir, self.b(sipf)+'.sbf')
        if self.newer(sbf, [sipf]+ext.headers):
            exe = '.exe' if iswindows else ''
            cmd = [pyqt.sip_bin+exe, '-w', '-c', src_dir, '-b', sbf, '-I'+\
                    pyqt.pyqt_sip_dir] + shlex.split(pyqt.pyqt_sip_flags) + [sipf]
            self.info(' '.join(cmd))
            subprocess.check_call(cmd)
        module = self.j(src_dir, self.b(dest))
        if self.newer(dest, [sbf]+qt_objects):
            mf = self.j(src_dir, 'Makefile')
            makefile = QtGuiModuleMakefile(configuration=pyqt, build_file=sbf,
                    makefile=mf, universal=OSX_SDK, qt=1)
            makefile.extra_lflags = qt_objects
            makefile.extra_include_dirs = ext.inc_dirs
            makefile.generate()
            if leopard_build:
                raw = open(mf, 'rb').read()
                raw = raw.replace('ppc64 x86_64', 'x86_64')
                for x in ('ppc64', 'ppc', 'i386'):
                    raw = raw.replace(x, 'x86_64')
                open(mf, 'wb').write(raw)

            subprocess.check_call([make, '-f', mf], cwd=src_dir)
            shutil.copy2(module, dest)

    def clean(self):
        for ext in extensions:
            dest = self.dest(ext)
            for x in (dest, dest+'.manifest'):
                if os.path.exists(x):
                    os.remove(x)
        shutil.rmtree(self.j(self.d(self.SRC), 'build'))











