#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, glob, py_compile, subprocess, re

from setup import Command, modules, functions, basenames, __version__, \
    __appname__
from setup.build_environment import msvc, MT, RC
from setup.installer.windows.wix import WixMixIn

QT_DIR = 'Q:\\Qt\\4.7.1'
QT_DLLS = ['Core', 'Gui', 'Network', 'Svg', 'WebKit', 'Xml', 'XmlPatterns']
LIBUSB_DIR       = 'C:\\libusb'
LIBUNRAR         = 'C:\\Program Files\\UnrarDLL\\unrar.dll'
SW               = r'C:\cygwin\home\kovid\sw'
IMAGEMAGICK      = os.path.join(SW, 'build', 'ImageMagick-6.5.6',
        'VisualMagick', 'bin')

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

class Win32Freeze(Command, WixMixIn):

    description = 'Free windows calibre installation'

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

        self.initbase()
        self.build_launchers()
        self.freeze()
        self.embed_manifests()
        self.install_site_py()
        self.create_installer()

    def initbase(self):
        if self.e(self.base):
            shutil.rmtree(self.base)
        os.makedirs(self.base)

    def freeze(self):
        shutil.copy2(self.j(self.src_root, 'LICENSE'), self.base)

        self.info('Adding plugins...')
        tgt = os.path.join(self.base, 'plugins')
        if not os.path.exists(tgt):
            os.mkdir(tgt)
        base = self.j(self.SRC, 'calibre', 'plugins')
        for pat in ('*.pyd', '*.manifest'):
            for f in glob.glob(self.j(base, pat)):
                shutil.copy2(f, tgt)

        self.info('Adding resources...')
        tgt = self.j(self.base, 'resources')
        if os.path.exists(tgt):
            shutil.rmtree(tgt)
        shutil.copytree(self.j(self.src_root, 'resources'), tgt)

        self.info('Adding Qt and python...')
        self.dll_dir = self.j(self.base, 'DLLs')
        shutil.copytree(r'C:\Python%s\DLLs'%self.py_ver, self.dll_dir,
                ignore=shutil.ignore_patterns('msvc*.dll', 'Microsoft.*'))
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
                    if 'py2exe' not in f:
                        shutil.copy2(f, self.dll_dir)
        shutil.copy2(
            r'C:\Python%(v)s\Lib\site-packages\pywin32_system32\pywintypes%(v)s.dll'
            % dict(v=self.py_ver), self.dll_dir)

        def ignore_lib(root, items):
            ans = []
            for x in items:
                ext = os.path.splitext(x)[1]
                if (not ext and (x in ('demos', 'tests') or 'py2exe' in x)) or \
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

        print
        print 'Adding third party dependencies'
        tdir = os.path.join(self.base, 'driver')
        os.makedirs(tdir)
        for pat in ('*.dll', '*.sys', '*.cat', '*.inf'):
            for f in glob.glob(os.path.join(LIBUSB_DIR, pat)):
                shutil.copyfile(f, os.path.join(tdir, os.path.basename(f)))
        print '\tAdding unrar'
        shutil.copyfile(LIBUNRAR,
                os.path.join(self.dll_dir, os.path.basename(LIBUNRAR)))

        print '\tAdding misc binary deps'
        bindir = os.path.join(SW, 'bin')
        shutil.copy2(os.path.join(bindir, 'pdftohtml.exe'), self.base)
        for pat in ('*.dll',):
            for f in glob.glob(os.path.join(bindir, pat)):
                ok = True
                for ex in ('expatw',):
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

    def embed_resources(self, module, desc=None):
        icon_base = self.j(self.src_root, 'icons')
        icon_map = {'calibre':'library', 'ebook-viewer':'viewer',
                'lrfviewer':'viewer'}
        file_type = 'DLL' if module.endswith('.dll') else 'APP'
        template = open(self.rc_template, 'rb').read()
        bname = self.b(module)
        internal_name = os.path.splitext(bname)[0]
        icon = icon_map.get(internal_name, 'command-prompt')
        icon = self.j(icon_base, icon+'.ico')
        if desc is None:
            defdesc = 'A dynamic link library' if file_type == 'DLL' else \
                    'An executable program'
            desc = DESCRIPTIONS.get(internal_name, defdesc)
        license = 'GNU GPL v3.0'
        def e(val): return val.replace('"', r'\"')
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
                product_description=e(__appname__+' - E-book management'),
                legal_copyright=e(license),
                legal_trademarks=e(__appname__ + \
                        ' is a registered U.S. trademark number 3,666,525')
        )
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

    def build_launchers(self):
        self.obj_dir = self.j(self.src_root, 'build', 'launcher')
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        base = self.j(self.src_root, 'setup', 'installer', 'windows')
        sources = [self.j(base, x) for x in ['util.c']]
        headers = [self.j(base, x) for x in ['util.h']]
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


