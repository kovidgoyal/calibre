#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os, shlex, subprocess, glob, shutil, re, sys
from distutils import sysconfig

from setup import Command, islinux, isbsd, isosx, SRC, iswindows, __version__
from setup.build_environment import (
    chmlib_inc_dirs, podofo_inc, podofo_lib, podofo_error, pyqt, NMAKE, QMAKE,
    msvc, win_inc, win_lib, magick_inc_dirs, magick_lib_dirs, magick_libs,
    chmlib_lib_dirs, sqlite_inc_dirs, icu_inc_dirs, icu_lib_dirs, ft_libs,
    ft_lib_dirs, ft_inc_dirs, cpu_count, zlib_libs, zlib_lib_dirs,
    zlib_inc_dirs, is64bit, glib_flags, fontconfig_flags, openssl_inc_dirs,
    openssl_lib_dirs)
from setup.parallel_build import create_job, parallel_build
isunix = islinux or isosx or isbsd

make = 'make' if isunix else NMAKE
py_lib = os.path.join(sys.prefix, 'libs', 'python%d%d.lib' % sys.version_info[:2])

class Extension(object):

    @classmethod
    def absolutize(cls, paths):
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
        of = kwargs.get('optimize_level', None)
        if of is None:
            of = '/Ox' if iswindows else '-O3'
        else:
            flag = '/O%d' if iswindows else '-O%d'
            of = flag % of
        self.cflags.insert(0, of)
        self.qt_private_headers = kwargs.get('qt_private', [])

    def preflight(self, obj_dir, compiler, linker, builder, cflags, ldflags):
        pass

reflow_sources = glob.glob(os.path.join(SRC, 'calibre', 'ebooks', 'pdf', '*.cpp'))
reflow_headers = glob.glob(os.path.join(SRC, 'calibre', 'ebooks', 'pdf', '*.h'))

icu_libs = ['icudata', 'icui18n', 'icuuc', 'icuio']
icu_cflags = []
if iswindows:
    icu_libs = ['icudt', 'icuin', 'icuuc', 'icuio']

extensions = [

    Extension('hunspell',
              ['hunspell/'+x for x in
                'affentry.cxx affixmgr.cxx csutil.cxx dictmgr.cxx filemgr.cxx hashmgr.cxx hunspell.cxx phonet.cxx replist.cxx suggestmgr.cxx'.split()
                ] + ['calibre/utils/spell/hunspell_wrapper.cpp',],
              inc_dirs=['hunspell'],
              cflags='/DHUNSPELL_STATIC /D_CRT_SECURE_NO_WARNINGS /DUNICODE /D_UNICODE'.split() if iswindows else ['-DHUNSPELL_STATIC'],
              optimize_level=2,
              ),

    Extension('_regex',
              ['regex/_regex.c', 'regex/_regex_unicode.c'],
              headers=['regex/_regex.h'],
              optimize_level=2,
              ),

    Extension('speedup',
        ['calibre/utils/speedup.c'],
        libraries=[] if iswindows else ['m']
        ),

    Extension('certgen',
        ['calibre/utils/certgen.c'],
        libraries=['libeay32'] if iswindows else ['crypto'],
        # Apple has deprecated openssl in OSX, so we need this, until we
        # build our own private copy of openssl
        cflags=['-Wno-deprecated-declarations'] if isosx else [],
        inc_dirs=openssl_inc_dirs, lib_dirs=openssl_lib_dirs,
        ),

    Extension('html',
        ['calibre/gui2/tweak_book/editor/syntax/html.c'],
        ),

    Extension('tokenizer',
        ['tinycss/tokenizer.c'],
        ),

    Extension('_patiencediff_c',
        ['calibre/gui2/tweak_book/diff/_patiencediff_c.c'],
        ),

    Extension('icu',
        ['calibre/utils/icu.c'],
        headers=['calibre/utils/icu_calibre_utils.h'],
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
        inc_dirs=magick_inc_dirs,
        cflags=['-DMAGICKCORE_QUANTUM_DEPTH=16', '-DMAGICKCORE_HDRI_ENABLE=0']
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

    Extension('freetype',
        ['calibre/utils/fonts/freetype.cpp'],
        inc_dirs=ft_inc_dirs,
        libraries=ft_libs,
        lib_dirs=ft_lib_dirs),

    Extension('woff',
        ['calibre/utils/fonts/woff/main.c',
         'calibre/utils/fonts/woff/woff.c'],
        headers=[
        'calibre/utils/fonts/woff/woff.h',
        'calibre/utils/fonts/woff/woff-private.h'],
        libraries=zlib_libs,
        lib_dirs=zlib_lib_dirs,
        inc_dirs=zlib_inc_dirs,
        ),


    Extension('msdes',
                ['calibre/utils/msdes/msdesmodule.c',
                        'calibre/utils/msdes/des.c'],
                headers=['calibre/utils/msdes/spr.h',
                        'calibre/utils/msdes/d3des.h'],
                inc_dirs=['calibre/utils/msdes']),

    Extension('cPalmdoc',
        ['calibre/ebooks/compression/palmdoc.c']),

    Extension('bzzdec',
        ['calibre/ebooks/djvu/bzzdecoder.c'],
        inc_dirs=(['calibre/utils/chm'] if iswindows else [])  # For stdint.h
    ),

    Extension('matcher',
        ['calibre/utils/matcher.c'],
        headers=['calibre/utils/icu_calibre_utils.h'],
        libraries=icu_libs,
        lib_dirs=icu_lib_dirs,
        cflags=icu_cflags,
        inc_dirs=icu_inc_dirs
    ),

    Extension('podofo',
                    [
                        'calibre/utils/podofo/utils.cpp',
                        'calibre/utils/podofo/output.cpp',
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
                inc_dirs=['calibre/gui2/pictureflow'],
                headers=['calibre/gui2/pictureflow/pictureflow.h'],
                sip_files=['calibre/gui2/pictureflow/pictureflow.sip']
                ),

    Extension('progress_indicator',
                ['calibre/gui2/progress_indicator/QProgressIndicator.cpp'],
                inc_dirs=['calibre/gui2/progress_indicator'],
                headers=['calibre/gui2/progress_indicator/QProgressIndicator.h'],
                sip_files=['calibre/gui2/progress_indicator/QProgressIndicator.sip']
                ),

    Extension('qt_hack',
                ['calibre/ebooks/pdf/render/qt_hack.cpp'],
                inc_dirs=['calibre/ebooks/pdf/render'],
                headers=['calibre/ebooks/pdf/render/qt_hack.h'],
                qt_private=['core', 'gui'],
                sip_files=['calibre/ebooks/pdf/render/qt_hack.sip']
                ),

    Extension('unrar',
              ['unrar/%s.cpp'%(x.partition('.')[0]) for x in '''
               rar.o strlist.o strfn.o pathfn.o savepos.o smallfn.o global.o file.o
               filefn.o filcreat.o archive.o arcread.o unicode.o system.o
               isnt.o crypt.o crc.o rawread.o encname.o resource.o match.o
               timefn.o rdwrfn.o consio.o options.o ulinks.o errhnd.o rarvm.o
               secpassword.o rijndael.o getbits.o sha1.o extinfo.o extract.o
               volume.o list.o find.o unpack.o cmddata.o filestr.o scantree.o
               '''.split()] + ['calibre/utils/unrar.cpp'],
              inc_dirs=['unrar'],
              cflags=[('/' if iswindows else '-') + x for x in (
                  'DSILENT', 'DRARDLL', 'DUNRAR')] + (
                  [] if iswindows else ['-D_FILE_OFFSET_BITS=64',
                                        '-D_LARGEFILE_SOURCE']),
              optimize_level=2,
              libraries=['User32', 'Advapi32', 'kernel32', 'Shell32'] if iswindows else []
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
            libraries=['ole32', 'oleaut32', 'portabledeviceguids', 'user32'],
            cflags=['/X']
            ),
        Extension('winfonts',
                ['calibre/utils/fonts/winfonts.cpp'],
                libraries=['Gdi32', 'User32'],
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
    debug = ''
    # debug = '-ggdb'
    cflags = os.environ.get('OVERRIDE_CFLAGS',
        '-Wall -DNDEBUG %s -fno-strict-aliasing -pipe' % debug)
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
    cflags.append('-D_OSX')
    ldflags.extend('-bundle -undefined dynamic_lookup'.split())
    cflags.extend(['-fno-common', '-dynamic'])
    cflags.append('-I'+sysconfig.get_python_inc())

if iswindows:
    cc = cxx = msvc.cc
    cflags = '/c /nologo /MD /W3 /EHsc /DNDEBUG'.split()
    ldflags = '/DLL /nologo /INCREMENTAL:NO /NODEFAULTLIB:libcmt.lib'.split()
    # cflags = '/c /nologo /Ox /MD /W3 /EHsc /Zi'.split()
    # ldflags = '/DLL /nologo /INCREMENTAL:NO /DEBUG'.split()
    if is64bit:
        cflags.append('/GS-')

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

           POPPLER_INC_DIR - poppler header files
           POPPLER_LIB_DIR - poppler-qt4 library

           PODOFO_INC_DIR - podofo header files
           PODOFO_LIB_DIR - podofo library files

           QMAKE          - Path to qmake
           SIP_BIN        - Path to the sip binary
           VS90COMNTOOLS  - Location of Microsoft Visual Studio 9 Tools (windows only)

        ''')

    def add_options(self, parser):
        choices = [e.name for e in extensions]+['all', 'headless']
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
        if opts.only in {'all', 'headless'}:
            self.build_headless()

    def dest(self, ext):
        ex = '.pyd' if iswindows else '.so'
        return os.path.join(SRC, 'calibre', 'plugins', getattr(ext, 'name', ext))+ex

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
        obj_dir = self.j(self.obj_dir, ext.name)
        ext.preflight(obj_dir, compiler, linker, self, cflags, ldflags)
        einc = self.inc_dirs_to_cflags(ext.inc_dirs)
        if not os.path.exists(obj_dir):
            os.makedirs(obj_dir)

        jobs = []
        for src in ext.sources:
            obj = self.j(obj_dir, os.path.splitext(self.b(src))[0]+'.o')
            objects.append(obj)
            if self.newer(obj, [src]+ext.headers):
                inf = '/Tp' if src.endswith('.cpp') or src.endswith('.cxx') else '/Tc'
                sinc = [inf+src] if iswindows else ['-c', src]
                oinc = ['/Fo'+obj] if iswindows else ['-o', obj]
                cmd = [compiler] + cflags + ext.cflags + einc + sinc + oinc
                jobs.append(create_job(cmd))
        if jobs:
            self.info('Compiling', ext.name)
            if not parallel_build(jobs, self.info):
                raise SystemExit(1)

        dest = self.dest(ext)
        elib = self.lib_dirs_to_ldflags(ext.lib_dirs)
        xlib = self.libraries_to_ldflags(ext.libraries)
        if self.newer(dest, objects+ext.extra_objs):
            self.info('Linking', ext.name)
            cmd = [linker]
            if iswindows:
                cmd += ldflags + ext.ldflags + elib + xlib + \
                    ['/EXPORT:init'+ext.name] + objects + ext.extra_objs + ['/OUT:'+dest]
            else:
                cmd += objects + ext.extra_objs + ['-o', dest] + ldflags + ext.ldflags + elib + xlib
            self.info('\n\n', ' '.join(cmd), '\n\n')
            self.check_call(cmd)
            if iswindows:
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

    def build_headless(self):
        if iswindows or isosx:
            return  # Dont have headless operation on these platforms
        from PyQt5.QtCore import QT_VERSION
        self.info('\n####### Building headless QPA plugin', '#'*7)
        a = Extension.absolutize
        headers = a([
            'calibre/headless/headless_backingstore.h',
            'calibre/headless/headless_integration.h',
        ])
        sources = a([
            'calibre/headless/main.cpp',
            'calibre/headless/headless_backingstore.cpp',
            'calibre/headless/headless_integration.cpp',
        ])
        if QT_VERSION >= 0x50401:
            headers.extend(a(['calibre/headless/fontconfig_database.h']))
            sources.extend(a(['calibre/headless/fontconfig_database.cpp']))
        others = a(['calibre/headless/headless.json'])
        target = self.dest('headless')
        if not self.newer(target, headers + sources + others):
            return
        # Arch and possibly other distros (fedora?) monkey patches qmake as a
        # result of which it fails to add glib-2.0 and freetype2 to the list of
        # library dependencies. Compiling QPA plugins uses the static
        # libQt5PlatformSupport.a which needs glib to be specified after it for
        # linking to succeed, so we add it to QMAKE_LIBS_PRIVATE (we cannot use
        # LIBS as that would put -lglib-2.0 before libQt5PlatformSupport. See
        # https://bugs.archlinux.org/task/38819

        pro = textwrap.dedent(
        '''\
            TARGET = headless
            PLUGIN_TYPE = platforms
            PLUGIN_CLASS_NAME = HeadlessIntegrationPlugin
            load(qt_plugin)
            QT += core-private gui-private platformsupport-private
            HEADERS = {headers}
            SOURCES = {sources}
            OTHER_FILES = {others}
            INCLUDEPATH += {freetype}
            DESTDIR = {destdir}
            CONFIG -= create_cmake  # Prevent qmake from generating a cmake build file which it puts in the calibre src directory
            QMAKE_LIBS_PRIVATE += {glib} {fontconfig}
            ''').format(
                headers=' '.join(headers), sources=' '.join(sources), others=' '.join(others), destdir=self.d(
                    target), glib=glib_flags, fontconfig=fontconfig_flags, freetype=' '.join(ft_inc_dirs))
        bdir = self.j(self.d(self.SRC), 'build', 'headless')
        if not os.path.exists(bdir):
            os.makedirs(bdir)
        pf = self.j(bdir, 'headless.pro')
        open(self.j(bdir, '.qmake.conf'), 'wb').close()
        with open(pf, 'wb') as f:
            f.write(pro.encode('utf-8'))
        cwd = os.getcwd()
        os.chdir(bdir)
        try:
            self.check_call([QMAKE] + [self.b(pf)])
            self.check_call([make] + ['-j%d'%(cpu_count or 1)])
        finally:
            os.chdir(cwd)

    def build_sip_files(self, ext, src_dir):
        sip_files = ext.sip_files
        ext.sip_files = []
        sipf = sip_files[0]
        sbf = self.j(src_dir, self.b(sipf)+'.sbf')
        if self.newer(sbf, [sipf]+ext.headers):
            cmd = [pyqt['sip_bin'], '-w', '-c', src_dir, '-b', sbf, '-I'+
                    pyqt['pyqt_sip_dir']] + shlex.split(pyqt['sip_flags']) + [sipf]
            self.info(' '.join(cmd))
            self.check_call(cmd)
            self.info('')
        raw = open(sbf, 'rb').read().decode('utf-8')
        def read(x):
            ans = re.search('^%s\s*=\s*(.+)$' % x, raw, flags=re.M).group(1).strip()
            if x != 'target':
                ans = ans.split()
            return ans
        return {x:read(x) for x in ('target', 'sources', 'headers')}

    def build_pyqt_extension(self, ext, dest):
        pyqt_dir = self.j(self.d(self.SRC), 'build', 'pyqt')
        src_dir = self.j(pyqt_dir, ext.name)
        if not os.path.exists(src_dir):
            os.makedirs(src_dir)
        sip = self.build_sip_files(ext, src_dir)
        pro = textwrap.dedent(
        '''\
        TEMPLATE = lib
        CONFIG += release plugin
        QT += widgets
        TARGET = {target}
        HEADERS = {headers}
        SOURCES = {sources}
        INCLUDEPATH += {sipinc} {pyinc}
        VERSION = {ver}
        win32 {{
            LIBS += {py_lib}
            TARGET_EXT = .dll
        }}
        macx {{
            QMAKE_LFLAGS += "-undefined dynamic_lookup"
        }}
        ''').format(
            target=sip['target'], headers=' '.join(sip['headers'] + ext.headers), sources=' '.join(ext.sources + sip['sources']),
            sipinc=pyqt['sip_inc_dir'], pyinc=sysconfig.get_python_inc(), py_lib=py_lib,
            ver=__version__
        )
        for incdir in ext.inc_dirs:
            pro += '\nINCLUDEPATH += ' + incdir
        if not iswindows and not isosx:
            # Ensure that only the init symbol is exported
            pro += '\nQMAKE_LFLAGS += -Wl,--version-script=%s.exp' % sip['target']
            with open(os.path.join(src_dir, sip['target'] + '.exp'), 'wb') as f:
                f.write(('{ global: init%s; local: *; };' % sip['target']).encode('utf-8'))
        if ext.qt_private_headers:
            qph = ' '.join(x + '-private' for x in ext.qt_private_headers)
            pro += '\nQT += ' + qph
        proname = '%s.pro' % sip['target']
        with open(os.path.join(src_dir, proname), 'wb') as f:
            f.write(pro.encode('utf-8'))
        cwd = os.getcwdu()
        qmc = []
        if iswindows:
            qmc += ['-spec', 'win32-msvc2008']
        fext = 'dll' if iswindows else 'dylib' if isosx else 'so'
        name = '%s%s.%s' % ('release/' if iswindows else 'lib', sip['target'], fext)
        try:
            os.chdir(src_dir)
            if self.newer(dest, sip['headers'] + sip['sources'] + ext.sources + ext.headers):
                self.check_call([QMAKE] + qmc + [proname])
                self.check_call([make]+([] if iswindows else ['-j%d'%(cpu_count or 1)]))
                shutil.copy2(os.path.realpath(name), dest)
                if iswindows:
                    shutil.copy2(name + '.manifest', dest + '.manifest')

        finally:
            os.chdir(cwd)

    def clean(self):
        for ext in extensions:
            dest = self.dest(ext)
            for x in (dest, dest+'.manifest'):
                if os.path.exists(x):
                    os.remove(x)
        build_dir = self.j(self.d(self.SRC), 'build')
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)




