#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement, print_function

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, glob, py_compile, subprocess, re, zipfile, time, errno, stat

from setup import (Command, modules, functions, basenames, __version__,
    __appname__)
from setup.build_environment import (
    msvc, MT, RC, is64bit, ICU as ICU_DIR, sw as SW, QT_DLLS, QMAKE, QT_PLUGINS, PYQT_MODULES)
from setup.installer.windows.wix import WixMixIn

OPENSSL_DIR = os.environ.get('OPENSSL_DIR', os.path.join(SW, 'private', 'openssl'))
IMAGEMAGICK = os.path.join(SW, 'build', 'ImageMagick-*\\VisualMagick\\bin')
LZMA = os.path.join(SW, *('private/easylzma/build/easylzma-0.0.8'.split('/')))
QT_DIR = subprocess.check_output([QMAKE, '-query', 'QT_INSTALL_PREFIX']).decode('utf-8').strip()

VERSION = re.sub('[a-z]\d+', '', __version__)
WINVER = VERSION+'.0'
machine = 'X64' if is64bit else 'X86'

DESCRIPTIONS = {
        'calibre' : 'The main calibre program',
        'ebook-viewer' : 'The calibre e-book viewer',
        'ebook-edit'   : 'The calibre e-book editor',
        'lrfviewer'    : 'Viewer for LRF files',
        'ebook-convert': 'Command line interface to the conversion/news download system',
        'ebook-meta'   : 'Command line interface for manipulating e-book metadata',
        'calibredb'    : 'Command line interface to the calibre database',
        'calibre-launcher' : 'Utility functions common to all executables',
        'calibre-debug' : 'Command line interface for calibre debugging/development',
        'calibre-customize' : 'Command line interface to calibre plugin system',
        'pdfmanipulate' : 'Command line tool to manipulate PDF files',
        'calibre-server': 'Standalone calibre content server',
        'calibre-parallel': 'calibre worker process',
        'calibre-smtp' : 'Command line interface for sending books via email',
        'calibre-eject' : 'Helper program for ejecting connected reader devices',
        'calibre-file-dialog' : 'Helper program to show file open/save dialogs',
}

# https://msdn.microsoft.com/en-us/library/windows/desktop/dn481241(v=vs.85).aspx
SUPPORTED_OS = {
    'vista': '{e2011457-1546-43c5-a5fe-008deee3d3f0}',
    'w7'   : '{35138b9a-5d96-4fbd-8e2d-a2440225f93a}',
    'w8'   : '{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}',
    'w81'  : '{1f676c76-80e1-4239-95bb-83d0f6d0da78}',
    'w10'  : '{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}',
}

EXE_MANIFEST = '''\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
  <assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
    <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
        <security>
            <requestedPrivileges>
                <requestedExecutionLevel level="asInvoker" uiAccess="false" />
            </requestedPrivileges>
        </security>
    </trustInfo>
    <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
      <application>
          <supportedOS Id="{vista}"/>
          <supportedOS Id="{w7}"/>
          <supportedOS Id="{w8}"/>
          <supportedOS Id="{w81}"/>
          <supportedOS Id="{w10}"/>
      </application>
    </compatibility>
  </assembly>
'''.format(**SUPPORTED_OS)

def walk(dir):
    ''' A nice interface to os.walk '''
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)

class Win32Freeze(Command, WixMixIn):

    description = 'Freeze windows calibre installation'

    def add_options(self, parser):
        parser.add_option('--no-ice', default=False, action='store_true',
                help='Disable ICE checks when building MSI (needed when running'
                ' from cygwin sshd)')
        parser.add_option('--msi-compression', '--compress', default='high',
                help='Compression when generating installer. Set to none to disable')
        parser.add_option('--keep-site', default=False, action='store_true',
            help='Keep human readable site.py')
        parser.add_option('--verbose', default=0, action="count",
                help="Be more verbose")
        parser.add_option('--no-installer', default=False, action='store_true',
                         help='Dont build the installer')
        if not parser.has_option('--dont-strip'):
            parser.add_option('-x', '--dont-strip', default=False,
                action='store_true', help='Dont strip the generated binaries (no-op on windows)')

    def run(self, opts):
        self.python_base = os.path.join(SW, 'private', 'python')
        self.portable_uncompressed_size = 0
        self.opts = opts
        self.src_root = self.d(self.SRC)
        self.base = self.j(self.d(self.SRC), 'build', 'winfrozen')
        self.app_base = self.j(self.base, 'app')
        self.rc_template = self.j(self.d(self.a(__file__)), 'template.rc')
        self.py_ver = ''.join(map(str, sys.version_info[:2]))
        self.lib_dir = self.j(self.app_base, 'Lib')
        self.pylib = self.j(self.app_base, 'pylib.zip')
        self.dll_dir = self.j(self.app_base, 'DLLs')
        self.portable_base = self.j(self.d(self.base), 'Calibre Portable')
        self.obj_dir = self.j(self.src_root, 'build', 'launcher')

        self.initbase()
        self.build_launchers()
        self.build_utils()
        self.freeze()
        self.embed_manifests()
        self.install_site_py()
        self.archive_lib_dir()
        self.copy_crt()
        if opts.no_installer:
            return
        self.create_installer()
        if not is64bit:
            self.build_portable()
            self.build_portable_installer()
        self.sign_installers()

    def initbase(self):
        if self.e(self.base):
            shutil.rmtree(self.base)
        os.makedirs(self.app_base)
        os.mkdir(self.dll_dir)

    def add_plugins(self):
        self.info('Adding plugins...')
        tgt = self.dll_dir
        base = self.j(self.SRC, 'calibre', 'plugins')
        for f in glob.glob(self.j(base, '*.pyd')):
            shutil.copy2(f, tgt)

    def freeze(self):
        shutil.copy2(self.j(self.src_root, 'LICENSE'), self.base)

        self.info('Adding resources...')
        tgt = self.j(self.app_base, 'resources')
        if os.path.exists(tgt):
            shutil.rmtree(tgt)
        shutil.copytree(self.j(self.src_root, 'resources'), tgt)

        self.info('Adding Qt...')
        for x in glob.glob(os.path.join(self.python_base, 'DLLs', '*')):
            shutil.copy2(x, self.dll_dir)
        for x in glob.glob(self.j(OPENSSL_DIR, 'bin', '*.dll')):
            shutil.copy2(x, self.dll_dir)
        for x in glob.glob(self.j(ICU_DIR, 'source', 'lib', '*.dll')):
            shutil.copy2(x, self.dll_dir)

        for x in QT_DLLS:
            shutil.copy2(os.path.join(QT_DIR, 'bin', x), self.dll_dir)
        shutil.copy2(os.path.join(self.python_base, 'python%s.dll'%self.py_ver), self.dll_dir)
        for dirpath, dirnames, filenames in os.walk(r'%s\Lib'%self.python_base):
            if os.path.basename(dirpath) == 'pythonwin':
                continue
            for f in filenames:
                if f.lower().endswith('.dll'):
                    f = self.j(dirpath, f)
                    shutil.copy2(f, self.dll_dir)
        self.add_plugins()

        def ignore_lib(root, items):
            ans = []
            for x in items:
                ext = os.path.splitext(x)[1]
                if (not ext and (x in ('demos', 'tests', 'test'))) or \
                    (ext in ('.dll', '.chm', '.htm', '.txt')):
                    ans.append(x)
            return ans

        self.info('Adding python...')
        shutil.copytree(r'%s\Lib'%self.python_base, self.lib_dir, ignore=ignore_lib)

        # Fix win32com
        sp_dir = self.j(self.lib_dir, 'site-packages')
        comext = self.j(sp_dir, 'win32comext')
        shutil.copytree(self.j(comext, 'shell'), self.j(sp_dir, 'win32com', 'shell'))
        shutil.rmtree(comext)

        for pat in (r'PyQt5\uic\port_v3', ):
            x = glob.glob(self.j(self.lib_dir, 'site-packages', pat))[0]
            shutil.rmtree(x)
        pyqt = self.j(self.lib_dir, 'site-packages', 'PyQt5')
        for x in {x for x in os.listdir(pyqt) if x.endswith('.pyd')} - PYQT_MODULES:
            os.remove(self.j(pyqt, x))

        self.info('Adding calibre sources...')
        for x in glob.glob(self.j(self.SRC, '*')):
            if os.path.isdir(x):
                if os.path.exists(os.path.join(x, '__init__.py')):
                    shutil.copytree(x, self.j(sp_dir, self.b(x)))
            else:
                shutil.copy(x, self.j(sp_dir, self.b(x)))

        for x in (r'calibre\manual', r'calibre\plugins', 'pythonwin'):
            deld = self.j(sp_dir, x)
            if os.path.exists(deld):
                shutil.rmtree(deld)

        for x in os.walk(self.j(sp_dir, 'calibre')):
            for f in x[-1]:
                if not f.endswith('.py'):
                    os.remove(self.j(x[0], f))

        self.extract_pyd_modules(sp_dir)

        self.info('Byte-compiling all python modules...')
        for x in ('test', 'lib2to3', 'distutils'):
            x = self.j(self.lib_dir, x)
            if os.path.exists(x):
                shutil.rmtree(x)
        for x in os.walk(self.lib_dir):
            root = x[0]
            for f in x[-1]:
                if f.endswith('.py'):
                    y = self.j(root, f)
                    rel = os.path.relpath(y, self.lib_dir)
                    try:
                        py_compile.compile(y, dfile=rel, doraise=True)
                        os.remove(y)
                    except:
                        self.warn('Failed to byte-compile', y)
                    pyc, pyo = y+'c', y+'o'
                    epyc, epyo, epy = map(os.path.exists, (pyc,pyo,y))
                    if (epyc or epyo) and epy:
                        os.remove(y)
                    if epyo and epyc:
                        os.remove(pyc)

        self.info('\nAdding Qt plugins...')
        qt_prefix = QT_DIR
        plugdir = self.j(qt_prefix, 'plugins')
        tdir = self.j(self.app_base, 'qt_plugins')
        for d in QT_PLUGINS:
            self.info('\t', d)
            imfd = os.path.join(plugdir, d)
            tg = os.path.join(tdir, d)
            if os.path.exists(tg):
                shutil.rmtree(tg)
            shutil.copytree(imfd, tg)

        for dirpath, dirnames, filenames in os.walk(tdir):
            for x in filenames:
                if not x.endswith('.dll'):
                    os.remove(self.j(dirpath, x))

        self.info('\nAdding third party dependencies')

        self.info('\tAdding misc binary deps')
        bindir = os.path.join(SW, 'bin')
        for x in ('pdftohtml', 'pdfinfo', 'pdftoppm', 'jpegtran-calibre', 'cjpeg-calibre', 'optipng-calibre'):
            shutil.copy2(os.path.join(bindir, x+'.exe'), self.dll_dir)
        for pat in ('*.dll',):
            for f in glob.glob(os.path.join(bindir, pat)):
                ok = True
                for ex in ('expatw', 'testplug'):
                    if ex in f.lower():
                        ok = False
                if not ok:
                    continue
                dest = self.dll_dir
                shutil.copy2(f, dest)
        for x in ('zlib1.dll', 'libxml2.dll', 'libxslt.dll', 'libexslt.dll'):
            msrc = self.j(bindir, x+'.manifest')
            if os.path.exists(msrc):
                shutil.copy2(msrc, self.dll_dir)

    def embed_manifests(self):
        self.info('Embedding remaining manifests...')
        for x in os.walk(self.base):
            for f in x[-1]:
                base, ext = os.path.splitext(f)
                if ext != '.manifest':
                    continue
                dll = self.j(x[0], base)
                manifest = self.j(x[0], f)
                res = 2
                if os.path.splitext(dll)[1] == '.exe':
                    res = 1
                if os.path.exists(dll):
                    self.run_builder([MT, '-manifest', manifest,
                        '-outputresource:%s;%d'%(dll,res)])
                    os.remove(manifest)

    def extract_pyd_modules(self, site_packages_dir):
        self.info('\nExtracting .pyd modules from site-packages...')

        def extract_pyd(path, root):
            fullname = os.path.relpath(path, root).replace(os.sep, '/').replace('/', '.')
            dest = os.path.join(self.dll_dir, fullname)
            if os.path.exists(dest):
                raise ValueError('Cannot extract %s into DLLs as it already exists' % fullname)
            os.rename(path, dest)
            bpy = dest[:-1]
            if os.path.exists(bpy):
                with open(bpy, 'rb') as f:
                    raw = f.read().strip()
                if (not raw.startswith('def __bootstrap__') or not raw.endswith('__bootstrap__()')):
                    raise ValueError('The file %r has non bootstrap code'%bpy)
            for ext in ('', 'c', 'o'):
                try:
                    os.remove(bpy + ext)
                except EnvironmentError as err:
                    if err.errno != errno.ENOENT:
                        raise

        def find_pyds(base):
            for dirpath, dirnames, filenames in os.walk(base):
                for fname in filenames:
                    if fname.lower().endswith('.pyd'):
                        yield os.path.join(dirpath, fname)

        def process_root(root, base=None):
            for path in find_pyds(root):
                extract_pyd(path, base or root)

        def absp(x):
            return os.path.normcase(os.path.abspath(os.path.join(site_packages_dir, x)))

        roots = set()
        for pth in glob.glob(os.path.join(site_packages_dir, '*.pth')):
            for line in open(pth, 'rb').readlines():
                line = line.strip()
                if line and not line.startswith('#') and os.path.exists(os.path.join(site_packages_dir, line)):
                    roots.add(absp(line))

        for x in os.listdir(site_packages_dir):
            x = absp(x)
            if x in roots:
                process_root(x)
            elif os.path.isdir(x):
                process_root(x, site_packages_dir)
            elif x.lower().endswith('.pyd'):
                extract_pyd(x, site_packages_dir)

    def compress(self):
        self.info('Compressing app dir using 7-zip')
        subprocess.check_call([r'C:\Program Files\7-Zip\7z.exe', 'a', '-r',
            '-scsUTF-8', '-sfx', 'winfrozen', 'winfrozen'], cwd=self.base)

    def embed_resources(self, module, desc=None, extra_data=None,
            product_description=None):
        icon_base = self.j(self.src_root, 'icons')
        icon_map = {'calibre':'library', 'ebook-viewer':'viewer', 'ebook-edit':'ebook-edit',
                'lrfviewer':'viewer', 'calibre-portable':'library'}
        file_type = 'DLL' if module.endswith('.dll') else 'APP'
        template = open(self.rc_template, 'rb').read()
        bname = self.b(module)
        internal_name = os.path.splitext(bname)[0]
        icon = icon_map.get(internal_name, 'command-prompt')
        if internal_name.startswith('calibre-portable-'):
            icon = 'install'
        icon = self.j(icon_base, icon+'.ico')
        if desc is None:
            defdesc = 'A dynamic link library' if file_type == 'DLL' else \
                    'An executable program'
            desc = DESCRIPTIONS.get(internal_name, defdesc)
        license = 'GNU GPL v3.0'
        def e(val):
            return val.replace('"', r'\"')
        if product_description is None:
            product_description = __appname__ + ' - E-book management'
        rc = template.format(
                icon=icon,
                file_type=e(file_type),
                file_version=e(WINVER.replace('.', ',')),
                file_version_str=e(WINVER),
                file_description=e(desc),
                internal_name=e(internal_name),
                original_filename=e(bname),
                product_version=e(WINVER.replace('.', ',')),
                product_version_str=e(__version__),
                product_name=e(__appname__),
                product_description=e(product_description),
                legal_copyright=e(license),
                legal_trademarks=e(__appname__ +
                        ' is a registered U.S. trademark number 3,666,525')
        )
        if extra_data:
            rc += '\nextra extra "%s"'%extra_data
        tdir = self.obj_dir
        rcf = self.j(tdir, bname+'.rc')
        with open(rcf, 'wb') as f:
            f.write(rc)
        res = self.j(tdir, bname + '.res')
        cmd = [RC, '/n', '/fo'+res, rcf]
        self.run_builder(cmd)
        return res

    def install_site_py(self):
        if not os.path.exists(self.lib_dir):
            os.makedirs(self.lib_dir)
        shutil.copy2(self.j(self.d(__file__), 'site.py'), self.lib_dir)
        y = os.path.join(self.lib_dir, 'site.py')
        py_compile.compile(y, dfile='site.py', doraise=True)
        if not self.opts.keep_site:
            os.remove(y)

    def run_builder(self, cmd, show_output=False):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        buf = []
        while p.poll() is None:
            x = p.stdout.read() + p.stderr.read()
            if x:
                buf.append(x)
        if p.returncode != 0:
            self.info('Failed to run builder:')
            self.info(*cmd)
            self.info(''.join(buf))
            self.info('')
            sys.stdout.flush()
            sys.exit(1)
        if show_output:
            self.info(''.join(buf) + '\n')

    def build_portable_installer(self):
        zf = self.a(self.j('dist', 'calibre-portable-%s.zip.lz'%VERSION))
        usz = self.portable_uncompressed_size or os.path.getsize(zf)
        def cc(src, obj):
            cflags  = '/c /EHsc /MT /W4 /Ox /nologo /D_UNICODE /DUNICODE /DPSAPI_VERSION=1'.split()
            cflags.append(r'/I%s\include'%LZMA)
            cflags.append('/DUNCOMPRESSED_SIZE=%d'%usz)
            if self.newer(obj, [src]):
                self.info('Compiling', obj)
                cmd = [msvc.cc] + cflags + ['/Fo'+obj, src]
                self.run_builder(cmd)

        src = self.j(self.src_root, 'setup', 'installer', 'windows',
                'portable-installer.cpp')
        obj = self.j(self.obj_dir, self.b(src)+'.obj')
        xsrc = self.j(self.src_root, 'setup', 'installer', 'windows',
                'XUnzip.cpp')
        xobj = self.j(self.obj_dir, self.b(xsrc)+'.obj')
        cc(src, obj)
        cc(xsrc, xobj)

        exe = self.j('dist', 'calibre-portable-installer-%s.exe'%VERSION)
        if self.newer(exe, [obj, xobj]):
            self.info('Linking', exe)
            manifest = exe + '.manifest'
            with open(manifest, 'wb') as f:
                f.write(EXE_MANIFEST)
            cmd = [msvc.linker] + ['/INCREMENTAL:NO', '/MACHINE:'+machine,
                    '/LIBPATH:'+self.obj_dir, '/SUBSYSTEM:WINDOWS',
                    '/LIBPATH:'+(LZMA+r'\lib'),
                    '/RELEASE', '/MANIFEST:EMBED', '/MANIFESTINPUT:' + manifest,
                    '/ENTRY:wWinMainCRTStartup',
                    '/OUT:'+exe, self.embed_resources(exe,
                        desc='Calibre Portable Installer', extra_data=zf,
                        product_description='Calibre Portable Installer'),
                    xobj, obj, 'User32.lib', 'Shell32.lib', 'easylzma_s.lib',
                    'Ole32.lib', 'Shlwapi.lib', 'Kernel32.lib', 'Psapi.lib']
            self.run_builder(cmd)

        os.remove(zf)

    def build_portable(self):
        base  = self.portable_base
        if os.path.exists(base):
            shutil.rmtree(base)
        os.makedirs(base)
        src = self.j(self.src_root, 'setup', 'installer', 'windows',
                'portable.c')
        obj = self.j(self.obj_dir, self.b(src)+'.obj')
        cflags  = '/c /EHsc /MT /W3 /Ox /nologo /D_UNICODE /DUNICODE'.split()

        if self.newer(obj, [src]):
            self.info('Compiling', obj)
            cmd = [msvc.cc] + cflags + ['/Fo'+obj, '/Tc'+src]
            self.run_builder(cmd)

        exe = self.j(base, 'calibre-portable.exe')
        if self.newer(exe, [obj]):
            self.info('Linking', exe)
            cmd = [msvc.linker] + ['/INCREMENTAL:NO', '/MACHINE:'+machine,
                    '/LIBPATH:'+self.obj_dir, '/SUBSYSTEM:WINDOWS',
                    '/RELEASE',
                    '/ENTRY:wWinMainCRTStartup',
                    '/OUT:'+exe, self.embed_resources(exe, desc='Calibre Portable', product_description='Calibre Portable'),
                    obj, 'User32.lib']
            self.run_builder(cmd)

        self.info('Creating portable installer')
        shutil.copytree(self.base, self.j(base, 'Calibre'))
        os.mkdir(self.j(base, 'Calibre Library'))
        os.mkdir(self.j(base, 'Calibre Settings'))

        name = '%s-portable-%s.zip'%(__appname__, __version__)
        name = self.j('dist', name)
        with zipfile.ZipFile(name, 'w', zipfile.ZIP_STORED) as zf:
            self.add_dir_to_zip(zf, base, 'Calibre Portable')

        self.portable_uncompressed_size = os.path.getsize(name)
        subprocess.check_call([LZMA + r'\bin\elzma.exe', '-9', '--lzip', name])

    def sign_installers(self):
        self.info('Signing installers...')
        files = glob.glob(self.j('dist', '*.msi')) + glob.glob(self.j('dist',
                                                                      '*.exe'))
        if not files:
            raise ValueError('No installers found')
        args = ['signtool.exe', 'sign', '/a', '/fd', 'sha256', '/td', 'sha256', '/d',
            'calibre - E-book management', '/du',
            'https://calibre-ebook.com', '/tr']

        def runcmd(cmd):
            for timeserver in ('http://sha256timestamp.ws.symantec.com/sha256/timestamp', 'http://timestamp.comodoca.com/rfc3161',):
                try:
                    subprocess.check_call(cmd + [timeserver] + files)
                    break
                except subprocess.CalledProcessError:
                    print ('Signing failed, retrying with different timestamp server')
            else:
                raise SystemExit('Signing failed')

        runcmd(args)

    def add_dir_to_zip(self, zf, path, prefix=''):
        '''
        Add a directory recursively to the zip file with an optional prefix.
        '''
        if prefix:
            zi = zipfile.ZipInfo(prefix+'/')
            zi.external_attr = 16
            zf.writestr(zi, '')
        cwd = os.path.abspath(os.getcwd())
        try:
            os.chdir(path)
            fp = (prefix + ('/' if prefix else '')).replace('//', '/')
            for f in os.listdir('.'):
                arcname = fp + f
                if os.path.isdir(f):
                    self.add_dir_to_zip(zf, f, prefix=arcname)
                else:
                    zf.write(f, arcname)
        finally:
            os.chdir(cwd)

    def build_utils(self):
        def build(src, name, subsys='CONSOLE', libs='setupapi.lib'.split()):
            self.info('Building '+name)
            obj = self.j(self.obj_dir, self.b(src)+'.obj')
            cflags  = '/c /EHsc /MD /W3 /Ox /nologo /D_UNICODE'.split()
            if self.newer(obj, src):
                ftype = '/T' + ('c' if src.endswith('.c') else 'p')
                cmd = [msvc.cc] + cflags + ['/Fo'+obj, ftype + src]
                self.run_builder(cmd, show_output=True)
            exe = self.j(self.dll_dir, name)
            mf = exe + '.manifest'
            with open(mf, 'wb') as f:
                f.write(EXE_MANIFEST)
            cmd = [msvc.linker] + ['/MACHINE:'+machine,
                    '/SUBSYSTEM:'+subsys, '/RELEASE', '/MANIFEST:EMBED', '/MANIFESTINPUT:'+mf,
                    '/OUT:'+exe] + [self.embed_resources(exe), obj] + libs
            self.run_builder(cmd)
        base = self.j(self.src_root, 'setup', 'installer', 'windows')
        build(self.j(base, 'file_dialogs.cpp'), 'calibre-file-dialog.exe', 'WINDOWS', 'Ole32.lib Shell32.lib'.split())
        build(self.j(base, 'eject.c'), 'calibre-eject.exe')

    def build_launchers(self, debug=False):
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        dflags = (['/Zi'] if debug else [])
        dlflags = (['/DEBUG'] if debug else ['/INCREMENTAL:NO'])
        base = self.j(self.src_root, 'setup', 'installer', 'windows')
        sources = [self.j(base, x) for x in ['util.c',]]
        objects = [self.j(self.obj_dir, self.b(x)+'.obj') for x in sources]
        cflags  = '/c /EHsc /W3 /Ox /nologo /D_UNICODE'.split()
        cflags += ['/DPYDLL="python%s.dll"'%self.py_ver, '/I%s/include'%self.python_base]
        for src, obj in zip(sources, objects):
            if not self.newer(obj, [src]):
                continue
            cmd = [msvc.cc] + cflags + dflags + ['/MD', '/Fo'+obj, '/Tc'+src]
            self.run_builder(cmd, show_output=True)

        dll = self.j(self.obj_dir, 'calibre-launcher.dll')
        ver = '.'.join(__version__.split('.')[:2])
        if self.newer(dll, objects):
            cmd = [msvc.linker, '/DLL', '/VERSION:'+ver, '/LTCG', '/OUT:'+dll,
                   '/nologo', '/MACHINE:'+machine] + dlflags + objects + \
                [self.embed_resources(dll),
                '/LIBPATH:%s/libs'%self.python_base,
                'delayimp.lib', 'user32.lib', 'shell32.lib',
                'python%s.lib'%self.py_ver,
                '/delayload:python%s.dll'%self.py_ver]
            self.info('Linking calibre-launcher.dll')
            self.run_builder(cmd, show_output=True)

        src = self.j(base, 'main.c')
        shutil.copy2(dll, self.dll_dir)
        for typ in ('console', 'gui', ):
            self.info('Processing %s launchers'%typ)
            subsys = 'WINDOWS' if typ == 'gui' else 'CONSOLE'
            for mod, bname, func in zip(modules[typ], basenames[typ],
                    functions[typ]):
                cflags  = '/c /EHsc /MT /W3 /O1 /nologo /D_UNICODE /DUNICODE /GS-'.split()
                if typ == 'gui':
                    cflags += ['/DGUI_APP=']

                cflags += ['/DMODULE="%s"'%mod, '/DBASENAME="%s"'%bname,
                    '/DFUNCTION="%s"'%func]
                dest = self.j(self.obj_dir, bname+'.obj')
                if self.newer(dest, [src, __file__]):
                    self.info('Compiling', bname)
                    cmd = [msvc.cc] + cflags + dflags + ['/Tc'+src, '/Fo'+dest]
                    self.run_builder(cmd)
                exe = self.j(self.base, bname+'.exe')
                lib = dll.replace('.dll', '.lib')
                u32 = ['user32.lib']
                if self.newer(exe, [dest, lib, self.rc_template, __file__]):
                    self.info('Linking', bname)
                    mf = dest + '.manifest'
                    with open(mf, 'wb') as f:
                        f.write(EXE_MANIFEST)
                    cmd = [msvc.linker] + ['/MACHINE:'+machine, '/NODEFAULTLIB', '/ENTRY:start_here',
                            '/LIBPATH:'+self.obj_dir, '/SUBSYSTEM:'+subsys,
                            '/LIBPATH:%s/libs'%self.python_base, '/RELEASE',
                            '/MANIFEST:EMBED', '/MANIFESTINPUT:' + mf,
                            'user32.lib', 'kernel32.lib',
                            '/OUT:'+exe] + u32 + dlflags + [self.embed_resources(exe),
                            dest, lib]
                    self.run_builder(cmd)

    def archive_lib_dir(self):
        self.info('Putting all python code into a zip file for performance')
        self.zf_timestamp = time.localtime(time.time())[:6]
        self.zf_names = set()
        with zipfile.ZipFile(self.pylib, 'w', zipfile.ZIP_STORED) as zf:
            # Add everything in Lib except site-packages to the zip file
            for x in os.listdir(self.lib_dir):
                if x == 'site-packages':
                    continue
                self.add_to_zipfile(zf, x, self.lib_dir)

            sp = self.j(self.lib_dir, 'site-packages')
            # Special handling for PIL and pywin32
            handled = {'pywin32.pth', 'win32'}
            base = self.j(sp, 'win32', 'lib')
            for x in os.listdir(base):
                if os.path.splitext(x)[1] not in ('.exe',):
                    self.add_to_zipfile(zf, x, base)
            base = self.d(base)
            for x in os.listdir(base):
                if not os.path.isdir(self.j(base, x)):
                    if os.path.splitext(x)[1] not in ('.exe',):
                        self.add_to_zipfile(zf, x, base)

            handled.add('easy-install.pth')
            # We dont want the site.py from site-packages
            handled.add('site.pyo')

            for d in self.get_pth_dirs(self.j(sp, 'easy-install.pth')):
                hname = self.b(d)
                if hname in handled:
                    continue
                handled.add(hname)
                for x in os.listdir(d):
                    if x in {'EGG-INFO', 'site.py', 'site.pyc', 'site.pyo'}:
                        continue
                    self.add_to_zipfile(zf, x, d)

            # The rest of site-packages
            for x in os.listdir(sp):
                if x in handled or x.endswith('.egg-info'):
                    continue
                absp = self.j(sp, x)
                if os.path.isdir(absp):
                    if not os.listdir(absp):
                        continue
                    self.add_to_zipfile(zf, x, sp)
                else:
                    self.add_to_zipfile(zf, x, sp)

        shutil.rmtree(self.lib_dir)

    def get_pth_dirs(self, pth):
        base = os.path.dirname(pth)
        for line in open(pth).readlines():
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('import'):
                continue
            candidate = os.path.abspath(self.j(base, line))
            if os.path.exists(candidate):
                if not os.path.isdir(candidate):
                    raise ValueError('%s is not a directory'%candidate)
                yield candidate

    def add_to_zipfile(self, zf, name, base, exclude=frozenset()):
        abspath = self.j(base, name)
        name = name.replace(os.sep, '/')
        if name in self.zf_names:
            raise ValueError('Already added %r to zipfile [%r]'%(name, abspath))
        zinfo = zipfile.ZipInfo(filename=name, date_time=self.zf_timestamp)

        if os.path.isdir(abspath):
            if not os.listdir(abspath):
                return
            zinfo.external_attr = 0o700 << 16
            zf.writestr(zinfo, '')
            for x in os.listdir(abspath):
                if x not in exclude:
                    self.add_to_zipfile(zf, name + os.sep + x, base)
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext in ('.dll',):
                raise ValueError('Cannot add %r to zipfile'%abspath)
            zinfo.external_attr = 0o600 << 16
            if ext in ('.py', '.pyc', '.pyo'):
                with open(abspath, 'rb') as f:
                    zf.writestr(zinfo, f.read())

        self.zf_names.add(name)

    def copy_crt(self):
        self.info('Copying CRT...')
        plat = ('x64' if is64bit else 'x86')
        vc_path = os.path.join(r'C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\redist', plat, 'Microsoft.VC140.CRT')
        if not os.path.exists(vc_path):
            raise SystemExit('Visual Studio redistributable CRT not found')
        # I cannot get app local deployment of the UCRT to work. Things left to
        # try: try dlls from the windows sdk standalone, try manually loading
        # ucrtbase.dll and some api dlls before loading the launcher.
        # sdk_path = os.path.join(r'C:\Program Files (x86)\Windows Kits\10\Redist\ucrt\DLLs', plat)
        # if not os.path.exists(sdk_path):
        #     raise SystemExit('Windows 10 redistributable CRT not found')
        # for dll in glob.glob(os.path.join(sdk_path, '*.dll')):
        #     shutil.copy2(dll, self.dll_dir)
        for dll in glob.glob(os.path.join(vc_path, '*.dll')):
            bname = os.path.basename(dll)
            if not bname.startswith('vccorlib') and not bname.startswith('concrt'):
                # Those two DLLs are not required vccorlib is for the CORE CLR
                # I think concrt is the concurrency runtime for C++ which I believe
                # nothing in calibre currently uses
                shutil.copy(dll, self.dll_dir)
                os.chmod(os.path.join(self.dll_dir, dll), stat.S_IRWXU)
