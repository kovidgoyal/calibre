#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, glob, py_compile, subprocess, re, zipfile, time

from setup import (Command, modules, functions, basenames, __version__,
    __appname__)
from setup.build_environment import msvc, MT, RC
from setup.installer.windows.wix import WixMixIn

ICU_DIR = r'Q:\icu'
OPENSSL_DIR = r'Q:\openssl'
QT_DIR = 'Q:\\Qt\\4.8.2'
QT_DLLS = ['Core', 'Gui', 'Network', 'Svg', 'WebKit', 'Xml', 'XmlPatterns']
QTCURVE = r'C:\plugins\styles'
LIBUNRAR         = 'C:\\Program Files\\UnrarDLL\\unrar.dll'
SW               = r'C:\cygwin\home\kovid\sw'
IMAGEMAGICK      = os.path.join(SW, 'build', 'ImageMagick-6.7.6',
        'VisualMagick', 'bin')
CRT = r'C:\Microsoft.VC90.CRT'
LZMA = r'Q:\easylzma\build\easylzma-0.0.8'

VERSION = re.sub('[a-z]\d+', '', __version__)
WINVER = VERSION+'.0'

DESCRIPTIONS = {
        'calibre' : 'The main calibre program',
        'ebook-viewer' : 'Viewer for all e-book formats',
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
}

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

    def run(self, opts):
        self.SW = SW
        self.opts = opts
        self.src_root = self.d(self.SRC)
        self.base = self.j(self.d(self.SRC), 'build', 'winfrozen')
        self.rc_template = self.j(self.d(self.a(__file__)), 'template.rc')
        self.py_ver = ''.join(map(str, sys.version_info[:2]))
        self.lib_dir = self.j(self.base, 'Lib')
        self.pylib = self.j(self.base, 'pylib.zip')
        self.dll_dir = self.j(self.base, 'DLLs')
        self.plugins_dir = os.path.join(self.base, 'plugins2')
        self.portable_base = self.j(self.d(self.base), 'Calibre Portable')
        self.obj_dir = self.j(self.src_root, 'build', 'launcher')

        self.initbase()
        self.build_launchers()
        self.add_plugins()
        self.freeze()
        self.embed_manifests()
        self.install_site_py()
        self.archive_lib_dir()
        self.remove_CRT_from_manifests()
        self.create_installer()
        self.build_portable()
        self.build_portable_installer()

    def remove_CRT_from_manifests(self):
        '''
        The dependency on the CRT is removed from the manifests of all DLLs.
        This allows the CRT loaded by the .exe files to be used instead.
        '''
        search_pat = re.compile(r'(?is)<dependency>.*Microsoft\.VC\d+\.CRT')
        repl_pat = re.compile(
            r'(?is)<dependency>.*?Microsoft\.VC\d+\.CRT.*?</dependency>')

        for dll in glob.glob(self.j(self.dll_dir, '*.dll')):
            bn = self.b(dll)
            with open(dll, 'rb') as f:
                raw = f.read()
            match = search_pat.search(raw)
            if match is None:
                continue
            self.info('Removing CRT dependency from manifest of: %s'%bn)
            # Blank out the bytes corresponding to the dependency specification
            nraw = repl_pat.sub(lambda m: b' '*len(m.group()), raw)
            if len(nraw) != len(raw):
                raise Exception('Something went wrong with %s'%bn)
            with open(dll, 'wb') as f:
                f.write(nraw)

    def initbase(self):
        if self.e(self.base):
            shutil.rmtree(self.base)
        os.makedirs(self.base)

    def add_plugins(self):
        self.info('Adding plugins...')
        tgt = self.plugins_dir
        if os.path.exists(tgt):
            shutil.rmtree(tgt)
        os.mkdir(tgt)
        base = self.j(self.SRC, 'calibre', 'plugins')
        for f in glob.glob(self.j(base, '*.pyd')):
            # We dont want the manifests as the manifest in the exe will be
            # used instead
            shutil.copy2(f, tgt)

    def freeze(self):
        shutil.copy2(self.j(self.src_root, 'LICENSE'), self.base)

        self.info('Adding CRT')
        shutil.copytree(CRT, self.j(self.base, os.path.basename(CRT)))

        self.info('Adding resources...')
        tgt = self.j(self.base, 'resources')
        if os.path.exists(tgt):
            shutil.rmtree(tgt)
        shutil.copytree(self.j(self.src_root, 'resources'), tgt)

        self.info('Adding Qt and python...')
        shutil.copytree(r'C:\Python%s\DLLs'%self.py_ver, self.dll_dir,
                ignore=shutil.ignore_patterns('msvc*.dll', 'Microsoft.*'))
        for x in glob.glob(self.j(OPENSSL_DIR, 'bin', '*.dll')):
            shutil.copy2(x, self.dll_dir)
        for x in glob.glob(self.j(ICU_DIR, 'source', 'lib', '*.dll')):
            shutil.copy2(x, self.dll_dir)
        for x in QT_DLLS:
            x += '4.dll'
            if not x.startswith('phonon'): x = 'Qt'+x
            shutil.copy2(os.path.join(QT_DIR, 'bin', x), self.dll_dir)
        shutil.copy2(r'C:\windows\system32\python%s.dll'%self.py_ver,
                    self.dll_dir)
        for x in os.walk(r'C:\Python%s\Lib'%self.py_ver):
            for f in x[-1]:
                if f.lower().endswith('.dll'):
                    f = self.j(x[0], f)
                    shutil.copy2(f, self.dll_dir)
        shutil.copy2(
            r'C:\Python%(v)s\Lib\site-packages\pywin32_system32\pywintypes%(v)s.dll'
            % dict(v=self.py_ver), self.dll_dir)

        def ignore_lib(root, items):
            ans = []
            for x in items:
                ext = os.path.splitext(x)[1]
                if (not ext and (x in ('demos', 'tests'))) or \
                    (ext in ('.dll', '.chm', '.htm', '.txt')):
                    ans.append(x)
            return ans

        shutil.copytree(r'C:\Python%s\Lib'%self.py_ver, self.lib_dir,
                ignore=ignore_lib)

        # Fix win32com
        sp_dir = self.j(self.lib_dir, 'site-packages')
        comext = self.j(sp_dir, 'win32comext')
        shutil.copytree(self.j(comext, 'shell'), self.j(sp_dir, 'win32com', 'shell'))
        shutil.rmtree(comext)

        # Fix PyCrypto, removing the bootstrap .py modules that load the .pyd
        # modules, since they do not work when in a zip file
        for crypto_dir in glob.glob(self.j(sp_dir, 'pycrypto-*', 'Crypto')):
            for dirpath, dirnames, filenames in os.walk(crypto_dir):
                for f in filenames:
                    name, ext = os.path.splitext(f)
                    if ext == '.pyd':
                        with open(self.j(dirpath, name+'.py')) as f:
                            raw = f.read().strip()
                        if (not raw.startswith('def __bootstrap__') or not
                                raw.endswith('__bootstrap__()')):
                            raise Exception('The PyCrypto file %r has non'
                                    ' bootstrap code'%self.j(dirpath, f))
                        for ext in ('.py', '.pyc', '.pyo'):
                            x = self.j(dirpath, name+ext)
                            if os.path.exists(x):
                                os.remove(x)

        for pat in (r'PyQt4\uic\port_v3', ):
            x = glob.glob(self.j(self.lib_dir, 'site-packages', pat))[0]
            shutil.rmtree(x)

        self.info('Adding calibre sources...')
        for x in glob.glob(self.j(self.SRC, '*')):
            shutil.copytree(x, self.j(sp_dir, self.b(x)))

        for x in (r'calibre\manual', r'calibre\trac', 'pythonwin'):
            deld = self.j(sp_dir, x)
            if os.path.exists(deld):
                shutil.rmtree(deld)

        for x in os.walk(self.j(sp_dir, 'calibre')):
            for f in x[-1]:
                if not f.endswith('.py'):
                    os.remove(self.j(x[0], f))

        self.info('Byte-compiling all python modules...')
        for x in ('test', 'lib2to3', 'distutils'):
            shutil.rmtree(self.j(self.lib_dir, x))
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
        tdir = self.j(self.base, 'qt_plugins')
        for d in ('imageformats', 'codecs', 'iconengines'):
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

        print
        print 'Adding third party dependencies'
        print '\tAdding unrar'
        shutil.copyfile(LIBUNRAR,
                os.path.join(self.dll_dir, os.path.basename(LIBUNRAR)))

        print '\tAdding misc binary deps'
        bindir = os.path.join(SW, 'bin')
        for x in ('pdftohtml', 'pdfinfo', 'pdftoppm'):
            shutil.copy2(os.path.join(bindir, x+'.exe'), self.base)
        for pat in ('*.dll',):
            for f in glob.glob(os.path.join(bindir, pat)):
                ok = True
                for ex in ('expatw', 'testplug'):
                    if ex in f.lower():
                        ok = False
                if not ok: continue
                dest = self.dll_dir
                shutil.copy2(f, dest)
        for x in ('zlib1.dll', 'libxml2.dll'):
            shutil.copy2(self.j(bindir, x+'.manifest'), self.dll_dir)

        shutil.copytree(os.path.join(SW, 'etc', 'fonts'),
						os.path.join(self.base, 'fontconfig'))
        # Copy ImageMagick
        for pat in ('*.dll', '*.xml'):
            for f in glob.glob(self.j(IMAGEMAGICK, pat)):
                ok = True
                for ex in ('magick++', 'x11.dll', 'xext.dll'):
                    if ex in f.lower(): ok = False
                if not ok: continue
                shutil.copy2(f, self.dll_dir)

    def embed_manifests(self):
        self.info('Embedding remaining manifests...')
        for x in os.walk(self.base):
            for f in x[-1]:
                base, ext = os.path.splitext(f)
                if ext != '.manifest': continue
                dll = self.j(x[0], base)
                manifest = self.j(x[0], f)
                res = 2
                if os.path.splitext(dll)[1] == '.exe':
                    res = 1
                if os.path.exists(dll):
                    self.run_builder([MT, '-manifest', manifest,
                        '-outputresource:%s;%d'%(dll,res)])
                    os.remove(manifest)

    def compress(self):
        self.info('Compressing app dir using 7-zip')
        subprocess.check_call([r'C:\Program Files\7-Zip\7z.exe', 'a', '-r',
            '-scsUTF-8', '-sfx', 'winfrozen', 'winfrozen'], cwd=self.base)

    def embed_resources(self, module, desc=None, extra_data=None,
            product_description=None):
        icon_base = self.j(self.src_root, 'icons')
        icon_map = {'calibre':'library', 'ebook-viewer':'viewer',
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
        def e(val): return val.replace('"', r'\"')
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
                legal_trademarks=e(__appname__ + \
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

    def run_builder(self, cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        if p.wait() != 0:
            self.info('Failed to run builder:')
            self.info(*cmd)
            self.info(p.stdout.read())
            self.info(p.stderr.read())
            sys.exit(1)

    def build_portable_installer(self):
        base  = self.portable_base
        zf = self.a(self.j('dist', 'calibre-portable-%s.zip.lz'%VERSION))
        usz = os.path.getsize(zf)
        def cc(src, obj):
            cflags  = '/c /EHsc /MT /W4 /Ox /nologo /D_UNICODE /DUNICODE'.split()
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
            cmd = [msvc.linker] + ['/INCREMENTAL:NO', '/MACHINE:X86',
                    '/LIBPATH:'+self.obj_dir, '/SUBSYSTEM:WINDOWS',
                    '/LIBPATH:'+(LZMA+r'\lib\Release'),
                    '/RELEASE',
                    '/ENTRY:wWinMainCRTStartup',
                    '/OUT:'+exe, self.embed_resources(exe,
                        desc='Calibre Portable Installer', extra_data=zf,
                        product_description='Calibre Portable Installer'),
                    xobj, obj, 'User32.lib', 'Shell32.lib', 'easylzma_s.lib',
                    'Ole32.lib', 'Shlwapi.lib', 'Kernel32.lib']
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
            cmd = [msvc.linker] + ['/INCREMENTAL:NO', '/MACHINE:X86',
                    '/LIBPATH:'+self.obj_dir, '/SUBSYSTEM:WINDOWS',
                    '/RELEASE',
                    '/ENTRY:wWinMainCRTStartup',
                    '/OUT:'+exe, self.embed_resources(exe),
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

        subprocess.check_call([LZMA + r'\bin\elzma.exe', '-9', '--lzip', name])

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

    def build_launchers(self):
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        base = self.j(self.src_root, 'setup', 'installer', 'windows')
        sources = [self.j(base, x) for x in ['util.c', 'MemoryModule.c']]
        headers = [self.j(base, x) for x in ['util.h', 'MemoryModule.h']]
        objects = [self.j(self.obj_dir, self.b(x)+'.obj') for x in sources]
        cflags  = '/c /EHsc /MD /W3 /Ox /nologo /D_UNICODE'.split()
        cflags += ['/DPYDLL="python%s.dll"'%self.py_ver, '/IC:/Python%s/include'%self.py_ver]
        for src, obj in zip(sources, objects):
            if not self.newer(obj, headers+[src]): continue
            cmd = [msvc.cc] + cflags + ['/Fo'+obj, '/Tc'+src]
            self.run_builder(cmd)

        dll = self.j(self.obj_dir, 'calibre-launcher.dll')
        ver = '.'.join(__version__.split('.')[:2])
        if self.newer(dll, objects):
            cmd = [msvc.linker, '/DLL', '/INCREMENTAL:NO', '/VERSION:'+ver,
                    '/OUT:'+dll, '/nologo', '/MACHINE:X86'] + objects + \
                [self.embed_resources(dll),
                '/LIBPATH:C:/Python%s/libs'%self.py_ver,
                'python%s.lib'%self.py_ver,
                '/delayload:python%s.dll'%self.py_ver]
            self.info('Linking calibre-launcher.dll')
            self.run_builder(cmd)

        src = self.j(base, 'main.c')
        shutil.copy2(dll, self.base)
        for typ in ('console', 'gui', ):
            self.info('Processing %s launchers'%typ)
            subsys = 'WINDOWS' if typ == 'gui' else 'CONSOLE'
            for mod, bname, func in zip(modules[typ], basenames[typ],
                    functions[typ]):
                xflags = list(cflags)
                if typ == 'gui':
                    xflags += ['/DGUI_APP=']

                xflags += ['/DMODULE="%s"'%mod, '/DBASENAME="%s"'%bname,
                    '/DFUNCTION="%s"'%func]
                dest = self.j(self.obj_dir, bname+'.obj')
                if self.newer(dest, [src]+headers):
                    self.info('Compiling', bname)
                    cmd = [msvc.cc] + xflags + ['/Tc'+src, '/Fo'+dest]
                    self.run_builder(cmd)
                exe = self.j(self.base, bname+'.exe')
                lib = dll.replace('.dll', '.lib')
                if self.newer(exe, [dest, lib, self.rc_template, __file__]):
                    self.info('Linking', bname)
                    cmd = [msvc.linker] + ['/INCREMENTAL:NO', '/MACHINE:X86',
                            '/LIBPATH:'+self.obj_dir, '/SUBSYSTEM:'+subsys,
                            '/LIBPATH:C:/Python%s/libs'%self.py_ver, '/RELEASE',
                            '/OUT:'+exe, self.embed_resources(exe),
                            dest, lib]
                    self.run_builder(cmd)

    def archive_lib_dir(self):
        self.info('Putting all python code into a zip file for performance')
        self.zf_timestamp = time.localtime(time.time())[:6]
        self.zf_names = set()
        with zipfile.ZipFile(self.pylib, 'w', zipfile.ZIP_STORED) as zf:
            # Add the .pyds from python and calibre to the zip file
            for x in (self.plugins_dir, self.dll_dir):
                for pyd in os.listdir(x):
                    if pyd.endswith('.pyd') and pyd not in {
                            'sqlite_custom.pyd', 'calibre_style.pyd'}:
                        # sqlite_custom has to be a file for
                        # sqlite_load_extension to work
                        self.add_to_zipfile(zf, pyd, x)
                        os.remove(self.j(x, pyd))

            # Add everything in Lib except site-packages to the zip file
            for x in os.listdir(self.lib_dir):
                if x == 'site-packages':
                    continue
                self.add_to_zipfile(zf, x, self.lib_dir)

            sp = self.j(self.lib_dir, 'site-packages')
            # Special handling for PIL and pywin32
            handled = set(['PIL.pth', 'pywin32.pth', 'PIL', 'win32'])
            self.add_to_zipfile(zf, 'PIL', sp)
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
            for d in self.get_pth_dirs(self.j(sp, 'easy-install.pth')):
                handled.add(self.b(d))
                for x in os.listdir(d):
                    if x == 'EGG-INFO':
                        continue
                    self.add_to_zipfile(zf, x, d)

            # The rest of site-packages
            # We dont want the site.py from site-packages
            handled.add('site.pyo')
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
            candidate = self.j(base, line)
            if os.path.exists(candidate):
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
            zinfo.external_attr = 0700 << 16
            zf.writestr(zinfo, '')
            for x in os.listdir(abspath):
                if x not in exclude:
                    self.add_to_zipfile(zf, name + os.sep + x, base)
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext in ('.dll',):
                raise ValueError('Cannot add %r to zipfile'%abspath)
            zinfo.external_attr = 0600 << 16
            if ext in ('.py', '.pyc', '.pyo', '.pyd'):
                with open(abspath, 'rb') as f:
                    zf.writestr(zinfo, f.read())

        self.zf_names.add(name)



