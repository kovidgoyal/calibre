#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, plistlib, subprocess, glob, zipfile, tempfile, \
    py_compile, stat, operator
abspath, join, basename = os.path.abspath, os.path.join, os.path.basename

from setup import __version__ as VERSION, __appname__ as APPNAME, basenames, \
        modules as main_modules, Command, SRC, functions as main_functions
LICENSE = open('LICENSE', 'rb').read()
MAGICK_HOME='@executable_path/../Frameworks/ImageMagick'
ENV = dict(
        FC_CONFIG_DIR='@executable_path/../Resources/fonts',
        FC_CONFIG_FILE='@executable_path/../Resources/fonts/fonts.conf',
        MAGICK_CONFIGURE_PATH=MAGICK_HOME+'/config',
        MAGICK_CODER_MODULE_PATH=MAGICK_HOME+'/modules-Q16/coders',
        MAGICK_CODER_FILTER_PATH=MAGICK_HOME+'/modules-Q16/filter',
        QT_PLUGIN_PATH='@executable_path/../MacOS',
        PYTHONIOENCODING='UTF-8',
        )

SW = os.environ.get('SW', '/sw')

info = warn = None

class OSX32_Freeze(Command):

    description = 'Freeze OSX calibre installation'

    def add_options(self, parser):
        parser.add_option('--test-launchers', default=False,
                action='store_true',
                help='Only build launchers')


    def run(self, opts):
        global info, warn
        info, warn = self.info, self.warn
        main(opts.test_launchers)

def compile_launcher_lib(contents_dir, gcc, base):
    info('\tCompiling calibre_launcher.dylib')
    fd = join(contents_dir, 'Frameworks')
    dest = join(fd, 'calibre-launcher.dylib')
    src = join(base, 'util.c')
    cmd = [gcc] + '-Wall -arch i386 -arch x86_64 -dynamiclib -std=gnu99'.split() + [src] + \
            ['-I'+base] + \
            ['-I/sw/python/Python.framework/Versions/Current/Headers'] + \
            '-current_version 1.0 -compatibility_version 1.0'.split() + \
            '-fvisibility=hidden -o'.split() + [dest] + \
            ['-install_name',
                '@executable_path/../Frameworks/'+os.path.basename(dest)] + \
            ['-F/sw/python', '-framework', 'Python', '-framework', 'CoreFoundation', '-headerpad_max_install_names']
    info('\t'+' '.join(cmd))
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
    for program, x in xprograms.items():
        module, func = x
        info('\tCompiling', program)
        out = join(contents_dir, 'MacOS', program)
        programs.append(out)
        psrc = src.replace('**PROGRAM**', program)
        psrc = psrc.replace('**MODULE**', module)
        psrc = psrc.replace('**FUNCTION**', func)
        psrc = psrc.replace('**PYVER**', pyver)
        fsrc = '/tmp/%s.c'%program
        with open(fsrc, 'wb') as f:
            f.write(psrc)
        cmd = [gcc, '-Wall', '-arch', 'x86_64', '-arch', 'i386',
                '-I'+base, fsrc, lib, '-o', out,
            '-headerpad_max_install_names']
        info('\t'+' '.join(cmd))
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

    def __init__(self, build_dir, test_launchers=False):
        self.build_dir = build_dir
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
            self.add_libjpeg()
            self.add_libpng()
            self.add_fontconfig()
            self.add_imagemagick()
            self.add_misc_libraries()

            self.add_resources()
            self.compile_py_modules()

            self.create_console_app()

        self.copy_site()
        self.create_exe()
        if not test_launchers:
            self.strip_files()

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
            progs += list(zip(basenames[x], main_modules[x], main_functions[x]))
        for program, module, func in progs:
            programs[program] = (module, func)
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
        raw = subprocess.Popen(['otool', '-L', path_to_lib],
                stdout=subprocess.PIPE).stdout.read()
        for line in raw.splitlines():
            if 'compatibility' not in line or line.strip().endswith(':'):
                continue
            idx = line.find('(')
            path = line[:idx].strip()
            yield path

    @flush
    def get_local_dependencies(self, path_to_lib):
        for x in self.get_dependencies(path_to_lib):
            if x.startswith('libpodofo'):
                yield x, x
                continue
            for y in (SW+'/lib/', '/usr/local/lib/', SW+'/qt/lib/',
                    '/opt/local/lib/',
                    SW+'/python/Python.framework/', SW+'/freetype/lib/'):
                if x.startswith(y):
                    if y == SW+'/python/Python.framework/':
                        y = SW+'/python/'
                    yield x, x[len(y):]
                    break

    @flush
    def change_dep(self, old_dep, new_dep, path_to_lib):
        info('\tResolving dependency %s to'%old_dep, new_dep)
        subprocess.check_call(['install_name_tool', '-change', old_dep, new_dep,
            path_to_lib])

    @flush
    def fix_dependencies_in_lib(self, path_to_lib):
        info('\nFixing dependencies in', path_to_lib)
        self.to_strip.append(path_to_lib)
        old_mode = flipwritable(path_to_lib)
        for dep, bname in self.get_local_dependencies(path_to_lib):
            ndep = self.FID+'/'+bname
            self.change_dep(dep, ndep, path_to_lib)
        if list(self.get_local_dependencies(path_to_lib)):
            raise Exception('Failed to resolve deps in: '+path_to_lib)
        if old_mode is not None:
            flipwritable(path_to_lib, old_mode)

    @flush
    def add_python_framework(self):
        info('\nAdding Python framework')
        src = join('/sw/python', 'Python.framework')
        x = join(self.frameworks_dir, 'Python.framework')
        curr = os.path.realpath(join(src, 'Versions', 'Current'))
        currd = join(x, 'Versions', basename(curr))
        rd = join(currd, 'Resources')
        os.makedirs(rd)
        shutil.copy2(join(curr, 'Resources', 'Info.plist'), rd)
        shutil.copy2(join(curr, 'Python'), currd)
        self.set_id(join(currd, 'Python'),
            self.FID+'/Python.framework/Versions/%s/Python'%basename(curr))

    @flush
    def add_qt_frameworks(self):
        info('\nAdding Qt Framework')
        for f in ('QtCore', 'QtGui', 'QtXml', 'QtNetwork', 'QtSvg', 'QtWebKit',
                'QtXmlPatterns'):
            self.add_qt_framework(f)
        for d in glob.glob(join(SW, 'qt', 'plugins', '*')):
            shutil.copytree(d, join(self.contents_dir, 'MacOS', basename(d)))
        for l in glob.glob(join(self.contents_dir, 'MacOS', '*/*.dylib')):
            self.fix_dependencies_in_lib(l)
            x = os.path.relpath(l, join(self.contents_dir, 'MacOS'))
            self.set_id(l, '@executable_path/'+x)

    @flush
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

    @flush
    def create_skeleton(self):
        c = join(self.build_dir, 'Contents')
        for x in ('Frameworks', 'MacOS', 'Resources'):
            os.makedirs(join(c, x))
        for x in ('library.icns', 'book.icns'):
            shutil.copyfile(join('icons', x), join(self.resources_dir, x))

    @flush
    def add_calibre_plugins(self):
        dest = join(self.frameworks_dir, 'plugins')
        os.mkdir(dest)
        for f in glob.glob('src/calibre/plugins/*.so'):
            shutil.copy2(f, dest)
            self.fix_dependencies_in_lib(join(dest, basename(f)))
            if 'podofo' in f:
                self.change_dep('libpodofo.0.8.4.dylib',
                self.FID+'/'+'libpodofo.0.8.4.dylib', join(dest, basename(f)))


    @flush
    def create_plist(self):
        from calibre.ebooks import BOOK_EXTENSIONS
        env = dict(**ENV)
        env['CALIBRE_LAUNCHED_FROM_BUNDLE']='1';
        docs = [{'CFBundleTypeName':'E-book',
            'CFBundleTypeExtensions':list(BOOK_EXTENSIONS),
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
                LSMinimumSystemVersion='10.5.2',
                LSRequiresNativeExecution=True,
                NSAppleScriptEnabled=False,
                NSHumanReadableCopyright='Copyright 2010, Kovid Goyal',
                CFBundleGetInfoString=('calibre, an E-book management '
                'application. Visit http://calibre-ebook.com for details.'),
                CFBundleIconFile='library.icns',
                LSMultipleInstancesProhibited=True,
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
        pdf = join(SW, 'lib', 'libpodofo.0.8.4.dylib')
        self.install_dylib(pdf)

    @flush
    def add_poppler(self):
        info('\nAdding poppler')
        for x in ('libpoppler.25.dylib',):
            self.install_dylib(os.path.join(SW, 'lib', x))
        self.install_dylib(os.path.join(SW, 'bin', 'pdftohtml'), False)

    @flush
    def add_libjpeg(self):
        info('\nAdding libjpeg')
        self.install_dylib(os.path.join(SW, 'lib', 'libjpeg.8.dylib'))

    @flush
    def add_libpng(self):
        info('\nAdding libpng')
        self.install_dylib(os.path.join(SW, 'lib', 'libpng12.0.dylib'))
        self.install_dylib(os.path.join(SW, 'lib', 'libpng.3.dylib'))


    @flush
    def add_fontconfig(self):
        info('\nAdding fontconfig')
        for x in ('fontconfig.1', 'freetype.6', 'expat.1'):
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
        <dir>/Network/Library/Fonts</dir>
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
        for x in ('Wand', 'Core'):
            self.install_dylib(os.path.join(SW, 'lib', 'libMagick%s.5.dylib'%x))
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
        for x in ('usb', 'unrar', 'readline.6.1', 'wmflite-0.2.7', 'chm.0',
                'sqlite3.0'):
            info('\nAdding', x)
            x = 'lib%s.dylib'%x
            shutil.copy2(join(SW, 'lib', x), self.frameworks_dir)
            self.set_id(join(self.frameworks_dir, x), self.FID+'/'+x)

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
        self.remove_bytecode(join(self.resources_dir, 'Python', 'site-packages'))

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
        src = '/sw/python/Python.framework/Versions/Current/lib/python'
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

    @flush
    def remove_bytecode(self, dest):
        for x in os.walk(dest):
            root = x[0]
            for f in x[-1]:
                if os.path.splitext(f) in ('.pyc', '.pyo'):
                    os.remove(join(root, f))

    @flush
    def compile_py_modules(self):
        info( '\nCompiling Python modules')
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

    @flush
    def create_console_app(self):
        info( '\nCreating console.app')
        cc_dir = os.path.join(self.contents_dir, 'console.app', 'Contents')
        os.makedirs(cc_dir)
        for x in os.listdir(self.contents_dir):
            if x == 'console.app':
                continue
            if x == 'Info.plist':
                plist = plistlib.readPlist(join(self.contents_dir, x))
                plist['LSUIElement'] = '1'
                plist.pop('CFBundleDocumentTypes')
                plistlib.writePlist(plist, join(cc_dir, x))
            else:
                os.symlink(join('../..', x),
                           join(cc_dir, x))

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
        info('\nCreating dmg')
        sys.stdout.flush()
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        dmg = os.path.join(destdir, volname+'.dmg')
        if os.path.exists(dmg):
            os.unlink(dmg)
        tdir = tempfile.mkdtemp()
        shutil.copytree(d, os.path.join(tdir, os.path.basename(d)),
                symlinks=True)
        os.symlink('/Applications', os.path.join(tdir, 'Applications'))
        subprocess.check_call(['/usr/bin/hdiutil', 'create', '-srcfolder', tdir,
                               '-volname', volname, '-format', format, dmg])
        shutil.rmtree(tdir)
        if internet_enable:
           subprocess.check_call(['/usr/bin/hdiutil', 'internet-enable', '-yes', dmg])
        size = os.stat(dmg).st_size/(1024*1024.)
        info('\nInstaller size: %.2fMB\n'%size)
        return dmg

def test_exe():
    build_dir = abspath(join('build', APPNAME+'.app'))
    py2app = Py2App(build_dir)
    py2app.create_exe()
    return 0


def main(test=False):
    if 'test_exe' in sys.argv:
        return test_exe()
    build_dir = abspath(join(os.path.dirname(SRC), 'build', APPNAME+'.app'))
    Py2App(build_dir, test_launchers=test)
    return 0


if __name__ == '__main__':
    sys.exit(main())
