#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import errno
import glob
import os
import re
import runpy
import shutil
import stat
import subprocess
import sys
import zipfile

from bypy.constants import (
    CL, LINK, MT, PREFIX, RC, SIGNTOOL, SRC as CALIBRE_DIR, SW, build_dir, is64bit,
    python_major_minor_version, worker_env
)
from bypy.utils import py_compile, run, walk

iv = globals()['init_env']
calibre_constants = iv['calibre_constants']
QT_PREFIX = os.path.join(PREFIX, 'qt')
QT_DLLS, QT_PLUGINS, PYQT_MODULES = iv['QT_DLLS'], iv['QT_PLUGINS'], iv['PYQT_MODULES']

APPNAME, VERSION = calibre_constants['appname'], calibre_constants['version']
WINVER = VERSION + '.0'
machine = 'X64' if is64bit else 'X86'
j, d, a, b = os.path.join, os.path.dirname, os.path.abspath, os.path.basename
create_installer = runpy.run_path(
    j(d(a(__file__)), 'wix.py'), {'calibre_constants': calibre_constants}
)['create_installer']

DESCRIPTIONS = {
    'calibre': 'The main calibre program',
    'ebook-viewer': 'The calibre e-book viewer',
    'ebook-edit': 'The calibre e-book editor',
    'lrfviewer': 'Viewer for LRF files',
    'ebook-convert': 'Command line interface to the conversion/news download system',
    'ebook-meta': 'Command line interface for manipulating e-book metadata',
    'calibredb': 'Command line interface to the calibre database',
    'calibre-launcher': 'Utility functions common to all executables',
    'calibre-debug': 'Command line interface for calibre debugging/development',
    'calibre-customize': 'Command line interface to calibre plugin system',
    'calibre-server': 'Standalone calibre content server',
    'calibre-parallel': 'calibre worker process',
    'calibre-smtp': 'Command line interface for sending books via email',
    'calibre-eject': 'Helper program for ejecting connected reader devices',
    'calibre-file-dialog': 'Helper program to show file open/save dialogs',
}

# https://msdn.microsoft.com/en-us/library/windows/desktop/dn481241(v=vs.85).aspx
SUPPORTED_OS = {
    'w7': '{35138b9a-5d96-4fbd-8e2d-a2440225f93a}',
    'w8': '{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}',
    'w81': '{1f676c76-80e1-4239-95bb-83d0f6d0da78}',
    'w10': '{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}',
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
          <supportedOS Id="{w7}"/>
          <supportedOS Id="{w8}"/>
          <supportedOS Id="{w81}"/>
          <supportedOS Id="{w10}"/>
      </application>
    </compatibility>
  </assembly>
'''.format(**SUPPORTED_OS)


def printf(*args, **kw):
    print(*args, **kw)
    sys.stdout.flush()


def run_compiler(env, *cmd):
    run(*cmd, cwd=env.obj_dir)


class Env(object):

    def __init__(self, build_dir):
        self.python_base = os.path.join(PREFIX, 'private', 'python')
        self.portable_uncompressed_size = 0
        self.src_root = CALIBRE_DIR
        self.base = j(build_dir, 'winfrozen')
        self.app_base = j(self.base, 'app')
        self.rc_template = j(d(a(__file__)), 'template.rc')
        self.py_ver = '.'.join(map(str, python_major_minor_version()))
        self.lib_dir = j(self.app_base, 'Lib')
        self.pylib = j(self.app_base, 'pylib.zip')
        self.dll_dir = j(self.app_base, 'bin')
        self.portable_base = j(d(self.base), 'Calibre Portable')
        self.obj_dir = j(build_dir, 'launcher')
        self.installer_dir = j(build_dir, 'wix')
        self.dist = j(SW, 'dist')


def initbase(env):
    os.makedirs(env.app_base)
    os.mkdir(env.dll_dir)
    try:
        shutil.rmtree(env.dist)
    except EnvironmentError as err:
        if err.errno != errno.ENOENT:
            raise
    os.mkdir(env.dist)


def add_plugins(env, ext_dir):
    printf('Adding plugins...')
    tgt = env.dll_dir
    for f in glob.glob(j(ext_dir, '*.pyd')):
        shutil.copy2(f, tgt)


def freeze(env, ext_dir):
    shutil.copy2(j(env.src_root, 'LICENSE'), env.base)

    printf('Adding resources...')
    tgt = j(env.app_base, 'resources')
    if os.path.exists(tgt):
        shutil.rmtree(tgt)
    shutil.copytree(j(env.src_root, 'resources'), tgt)

    printf('\tAdding misc binary deps')

    def copybin(x):
        shutil.copy2(x, env.dll_dir)
        try:
            shutil.copy2(x + '.manifest', env.dll_dir)
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise

    bindir = os.path.join(PREFIX, 'bin')
    for x in ('pdftohtml', 'pdfinfo', 'pdftoppm', 'jpegtran-calibre', 'cjpeg-calibre', 'optipng-calibre', 'JXRDecApp-calibre'):
        copybin(os.path.join(bindir, x + '.exe'))
    for f in glob.glob(os.path.join(bindir, '*.dll')):
        if re.search(r'(easylzma|icutest)', f.lower()) is None:
            copybin(f)

    copybin(os.path.join(env.python_base, 'python%s.dll' % env.py_ver.replace('.', '')))
    for x in glob.glob(os.path.join(env.python_base, 'DLLs', '*')):  # python pyd modules
        copybin(x)
    for f in walk(os.path.join(env.python_base, 'Lib')):
        if f.lower().endswith('.dll') and 'scintilla' not in f.lower():
            copybin(f)
    add_plugins(env, ext_dir)

    printf('Adding Qt...')
    for x in QT_DLLS:
        copybin(os.path.join(QT_PREFIX, 'bin', x + '.dll'))
    copybin(os.path.join(QT_PREFIX, 'bin', 'QtWebEngineProcess.exe'))
    for x in 'libGLESv2 libEGL'.split():
        copybin(os.path.join(QT_PREFIX, 'bin', x + '.dll'))
    plugdir = j(QT_PREFIX, 'plugins')
    tdir = j(env.app_base, 'plugins')
    for d in QT_PLUGINS:
        imfd = os.path.join(plugdir, d)
        tg = os.path.join(tdir, d)
        if os.path.exists(tg):
            shutil.rmtree(tg)
        shutil.copytree(imfd, tg)
    for f in walk(tdir):
        if not f.lower().endswith('.dll'):
            os.remove(f)
    for data_file in os.listdir(j(QT_PREFIX, 'resources')):
        shutil.copy2(j(QT_PREFIX, 'resources', data_file), j(env.app_base, 'resources'))
    shutil.copytree(j(QT_PREFIX, 'translations'), j(env.app_base, 'translations'))

    printf('Adding python...')

    def ignore_lib(root, items):
        ans = []
        for x in items:
            ext = os.path.splitext(x)[1].lower()
            if ext in ('.dll', '.chm', '.htm', '.txt'):
                ans.append(x)
        return ans

    shutil.copytree(r'%s\Lib' % env.python_base, env.lib_dir, ignore=ignore_lib)
    install_site_py(env)

    # Fix win32com
    sp_dir = j(env.lib_dir, 'site-packages')
    comext = j(sp_dir, 'win32comext')
    shutil.copytree(j(comext, 'shell'), j(sp_dir, 'win32com', 'shell'))
    shutil.rmtree(comext)

    pyqt = j(env.lib_dir, 'site-packages', 'PyQt5')
    for x in {x for x in os.listdir(pyqt) if x.endswith('.pyd')}:
        if x.partition('.')[0] not in PYQT_MODULES and x != 'sip.pyd':
            os.remove(j(pyqt, x))
    with open(j(pyqt, '__init__.py') , 'r+b') as f:
        raw = f.read()
        nraw = raw.replace(b'def find_qt():', b'def find_qt():\n    return # disabled for calibre')
        if nraw == raw:
            raise Exception('Failed to patch PyQt to disable dll directory manipulation')
        f.seek(0), f.truncate(), f.write(nraw)

    printf('Adding calibre sources...')
    for x in glob.glob(j(CALIBRE_DIR, 'src', '*')):
        if os.path.isdir(x):
            if os.path.exists(os.path.join(x, '__init__.py')):
                shutil.copytree(x, j(sp_dir, b(x)), ignore=shutil.ignore_patterns('*.pyc', '*.pyo'))
        else:
            shutil.copy(x, j(sp_dir, b(x)))

    for x in (r'calibre\manual', r'calibre\plugins', 'pythonwin'):
        deld = j(sp_dir, x)
        if os.path.exists(deld):
            shutil.rmtree(deld)

    for x in os.walk(j(sp_dir, 'calibre')):
        for f in x[-1]:
            if not f.endswith('.py'):
                os.remove(j(x[0], f))

    extract_pyd_modules(env, sp_dir)

    printf('Byte-compiling all python modules...')
    for x in ('test', 'lib2to3'):
        x = j(env.lib_dir, x)
        if os.path.exists(x):
            shutil.rmtree(x)
    py_compile(env.lib_dir.replace(os.sep, '/'))


def embed_manifests(env):
    printf('Embedding remaining manifests...')
    for manifest in walk(env.base):
        dll, ext = os.path.splitext(manifest)
        if ext != '.manifest':
            continue
        res = 2
        if os.path.splitext(dll)[1] == '.exe':
            res = 1
        if os.path.exists(dll) and open(manifest, 'rb').read().strip():
            run(MT, '-manifest', manifest, '-outputresource:%s;%d' % (dll, res))
        os.remove(manifest)


def extract_pyd_modules(env, site_packages_dir):
    printf('\nExtracting .pyd modules from site-packages...')

    def extract_pyd(path, root):
        fullname = os.path.relpath(path, root).replace(os.sep, '/').replace('/', '.')
        dest = os.path.join(env.dll_dir, fullname)
        if os.path.exists(dest):
            raise ValueError('Cannot extract %s into DLLs as it already exists' % fullname)
        os.rename(path, dest)
        bpy = dest[:-1]
        if os.path.exists(bpy):
            with open(bpy, 'rb') as f:
                raw = f.read().strip().decode('utf-8')
            if (not raw.startswith('def __bootstrap__') or not raw.endswith('__bootstrap__()')):
                raise ValueError('The file %r has non bootstrap code' % bpy)
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
        for line in open(pth).readlines():
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


def embed_resources(env, module, desc=None, extra_data=None, product_description=None):
    icon_base = j(env.src_root, 'icons')
    icon_map = {'calibre': 'library', 'ebook-viewer': 'viewer', 'ebook-edit': 'ebook-edit',
                'lrfviewer': 'viewer', 'calibre-portable': 'library'}
    file_type = 'DLL' if module.endswith('.dll') else 'APP'
    with open(env.rc_template, 'rb') as f:
        template = f.read().decode('utf-8')
    bname = b(module)
    internal_name = os.path.splitext(bname)[0]
    icon = icon_map.get(internal_name, 'command-prompt')
    if internal_name.startswith('calibre-portable-'):
        icon = 'install'
    icon = j(icon_base, icon + '.ico')
    if desc is None:
        defdesc = 'A dynamic link library' if file_type == 'DLL' else \
            'An executable program'
        desc = DESCRIPTIONS.get(internal_name, defdesc)
    license = 'GNU GPL v3.0'

    def e(val):
        return val.replace('"', r'\"')
    if product_description is None:
        product_description = APPNAME + ' - E-book management'
    rc = template.format(
        icon=icon.replace('\\', '/'),
        file_type=e(file_type),
        file_version=e(WINVER.replace('.', ',')),
        file_version_str=e(WINVER),
        file_description=e(desc),
        internal_name=e(internal_name),
        original_filename=e(bname),
        product_version=e(WINVER.replace('.', ',')),
        product_version_str=e(VERSION),
        product_name=e(APPNAME),
        product_description=e(product_description),
        legal_copyright=e(license),
        legal_trademarks=e(APPNAME + ' is a registered U.S. trademark number 3,666,525')
    )
    if extra_data:
        rc += '\nextra extra "%s"' % extra_data
    tdir = env.obj_dir
    rcf = j(tdir, bname + '.rc')
    with open(rcf, 'w') as f:
        f.write(rc)
    res = j(tdir, bname + '.res')
    run(RC, '/n', '/fo' + res, rcf)
    return res


def install_site_py(env):
    if not os.path.exists(env.lib_dir):
        os.makedirs(env.lib_dir)
    shutil.copy2(j(d(__file__), 'site.py'), env.lib_dir)


def build_portable_installer(env):
    zf = a(j(env.dist, 'calibre-portable-%s.zip.lz' % VERSION)).replace(os.sep, '/')
    usz = env.portable_uncompressed_size or os.path.getsize(zf)

    def cc(src, obj):
        cflags = '/c /EHsc /MT /W4 /Ox /nologo /D_UNICODE /DUNICODE /DPSAPI_VERSION=1'.split()
        cflags.append(r'/I%s\include' % PREFIX)
        cflags.append('/DUNCOMPRESSED_SIZE=%d' % usz)
        printf('Compiling', obj)
        cmd = [CL] + cflags + ['/Fo' + obj, src]
        run_compiler(env, *cmd)

    base = d(a(__file__))
    src = j(base, 'portable-installer.cpp')
    obj = j(env.obj_dir, b(src) + '.obj')
    xsrc = j(base, 'XUnzip.cpp')
    xobj = j(env.obj_dir, b(xsrc) + '.obj')
    cc(src, obj)
    cc(xsrc, xobj)

    exe = j(env.dist, 'calibre-portable-installer-%s.exe' % VERSION)
    printf('Linking', exe)
    manifest = exe + '.manifest'
    with open(manifest, 'wb') as f:
        f.write(EXE_MANIFEST.encode('utf-8'))
    cmd = [LINK] + [
        '/INCREMENTAL:NO', '/MACHINE:' + machine,
        '/LIBPATH:' + env.obj_dir, '/SUBSYSTEM:WINDOWS',
        '/LIBPATH:' + (PREFIX + r'\lib'),
        '/RELEASE', '/MANIFEST:EMBED', '/MANIFESTINPUT:' + manifest,
        '/ENTRY:wWinMainCRTStartup',
        '/OUT:' + exe, embed_resources(
            env, exe, desc='Calibre Portable Installer', extra_data=zf, product_description='Calibre Portable Installer'),
        xobj, obj, 'User32.lib', 'Shell32.lib', 'easylzma_s.lib',
        'Ole32.lib', 'Shlwapi.lib', 'Kernel32.lib', 'Psapi.lib']
    run(*cmd)
    os.remove(zf)


def build_portable(env):
    base = env.portable_base
    if os.path.exists(base):
        shutil.rmtree(base)
    os.makedirs(base)
    root = d(a(__file__))
    src = j(root, 'portable.c')
    obj = j(env.obj_dir, b(src) + '.obj')
    cflags = '/c /EHsc /MT /W3 /Ox /nologo /D_UNICODE /DUNICODE'.split()

    printf('Compiling', obj)
    cmd = [CL] + cflags + ['/Fo' + obj, '/Tc' + src]
    run_compiler(env, *cmd)

    exe = j(base, 'calibre-portable.exe')
    printf('Linking', exe)
    cmd = [LINK] + [
        '/INCREMENTAL:NO', '/MACHINE:' + machine,
        '/LIBPATH:' + env.obj_dir, '/SUBSYSTEM:WINDOWS',
        '/RELEASE',
        '/ENTRY:wWinMainCRTStartup',
        '/OUT:' + exe, embed_resources(env, exe, desc='Calibre Portable', product_description='Calibre Portable'),
        obj, 'User32.lib']
    run(*cmd)

    printf('Creating portable installer')
    shutil.copytree(env.base, j(base, 'Calibre'))
    os.mkdir(j(base, 'Calibre Library'))
    os.mkdir(j(base, 'Calibre Settings'))

    name = '%s-portable-%s.zip' % (APPNAME, VERSION)
    name = j(env.dist, name)
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_STORED) as zf:
        add_dir_to_zip(zf, base, 'Calibre Portable')

    env.portable_uncompressed_size = os.path.getsize(name)
    subprocess.check_call([PREFIX + r'\bin\elzma.exe', '-9', '--lzip', name])


def sign_files(env, files):
    args = [SIGNTOOL, 'sign', '/a', '/fd', 'sha256', '/td', 'sha256', '/d',
            'calibre - E-book management', '/du',
            'https://calibre-ebook.com', '/tr']

    def runcmd(cmd):
        for timeserver in ('http://sha256timestamp.ws.symantec.com/sha256/timestamp', 'http://timestamp.comodoca.com/rfc3161',):
            try:
                subprocess.check_call(cmd + [timeserver] + list(files))
                break
            except subprocess.CalledProcessError:
                print('Signing failed, retrying with different timestamp server')
        else:
            raise SystemExit('Signing failed')

    runcmd(args)


def sign_installers(env):
    printf('Signing installers...')
    installers = set()
    for f in glob.glob(j(env.dist, '*')):
        if f.rpartition('.')[-1].lower() in {'exe', 'msi'}:
            installers.add(f)
        else:
            os.remove(f)
    if not installers:
        raise ValueError('No installers found')
    sign_files(env, installers)


def add_dir_to_zip(zf, path, prefix=''):
    '''
    Add a directory recursively to the zip file with an optional prefix.
    '''
    if prefix:
        zi = zipfile.ZipInfo(prefix + '/')
        zi.external_attr = 16
        zf.writestr(zi, '')
    cwd = os.path.abspath(os.getcwd())
    try:
        os.chdir(path)
        fp = (prefix + ('/' if prefix else '')).replace('//', '/')
        for f in os.listdir('.'):
            arcname = fp + f
            if os.path.isdir(f):
                add_dir_to_zip(zf, f, prefix=arcname)
            else:
                zf.write(f, arcname)
    finally:
        os.chdir(cwd)


def build_utils(env):

    def build(src, name, subsys='CONSOLE', libs='setupapi.lib'.split()):
        printf('Building ' + name)
        obj = j(env.obj_dir, os.path.basename(src) + '.obj')
        cflags = '/c /EHsc /MD /W3 /Ox /nologo /D_UNICODE'.split()
        ftype = '/T' + ('c' if src.endswith('.c') else 'p')
        cmd = [CL] + cflags + ['/Fo' + obj, ftype + src]
        run_compiler(env, *cmd)
        exe = j(env.dll_dir, name)
        mf = exe + '.manifest'
        with open(mf, 'wb') as f:
            f.write(EXE_MANIFEST.encode('utf-8'))
        cmd = [LINK] + [
            '/MACHINE:' + machine,
            '/SUBSYSTEM:' + subsys, '/RELEASE', '/MANIFEST:EMBED', '/MANIFESTINPUT:' + mf,
            '/OUT:' + exe] + [embed_resources(env, exe), obj] + libs
        run(*cmd)
    base = d(a(__file__))
    build(j(base, 'file_dialogs.cpp'), 'calibre-file-dialog.exe', 'WINDOWS', 'Ole32.lib Shell32.lib'.split())
    build(j(base, 'eject.c'), 'calibre-eject.exe')


def build_launchers(env, debug=False):
    if not os.path.exists(env.obj_dir):
        os.makedirs(env.obj_dir)
    dflags = (['/Zi'] if debug else [])
    dlflags = (['/DEBUG'] if debug else ['/INCREMENTAL:NO'])
    base = d(a(__file__))
    sources = [j(base, x) for x in ['util.c', ]]
    objects = [j(env.obj_dir, b(x) + '.obj') for x in sources]
    cflags = '/c /EHsc /W3 /Ox /nologo /D_UNICODE'.split()
    cflags += ['/DPYDLL="python%s.dll"' % env.py_ver.replace('.', ''), '/I%s/include' % env.python_base]
    for src, obj in zip(sources, objects):
        cmd = [CL] + cflags + dflags + ['/MD', '/Fo' + obj, '/Tc' + src]
        run_compiler(env, *cmd)

    dll = j(env.obj_dir, 'calibre-launcher.dll')
    ver = '.'.join(VERSION.split('.')[:2])
    cmd = [LINK, '/DLL', '/VERSION:' + ver, '/LTCG', '/OUT:' + dll,
           '/nologo', '/MACHINE:' + machine] + dlflags + objects + \
        [embed_resources(env, dll),
            '/LIBPATH:%s/libs' % env.python_base,
            'delayimp.lib', 'user32.lib', 'shell32.lib',
            'python%s.lib' % env.py_ver.replace('.', ''),
            '/delayload:python%s.dll' % env.py_ver.replace('.', '')]
    printf('Linking calibre-launcher.dll')
    run(*cmd)

    src = j(base, 'main.c')
    shutil.copy2(dll, env.dll_dir)
    basenames, modules, functions = calibre_constants['basenames'], calibre_constants['modules'], calibre_constants['functions']
    for typ in ('console', 'gui', ):
        printf('Processing %s launchers' % typ)
        subsys = 'WINDOWS' if typ == 'gui' else 'CONSOLE'
        for mod, bname, func in zip(modules[typ], basenames[typ], functions[typ]):
            cflags = '/c /EHsc /MT /W3 /O1 /nologo /D_UNICODE /DUNICODE /GS-'.split()
            if typ == 'gui':
                cflags += ['/DGUI_APP=']

            cflags += ['/DMODULE="%s"' % mod, '/DBASENAME="%s"' % bname,
                       '/DFUNCTION="%s"' % func]
            dest = j(env.obj_dir, bname + '.obj')
            printf('Compiling', bname)
            cmd = [CL] + cflags + dflags + ['/Tc' + src, '/Fo' + dest]
            run_compiler(env, *cmd)
            exe = j(env.base, bname + '.exe')
            lib = dll.replace('.dll', '.lib')
            u32 = ['user32.lib']
            printf('Linking', bname)
            mf = dest + '.manifest'
            with open(mf, 'wb') as f:
                f.write(EXE_MANIFEST.encode('utf-8'))
            cmd = [LINK] + [
                '/MACHINE:' + machine, '/NODEFAULTLIB', '/ENTRY:start_here',
                '/LIBPATH:' + env.obj_dir, '/SUBSYSTEM:' + subsys,
                '/LIBPATH:%s/libs' % env.python_base, '/RELEASE',
                '/MANIFEST:EMBED', '/MANIFESTINPUT:' + mf,
                'user32.lib', 'kernel32.lib',
                '/OUT:' + exe] + u32 + dlflags + [embed_resources(env, exe), dest, lib]
            run(*cmd)


def add_to_zipfile(zf, name, base, zf_names):
    abspath = j(base, name)
    name = name.replace(os.sep, '/')
    if name in zf_names:
        raise ValueError('Already added %r to zipfile [%r]' % (name, abspath))
    zinfo = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))

    if os.path.isdir(abspath):
        if not os.listdir(abspath):
            return
        zinfo.external_attr = 0o700 << 16
        zf.writestr(zinfo, '')
        for x in os.listdir(abspath):
            add_to_zipfile(zf, name + os.sep + x, base, zf_names)
    else:
        ext = os.path.splitext(name)[1].lower()
        if ext in ('.dll',):
            raise ValueError('Cannot add %r to zipfile' % abspath)
        zinfo.external_attr = 0o600 << 16
        if ext in ('.py', '.pyc', '.pyo'):
            with open(abspath, 'rb') as f:
                zf.writestr(zinfo, f.read())

    zf_names.add(name)


def archive_lib_dir(env):
    printf('Putting all python code into a zip file for performance')
    zf_names = set()
    with zipfile.ZipFile(env.pylib, 'w', zipfile.ZIP_STORED) as zf:
        # Add everything in Lib except site-packages to the zip file
        for x in os.listdir(env.lib_dir):
            if x == 'site-packages':
                continue
            add_to_zipfile(zf, x, env.lib_dir, zf_names)

        sp = j(env.lib_dir, 'site-packages')
        # Special handling for pywin32
        handled = {'pywin32.pth', 'win32'}
        base = j(sp, 'win32', 'lib')
        for x in os.listdir(base):
            if os.path.splitext(x)[1] not in ('.exe',):
                add_to_zipfile(zf, x, base, zf_names)
        base = os.path.dirname(base)
        for x in os.listdir(base):
            if not os.path.isdir(j(base, x)):
                if os.path.splitext(x)[1] not in ('.exe',):
                    add_to_zipfile(zf, x, base, zf_names)

        # We dont want the site.py (if any) from site-packages
        handled.add('site.pyo')

        # The rest of site-packages
        for x in os.listdir(sp):
            if x in handled or x.endswith('.egg-info'):
                continue
            absp = j(sp, x)
            if os.path.isdir(absp):
                if not os.listdir(absp):
                    continue
                add_to_zipfile(zf, x, sp, zf_names)
            else:
                add_to_zipfile(zf, x, sp, zf_names)

    shutil.rmtree(env.lib_dir)


def copy_crt_and_d3d(env):
    printf('Copying CRT and D3D...')
    plat = ('x64' if is64bit else 'x86')
    for key, val in worker_env.items():
        if 'COMNTOOLS' in key.upper():
            redist_dir = os.path.dirname(os.path.dirname(val.rstrip(os.sep)))
            redist_dir = os.path.join(redist_dir, 'VC', 'Redist', 'MSVC')
            vc_path = glob.glob(os.path.join(redist_dir, '*', plat, '*.CRT'))[0]
            break
    else:
        raise SystemExit('Could not find Visual Studio redistributable CRT')

    sdk_path = os.path.join(
        worker_env['UNIVERSALCRTSDKDIR'], 'Redist', worker_env['WINDOWSSDKVERSION'],
        'ucrt', 'DLLs', plat)
    if not os.path.exists(sdk_path):
        raise SystemExit('Windows 10 Universal CRT redistributable not found at: %r' % sdk_path)
    d3d_path = os.path.join(
        worker_env['WINDOWSSDKDIR'], 'Redist', 'D3D', plat)
    if not os.path.exists(d3d_path):
        raise SystemExit('Windows 10 D3D redistributable not found at: %r' % d3d_path)
    mesa_path = os.path.join(os.environ['MESA'], ('64' if is64bit else '32'), 'opengl32sw.dll')
    if not os.path.exists(mesa_path):
        raise SystemExit('Mesa DLLs (opengl32sw.dll) not found at: %r' % mesa_path)

    def copy_dll(dll):
        shutil.copy2(dll, env.dll_dir)
        os.chmod(os.path.join(env.dll_dir, b(dll)), stat.S_IRWXU)

    for dll in glob.glob(os.path.join(d3d_path, '*.dll')):
        if os.path.basename(dll).lower().startswith('d3dcompiler_'):
            copy_dll(dll)
    copy_dll(mesa_path)
    for dll in glob.glob(os.path.join(sdk_path, '*.dll')):
        copy_dll(dll)
    for dll in glob.glob(os.path.join(vc_path, '*.dll')):
        bname = os.path.basename(dll)
        if not bname.startswith('vccorlib') and not bname.startswith('concrt'):
            # Those two DLLs are not required vccorlib is for the CORE CLR
            # I think concrt is the concurrency runtime for C++ which I believe
            # nothing in calibre currently uses
            copy_dll(dll)


def sign_executables(env):
    files_to_sign = []
    for path in walk(env.base):
        if path.lower().endswith('.exe'):
            files_to_sign.append(path)
    printf('Signing {} exe files'.format(len(files_to_sign)))
    sign_files(env, files_to_sign)


def main():
    ext_dir = globals()['ext_dir']
    args = globals()['args']
    run_tests = iv['run_tests']
    env = Env(build_dir())
    initbase(env)
    build_launchers(env)
    build_utils(env)
    freeze(env, ext_dir)
    embed_manifests(env)
    copy_crt_and_d3d(env)
    archive_lib_dir(env)
    if not args.skip_tests:
        run_tests(os.path.join(env.base, 'calibre-debug.exe'), env.base)
    if args.sign_installers:
        sign_executables(env)
    create_installer(env)
    if not is64bit:
        build_portable(env)
        build_portable_installer(env)
    if args.sign_installers:
        sign_installers(env)


def develop_launcher():
    import subprocess

    def r(*a):
        subprocess.check_call(list(a))

    r(
        'cl.EXE', '/c', '/EHsc', '/MT', '/W3', '/O1', '/nologo', '/D_UNICODE', '/DUNICODE', '/GS-',
        '/DMODULE="calibre.debug"', '/DBASENAME="calibre-debug"', '/DFUNCTION="main"',
        r'/TcC:\r\src\bypy\windows\main.c', r'/Fo..\launcher\calibre-debug.obj'
    )
    r(
        'link.EXE', '/MACHINE:X86', '/NODEFAULTLIB', '/ENTRY:start_here',
        r'/LIBPATH:..\launcher', '/SUBSYSTEM:CONSOLE',
        r'/LIBPATH:C:\r\sw32\sw\private\python/libs', '/RELEASE',
        '/MANIFEST:EMBED', r'/MANIFESTINPUT:..\launcher\calibre-debug.obj.manifest',
        'user32.lib', 'kernel32.lib', r'/OUT:calibre-debug.exe',
        'user32.lib', '/INCREMENTAL:NO', r'..\launcher\calibre-debug.exe.res',
        r'..\launcher\calibre-debug.obj', r'..\launcher\calibre-launcher.lib'
    )


if __name__ == '__main__':
    main()
