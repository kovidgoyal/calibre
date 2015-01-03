#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, plistlib, subprocess, glob, zipfile, tempfile, \
    py_compile, stat, operator, time
from functools import partial
from contextlib import contextmanager
from itertools import repeat

abspath, join, basename = os.path.abspath, os.path.join, os.path.basename

from setup import (
    __version__ as VERSION, __appname__ as APPNAME, basenames, modules as
    main_modules, Command, SRC, functions as main_functions)
from setup.build_environment import sw as SW, QT_FRAMEWORKS, QT_PLUGINS, PYQT_MODULES
from setup.installer.osx.app.sign import current_dir, sign_app

LICENSE = open('LICENSE', 'rb').read()
MAGICK_HOME='@executable_path/../Frameworks/ImageMagick'
ENV = dict(
        FONTCONFIG_PATH='@executable_path/../Resources/fonts',
        FONTCONFIG_FILE='@executable_path/../Resources/fonts/fonts.conf',
        MAGICK_CONFIGURE_PATH=MAGICK_HOME+'/config-Q16',
        MAGICK_CODER_MODULE_PATH=MAGICK_HOME+'/modules-Q16/coders',
        MAGICK_CODER_FILTER_PATH=MAGICK_HOME+'/modules-Q16/filters',
        QT_PLUGIN_PATH='@executable_path/../MacOS/qt-plugins',
        PYTHONIOENCODING='UTF-8',
        )


info = warn = None

@contextmanager
def timeit():
    times = [0, 0]
    st = time.time()
    yield times
    dt = time.time() - st
    times[0], times[1] = dt // 60, dt % 60

class OSX32_Freeze(Command):

    description = 'Freeze OSX calibre installation'

    def add_options(self, parser):
        parser.add_option('--test-launchers', default=False,
                action='store_true',
                help='Only build launchers')
        if not parser.has_option('--dont-strip'):
            parser.add_option('-x', '--dont-strip', default=False,
                action='store_true', help='Dont strip the generated binaries')

    def run(self, opts):
        global info, warn
        info, warn = self.info, self.warn
        main(opts.test_launchers, opts.dont_strip)

def compile_launcher_lib(contents_dir, gcc, base):
    info('\tCompiling calibre_launcher.dylib')
    fd = join(contents_dir, 'Frameworks')
    dest = join(fd, 'calibre-launcher.dylib')
    src = join(base, 'util.c')
    cmd = [gcc] + '-Wall -dynamiclib -std=gnu99'.split() + [src] + \
            ['-I'+base] + \
            ['-I%s/python/Python.framework/Versions/Current/Headers' % SW] + \
            '-current_version 1.0 -compatibility_version 1.0'.split() + \
            '-fvisibility=hidden -o'.split() + [dest] + \
            ['-install_name',
                '@executable_path/../Frameworks/'+os.path.basename(dest)] + \
            [('-F%s/python' % SW), '-framework', 'Python', '-framework', 'CoreFoundation', '-headerpad_max_install_names']
    # info('\t'+' '.join(cmd))
    sys.stdout.flush()
    subprocess.check_call(cmd)
    return dest


def compile_launchers(contents_dir, xprograms, pyver):
    gcc = os.environ.get('CC', 'gcc')
    base = os.path.dirname(__file__)
    lib = compile_launcher_lib(contents_dir, gcc, base)
    src = open(join(base, 'launcher.c'), 'rb').read()
    env, env_vals = [], []
    for key, val in ENV.items():
        env.append('"%s"'% key)
        env_vals.append('"%s"'% val)
    env = ', '.join(env)+', '
    env_vals = ', '.join(env_vals)+', '
    src = src.replace('/*ENV_VARS*/', env)
    src = src.replace('/*ENV_VAR_VALS*/', env_vals)
    programs = [lib]
    for program, x in xprograms.iteritems():
        module, func, ptype = x
        info('\tCompiling', program)
        out = join(contents_dir, 'MacOS', program)
        programs.append(out)
        psrc = src.replace('**PROGRAM**', program)
        psrc = psrc.replace('**MODULE**', module)
        psrc = psrc.replace('**FUNCTION**', func)
        psrc = psrc.replace('**PYVER**', pyver)
        psrc = psrc.replace('**IS_GUI**', ('1' if ptype == 'gui' else '0'))
        fsrc = '/tmp/%s.c'%program
        with open(fsrc, 'wb') as f:
            f.write(psrc)
        cmd = [gcc, '-Wall', '-I'+base, fsrc, lib, '-o', out,
            '-headerpad_max_install_names']
        # info('\t'+' '.join(cmd))
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

class Py2App(object):

    FID = '@executable_path/../Frameworks'

    def __init__(self, build_dir, test_launchers=False, dont_strip=False):
        self.build_dir = build_dir
        self.dont_strip = dont_strip
        self.contents_dir = join(self.build_dir, 'Contents')
        self.resources_dir = join(self.contents_dir, 'Resources')
        self.frameworks_dir = join(self.contents_dir, 'Frameworks')
        self.version_info = '.'.join(map(str, sys.version_info[:2]))
        self.site_packages = join(self.resources_dir, 'Python', 'site-packages')
        self.to_strip = []
        self.warnings = []

        self.run(test_launchers)

    def warn(self, *args):
        warn(*args)

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
            self.add_imagemagick()
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

        ret = self.makedmg(self.build_dir, APPNAME+'-'+VERSION)

        return ret

    @flush
    def add_resources(self):
        shutil.copytree('resources', os.path.join(self.resources_dir,
            'resources'))

    @flush
    def strip_files(self):
        info('\nStripping files...')
        strip_files(self.to_strip)

    @flush
    def create_exe(self):
        info('\nCreating launchers')
        programs = {}
        progs = []
        for x in ('console', 'gui'):
            progs += list(zip(basenames[x], main_modules[x], main_functions[x], repeat(x)))
        for program, module, func, ptype in progs:
            programs[program] = (module, func, ptype)
        programs = compile_launchers(self.contents_dir, programs,
                self.version_info)
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
        raw = subprocess.check_output(['otool', '-L', path_to_lib])
        for line in raw.splitlines():
            if 'compatibility' not in line or line.strip().endswith(':'):
                continue
            idx = line.find('(')
            path = line[:idx].strip()
            yield path, path == install_name

    @flush
    def get_local_dependencies(self, path_to_lib):
        for x, is_id in self.get_dependencies(path_to_lib):
            for y in (SW+'/lib/', SW+'/qt/lib/', SW+'/python/Python.framework/',):
                if x.startswith(y):
                    if y == SW+'/python/Python.framework/':
                        y = SW+'/python/'
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
            ndep = self.FID+'/'+bname
            self.change_dep(dep, ndep, is_id, path_to_lib)
        ldeps = list(self.get_local_dependencies(path_to_lib))
        if ldeps:
            info('\nFailed to fix dependencies in', path_to_lib)
            info('Remaining local dependencies:', ldeps)
            raise SystemExit(1)
        if old_mode is not None:
            flipwritable(path_to_lib, old_mode)

    @flush
    def add_python_framework(self):
        info('\nAdding Python framework')
        src = join(SW + '/python', 'Python.framework')
        x = join(self.frameworks_dir, 'Python.framework')
        curr = os.path.realpath(join(src, 'Versions', 'Current'))
        currd = join(x, 'Versions', basename(curr))
        rd = join(currd, 'Resources')
        os.makedirs(rd)
        shutil.copy2(join(curr, 'Resources', 'Info.plist'), rd)
        shutil.copy2(join(curr, 'Python'), currd)
        self.set_id(join(currd, 'Python'),
            self.FID+'/Python.framework/Versions/%s/Python'%basename(curr))
        # The following is needed for codesign in OS X >= 10.9.5
        with current_dir(x):
            os.symlink(basename(curr), 'Versions/Current')
            for y in ('Python', 'Resources'):
                os.symlink('Versions/Current/%s'%y, y)

    @flush
    def add_qt_frameworks(self):
        info('\nAdding Qt Frameworks')
        for f in QT_FRAMEWORKS:
            self.add_qt_framework(f)
        pdir = join(SW, 'qt', 'plugins')
        ddir = join(self.contents_dir, 'MacOS', 'qt-plugins')
        os.mkdir(ddir)
        for x in QT_PLUGINS:
            shutil.copytree(join(pdir, x), join(ddir, x))
        for l in glob.glob(join(ddir, '*/*.dylib')):
            self.fix_dependencies_in_lib(l)
            x = os.path.relpath(l, ddir)
            self.set_id(l, '@executable_path/'+x)

    def add_qt_framework(self, f):
        libname = f
        f = f+'.framework'
        src = join(SW, 'qt', 'lib', f)
        ignore = shutil.ignore_patterns('Headers', '*.h', 'Headers/*')
        dest = join(self.frameworks_dir, f)
        shutil.copytree(src, dest, symlinks=True,
                ignore=ignore)
        lib = os.path.realpath(join(dest, libname))
        rpath = os.path.relpath(lib, self.frameworks_dir)
        self.set_id(lib, self.FID+'/'+rpath)
        self.fix_dependencies_in_lib(lib)
        # The following is needed for codesign in OS X >= 10.9.5
        # See https://bugreports.qt-project.org/browse/QTBUG-32895
        with current_dir(dest):
            os.rename('Contents', 'Versions/Current/Resources')
            os.symlink('Versions/Current/Resources', 'Resources')
            for x in os.listdir('.'):
                if x != 'Versions' and not os.path.islink(x):
                    os.remove(x)

    @flush
    def create_skeleton(self):
        c = join(self.build_dir, 'Contents')
        for x in ('Frameworks', 'MacOS', 'Resources'):
            os.makedirs(join(c, x))
        for x in glob.glob(join('icons', 'icns', '*.iconset')):
            subprocess.check_call([
                'iconutil', '-c', 'icns', x, '-o', join(
                    self.resources_dir, basename(x).partition('.')[0] + '.icns')])

    @flush
    def add_calibre_plugins(self):
        dest = join(self.frameworks_dir, 'plugins')
        os.mkdir(dest)
        for f in glob.glob('src/calibre/plugins/*.so'):
            shutil.copy2(f, dest)
            self.fix_dependencies_in_lib(join(dest, basename(f)))

    @flush
    def create_plist(self):
        from calibre.ebooks import BOOK_EXTENSIONS
        env = dict(**ENV)
        env['CALIBRE_LAUNCHED_FROM_BUNDLE']='1'
        docs = [{'CFBundleTypeName':'E-book',
            'CFBundleTypeExtensions':list(BOOK_EXTENSIONS),
            'CFBundleTypeIconFile':'book.icns',
            'CFBundleTypeRole':'Viewer',
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
                LSMinimumSystemVersion='10.7.2',
                LSRequiresNativeExecution=True,
                NSAppleScriptEnabled=False,
                NSHumanReadableCopyright=time.strftime('Copyright %Y, Kovid Goyal'),
                CFBundleGetInfoString=('calibre, an E-book management '
                'application. Visit http://calibre-ebook.com for details.'),
                CFBundleIconFile='calibre.icns',
                NSHighResolutionCapable=True,
                LSApplicationCategoryType='public.app-category.productivity',
                LSEnvironment=env
        )
        plistlib.writePlist(pl, join(self.contents_dir, 'Info.plist'))

    @flush
    def install_dylib(self, path, set_id=True):
        shutil.copy2(path, self.frameworks_dir)
        if set_id:
            self.set_id(join(self.frameworks_dir, basename(path)),
                    self.FID+'/'+basename(path))
        self.fix_dependencies_in_lib(join(self.frameworks_dir, basename(path)))

    @flush
    def add_podofo(self):
        info('\nAdding PoDoFo')
        pdf = join(SW, 'lib', 'libpodofo.0.9.3.dylib')
        self.install_dylib(pdf)

    @flush
    def add_poppler(self):
        info('\nAdding poppler')
        for x in ('libpoppler.46.dylib',):
            self.install_dylib(os.path.join(SW, 'lib', x))
        for x in ('pdftohtml', 'pdftoppm', 'pdfinfo'):
            self.install_dylib(os.path.join(SW, 'bin', x), False)

    @flush
    def add_imaging_libs(self):
        info('\nAdding libjpeg, libpng and libwebp')
        for x in ('jpeg.8', 'png16.16', 'webp.5'):
            self.install_dylib(os.path.join(SW, 'lib', 'lib%s.dylib' % x))

    @flush
    def add_fontconfig(self):
        info('\nAdding fontconfig')
        for x in ('fontconfig.1', 'freetype.6', 'expat.1',
                  'plist.3', 'usbmuxd.4', 'imobiledevice.5'):
            src = os.path.join(SW, 'lib', 'lib'+x+'.dylib')
            self.install_dylib(src)
        dst = os.path.join(self.resources_dir, 'fonts')
        if os.path.exists(dst):
            shutil.rmtree(dst)
        src = os.path.join(SW, 'etc', 'fonts')
        shutil.copytree(src, dst, symlinks=False)
        fc = os.path.join(dst, 'fonts.conf')
        raw = open(fc, 'rb').read()
        raw = raw.replace('<dir>/usr/share/fonts</dir>', '''\
        <dir>/Library/Fonts</dir>
        <dir>/System/Library/Fonts</dir>
        <dir>/usr/X11R6/lib/X11/fonts</dir>
        <dir>/usr/share/fonts</dir>
        <dir>/var/root/Library/Fonts</dir>
        <dir>/usr/share/fonts</dir>
        ''')
        open(fc, 'wb').write(raw)

    @flush
    def add_imagemagick(self):
        info('\nAdding ImageMagick')
        for x in ('Wand-6', 'Core-6'):
            self.install_dylib(os.path.join(SW, 'lib', 'libMagick%s.Q16.2.dylib'%x))
        idir = glob.glob(os.path.join(SW, 'lib', 'ImageMagick-*'))[-1]
        dest = os.path.join(self.frameworks_dir, 'ImageMagick')
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(idir, dest, True)
        for x in os.walk(dest):
            for f in x[-1]:
                if f.endswith('.so'):
                    f = join(x[0], f)
                    self.fix_dependencies_in_lib(f)

    @flush
    def add_misc_libraries(self):
        for x in ('usb-1.0.0', 'mtp.9', 'ltdl.7',
                  'chm.0', 'sqlite3.0', 'icudata.53', 'icui18n.53', 'icuio.53', 'icuuc.53'):
            info('\nAdding', x)
            x = 'lib%s.dylib'%x
            shutil.copy2(join(SW, 'lib', x), self.frameworks_dir)
            dest = join(self.frameworks_dir, x)
            self.set_id(dest, self.FID+'/'+x)
            self.fix_dependencies_in_lib(dest)

    @flush
    def add_site_packages(self):
        info('\nAdding site-packages')
        os.makedirs(self.site_packages)
        paths = reversed(map(abspath, [x for x in sys.path if x.startswith('/')]))
        upaths = []
        for x in paths:
            if x not in upaths and (x.endswith('.egg') or
                    x.endswith('/site-packages')):
                upaths.append(x)
        upaths.append(os.path.expanduser('~/build/calibre/src'))
        for x in upaths:
            info('\t', x)
            tdir = None
            try:
                if not os.path.isdir(x):
                    try:
                        zf = zipfile.ZipFile(x)
                    except:
                        self.warn(x, 'is neither a directory nor a zipfile')
                        continue
                    tdir = tempfile.mkdtemp()
                    zf.extractall(tdir)
                    x = tdir
                self.add_modules_from_dir(x)
                self.add_packages_from_dir(x)
            finally:
                if tdir is not None:
                    shutil.rmtree(tdir)
        shutil.rmtree(os.path.join(self.site_packages, 'calibre', 'plugins'))
        sp = join(self.resources_dir, 'Python', 'site-packages')
        for x in os.listdir(join(sp, 'PyQt5')):
            if x.endswith('.so') and x.rpartition('.')[0] not in PYQT_MODULES:
                os.remove(join(sp, 'PyQt5', x))
        os.remove(join(sp, 'PyQt5', 'uic/port_v3/proxy_base.py'))
        self.remove_bytecode(sp)

    @flush
    def add_modules_from_dir(self, src):
        for x in glob.glob(join(src, '*.py'))+glob.glob(join(src, '*.so')):
            shutil.copy2(x, self.site_packages)
            if x.endswith('.so'):
                self.fix_dependencies_in_lib(x)

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
            ans  = []
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
        info('\nAdding python stdlib')
        src = SW + '/python/Python.framework/Versions/Current/lib/python'
        src += self.version_info
        dest = join(self.resources_dir, 'Python', 'lib', 'python')
        dest += self.version_info
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
        self.remove_bytecode(join(self.resources_dir, 'Python', 'lib'))
        confdir = join(self.resources_dir, 'Python',
                'lib/python%s/config'%self.version_info)
        os.makedirs(confdir)
        shutil.copy2(join(src, 'config/Makefile'), confdir)
        incdir = join(self.resources_dir, 'Python',
                'include/python'+self.version_info)
        os.makedirs(incdir)
        shutil.copy2(join(src.replace('/lib/', '/include/'), 'pyconfig.h'),
                incdir)

    @flush
    def remove_bytecode(self, dest):
        for x in os.walk(dest):
            root = x[0]
            for f in x[-1]:
                if os.path.splitext(f) in ('.pyc', '.pyo'):
                    os.remove(join(root, f))

    @flush
    def compile_py_modules(self):
        info('\nCompiling Python modules')
        base = join(self.resources_dir, 'Python')
        for x in os.walk(base):
            root = x[0]
            for f in x[-1]:
                if f.endswith('.py'):
                    y = join(root, f)
                    rel = os.path.relpath(y, base)
                    try:
                        py_compile.compile(y, dfile=rel, doraise=True)
                        os.remove(y)
                    except:
                        self.warn('WARNING: Failed to byte-compile', y)

    def create_app_clone(self, name, specialise_plist):
        info('\nCreating ' + name)
        cc_dir = os.path.join(self.contents_dir, name, 'Contents')
        exe_dir = join(cc_dir, 'MacOS')
        os.makedirs(exe_dir)
        for x in os.listdir(self.contents_dir):
            if x.endswith('.app'):
                continue
            if x == 'Info.plist':
                plist = plistlib.readPlist(join(self.contents_dir, x))
                specialise_plist(plist)
                plist.pop('CFBundleDocumentTypes')
                exe = plist['CFBundleExecutable']
                # We cannot symlink the bundle executable as if we do,
                # codesigning fails
                nexe = plist['CFBundleExecutable'] = exe + '-placeholder-for-codesigning'
                shutil.copy2(join(self.contents_dir, 'MacOS', exe), join(exe_dir, nexe))
                exe = join(exe_dir, plist['CFBundleExecutable'])
                plistlib.writePlist(plist, join(cc_dir, x))
            elif x == 'MacOS':
                for item in os.listdir(join(self.contents_dir, 'MacOS')):
                    os.symlink('../../../MacOS/'+item, join(exe_dir, item))
            else:
                os.symlink(join('../..', x), join(cc_dir, x))

    @flush
    def create_console_app(self):
        def specialise_plist(plist):
            plist['LSBackgroundOnly'] = '1'
            plist['CFBundleIdentifier'] = 'com.calibre-ebook.console'
            plist['CFBundleExecutable'] = 'calibre-parallel'
        self.create_app_clone('console.app', specialise_plist)
        # Comes from the terminal-notifier project:
        # https://github.com/alloy/terminal-notifier
        shutil.copytree(join(SW, 'build/notifier.app'), join(
            self.contents_dir, 'calibre-notifier.app'))

    @flush
    def create_gui_apps(self):
        def specialise_plist(launcher, plist):
            plist['CFBundleDisplayName'] = plist['CFBundleName'] = {
                'ebook-viewer':'E-book Viewer', 'ebook-edit':'Edit Book', 'calibre-debug': 'calibre (debug)',
            }[launcher]
            plist['CFBundleExecutable'] = launcher
            if launcher != 'calibre-debug':
                plist['CFBundleIconFile'] = launcher + '.icns'
            plist['CFBundleIdentifier'] = 'com.calibre-ebook.' + launcher
        for launcher in ('ebook-viewer', 'ebook-edit', 'calibre-debug'):
            self.create_app_clone(launcher + '.app', partial(specialise_plist, launcher))

    @flush
    def copy_site(self):
        base = os.path.dirname(__file__)
        shutil.copy2(join(base, 'site.py'), join(self.resources_dir, 'Python',
            'lib', 'python'+self.version_info))

    @flush
    def makedmg(self, d, volname,
                destdir='dist',
                internet_enable=True,
                format='UDBZ'):
        ''' Copy a directory d into a dmg named volname '''
        info('\nSigning...')
        sys.stdout.flush()
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        dmg = os.path.join(destdir, volname+'.dmg')
        if os.path.exists(dmg):
            os.unlink(dmg)
        tdir = tempfile.mkdtemp()
        appdir = os.path.join(tdir, os.path.basename(d))
        shutil.copytree(d, appdir, symlinks=True)
        with timeit() as times:
            sign_app(appdir)
        info('Signing completed in %d minutes %d seconds' % tuple(times))
        os.symlink('/Applications', os.path.join(tdir, 'Applications'))
        size_in_mb = int(subprocess.check_output(['du', '-s', '-k', tdir]).decode('utf-8').split()[0]) / 1024.
        cmd = ['/usr/bin/hdiutil', 'create', '-srcfolder', tdir, '-volname', volname, '-format', format]
        if 190 < size_in_mb < 250:
            # We need -size 255m because of a bug in hdiutil. When the size of
            # srcfolder is close to 200MB hdiutil fails with
            # diskimages-helper: resize request is above maximum size allowed.
            cmd += ['-size', '255m']
        info('\nCreating dmg...')
        with timeit() as times:
            subprocess.check_call(cmd + [dmg])
            if internet_enable:
                subprocess.check_call(['/usr/bin/hdiutil', 'internet-enable', '-yes', dmg])
        info('dmg created in %d minutes and %d seconds' % tuple(times))
        shutil.rmtree(tdir)
        size = os.stat(dmg).st_size/(1024*1024.)
        info('\nInstaller size: %.2fMB\n'%size)
        return dmg

def test_exe():
    build_dir = abspath(join('build', APPNAME+'.app'))
    py2app = Py2App(build_dir)
    py2app.create_exe()
    return 0


def main(test=False, dont_strip=False):
    if 'test_exe' in sys.argv:
        return test_exe()
    build_dir = abspath(join(os.path.dirname(SRC), 'build', APPNAME+'.app'))
    Py2App(build_dir, test_launchers=test, dont_strip=dont_strip)
    return 0


if __name__ == '__main__':
    sys.exit(main())
