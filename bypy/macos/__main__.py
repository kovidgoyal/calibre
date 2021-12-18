#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

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
from bypy.freeze import (
    extract_extension_modules, fix_pycryptodome, freeze_python, path_to_freeze_dir
)
from bypy.utils import (
    current_dir, get_arches_in_binary, mkdtemp, py_compile, timeit, walk
)

abspath, join, basename, dirname = os.path.abspath, os.path.join, os.path.basename, os.path.dirname
iv = globals()['init_env']
calibre_constants = iv['calibre_constants']
QT_DLLS, QT_PLUGINS, PYQT_MODULES = iv['QT_DLLS'], iv['QT_PLUGINS'], iv['PYQT_MODULES']
QT_MAJOR = iv['QT_MAJOR']
py_ver = '.'.join(map(str, python_major_minor_version()))
sign_app = runpy.run_path(join(dirname(abspath(__file__)), 'sign.py'))['sign_app']

QT_PREFIX = join(PREFIX, 'qt')
QT_FRAMEWORKS = [x.replace(f'{QT_MAJOR}', '') for x in QT_DLLS]

ENV = dict(
    FONTCONFIG_PATH='@executable_path/../Resources/fonts',
    FONTCONFIG_FILE='@executable_path/../Resources/fonts/fonts.conf',
    SSL_CERT_FILE='@executable_path/../Resources/resources/mozilla-ca-certs.pem',
)
APPNAME, VERSION = calibre_constants['appname'], calibre_constants['version']
basenames, main_modules, main_functions = calibre_constants['basenames'], calibre_constants['modules'], calibre_constants['functions']


def compile_launcher_lib(contents_dir, gcc, base, pyver, inc_dir):
    print('\tCompiling calibre_launcher.dylib')
    env, env_vals = [], []
    for key, val in ENV.items():
        env.append(f'"{key}"'), env_vals.append(f'"{val}"')
    env = ','.join(env)
    env_vals = ','.join(env_vals)

    dest = join(contents_dir, 'Frameworks', 'calibre-launcher.dylib')
    src = join(base, 'util.c')
    cmd = [gcc] + '-arch x86_64 -arch arm64 -Wall -dynamiclib -std=gnu99'.split() + [src] + \
        ['-I' + base] + '-DPY_VERSION_MAJOR={} -DPY_VERSION_MINOR={}'.format(*pyver.split('.')).split() + \
        [f'-I{path_to_freeze_dir()}', f'-I{inc_dir}'] + \
        [f'-DENV_VARS={env}', f'-DENV_VAR_VALS={env_vals}'] + \
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


def compile_launchers(contents_dir, inc_dir, xprograms, pyver):
    base = dirname(abspath(__file__))
    lib = compile_launcher_lib(contents_dir, gcc, base, pyver, inc_dir)
    src = join(base, 'launcher.c')
    programs = [lib]
    for program, x in xprograms.items():
        module, func, ptype = x
        print('\tCompiling', program)
        out = join(contents_dir, 'MacOS', program)
        programs.append(out)
        is_gui = 'true' if ptype == 'gui' else 'false'
        cmd = [
            gcc, '-Wall', '-arch', 'x86_64', '-arch', 'arm64',
            f'-DPROGRAM=L"{program}"', f'-DMODULE=L"{module}"', f'-DFUNCTION=L"{func}"', f'-DIS_GUI={is_gui}',
            '-I' + base, src, lib, '-o', out, '-headerpad_max_install_names'
        ]
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


def check_universal(path):
    arches = get_arches_in_binary(path)
    if arches != EXPECTED_ARCHES:
        raise SystemExit(f'The file {path} is not a universal binary, it only has arches: {", ".join(arches)}')


STRIPCMD = ['/usr/bin/strip', '-x', '-S', '-']
EXPECTED_ARCHES = {'x86_64', 'arm64'}


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


class Freeze:

    FID = '@executable_path/../Frameworks'

    def __init__(self, build_dir, ext_dir, inc_dir, test_runner, test_launchers=False, dont_strip=False, sign_installers=False, notarize=False):
        self.build_dir = os.path.realpath(build_dir)
        self.inc_dir = os.path.realpath(inc_dir)
        self.sign_installers = sign_installers
        self.notarize = notarize
        self.ext_dir = os.path.realpath(ext_dir)
        self.test_runner = test_runner
        self.dont_strip = dont_strip
        self.contents_dir = join(self.build_dir, 'Contents')
        self.resources_dir = join(self.contents_dir, 'Resources')
        self.frameworks_dir = join(self.contents_dir, 'Frameworks')
        self.exe_dir = join(self.contents_dir, 'MacOS')
        self.helpers_dir = join(self.contents_dir, 'utils.app', 'Contents', 'MacOS')
        self.site_packages = join(self.resources_dir, 'Python', 'site-packages')
        self.to_strip = []
        self.warnings = []

        self.run(test_launchers)

    def run(self, test_launchers):
        ret = 0
        self.ext_map = {}
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
            self.copy_site()
            self.compile_py_modules()

        self.create_exe()
        if not test_launchers and not self.dont_strip:
            self.strip_files()
        if not test_launchers:
            self.create_gui_apps()

        self.run_tests()
        ret = self.makedmg(self.build_dir, APPNAME + '-' + VERSION)

        return ret

    @flush
    def run_tests(self):
        self.test_runner(join(self.contents_dir, 'MacOS', 'calibre-debug'), self.contents_dir)

    @flush
    def add_resources(self):
        shutil.copytree('resources', join(self.resources_dir,
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
        programs = compile_launchers(self.contents_dir, self.inc_dir, programs, py_ver)
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
            if x.startswith('@rpath/Qt') or x.startswith('@rpath/libexpat'):
                yield x, x[len('@rpath/'):], is_id
            elif x in ('libunrar.dylib', 'libstemmer.0.dylib', 'libstemmer.dylib') and not is_id:
                yield x, x, is_id
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
        check_universal(path_to_lib)
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
        ddir = join(self.contents_dir, 'PlugIns')
        os.mkdir(ddir)
        for x in QT_PLUGINS:
            shutil.copytree(join(pdir, x), join(ddir, x))
        for l in glob.glob(join(ddir, '*/*.dylib')):
            self.fix_dependencies_in_lib(l)
            x = os.path.relpath(l, ddir)
            self.set_id(l, '@executable_path/' + x)
        webengine_process = os.path.realpath(join(
            self.frameworks_dir, 'QtWebEngineCore.framework/Versions/Current/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess'))
        self.fix_dependencies_in_lib(webengine_process)
        cdir = dirname(dirname(webengine_process))
        dest = join(cdir, 'Frameworks')
        os.symlink(os.path.relpath(self.frameworks_dir, cdir), dest)

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
        for helpers in (self.helpers_dir,):
            os.makedirs(helpers)
            cdir = dirname(helpers)
            dest = join(cdir, 'Frameworks')
            src = self.frameworks_dir
            os.symlink(os.path.relpath(src, cdir), dest)
            dest = join(cdir, 'Resources')
            src = self.resources_dir
            os.symlink(os.path.relpath(src, cdir), dest)
            pl = dict(
                CFBundleDevelopmentRegion='English',
                CFBundleDisplayName=APPNAME + ' - utils',
                CFBundleName=APPNAME + '-utils',
                CFBundleIdentifier='com.calibre-ebook.utils',
                LSBackgroundOnly='1',
                CFBundleVersion=VERSION,
                CFBundleShortVersionString=VERSION,
                CFBundlePackageType='APPL',
                CFBundleSignature='????',
                CFBundleExecutable='pdftohtml',
                LSMinimumSystemVersion='10.14.0',
                LSRequiresNativeExecution=True,
                NSAppleScriptEnabled=False,
                CFBundleIconFile='',
            )
            with open(join(cdir, 'Info.plist'), 'wb') as p:
                plistlib.dump(pl, p)

    @flush
    def add_calibre_plugins(self):
        dest = join(self.frameworks_dir, 'plugins')
        os.mkdir(dest)
        print('Extracting extension modules from:', self.ext_dir, 'to', dest)
        self.ext_map = extract_extension_modules(self.ext_dir, dest)
        plugins = glob.glob(dest + '/*.so')
        if not plugins:
            raise SystemExit('No calibre plugins found in: ' + self.ext_dir)
        for f in plugins:
            self.fix_dependencies_in_lib(f)
            if f.endswith('/podofo.so'):
                self.change_dep('libpodofo.0.9.7.dylib',
                    '@executable_path/../Frameworks/libpodofo.0.9.7.dylib', False, f)

    @flush
    def create_plist(self):
        BOOK_EXTENSIONS = calibre_constants['book_extensions']
        env = dict(**ENV)
        env['CALIBRE_LAUNCHED_FROM_BUNDLE'] = '1'
        docs = [{
            'CFBundleTypeName': 'E-book',
            'CFBundleTypeExtensions': list(BOOK_EXTENSIONS),
            'CFBundleTypeIconFile': 'book.icns',
            'CFBundleTypeRole': 'Viewer',
        }]
        url_handlers = [dict(
            CFBundleTypeRole='Viewer',
            CFBundleURLIconFile='calibre',
            CFBundleURLName='com.calibre-ebook.calibre-url',
            CFBundleURLSchemes=['calibre']
        )]

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
            CFBundleURLTypes=url_handlers,
            LSMinimumSystemVersion='10.14.0',
            LSRequiresNativeExecution=True,
            NSAppleScriptEnabled=False,
            NSSupportsAutomaticGraphicsSwitching=True,
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
    def install_dylib(self, path, set_id=True, dest=None):
        dest = dest or self.frameworks_dir
        os.makedirs(dest, exist_ok=True)
        shutil.copy2(path, dest)
        if set_id:
            self.set_id(join(dest, basename(path)),
                        self.FID + '/' + basename(path))
        self.fix_dependencies_in_lib(join(dest, basename(path)))

    @flush
    def add_podofo(self):
        print('\nAdding PoDoFo')
        pdf = join(PREFIX, 'lib', 'libpodofo.0.9.7.dylib')
        self.install_dylib(pdf)

    @flush
    def add_poppler(self):
        print('\nAdding poppler')
        for x in ('libopenjp2.7.dylib', 'libpoppler.115.dylib',):
            self.install_dylib(join(PREFIX, 'lib', x))
        for x in ('pdftohtml', 'pdftoppm', 'pdfinfo'):
            self.install_dylib(
                join(PREFIX, 'bin', x), set_id=False, dest=self.helpers_dir)

    @flush
    def add_imaging_libs(self):
        print('\nAdding libjpeg, libpng, libwebp, optipng and mozjpeg')
        for x in ('jpeg.8', 'png16.16', 'webp.7', 'webpmux.3', 'webpdemux.2'):
            self.install_dylib(join(PREFIX, 'lib', 'lib%s.dylib' % x))
        for x in 'optipng', 'JxrDecApp':
            self.install_dylib(join(PREFIX, 'bin', x), set_id=False, dest=self.helpers_dir)
        for x in ('jpegtran', 'cjpeg'):
            self.install_dylib(
                join(PREFIX, 'private', 'mozjpeg', 'bin', x), set_id=False, dest=self.helpers_dir)

    @flush
    def add_fontconfig(self):
        print('\nAdding fontconfig')
        for x in ('fontconfig.1', 'freetype.6', 'expat.1'):
            src = join(PREFIX, 'lib', 'lib' + x + '.dylib')
            self.install_dylib(src)
        dst = join(self.resources_dir, 'fonts')
        if os.path.exists(dst):
            shutil.rmtree(dst)
        src = join(PREFIX, 'etc', 'fonts')
        shutil.copytree(src, dst, symlinks=False)
        fc = join(dst, 'fonts.conf')
        with open(fc, 'rb') as f:
            raw = f.read().decode('utf-8')
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
            'usb-1.0.0', 'mtp.9', 'chm.0', 'sqlite3.0', 'hunspell-1.7.0',
            'icudata.70', 'icui18n.70', 'icuio.70', 'icuuc.70', 'hyphen.0',
            'stemmer.0', 'xslt.1', 'exslt.0', 'xml2.2', 'z.1', 'unrar', 'lzma.5',
            'crypto.1.1', 'ssl.1.1', 'iconv.2',  # 'ltdl.7'
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
        fix_pycryptodome(self.site_packages)
        try:
            shutil.rmtree(join(self.site_packages, 'calibre', 'plugins'))
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        sp = join(self.resources_dir, 'Python', 'site-packages')
        self.remove_bytecode(sp)

    @flush
    def add_modules_from_dir(self, src):
        for x in glob.glob(join(src, '*.py')) + glob.glob(join(src, '*.so')):
            dest = join(self.site_packages, os.path.basename(x))
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
        pydir = join(base, f'lib/python{py_ver}')
        src = join(pydir, 'lib-dynload')
        dest = join(self.frameworks_dir, 'plugins')
        print('Extracting extension modules from:', src, 'to', dest)
        self.ext_map.update(extract_extension_modules(src, dest))
        os.rmdir(src)
        src = join(base, 'site-packages')
        print('Extracting extension modules from:', src, 'to', dest)
        self.ext_map.update(extract_extension_modules(src, dest))
        for x in os.listdir(src):
            os.rename(join(src, x), join(pydir, x))
        os.rmdir(src)
        py_compile(pydir)
        freeze_python(
            pydir, dest, self.inc_dir, self.ext_map,
            develop_mode_env_var='CALIBRE_DEVELOP_FROM',
            path_to_user_env_vars='~/Library/Preferences/calibre/macos-env.txt'
        )
        shutil.rmtree(pydir)

    def create_app_clone(self, name, specialise_plist, remove_doc_types=False, base_dir=None):
        print('\nCreating ' + name)
        base_dir = base_dir or self.contents_dir
        cc_dir = join(base_dir, name, 'Contents')
        exe_dir = join(cc_dir, 'MacOS')
        rel_path = os.path.relpath(join(self.contents_dir, 'MacOS'), exe_dir)
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
                cmd = [
                    gcc, '-Wall', '-Werror', '-DEXE_NAME="%s"' % exe, '-DREL_PATH="%s"' % rel_path,
                    join(base, 'placeholder.c'), '-o', nexe, '-headerpad_max_install_names'
                ]
                subprocess.check_call(cmd)
                with open(join(cc_dir, x), 'wb') as p:
                    plistlib.dump(plist, p)
            elif x == 'MacOS':
                for item in os.listdir(join(self.contents_dir, 'MacOS')):
                    src = join(self.contents_dir, x, item)
                    os.symlink(os.path.relpath(src, exe_dir), join(exe_dir, item))
            else:
                src = join(self.contents_dir, x)
                os.symlink(os.path.relpath(src, cc_dir), join(cc_dir, x))

    @flush
    def create_gui_apps(self):

        def get_data(cmd):
            return json.loads(subprocess.check_output([join(self.contents_dir, 'MacOS', 'calibre-debug'), '-c', cmd]))

        data = get_data(
            'from calibre.customize.ui import all_input_formats; import sys, json; from calibre.ebooks.oeb.polish.main import SUPPORTED;'
            'sys.stdout.write(json.dumps({"i": tuple(all_input_formats()), "e": tuple(SUPPORTED)}))'
        )
        input_formats = sorted(set(data['i']))
        edit_formats = sorted(set(data['e']))

        def specialise_plist(launcher, formats, plist):
            plist['CFBundleDisplayName'] = plist['CFBundleName'] = {
                'ebook-viewer': 'E-book Viewer', 'ebook-edit': 'Edit Book',
            }[launcher]
            plist['CFBundleExecutable'] = launcher
            plist['CFBundleIdentifier'] = 'com.calibre-ebook.' + launcher
            plist['CFBundleIconFile'] = launcher + '.icns'
            e = plist['CFBundleDocumentTypes'][0]
            e['CFBundleTypeExtensions'] = [x.lower() for x in formats]

        self.create_app_clone('ebook-viewer.app', partial(specialise_plist, 'ebook-viewer', input_formats))
        self.create_app_clone('ebook-edit.app', partial(specialise_plist, 'ebook-edit', edit_formats),
                base_dir=join(self.contents_dir, 'ebook-viewer.app', 'Contents'))
        # We need to move the webengine resources into the deepest sub-app
        # because the sandbox gets set to the nearest enclosing app which
        # means that WebEngine will fail to access its resources when running
        # in the sub-apps unless they are present inside the sub app bundle
        # somewhere
        base_dest = join(self.contents_dir, 'ebook-viewer.app', 'Contents', 'ebook-edit.app', 'Contents', 'SharedSupport')
        os.mkdir(base_dest)
        base_src = os.path.realpath(join(self.frameworks_dir, 'QtWebEngineCore.framework/Resources'))
        items = [join(base_src, 'qtwebengine_locales')] + glob.glob(join(base_src, '*.pak')) + glob.glob(join(base_src, '*.dat'))
        for src in items:
            dest = join(base_dest, os.path.basename(src))
            os.rename(src, dest)
            os.symlink(os.path.relpath(dest, base_src), src)

    @flush
    def copy_site(self):
        base = os.path.dirname(abspath(__file__))
        shutil.copy2(join(base, 'site.py'), join(self.resources_dir, 'Python',
                                                 'lib', 'python' + py_ver))

    @flush
    def makedmg(self, d, volname):
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
        dmg = join(destdir, volname + '.dmg')
        if os.path.exists(dmg):
            os.unlink(dmg)
        tdir = tempfile.mkdtemp()
        appdir = join(tdir, os.path.basename(d))
        shutil.copytree(d, appdir, symlinks=True)
        if self.sign_installers or self.notarize:
            with timeit() as times:
                sign_app(appdir, self.notarize)
            print('Signing completed in %d minutes %d seconds' % tuple(times))
        os.symlink('/Applications', join(tdir, 'Applications'))
        size_in_mb = int(subprocess.check_output(['du', '-s', '-k', tdir]).decode('utf-8').split()[0]) / 1024.
        # UDBZ gives the best compression, better than ULFO
        cmd = ['/usr/bin/hdiutil', 'create', '-srcfolder', tdir, '-volname', volname, '-format', 'UDBZ']
        if 190 < size_in_mb < 250:
            # We need -size 255m because of a bug in hdiutil. When the size of
            # srcfolder is close to 200MB hdiutil fails with
            # diskimages-helper: resize request is above maximum size allowed.
            cmd += ['-size', '255m']
        print('\nCreating dmg...')
        with timeit() as times:
            subprocess.check_call(cmd + [dmg])
        print('dmg created in %d minutes and %d seconds' % tuple(times))
        shutil.rmtree(tdir)
        size = os.stat(dmg).st_size / (1024 * 1024.)
        print('\nInstaller size: %.2fMB\n' % size)
        return dmg


def main(args, ext_dir, test_runner):
    build_dir = abspath(join(mkdtemp('frozen-'), APPNAME + '.app'))
    inc_dir = abspath(mkdtemp('include'))
    if args.skip_tests:
        test_runner = lambda *a: None
    Freeze(build_dir, ext_dir, inc_dir, test_runner, dont_strip=args.dont_strip, sign_installers=args.sign_installers, notarize=args.notarize)


if __name__ == '__main__':
    args = globals()['args']
    ext_dir = globals()['ext_dir']
    run_tests = iv['run_tests']
    main(args, ext_dir, run_tests)
