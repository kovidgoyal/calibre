#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, plistlib, subprocess, glob, zipfile, tempfile, \
    py_compile, stat, operator
abspath, join, basename = os.path.abspath, os.path.join, os.path.basename

l = {}
exec open('setup.py').read() in l
VERSION = l['VERSION']
APPNAME = l['APPNAME']
scripts = l['scripts']
basenames = l['basenames']
main_functions = l['main_functions']
main_modules = l['main_modules']
LICENSE = open('LICENSE', 'rb').read()
ENV = dict(
        FC_CONFIG_DIR='@executable_path/../Resources/fonts',
        MAGICK_HOME='@executable_path/../Frameworks/ImageMagick',
        PYTHONDONTWRITEBYTECODE='1',
        PYTHONIOENCODING='utf-8:replace',
        PYTHONPATH='@executable_path/../Resources/Python/site-packages',
        PYTHONHOME='@executable_path/../Resources/Python',
        )

SW = os.environ.get('SW')

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
    tostrip = [(fn, flipwritable(fn)) for fn in files]
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

class Py2App(object):

    FID = '@executable_path/../Frameworks'

    def __init__(self, build_dir):
        self.build_dir = build_dir
        self.contents_dir = join(self.build_dir, 'Contents')
        self.resources_dir = join(self.contents_dir, 'Resources')
        self.frameworks_dir = join(self.contents_dir, 'Frameworks')
        self.to_strip = []

    def run(self):
        self.create_skeleton()
        self.create_plist()

        self.add_python_framework()
        self.add_qt_frameworks()
        self.add_calibre_plugins()
        self.add_podofo()
        self.add_poppler()
        self.add_libjpeg()
        self.add_libpng()
        self.add_fontconfig()
        self.add_imagemagick()
        self.add_misc_libraries()

        self.add_site_packages()
        self.add_stdlib()
        self.compile_py_modules()

        self.create_console_app()

        self.copy_launcher_and_site()
        self.create_exe()
        self.strip_files()

        return self.makedmg(self.builddir, APPNAME+'-'+VERSION+'-x86_64')

    def strip_files(self):
        print '\nStripping files...'
        strip_files(self.to_strip)

    def create_exe(self):
        gcc = os.environ.get('GCC', 'gcc')
        base = os.path.dirname(__file__)
        out = join(self.contents_dir, 'MacOS', 'calibre')
        subprocess.check_call([gcc, '-Wall', '-arch x86_64', join(base,
            'main.c'), '-o', out])
        self.to_strip(out)

    def set_id(self, path_to_lib, new_id):
        old_mode = flipwritable(path_to_lib)
        subprocess.check_call(['install_name_tool', '-id', new_id, path_to_lib])
        if old_mode is not None:
            flipwritable(path_to_lib, old_mode)

    def get_dependencies(self, path_to_lib):
        raw = subprocess.Popen(['otool', '-L', path_to_lib],
                stdout=subprocess.PIPE).stdout.read()
        for line in raw.splitlines():
            if 'compatibility' not in line:
                continue
            idx = line.find('(')
            path = line[:idx].strip()
            bname = os.path.basename(path).partition('.')[0]
            if bname in path_to_lib:
                continue
            yield path

    def get_local_dependencies(self, path_to_lib):
        for x in self.get_dependencies(path_to_lib):
            for y in (SW+'/lib/', '/usr/local/lib/', SW+'/qt/lib/',
                    SW+'/python/'):
                if x.startswith(y):
                    yield x, x[len(y):]
                    break

    def change_dep(self, old_dep, new_dep, path_to_lib):
        print '\tResolving dependency %s to'%old_dep, new_dep
        subprocess.check_call(['install_name_tool', '-change', old_dep, new_dep,
            path_to_lib])

    def fix_dependencies_in_lib(self, path_to_lib):
        print '\nFixing dependencies in', path_to_lib
        self.to_strip.append(path_to_lib)
        old_mode = flipwritable(path_to_lib)
        for dep, bname in self.get_local_dependencies(path_to_lib):
            ndep = self.FID+'/'+bname
            self.change_dep(dep, ndep, path_to_lib)
        if list(self.get_local_dependencies(path_to_lib)):
            raise Exception('Failed to resolve deps in: '+path_to_lib)
        if old_mode is not None:
            flipwritable(path_to_lib, old_mode)

    def add_python_framework(self):
        src = join(SW, 'python', 'Python.framework')
        x = join(self.frameworks_dir, 'Python.framework')
        curr = os.path.realpath(join(src, 'Versions', 'Current'))
        currd = join(x, 'Versions', basename(curr))
        rd = join(currd, 'Resources')
        os.makedirs(rd)
        shutil.copy2(join(curr, 'Resources', 'Info.plist'), rd)
        shutil.copy2(join(curr, 'Python'), currd)
        self.set_id(join(currd, 'Python'),
            self.FID+'/Python.framework/Versions/%s/Python'%basename(curr))

    def add_qt_frameworks(self):
        for f in ('QtCore', 'QtGui', 'QtXml', 'QtNetwork', 'QtSvg', 'QtWebkit',
                'phonon'):
            self.add_qt_framework(f)
        for d in glob.glob(join(SW, 'qt', 'plugins', '*')):
            shutil.copytree(d, join(self.contents_dir, 'MacOS', basename(d)))
        for l in glob.glob(join(self.contents_dir, 'MacOS', '*/*.dylib')):
            self.fix_dependencies_in_lib(l)
            x = os.path.relpath(l, join(self.contents_dir, 'MacOS'))
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

    def create_skeleton(self):
        c = join(self.build_dir, 'Contents')
        for x in ('Frameworks', 'MacOS', 'Resources'):
            os.makedirs(join(c, x))
        x = 'library.icns'
        shutil.copyfile(join('icons', x), join(self.resources_dir, x))

    def add_calibre_plugins(self):
        dest = join(self.frameworks_dir, 'plugins')
        os.mkdir(dest)
        for f in glob.glob('src/calibre/plugins/*.so'):
            shutil.copy2(f, dest)
        self.fix_dependencies_in_lib(join(dest, basename(f)))


    def create_plist(self):
        pl = dict(
                CFBundleDevelopmentRegion='English',
                CFBundleDisplayName=APPNAME,
                CFBundleName=APPNAME,
                CFBundleIdentifier='net.kovidgoyal.calibre',
                CFBundleVersion=VERSION,
                CFBundlePackageType='APPL',
                CFBundleSignature='????',
                CFBundleExecutable='calibre',
                LSMinimumSystemVersion='10.5.2',
                PyRuntimeLocations=[self.FID+'/Python.framework/Versions/Current/Python'],
                LSRequiresNativeExecution=True,
                NSAppleScriptEnabled=False,
                NSHumanReadableCopyright='Copyright 2008, Kovid Goyal',
                CFBundleGetInfoString=('calibre, an E-book management '
                'application. Visit http://calibre.kovidgoyal.net for details.'),
                CFBundleIconFile='library.icns',
                LSMultipleInstancesProhibited=True,
                LSEnvironment=ENV
        )
        plistlib.writePlist(pl, join(self.contents_dir, 'Info.plist'))

    def install_dylib(self, path, set_id=True):
        shutil.copy2(path, self.frameworks_dir)
        if set_id:
            self.set_id(join(self.frameworks_dir, basename(path)),
                    self.FID+'/'+basename(path))
        self.fix_dependencies_in_lib(join(self.frameworks_dir, basename(path)))

    def add_podofo(self):
        print '\nAdding PoDoFo'
        pdf = join(SW, 'lib', 'libpodofo.0.6.99.dylib')
        self.install_dylib(pdf)

    def add_poppler(self):
        print '\nAdding poppler'
        for x in ('libpoppler.4.dylib', 'libpoppler-qt4.3.dylib'):
            self.install_dylib(os.path.join(SW, 'lib', x))
        self.install_dylib(os.path.join(SW, 'bin', 'pdftohtml'), False)

    def add_libjpeg(self):
        print '\nAdding libjpeg'
        self.install_dylib(os.path.join(SW, 'lib', 'libjpeg.7.dylib'))

    def add_libpng(self):
        print '\nAdding libpng'
        self.install_dylib(os.path.join(SW, 'lib', 'libpng12.0.dylib'))

    def add_fontconfig(self):
        print '\nAdding fontconfig'
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

    def add_imagemagick(self):
        print '\nAdding ImageMagick'
        for x in ('Wand', 'Core'):
            self.install_dylib(os.path.join(SW, 'lib', 'libMagick%s.2.dylib'%x))
        idir = glob.glob(os.path.join(SW, 'lib', 'ImageMagick-*'))[-1]
        dest = os.path.join(self.frameworks_dir, 'ImageMagick', 'lib')
        if not os.path.exists(dest):
            os.makedirs(dest)
        dest = os.path.join(dest, os.path.basename(idir))
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(idir, dest, True)
        for x in os.walk(dest):
            for f in x[-1]:
                if f.endswith('.so'):
                    f = join(x[0], f)
                    self.fix_dependencies_in_lib(f)

    def add_misc_libraries(self):
        for x in ('usb', 'unrar'):
            print '\nAdding', x
            shutil.copy2(join(SW, 'lib', 'lib%s.dylib'%x), self.frameworks_dir)

    def add_site_packages(self):
        print '\nAdding site-packages'
        self.site_packages = join(self.resources_dir, 'Python', 'site-packages')
        os.makedirs(self.site_packages)
        paths = reversed(map(abspath, [x for x in sys.path if x.startswith('/')]))
        upaths = []
        for x in paths:
            if x not in upaths:
                upaths.append(x)
        for x in upaths:
            if x.endswith('/PIL') or 'site-packages' not in x:
                continue
            tdir = None
            try:
                if not os.path.isdir(x):
                    try:
                        zf = zipfile.ZipFile(x)
                    except:
                        print "WARNING:", x, 'is neither a directory nor a zipfile'
                        continue
                    tdir = tempfile.mkdtemp()
                    zf.extractall(tdir)
                    x = tdir
                self.add_modules_from_dir(x)
                self.add_packages_from_dir(x)
            finally:
                if tdir is not None:
                    shutil.rmtree(tdir)
        self.remove_bytecode(join(self.resources_dir, 'Python', 'site-packages'))

    def add_modules_from_dir(self, src):
        for x in glob.glob(join(src, '*.py'))+glob.glob(join(src, '*.so')):
            dest = join(self.site_packages, basename(x))
            shutil.copy2(x, self.site_packages)
            if x.endswith('.so'):
                self.fix_dependencies_in_lib(x)

    def add_packages_from_dir(self, src):
        for x in os.listdir(src):
            x = join(src, x)
            if os.path.isdir(x) and os.path.exists(join(x, '__init__.py')):
                if self.filter_package(basename(x)):
                    continue
                self.add_package_dir(x)

    def add_package_dir(self, x, dest=None):
        def ignore(root, files):
            ans  = []
            for y in files:
                if os.path.splitext(y) in ('.py', '.so'):
                    continue
            ans.append(y)
            return ans
        if dest is None:
            dest = self.site_packages
        dest = join(dest, basename(x))
        shutil.copytree(x, dest, symlinks=True, ignore=ignore)
        self.postprocess_package(x, dest)

    def filter_package(self, name):
        return name in ('Cython', 'modulegraph', 'macholib', 'py2app',
        'bdist_mpkg', 'altgraph')

    def postprocess_package(self, src_path, dest_path):
        pass

    def add_stdlib(self):
        print '\nAdding python stdlib'
        src = join(SW, '/python/Python.framework/Versions/Current/lib/python')
        src += '.'.join(map(str, sys.version_info[:2]))
        dest = join(self.resources_dir, 'Python', 'lib', 'python')
        dest += '.'.join(map(str, sys.version_info[:2]))
        for x in os.listdir(src):
            if x in ('site-packages', 'config', 'test', 'lib2to3', 'lib-tk',
            'lib-old', 'idlelib', 'plat-mac', 'plat-darwin', 'site.py'):
                continue
            if os.path.isdir(x):
                self.add_package_dir(join(src, x), dest)
            elif os.path.splitext(x) in ('.so', '.py'):
                shutil.copy2(join(src, x), dest)
                dest = join(dest, basename(x))
                if dest.endswith('.so'):
                    self.fix_dependencies_in_lib(dest)
        self.remove_bytecode(join(self.resources_dir, 'Python', 'lib'))

    def remove_bytecode(self, dest):
        for x in os.walk(dest):
            root = x[0]
            for f in x[-1]:
                if os.path.splitext(f) in ('.pyc', '.pyo'):
                    os.remove(join(root, f))

    def compile_py_modules(self):
        print '\nCompiling Python modules'
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
                        print 'WARNING: Failed to byte-compile', y

    def create_console_app(self):
        print '\nCreating console.app'
        cc_dir = os.path.join(self.contents_dir, 'console.app', 'Contents')
        os.makedirs(cc_dir)
        for x in os.listdir(self.contents_dir):
            if x == 'console.app':
                continue
            if x == 'Info.plist':
                plist = plistlib.readPlist(join(self.contents_dir, x))
                plist['LSUIElement'] = '1'
                plistlib.writePlist(plist, join(cc_dir, x))
            else:
                os.symlink(join('../..', x),
                           join(cc_dir, x))

    def copy_launcher_and_site(self):
        base = os.path.dirname(__file__)
        for x in ('launcher', 'site'):
            shutil.copy2(join(base, x+'.py'), self.resources_dir)

    def makedmg(self, d, volname,
                destdir='dist',
                internet_enable=True,
                format='UDBZ'):
        ''' Copy a directory d into a dmg named volname '''
        dmg = os.path.join(destdir, volname+'.dmg')
        if os.path.exists(dmg):
            os.unlink(dmg)
        subprocess.check_call(['/usr/bin/hdiutil', 'create', '-srcfolder', os.path.abspath(d),
                               '-volname', volname, '-format', format, dmg])
        if internet_enable:
           subprocess.check_call(['/usr/bin/hdiutil', 'internet-enable', '-yes', dmg])
        return dmg



def main():
    build_dir = abspath(join('build', APPNAME+'.app'))
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)
    py2app = Py2App(build_dir)
    py2app.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
