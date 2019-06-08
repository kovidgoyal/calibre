#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import errno
import glob
import json
import operator
import os
import plistlib
import runpy
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from functools import partial, reduce
from itertools import repeat

from bypy.constants import (
    OUTPUT_DIR, PREFIX, PYTHON, SRC as CALIBRE_DIR, python_major_minor_version
)
from bypy.utils import current_dir, mkdtemp, py_compile, timeit, walk

abspath, join, basename, dirname = os.path.abspath, os.path.join, os.path.basename, os.path.dirname
iv = globals()['init_env']
calibre_constants = iv['calibre_constants']
QT_DLLS, QT_PLUGINS, PYQT_MODULES = iv['QT_DLLS'], iv['QT_PLUGINS'], iv['PYQT_MODULES']
py_ver = '.'.join(map(str, python_major_minor_version()))
sign_app = runpy.run_path(join(dirname(abspath(__file__)), 'sign.py'))['sign_app']

QT_PREFIX = os.path.join(PREFIX, 'qt')
QT_FRAMEWORKS = [x.replace('5', '') for x in QT_DLLS]

ENV = dict(
    FONTCONFIG_PATH='@executable_path/../Resources/fonts',
    FONTCONFIG_FILE='@executable_path/../Resources/fonts/fonts.conf',
    QT_PLUGIN_PATH='@executable_path/../MacOS/qt-plugins',
    PYTHONIOENCODING='UTF-8',
    SSL_CERT_FILE='@executable_path/../Resources/resources/mozilla-ca-certs.pem',
)
APPNAME, VERSION = calibre_constants['appname'], calibre_constants['version']
basenames, main_modules, main_functions = calibre_constants['basenames'], calibre_constants['modules'], calibre_constants['functions']


def compile_launcher_lib(contents_dir, gcc, base):
    print('\tCompiling calibre_launcher.dylib')
    fd = join(contents_dir, 'Frameworks')
    dest = join(fd, 'calibre-launcher.dylib')
    src = join(base, 'util.c')
    cmd = [gcc] + '-Wall -dynamiclib -std=gnu99'.split() + [src] + \
        ['-I' + base] + \
        ['-I%s/python/Python.framework/Versions/Current/Headers' % PREFIX] + \
        '-current_version 1.0 -compatibility_version 1.0'.split() + \
        '-fvisibility=hidden -o'.split() + [dest] + \
        ['-install_name',
         '@executable_path/../Frameworks/' + os.path.basename(dest)] + \
        [('-F%s/python' % PREFIX), '-framework', 'Python', '-framework', 'CoreFoundation', '-headerpad_max_install_names']
    # print('\t'+' '.join(cmd))
    sys.stdout.flush()
    subprocess.check_call(cmd)
    return dest


gcc = os.environ.get('CC', 'clang')


def compile_launchers(contents_dir, xprograms, pyver):
    base = dirname(abspath(__file__))
    lib = compile_launcher_lib(contents_dir, gcc, base)
    src = open(join(base, 'launcher.c'), 'rb').read().decode('utf-8')
    env, env_vals = [], []
    for key, val in ENV.items():
        env.append('"%s"' % key)
        env_vals.append('"%s"' % val)
    env = ', '.join(env) + ', '
    env_vals = ', '.join(env_vals) + ', '
    src = src.replace('/*ENV_VARS*/', env)
    src = src.replace('/*ENV_VAR_VALS*/', env_vals)
    programs = [lib]
    for program, x in xprograms.items():
        module, func, ptype = x
        print('\tCompiling', program)
        out = join(contents_dir, 'MacOS', program)
        programs.append(out)
        psrc = src.replace('**PROGRAM**', program)
        psrc = psrc.replace('**MODULE**', module)
        psrc = psrc.replace('**FUNCTION**', func)
        psrc = psrc.replace('**PYVER**', pyver)
        psrc = psrc.replace('**IS_GUI**', ('1' if ptype == 'gui' else '0'))
        fsrc = '/tmp/%s.c' % program
        with open(fsrc, 'wb') as f:
            f.write(psrc.encode('utf-8'))
        cmd = [gcc, '-Wall', '-I' + base, fsrc, lib, '-o', out,
               '-headerpad_max_install_names']
        # print('\t'+' '.join(cmd))
        sys.stdout.flush()
        subprocess.check_call(cmd)
    return programs


def flipwritable(fn, mode=None):
    """
    Flip the writability of a file and return the old mode. Returns None
    if the file is already writable.
    """
    if os.access(fn, os.W_OK):
        return None
    old_mode = os.stat(fn).st_mode
    os.chmod(fn, stat.S_IWRITE | old_mode)
    return old_mode


STRIPCMD = ['/usr/bin/strip', '-x', '-S', '-']


def strip_files(files, argv_max=(256 * 1024)):
    """
    Strip a list of files
    """
    tostrip = [(fn, flipwritable(fn)) for fn in files if os.path.exists(fn)]
    while tostrip:
        cmd = list(STRIPCMD)
        flips = []
        pathlen = reduce(operator.add, [len(s) + 1 for s in cmd])
        while pathlen < argv_max:
            if not tostrip:
                break
            added, flip = tostrip.pop()
            pathlen += len(added) + 1
            cmd.append(added)
            flips.append((added, flip))
        else:
            cmd.pop()
            tostrip.append(flips.pop())
        os.spawnv(os.P_WAIT, cmd[0], cmd)
        for args in flips:
            flipwritable(*args)


def flush(func):
    def ff(*args, **kwargs):
        sys.stdout.flush()
        sys.stderr.flush()
        ret = func(*args, **kwargs)
        sys.stdout.flush()
        sys.stderr.flush()
        return ret
    return ff


class Freeze(object):

    FID = '@executable_path/../Frameworks'

    def __init__(self, build_dir, ext_dir, test_runner, test_launchers=False, dont_strip=False, sign_installers=False):
        self.build_dir = build_dir
        self.sign_installers = sign_installers
        self.ext_dir = ext_dir
        self.test_runner = test_runner
        self.dont_strip = dont_strip
        self.contents_dir = join(self.build_dir, 'Contents')
        self.resources_dir = join(self.contents_dir, 'Resources')
        self.frameworks_dir = join(self.contents_dir, 'Frameworks')
        self.site_packages = join(self.resources_dir, 'Python', 'site-packages')
        self.to_strip = []
        self.warnings = []

        self.run(test_launchers)

    def run(self, test_launchers):
        ret = 0
        if not test_launchers:
            if os.path.exists(self.build_dir):
                shutil.rmtree(self.build_dir)
            os.makedirs(self.build_dir)
            self.create_skeleton()
            self.create_plist()

            self.add_python_framework()
            self.add_site_packages()
            self.add_stdlib()
            self.add_qt_frameworks()
            self.add_calibre_plugins()
            self.add_podofo()
            self.add_poppler()
            self.add_imaging_libs()
            self.add_fontconfig()
            self.add_misc_libraries()

            self.add_resources()
            self.compile_py_modules()

        self.copy_site()
        self.create_exe()
        if not test_launchers and not self.dont_strip:
            self.strip_files()
        if not test_launchers:
            self.create_console_app()
            self.create_gui_apps()

        self.run_tests()
        ret = self.makedmg(self.build_dir, APPNAME + '-' + VERSION)

        return ret

    @flush
    def run_tests(self):
        cc_dir = os.path.join(self.contents_dir, 'calibre-debug.app', 'Contents')
        self.test_runner(join(cc_dir, 'MacOS', 'calibre-debug'), self.contents_dir)

    @flush
    def add_resources(self):
        shutil.copytree('resources', os.path.join(self.resources_dir,
                                                  'resources'))

    @flush
    def strip_files(self):
        print('\nStripping files...')
        strip_files(self.to_strip)

    @flush
    def create_exe(self):
        print('\nCreating launchers')
        programs = {}
        progs = []
        for x in ('console', 'gui'):
            progs += list(zip(basenames[x], main_modules[x], main_functions[x], repeat(x)))
        for program, module, func, ptype in progs:
            programs[program] = (module, func, ptype)
        programs = compile_launchers(self.contents_dir, programs, py_ver)
        for out in programs:
            self.fix_dependencies_in_lib(out)

    @flush
    def set_id(self, path_to_lib, new_id):
        old_mode = flipwritable(path_to_lib)
        subprocess.check_call(['install_name_tool', '-id', new_id, path_to_lib])
        if old_mode is not None:
            flipwritable(path_to_lib, old_mode)

    @flush
    def get_dependencies(self, path_to_lib):
        install_name = subprocess.check_output(['otool', '-D', path_to_lib]).splitlines()[-1].strip()
        raw = subprocess.check_output(['otool', '-L', path_to_lib]).decode('utf-8')
        for line in raw.splitlines():
            if 'compatibility' not in line or line.strip().endswith(':'):
                continue
            idx = line.find('(')
            path = line[:idx].strip()
            yield path, path == install_name

    @flush
    def get_local_dependencies(self, path_to_lib):
        for x, is_id in self.get_dependencies(path_to_lib):
            if x.startswith('@rpath/Qt'):
                yield x, x[len('@rpath/'):], is_id
            elif x.startswith('@rpath/libjpeg'):
                yield x, x[len('@rpath/'):], is_id
            else:
                for y in (PREFIX + '/lib/', PREFIX + '/python/Python.framework/'):
                    if x.startswith(y):
                        if y == PREFIX + '/python/Python.framework/':
                            y = PREFIX + '/python/'
                        yield x, x[len(y):], is_id
                        break

    @flush
    def change_dep(self, old_dep, new_dep, is_id, path_to_lib):
        cmd = ['-id', new_dep] if is_id else ['-change', old_dep, new_dep]
        subprocess.check_call(['install_name_tool'] + cmd + [path_to_lib])

    @flush
    def fix_dependencies_in_lib(self, path_to_lib):
        self.to_strip.append(path_to_lib)
        old_mode = flipwritable(path_to_lib)
        for dep, bname, is_id in self.get_local_dependencies(path_to_lib):
            ndep = self.FID + '/' + bname
            self.change_dep(dep, ndep, is_id, path_to_lib)
        ldeps = list(self.get_local_dependencies(path_to_lib))
        if ldeps:
            print('\nFailed to fix dependencies in', path_to_lib)
            print('Remaining local dependencies:', ldeps)
            raise SystemExit(1)
        if old_mode is not None:
            flipwritable(path_to_lib, old_mode)

    @flush
    def add_python_framework(self):
        print('\nAdding Python framework')
        src = join(PREFIX + '/python', 'Python.framework')
        x = join(self.frameworks_dir, 'Python.framework')
        curr = os.path.realpath(join(src, 'Versions', 'Current'))
        currd = join(x, 'Versions', basename(curr))
        rd = join(currd, 'Resources')
        os.makedirs(rd)
        shutil.copy2(join(curr, 'Resources', 'Info.plist'), rd)
        shutil.copy2(join(curr, 'Python'), currd)
        self.set_id(join(currd, 'Python'),
                    self.FID + '/Python.framework/Versions/%s/Python' % basename(curr))
        # The following is needed for codesign in OS X >= 10.9.5
        with current_dir(x):
            os.symlink(basename(curr), 'Versions/Current')
            for y in ('Python', 'Resources'):
                os.symlink('Versions/Current/%s' % y, y)

    @flush
    def add_qt_frameworks(self):
        print('\nAdding Qt Frameworks')
        for f in QT_FRAMEWORKS:
            self.add_qt_framework(f)
        pdir = join(QT_PREFIX, 'plugins')
        ddir = join(self.contents_dir, 'MacOS', 'qt-plugins')
        os.mkdir(ddir)
        for x in QT_PLUGINS:
            shutil.copytree(join(pdir, x), join(ddir, x))
        for l in glob.glob(join(ddir, '*/*.dylib')):
            self.fix_dependencies_in_lib(l)
            x = os.path.relpath(l, ddir)
            self.set_id(l, '@executable_path/' + x)

    def add_qt_framework(self, f):
        libname = f
        f = f + '.framework'
        src = join(PREFIX, 'qt', 'lib', f)
        ignore = shutil.ignore_patterns('Headers', '*.h', 'Headers/*')
        dest = join(self.frameworks_dir, f)
        shutil.copytree(src, dest, symlinks=True,
                        ignore=ignore)
        lib = os.path.realpath(join(dest, libname))
        rpath = os.path.relpath(lib, self.frameworks_dir)
        self.set_id(lib, self.FID + '/' + rpath)
        self.fix_dependencies_in_lib(lib)
        # The following is needed for codesign in OS X >= 10.9.5
        # The presence of the .prl file in the root of the framework causes
        # codesign to fail.
        with current_dir(dest):
            for x in os.listdir('.'):
                if x != 'Versions' and not os.path.islink(x):
                    os.remove(x)

    @flush
    def create_skeleton(self):
        c = join(self.build_dir, 'Contents')
        for x in ('Frameworks', 'MacOS', 'Resources'):
            os.makedirs(join(c, x))
        icons = glob.glob(join(CALIBRE_DIR, 'icons', 'icns', '*.iconset'))
        if not icons:
            raise SystemExit('Failed to find icns format icons')
        for x in icons:
            subprocess.check_call([
                'iconutil', '-c', 'icns', x, '-o', join(
                    self.resources_dir, basename(x).partition('.')[0] + '.icns')])

    @flush
    def add_calibre_plugins(self):
        dest = join(self.frameworks_dir, 'plugins')
        os.mkdir(dest)
        plugins = glob.glob(self.ext_dir + '/*.so')
        if not plugins:
            raise SystemExit('No calibre plugins found in: ' + self.ext_dir)
        for f in plugins:
            shutil.copy2(f, dest)
            self.fix_dependencies_in_lib(join(dest, basename(f)))
            if f.endswith('/podofo.so'):
                self.change_dep('libpodofo.0.9.6.dylib',
                    '@executable_path/../Frameworks/libpodofo.0.9.6.dylib', False, join(dest, basename(f)))

    @flush
    def create_plist(self):
        BOOK_EXTENSIONS = calibre_constants['book_extensions']
        env = dict(**ENV)
        env['CALIBRE_LAUNCHED_FROM_BUNDLE'] = '1'
        docs = [{'CFBundleTypeName': 'E-book',
                 'CFBundleTypeExtensions': list(BOOK_EXTENSIONS),
                 'CFBundleTypeIconFile': 'book.icns',
                 'CFBundleTypeRole': 'Viewer',
                 }]

        pl = dict(
            CFBundleDevelopmentRegion='English',
            CFBundleDisplayName=APPNAME,
            CFBundleName=APPNAME,
            CFBundleIdentifier='net.kovidgoyal.calibre',
            CFBundleVersion=VERSION,
            CFBundleShortVersionString=VERSION,
            CFBundlePackageType='APPL',
            CFBundleSignature='????',
            CFBundleExecutable='calibre',
            CFBundleDocumentTypes=docs,
            LSMinimumSystemVersion='10.9.5',
            LSRequiresNativeExecution=True,
            NSAppleScriptEnabled=False,
            NSHumanReadableCopyright=time.strftime('Copyright %Y, Kovid Goyal'),
            CFBundleGetInfoString=('calibre, an E-book management '
                                   'application. Visit https://calibre-ebook.com for details.'),
            CFBundleIconFile='calibre.icns',
            NSHighResolutionCapable=True,
            LSApplicationCategoryType='public.app-category.productivity',
            LSEnvironment=env
        )
        with open(join(self.contents_dir, 'Info.plist'), 'wb') as p:
            plistlib.dump(pl, p)

    @flush
    def install_dylib(self, path, set_id=True):
        shutil.copy2(path, self.frameworks_dir)
        if set_id:
            self.set_id(join(self.frameworks_dir, basename(path)),
                        self.FID + '/' + basename(path))
        self.fix_dependencies_in_lib(join(self.frameworks_dir, basename(path)))

    @flush
    def add_podofo(self):
        print('\nAdding PoDoFo')
        pdf = join(PREFIX, 'lib', 'libpodofo.0.9.6.dylib')
        self.install_dylib(pdf)

    @flush
    def add_poppler(self):
        print('\nAdding poppler')
        for x in ('libpoppler.87.dylib',):
            self.install_dylib(os.path.join(PREFIX, 'lib', x))
        for x in ('pdftohtml', 'pdftoppm', 'pdfinfo'):
            self.install_dylib(os.path.join(PREFIX, 'bin', x), False)

    @flush
    def add_imaging_libs(self):
        print('\nAdding libjpeg, libpng, libwebp, optipng and mozjpeg')
        for x in ('jpeg.8', 'png16.16', 'webp.7', 'webpmux.3', 'webpdemux.2'):
            self.install_dylib(os.path.join(PREFIX, 'lib', 'lib%s.dylib' % x))
        for x in 'optipng', 'JxrDecApp':
            self.install_dylib(os.path.join(PREFIX, 'bin', x), False)
        for x in ('jpegtran', 'cjpeg'):
            self.install_dylib(os.path.join(PREFIX, 'private', 'mozjpeg', 'bin', x), False)

    @flush
    def add_fontconfig(self):
        print('\nAdding fontconfig')
        for x in ('fontconfig.1', 'freetype.6', 'expat.1'):
            src = os.path.join(PREFIX, 'lib', 'lib' + x + '.dylib')
            self.install_dylib(src)
        dst = os.path.join(self.resources_dir, 'fonts')
        if os.path.exists(dst):
            shutil.rmtree(dst)
        src = os.path.join(PREFIX, 'etc', 'fonts')
        shutil.copytree(src, dst, symlinks=False)
        fc = os.path.join(dst, 'fonts.conf')
        raw = open(fc, 'rb').read().decode('utf-8')
        raw = raw.replace('<dir>/usr/share/fonts</dir>', '''\
        <dir>/Library/Fonts</dir>
        <dir>/System/Library/Fonts</dir>
        <dir>/usr/X11R6/lib/X11/fonts</dir>
        <dir>/usr/share/fonts</dir>
        <dir>/var/root/Library/Fonts</dir>
        <dir>/usr/share/fonts</dir>
        ''')
        open(fc, 'wb').write(raw.encode('utf-8'))

    @flush
    def add_misc_libraries(self):
        for x in (
                'usb-1.0.0', 'mtp.9', 'chm.0', 'sqlite3.0',
                'icudata.64', 'icui18n.64', 'icuio.64', 'icuuc.64',
                'xslt.1', 'exslt.0', 'xml2.2', 'z.1', 'unrar',
                'crypto.1.0.0', 'ssl.1.0.0', 'iconv.2',  # 'ltdl.7'
        ):
            print('\nAdding', x)
            x = 'lib%s.dylib' % x
            src = join(PREFIX, 'lib', x)
            shutil.copy2(src, self.frameworks_dir)
            dest = join(self.frameworks_dir, x)
            self.set_id(dest, self.FID + '/' + x)
            self.fix_dependencies_in_lib(dest)

    @flush
    def add_site_packages(self):
        print('\nAdding site-packages')
        os.makedirs(self.site_packages)
        sys_path = json.loads(subprocess.check_output([
            PYTHON, '-c', 'import sys, json; json.dump(sys.path, sys.stdout)']))
        paths = reversed(tuple(map(abspath, [x for x in sys_path if x.startswith('/') and not x.startswith('/Library/')])))
        upaths = []
        for x in paths:
            if x not in upaths and (x.endswith('.egg') or x.endswith('/site-packages')):
                upaths.append(x)
        upaths.append(join(CALIBRE_DIR, 'src'))
        for x in upaths:
            print('\t', x)
            tdir = None
            try:
                if not os.path.isdir(x):
                    zf = zipfile.ZipFile(x)
                    tdir = tempfile.mkdtemp()
                    zf.extractall(tdir)
                    x = tdir
                self.add_modules_from_dir(x)
                self.add_packages_from_dir(x)
            finally:
                if tdir is not None:
                    shutil.rmtree(tdir)
        try:
            shutil.rmtree(os.path.join(self.site_packages, 'calibre', 'plugins'))
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        sp = join(self.resources_dir, 'Python', 'site-packages')
        for x in os.listdir(join(sp, 'PyQt5')):
            if x.endswith('.so') and x.rpartition('.')[0] not in PYQT_MODULES and x != 'sip.so':
                os.remove(join(sp, 'PyQt5', x))
        os.remove(join(sp, 'PyQt5', 'uic/port_v3/proxy_base.py'))
        self.remove_bytecode(sp)

    @flush
    def add_modules_from_dir(self, src):
        for x in glob.glob(join(src, '*.py')) + glob.glob(join(src, '*.so')):
            dest = os.path.join(self.site_packages, os.path.basename(x))
            shutil.copy2(x, dest)
            if x.endswith('.so'):
                self.fix_dependencies_in_lib(dest)

    @flush
    def add_packages_from_dir(self, src):
        for x in os.listdir(src):
            x = join(src, x)
            if os.path.isdir(x) and os.path.exists(join(x, '__init__.py')):
                if self.filter_package(basename(x)):
                    continue
                self.add_package_dir(x)

    @flush
    def add_package_dir(self, x, dest=None):
        def ignore(root, files):
            ans = []
            for y in files:
                ext = os.path.splitext(y)[1]
                if ext not in ('', '.py', '.so') or \
                        (not ext and not os.path.isdir(join(root, y))):
                    ans.append(y)

            return ans
        if dest is None:
            dest = self.site_packages
        dest = join(dest, basename(x))
        shutil.copytree(x, dest, symlinks=True, ignore=ignore)
        self.postprocess_package(x, dest)
        for x in os.walk(dest):
            for f in x[-1]:
                if f.endswith('.so'):
                    f = join(x[0], f)
                    self.fix_dependencies_in_lib(f)

    @flush
    def filter_package(self, name):
        return name in ('Cython', 'modulegraph', 'macholib', 'py2app',
                        'bdist_mpkg', 'altgraph')

    @flush
    def postprocess_package(self, src_path, dest_path):
        pass

    @flush
    def add_stdlib(self):
        print('\nAdding python stdlib')
        src = PREFIX + '/python/Python.framework/Versions/Current/lib/python'
        src += py_ver
        dest = join(self.resources_dir, 'Python', 'lib', 'python')
        dest += py_ver
        os.makedirs(dest)
        for x in os.listdir(src):
            if x in ('site-packages', 'config', 'test', 'lib2to3', 'lib-tk',
                     'lib-old', 'idlelib', 'plat-mac', 'plat-darwin', 'site.py'):
                continue
            x = join(src, x)
            if os.path.isdir(x):
                self.add_package_dir(x, dest)
            elif os.path.splitext(x)[1] in ('.so', '.py'):
                shutil.copy2(x, dest)
                dest2 = join(dest, basename(x))
                if dest2.endswith('.so'):
                    self.fix_dependencies_in_lib(dest2)

        target = join(self.resources_dir, 'Python', 'lib')
        self.remove_bytecode(target)
        for path in walk(target):
            if path.endswith('.so'):
                self.fix_dependencies_in_lib(path)

    @flush
    def remove_bytecode(self, dest):
        for x in os.walk(dest):
            root = x[0]
            for f in x[-1]:
                if os.path.splitext(f) in ('.pyc', '.pyo'):
                    os.remove(join(root, f))

    @flush
    def compile_py_modules(self):
        print('\nCompiling Python modules')
        base = join(self.resources_dir, 'Python')
        py_compile(base)

    def create_app_clone(self, name, specialise_plist, remove_doc_types=True):
        print('\nCreating ' + name)
        cc_dir = os.path.join(self.contents_dir, name, 'Contents')
        exe_dir = join(cc_dir, 'MacOS')
        os.makedirs(exe_dir)
        for x in os.listdir(self.contents_dir):
            if x.endswith('.app'):
                continue
            if x == 'Info.plist':
                with open(join(self.contents_dir, x), 'rb') as r:
                    plist = plistlib.load(r)
                specialise_plist(plist)
                if remove_doc_types:
                    plist.pop('CFBundleDocumentTypes')
                exe = plist['CFBundleExecutable']
                # We cannot symlink the bundle executable as if we do,
                # codesigning fails
                plist['CFBundleExecutable'] = exe + '-placeholder-for-codesigning'
                nexe = join(exe_dir, plist['CFBundleExecutable'])
                base = os.path.dirname(abspath(__file__))
                cmd = [gcc, '-Wall', '-Werror', '-DEXE_NAME="%s"' % exe, join(base, 'placeholder.c'), '-o', nexe, '-headerpad_max_install_names']
                subprocess.check_call(cmd)
                with open(join(cc_dir, x), 'wb') as p:
                    plistlib.dump(plist, p)
            elif x == 'MacOS':
                for item in os.listdir(join(self.contents_dir, 'MacOS')):
                    os.symlink('../../../MacOS/' + item, join(exe_dir, item))
            else:
                os.symlink(join('../..', x), join(cc_dir, x))

    @flush
    def create_console_app(self):
        def specialise_plist(plist):
            plist['LSBackgroundOnly'] = '1'
            plist['CFBundleIdentifier'] = 'com.calibre-ebook.console'
            plist['CFBundleExecutable'] = 'calibre-parallel'
        self.create_app_clone('console.app', specialise_plist)

    @flush
    def create_gui_apps(self):
        input_formats = sorted(set(json.loads(
            subprocess.check_output([
                join(self.contents_dir, 'MacOS', 'calibre-debug'), '-c',
                'from calibre.customize.ui import all_input_formats; import sys, json; sys.stdout.write(json.dumps(tuple(all_input_formats())))'
            ])
        )))

        def specialise_plist(launcher, remove_types, plist):
            plist['CFBundleDisplayName'] = plist['CFBundleName'] = {
                'ebook-viewer': 'E-book Viewer', 'ebook-edit': 'Edit Book', 'calibre-debug': 'calibre (debug)',
            }[launcher]
            plist['CFBundleExecutable'] = launcher
            if launcher != 'calibre-debug':
                plist['CFBundleIconFile'] = launcher + '.icns'
            plist['CFBundleIdentifier'] = 'com.calibre-ebook.' + launcher
            if not remove_types:
                e = plist['CFBundleDocumentTypes'][0]
                exts = 'epub azw3'.split() if launcher == 'ebook-edit' else input_formats
                e['CFBundleTypeExtensions'] = exts
        for launcher in ('ebook-viewer', 'ebook-edit', 'calibre-debug'):
            remove_types = launcher == 'calibre-debug'
            self.create_app_clone(launcher + '.app', partial(specialise_plist, launcher, remove_types), remove_doc_types=remove_types)

    @flush
    def copy_site(self):
        base = os.path.dirname(abspath(__file__))
        shutil.copy2(join(base, 'site.py'), join(self.resources_dir, 'Python',
                                                 'lib', 'python' + py_ver))

    @flush
    def makedmg(self, d, volname, internet_enable=True, format='UDBZ'):
        ''' Copy a directory d into a dmg named volname '''
        print('\nSigning...')
        sys.stdout.flush()
        destdir = OUTPUT_DIR
        try:
            shutil.rmtree(destdir)
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        os.mkdir(destdir)
        dmg = os.path.join(destdir, volname + '.dmg')
        if os.path.exists(dmg):
            os.unlink(dmg)
        tdir = tempfile.mkdtemp()
        appdir = os.path.join(tdir, os.path.basename(d))
        shutil.copytree(d, appdir, symlinks=True)
        if self.sign_installers:
            with timeit() as times:
                sign_app(appdir)
            print('Signing completed in %d minutes %d seconds' % tuple(times))
        os.symlink('/Applications', os.path.join(tdir, 'Applications'))
        size_in_mb = int(subprocess.check_output(['du', '-s', '-k', tdir]).decode('utf-8').split()[0]) / 1024.
        cmd = ['/usr/bin/hdiutil', 'create', '-srcfolder', tdir, '-volname', volname, '-format', format]
        if 190 < size_in_mb < 250:
            # We need -size 255m because of a bug in hdiutil. When the size of
            # srcfolder is close to 200MB hdiutil fails with
            # diskimages-helper: resize request is above maximum size allowed.
            cmd += ['-size', '255m']
        print('\nCreating dmg...')
        with timeit() as times:
            subprocess.check_call(cmd + [dmg])
            if internet_enable:
                subprocess.check_call(['/usr/bin/hdiutil', 'internet-enable', '-yes', dmg])
        print('dmg created in %d minutes and %d seconds' % tuple(times))
        shutil.rmtree(tdir)
        size = os.stat(dmg).st_size / (1024 * 1024.)
        print('\nInstaller size: %.2fMB\n' % size)
        return dmg


def main(args, ext_dir, test_runner):
    build_dir = abspath(join(mkdtemp('frozen-'), APPNAME + '.app'))
    if args.skip_tests:
        test_runner = lambda *a: None
    Freeze(build_dir, ext_dir, test_runner, dont_strip=args.dont_strip, sign_installers=args.sign_installers)


if __name__ == '__main__':
    args = globals()['args']
    ext_dir = globals()['ext_dir']
    run_tests = iv['run_tests']
    main(args, ext_dir, run_tests)
