#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os, shlex, subprocess, glob, shutil
from distutils import sysconfig
from multiprocessing import cpu_count

from PyQt4.pyqtconfig import QtGuiModuleMakefile

from setup import Command, islinux, isbsd, isosx, SRC, iswindows
from setup.build_environment import (fc_inc, fc_lib, chmlib_inc_dirs, fc_error,
        podofo_inc, podofo_lib, podofo_error, pyqt, OSX_SDK, NMAKE, QMAKE,
        msvc, MT, win_inc, win_lib, win_ddk, magick_inc_dirs, magick_lib_dirs,
        magick_libs, chmlib_lib_dirs, sqlite_inc_dirs, icu_inc_dirs,
        icu_lib_dirs, win_ddk_lib_dirs)
MT
isunix = islinux or isosx or isbsd

make = 'make' if isunix else NMAKE

class Extension(object):

    def absolutize(self, paths):
        return list(set([x if os.path.isabs(x) else os.path.join(SRC, x.replace('/',
            os.sep)) for x in paths]))


    def __init__(self, name, sources, **kwargs):
        self.name = name
        self.needs_cxx = bool([1 for x in sources if os.path.splitext(x)[1] in
            ('.cpp', '.c++', '.cxx')])
        self.sources = self.absolutize(sources)
        self.headers = self.absolutize(kwargs.get('headers', []))
        self.sip_files = self.absolutize(kwargs.get('sip_files', []))
        self.inc_dirs = self.absolutize(kwargs.get('inc_dirs', []))
        self.lib_dirs = self.absolutize(kwargs.get('lib_dirs', []))
        self.extra_objs = self.absolutize(kwargs.get('extra_objs', []))
        self.error = kwargs.get('error', None)
        self.libraries = kwargs.get('libraries', [])
        self.cflags = kwargs.get('cflags', [])
        self.ldflags = kwargs.get('ldflags', [])
        self.optional = kwargs.get('optional', False)
        self.needs_ddk = kwargs.get('needs_ddk', False)

reflow_sources = glob.glob(os.path.join(SRC, 'calibre', 'ebooks', 'pdf', '*.cpp'))
reflow_headers = glob.glob(os.path.join(SRC, 'calibre', 'ebooks', 'pdf', '*.h'))

pdfreflow_libs = []
if iswindows:
    pdfreflow_libs = ['advapi32', 'User32', 'Gdi32', 'zlib']

icu_libs = ['icudata', 'icui18n', 'icuuc', 'icuio']
icu_cflags = []
if iswindows:
    icu_libs = ['icudt', 'icuin', 'icuuc', 'icuio']
if isosx:
    icu_libs = ['icucore']
    icu_cflags = ['-DU_DISABLE_RENAMING'] # Needed to use system libicucore.dylib


extensions = [

    Extension('speedup',
        ['calibre/utils/speedup.c'],
        ),

    Extension('icu',
        ['calibre/utils/icu.c'],
        libraries=icu_libs,
        lib_dirs=icu_lib_dirs,
        inc_dirs=icu_inc_dirs,
        cflags=icu_cflags
        ),

    Extension('sqlite_custom',
        ['calibre/library/sqlite_custom.c'],
        inc_dirs=sqlite_inc_dirs
        ),

    Extension('chmlib',
            ['calibre/utils/chm/swig_chm.c'],
            libraries=['ChmLib' if iswindows else 'chm'],
            inc_dirs=chmlib_inc_dirs,
            lib_dirs=chmlib_lib_dirs,
            cflags=["-DSWIG_COBJECT_TYPES"]),

    Extension('chm_extra',
            ['calibre/utils/chm/extra.c'],
            libraries=['ChmLib' if iswindows else 'chm'],
            inc_dirs=chmlib_inc_dirs,
            lib_dirs=chmlib_lib_dirs,
            cflags=["-D__PYTHON__"]),

    Extension('magick',
        ['calibre/utils/magick/magick.c'],
        headers=['calibre/utils/magick/magick_constants.h'],
        libraries=magick_libs,
        lib_dirs=magick_lib_dirs,
        inc_dirs=magick_inc_dirs
        ),

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

    Extension('podofo',
                    [
                        'calibre/utils/podofo/utils.cpp',
                        'calibre/utils/podofo/doc.cpp',
                        'calibre/utils/podofo/outline.cpp',
                        'calibre/utils/podofo/podofo.cpp',
                    ],
                    headers=[
                        'calibre/utils/podofo/global.h',
                    ],
                    libraries=['podofo'],
                    lib_dirs=[podofo_lib],
                    inc_dirs=[podofo_inc, os.path.dirname(podofo_inc)],
                    error=podofo_error),

    Extension('pictureflow',
                ['calibre/gui2/pictureflow/pictureflow.cpp'],
                inc_dirs = ['calibre/gui2/pictureflow'],
                headers = ['calibre/gui2/pictureflow/pictureflow.h'],
                sip_files = ['calibre/gui2/pictureflow/pictureflow.sip']
                ),

    Extension('progress_indicator',
                ['calibre/gui2/progress_indicator/QProgressIndicator.cpp'],
                inc_dirs = ['calibre/gui2/progress_indicator'],
                headers = ['calibre/gui2/progress_indicator/QProgressIndicator.h'],
                sip_files = ['calibre/gui2/progress_indicator/QProgressIndicator.sip']
                ),

    ]


if iswindows:
    extensions.extend([
        Extension('winutil',
                ['calibre/utils/windows/winutil.c'],
                libraries=['shell32', 'setupapi', 'wininet'],
                cflags=['/X']
                ),
        Extension('wpd',
            [
                'calibre/devices/mtp/windows/utils.cpp',
                'calibre/devices/mtp/windows/device_enumeration.cpp',
                'calibre/devices/mtp/windows/content_enumeration.cpp',
                'calibre/devices/mtp/windows/device.cpp',
                'calibre/devices/mtp/windows/wpd.cpp',
            ],
            headers=[
                'calibre/devices/mtp/windows/global.h',
            ],
            libraries=['ole32', 'portabledeviceguids', 'user32'],
            # needs_ddk=True,
            cflags=['/X']
            ),
        ])

if isosx:
    extensions.append(Extension('usbobserver',
                ['calibre/devices/usbobserver/usbobserver.c'],
                ldflags=['-framework', 'CoreServices', '-framework', 'IOKit'])
            )

if islinux or isosx:
    extensions.append(Extension('libusb',
        ['calibre/devices/libusb/libusb.c'],
        libraries=['usb-1.0']
    ))

    extensions.append(Extension('libmtp',
        [
        'calibre/devices/mtp/unix/devices.c',
        'calibre/devices/mtp/unix/libmtp.c'
        ],
        headers=[
        'calibre/devices/mtp/unix/devices.h',
        'calibre/devices/mtp/unix/upstream/music-players.h',
        'calibre/devices/mtp/unix/upstream/device-flags.h',
        ],
        libraries=['mtp']
    ))

if isunix:
    cc = os.environ.get('CC', 'gcc')
    cxx = os.environ.get('CXX', 'g++')
    cflags = os.environ.get('OVERRIDE_CFLAGS',
        '-O3 -Wall -DNDEBUG -fno-strict-aliasing -pipe')
    cflags = shlex.split(cflags) + ['-fPIC']
    ldflags = os.environ.get('OVERRIDE_LDFLAGS', '-Wall')
    ldflags = shlex.split(ldflags)
    cflags += shlex.split(os.environ.get('CFLAGS', ''))
    ldflags += shlex.split(os.environ.get('LDFLAGS', ''))

if islinux:
    cflags.append('-pthread')
    ldflags.append('-shared')
    cflags.append('-I'+sysconfig.get_python_inc())
    ldflags.append('-lpython'+sysconfig.get_python_version())


if isbsd:
    cflags.append('-pthread')
    ldflags.append('-shared')
    cflags.append('-I'+sysconfig.get_python_inc())
    ldflags.append('-lpython'+sysconfig.get_python_version())


if isosx:
    x, p = ('i386', 'x86_64')
    archs = ['-arch', x, '-arch', p, '-isysroot',
                OSX_SDK]
    cflags.append('-D_OSX')
    cflags.extend(archs)
    ldflags.extend(archs)
    ldflags.extend('-bundle -undefined dynamic_lookup'.split())
    cflags.extend(['-fno-common', '-dynamic'])
    cflags.append('-I'+sysconfig.get_python_inc())


if iswindows:
    cc = cxx = msvc.cc
    cflags = '/c /nologo /Ox /MD /W3 /EHsc /DNDEBUG'.split()
    ldflags = '/DLL /nologo /INCREMENTAL:NO /NODEFAULTLIB:libcmt.lib'.split()
    #cflags = '/c /nologo /Ox /MD /W3 /EHsc /Zi'.split()
    #ldflags = '/DLL /nologo /INCREMENTAL:NO /DEBUG'.split()

    for p in win_inc:
        cflags.append('-I'+p)
    for p in win_lib:
        ldflags.append('/LIBPATH:'+p)
    cflags.append('-I%s'%sysconfig.get_python_inc())
    ldflags.append('/LIBPATH:'+os.path.join(sysconfig.PREFIX, 'libs'))


class Build(Command):

    short_description = 'Build calibre C/C++ extension modules'

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
        choices = [e.name for e in extensions]+['all', 'style']
        parser.add_option('-1', '--only', choices=choices, default='all',
                help=('Build only the named extension. Available: '+
                    ', '.join(choices)+'. Default:%default'))
        parser.add_option('--no-compile', default=False, action='store_true',
                help='Skip compiling all C/C++ extensions.')

    def run(self, opts):
        if opts.no_compile:
            self.info('--no-compile specified, skipping compilation')
            return
        self.obj_dir = os.path.join(os.path.dirname(SRC), 'build', 'objects')
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        if opts.only in {'all', 'style'}:
            self.build_style(self.j(self.SRC, 'calibre', 'plugins'))
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
        if ext.needs_ddk:
            ddk_flags = ['-I'+x for x in win_ddk]
            cflags.extend(ddk_flags)
            ldflags.extend(['/LIBPATH:'+x for x in win_ddk_lib_dirs])
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
                self.check_call(cmd)

        dest = self.dest(ext)
        elib = self.lib_dirs_to_ldflags(ext.lib_dirs)
        xlib = self.libraries_to_ldflags(ext.libraries)
        if self.newer(dest, objects):
            print 'Linking', ext.name
            cmd = [linker]
            if iswindows:
                cmd += ldflags + ext.ldflags + elib + xlib + \
                    ['/EXPORT:init'+ext.name] + objects + ext.extra_objs + ['/OUT:'+dest]
            else:
                cmd += objects + ext.extra_objs + ['-o', dest] + ldflags + ext.ldflags + elib + xlib
            self.info('\n\n', ' '.join(cmd), '\n\n')
            self.check_call(cmd)
            if iswindows:
                #manifest = dest+'.manifest'
                #cmd = [MT, '-manifest', manifest, '-outputresource:%s;2'%dest]
                #self.info(*cmd)
                #self.check_call(cmd)
                #os.remove(manifest)
                for x in ('.exp', '.lib'):
                    x = os.path.splitext(dest)[0]+x
                    if os.path.exists(x):
                        os.remove(x)

    def check_call(self, *args, **kwargs):
        """print cmdline if an error occured

        If something is missing (qmake e.g.) you get a non-informative error
         self.check_call(qmc + [ext.name+'.pro'])
         so you would have to look a the source to see the actual command.
        """
        try:
            subprocess.check_call(*args, **kwargs)
        except:
            cmdline = ' '.join(['"%s"' % (arg) if ' ' in arg else arg for arg in args[0]])
            print "Error while executing: %s\n" % (cmdline)
            raise

    def build_style(self, dest):
        self.info('\n####### Building calibre style', '#'*7)
        sdir = self.j(self.SRC, 'qtcurve')
        def path(x):
            x=self.j(sdir, x)
            return ('"%s"'%x).replace(os.sep, '/')
        headers = [
           "common/colorutils.h",
           "common/common.h",
           "common/config_file.h",
           "style/blurhelper.h",
           "style/fixx11h.h",
           "style/pixmaps.h",
           "style/qtcurve.h",
           "style/shortcuthandler.h",
           "style/utils.h",
           "style/windowmanager.h",
        ]
        sources = [
           "common/colorutils.c",
           "common/common.c",
           "common/config_file.c",
           "style/blurhelper.cpp",
           "style/qtcurve.cpp",
           "style/shortcuthandler.cpp",
           "style/utils.cpp",
           "style/windowmanager.cpp",
        ]
        if not iswindows and not isosx:
            headers.append( "style/shadowhelper.h")
            sources.append('style/shadowhelper.cpp')

        pro = textwrap.dedent('''
        TEMPLATE = lib
        CONFIG += qt plugin release
        CONFIG -= embed_manifest_dll
        VERSION = 1.0.0
        DESTDIR = .
        TARGET = calibre
        QT *= svg
        INCLUDEPATH *= {conf} {inc}
        win32-msvc*:DEFINES *= _CRT_SECURE_NO_WARNINGS

        # Force C++ language
        *g++*:QMAKE_CFLAGS *= -x c++
        *msvc*:QMAKE_CFLAGS *= -TP
        *msvc*:QMAKE_CXXFLAGS += /MP

        ''').format(conf=path(''), inc=path('common'))
        if isosx:
            pro += '\nCONFIG += x86 x86_64\n'
        else:
            pro += '\nunix:QT *= dbus\n'

        for x in headers:
            pro += 'HEADERS += %s\n'%path(x)
        for x in sources:
            pro += 'SOURCES += %s\n'%path(x)
        odir = self.j(self.d(self.SRC), 'build', 'qtcurve')
        if not os.path.exists(odir):
            os.makedirs(odir)
        ocwd = os.getcwdu()
        os.chdir(odir)
        try:
            if not os.path.exists('qtcurve.pro') or (open('qtcurve.pro',
                'rb').read() != pro):
                with open('qtcurve.pro', 'wb') as f:
                    f.write(pro)
            qmc = [QMAKE, '-o', 'Makefile']
            if iswindows:
                qmc += ['-spec', 'win32-msvc2008']
            self.check_call(qmc + ['qtcurve.pro'])
            self.check_call([make]+([] if iswindows else ['-j%d'%(cpu_count()
                or 1)]))
            src = (glob.glob('*.so') + glob.glob('release/*.dll') +
                    glob.glob('*.dylib'))
            ext = 'pyd' if iswindows else 'so'
            shutil.copy2(src[0], self.j(dest, 'calibre_style.'+ext))
        finally:
            os.chdir(ocwd)

    def build_qt_objects(self, ext):
        obj_pat = 'release\\*.obj' if iswindows else '*.o'
        objects = glob.glob(obj_pat)
        if not objects or self.newer(objects, ext.sources+ext.headers):
            archs = 'x86 x86_64'
            pro = textwrap.dedent('''\
                TARGET   = %s
                TEMPLATE = lib
                HEADERS  = %s
                SOURCES  = %s
                VERSION  = 1.0.0
                CONFIG   += %s
            ''')%(ext.name, ' '.join(ext.headers), ' '.join(ext.sources), archs)
            pro = pro.replace('\\', '\\\\')
            open(ext.name+'.pro', 'wb').write(pro)
            qmc = [QMAKE, '-o', 'Makefile']
            if iswindows:
                qmc += ['-spec', 'win32-msvc2008']
            self.check_call(qmc + [ext.name+'.pro'])
            self.check_call([make, '-f', 'Makefile'])
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
            self.check_call(cmd)
        module = self.j(src_dir, self.b(dest))
        if self.newer(dest, [sbf]+qt_objects):
            mf = self.j(src_dir, 'Makefile')
            makefile = QtGuiModuleMakefile(configuration=pyqt, build_file=sbf,
                    makefile=mf, universal=OSX_SDK, qt=1)
            makefile.extra_lflags = qt_objects
            makefile.extra_include_dirs = ext.inc_dirs
            makefile.generate()

            self.check_call([make, '-f', mf], cwd=src_dir)
            shutil.copy2(module, dest)

    def clean(self):
        for ext in extensions:
            dest = self.dest(ext)
            for x in (dest, dest+'.manifest'):
                if os.path.exists(x):
                    os.remove(x)
        build_dir = self.j(self.d(self.SRC), 'build')
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)




