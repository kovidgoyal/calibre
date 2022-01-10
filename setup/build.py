#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os, shlex, subprocess, glob, shutil, sys, json, errno, sysconfig
from collections import namedtuple

from setup import Command, islinux, isbsd, isfreebsd, ismacos, ishaiku, SRC, iswindows
isunix = islinux or ismacos or isbsd or ishaiku

py_lib = os.path.join(sys.prefix, 'libs', 'python%d%d.lib' % sys.version_info[:2])
CompileCommand = namedtuple('CompileCommand', 'cmd src dest')
LinkCommand = namedtuple('LinkCommand', 'cmd objects dest')


def walk(path='.'):
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            yield os.path.join(dirpath, f)


def init_symbol_name(name):
    prefix = 'PyInit_'
    return prefix + name


def absolutize(paths):
    return list({x if os.path.isabs(x) else os.path.join(SRC, x.replace('/', os.sep)) for x in paths})


class Extension:

    def __init__(self, name, sources, **kwargs):
        self.data = d = {}
        self.name = d['name'] = name
        self.sources = d['sources'] = absolutize(sources)
        self.needs_cxx = d['needs_cxx'] = bool([1 for x in self.sources if os.path.splitext(x)[1] in ('.cpp', '.c++', '.cxx')])
        self.needs_py2 = d['needs_py2'] = kwargs.get('needs_py2', False)
        self.headers = d['headers'] = absolutize(kwargs.get('headers', []))
        self.sip_files = d['sip_files'] = absolutize(kwargs.get('sip_files', []))
        self.needs_exceptions = d['needs_exceptions'] = kwargs.get('needs_exceptions', False)
        self.qt_project_type = d['qt_project_type'] = kwargs.get('qt_project_type', "widgets")
        self.inc_dirs = d['inc_dirs'] = absolutize(kwargs.get('inc_dirs', []))
        self.lib_dirs = d['lib_dirs'] = absolutize(kwargs.get('lib_dirs', []))
        self.extra_objs = d['extra_objs'] = absolutize(kwargs.get('extra_objs', []))
        self.error = d['error'] = kwargs.get('error', None)
        self.libraries = d['libraries'] = kwargs.get('libraries', [])
        self.cflags = d['cflags'] = kwargs.get('cflags', [])
        self.uses_icu = 'icuuc' in self.libraries
        if iswindows:
            self.cflags.append('/DCALIBRE_MODINIT_FUNC=PyMODINIT_FUNC')
            if self.needs_cxx and kwargs.get('needs_c++14'):
                self.cflags.insert(0, '/std:c++14')
        else:
            return_type = 'PyObject*'
            extern_decl = 'extern "C"' if self.needs_cxx else ''

            self.cflags.append(
                '-DCALIBRE_MODINIT_FUNC='
                '{} __attribute__ ((visibility ("default"))) {}'.format(extern_decl, return_type))

            if self.needs_cxx:
                if kwargs.get('needs_c++11'):
                    self.cflags.insert(0, '-std=c++11')
                elif kwargs.get('needs_c++14'):
                    self.cflags.insert(0, '-std=c++14')
            else:
                if kwargs.get('needs_c99'):
                    self.cflags.insert(0, '-std=c99')

        self.ldflags = d['ldflags'] = kwargs.get('ldflags', [])
        self.optional = d['options'] = kwargs.get('optional', False)
        of = kwargs.get('optimize_level', None)
        if of is None:
            of = '/Ox' if iswindows else '-O3'
        else:
            flag = '/O%d' if iswindows else '-O%d'
            of = flag % of
        self.cflags.insert(0, of)


def lazy_load(name):
    if name.startswith('!'):
        name = name[1:]
    from setup import build_environment
    try:
        return getattr(build_environment, name)
    except AttributeError:
        raise ImportError('The setup.build_environment module has no symbol named: %s' % name)


def expand_file_list(items, is_paths=True):
    if not items:
        return []
    ans = []
    for item in items:
        if item.startswith('!'):
            item = lazy_load(item)
            if hasattr(item, 'rjust'):
                item = [item]
            ans.extend(expand_file_list(item, is_paths=is_paths))
        else:
            if '*' in item:
                ans.extend(expand_file_list(sorted(glob.glob(os.path.join(SRC, item))), is_paths=is_paths))
            else:
                item = [item]
                if is_paths:
                    item = absolutize(item)
                ans.extend(item)
    return ans


def is_ext_allowed(ext):
    only = ext.get('only', '')
    if only:
        only = set(only.split())
        q = set(filter(lambda x: globals()["is" + x], ["bsd", "freebsd", "haiku", "linux", "macos", "windows"]))
        return len(q.intersection(only)) > 0
    return True


def parse_extension(ext):
    ext = ext.copy()
    ext.pop('only', None)
    kw = {}
    name = ext.pop('name')

    def get(k, default=''):
        ans = ext.pop(k, default)
        if iswindows:
            ans = ext.pop('windows_' + k, ans)
        elif ismacos:
            ans = ext.pop('macos_' + k, ans)
        elif isbsd:
            ans = ext.pop('bsd_' + k, ans)
        elif isfreebsd:
            ans = ext.pop('freebsd_' + k, ans)
        elif ishaiku:
            ans = ext.pop('haiku_' + k, ans)
        else:
            ans = ext.pop('linux_' + k, ans)
        return ans
    for k in 'libraries qt_private ldflags cflags error'.split():
        kw[k] = expand_file_list(get(k).split(), is_paths=False)
    defines = get('defines')
    if defines:
        if 'cflags' not in kw:
            kw['cflags'] = []
        cflags = kw['cflags']
        prefix = '/D' if iswindows else '-D'
        cflags.extend(prefix + x for x in defines.split())
    for k in 'inc_dirs lib_dirs sources headers sip_files'.split():
        v = get(k)
        if v:
            kw[k] = expand_file_list(v.split())
    kw.update(ext)
    return Extension(name, **kw)


def read_extensions():
    if hasattr(read_extensions, 'extensions'):
        return read_extensions.extensions
    with open(os.path.dirname(os.path.abspath(__file__)) + '/extensions.json', 'rb') as f:
        ans = read_extensions.extensions = json.load(f)
    return ans


def get_python_include_paths():
    ans = []
    for name in sysconfig.get_path_names():
        if 'include' in name:
            ans.append(name)

    def gp(x):
        return sysconfig.get_path(x)

    return sorted(frozenset(filter(None, map(gp, sorted(ans)))))


is_macos_universal_build = ismacos and 'universal2' in sysconfig.get_platform()


def init_env(debug=False, sanitize=False):
    from setup.build_environment import win_ld, win_inc, win_lib, NMAKE, win_cc
    linker = None
    if isunix:
        cc = os.environ.get('CC', 'gcc')
        cxx = os.environ.get('CXX', 'g++')
        debug = '-ggdb' if debug else ''
        cflags = os.environ.get('OVERRIDE_CFLAGS',
            f'-Wall -DNDEBUG {debug} -fno-strict-aliasing -pipe')
        cflags = shlex.split(cflags) + ['-fPIC']
        ldflags = os.environ.get('OVERRIDE_LDFLAGS', '-Wall')
        ldflags = shlex.split(ldflags)
        cflags += shlex.split(os.environ.get('CFLAGS', ''))
        ldflags += shlex.split(os.environ.get('LDFLAGS', ''))
        cflags += ['-fvisibility=hidden']
        if sanitize:
            cflags.append('-fsanitize-address')
            ldflags.append('-shared-libasan')

    if islinux:
        cflags.append('-pthread')
        if sys.stdout.isatty():
            cflags.append('-fdiagnostics-color=always')
        ldflags.append('-shared')

    if isbsd:
        cflags.append('-pthread')
        ldflags.append('-shared')

    if ishaiku:
        cflags.append('-lpthread')
        ldflags.append('-shared')

    if islinux or isbsd or ishaiku:
        cflags.extend('-I' + x for x in get_python_include_paths())
        ldlib = sysconfig.get_config_var('LIBDIR')
        if ldlib:
            ldflags += ['-L' + ldlib]
        ldlib = sysconfig.get_config_var('VERSION')
        if ldlib:
            ldflags += ['-lpython' + ldlib + sys.abiflags]
        ldflags += (sysconfig.get_config_var('LINKFORSHARED') or '').split()

    if ismacos:
        if is_macos_universal_build:
            cflags.extend(['-arch', 'x86_64', '-arch', 'arm64'])
            ldflags.extend(['-arch', 'x86_64', '-arch', 'arm64'])
        cflags.append('-D_OSX')
        ldflags.extend('-bundle -undefined dynamic_lookup'.split())
        cflags.extend(['-fno-common', '-dynamic'])
        cflags.extend('-I' + x for x in get_python_include_paths())

    if iswindows:
        cc = cxx = win_cc
        cflags = '/c /nologo /W3 /EHsc /utf-8'.split()
        cflags.append('/Zi' if debug else '/DNDEBUG')
        suffix = ('d' if debug else '')
        cflags.append('/MD' + suffix)
        ldflags = f'/DLL /nologo /INCREMENTAL:NO /NODEFAULTLIB:libcmt{suffix}.lib'.split()
        if debug:
            ldflags.append('/DEBUG')
        # cflags = '/c /nologo /Ox /MD /W3 /EHsc /Zi'.split()
        # ldflags = '/DLL /nologo /INCREMENTAL:NO /DEBUG'.split()
        cflags.append('/GS-')

        for p in win_inc:
            cflags.append('-I'+p)
        for p in win_lib:
            if p:
                ldflags.append('/LIBPATH:'+p)
        cflags.extend('-I' + x for x in get_python_include_paths())
        ldflags.append('/LIBPATH:'+os.path.join(sysconfig.get_config_var('prefix'), 'libs'))
        linker = win_ld
    return namedtuple('Environment', 'cc cxx cflags ldflags linker make')(
        cc=cc, cxx=cxx, cflags=cflags, ldflags=ldflags, linker=linker, make=NMAKE if iswindows else 'make')


class Build(Command):

    short_description = 'Build calibre C/C++ extension modules'
    DEFAULT_OUTPUTDIR = os.path.abspath(os.path.join(SRC, 'calibre', 'plugins'))
    DEFAULT_BUILDDIR = os.path.abspath(os.path.join(os.path.dirname(SRC), 'build'))

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
        ''')

    def add_options(self, parser):
        choices = [e['name'] for e in read_extensions() if is_ext_allowed(e)]+['all', 'headless']
        parser.add_option('-1', '--only', choices=choices, default='all',
                help=('Build only the named extension. Available: '+ ', '.join(choices)+'. Default:%default'))
        parser.add_option('--no-compile', default=False, action='store_true',
                help='Skip compiling all C/C++ extensions.')
        parser.add_option('--build-dir', default=None,
            help='Path to directory in which to place object files during the build process, defaults to "build"')
        parser.add_option('--output-dir', default=None,
            help='Path to directory in which to place the built extensions. Defaults to src/calibre/plugins')
        parser.add_option('--debug', default=False, action='store_true',
            help='Build in debug mode')
        parser.add_option('--sanitize', default=False, action='store_true',
            help='Build with sanitization support. Run with LD_PRELOAD=$(gcc -print-file-name=libasan.so)')

    def dump_db(self, name, db):
        try:
            with open(f'{name}_commands.json', 'w') as f:
                json.dump(db, f, indent=2)
        except OSError as err:
            if err.errno != errno.EROFS:
                raise

    def run(self, opts):
        from setup.parallel_build import parallel_build, create_job
        if opts.no_compile:
            self.info('--no-compile specified, skipping compilation')
            return
        self.env = init_env(debug=opts.debug)
        all_extensions = map(parse_extension, filter(is_ext_allowed, read_extensions()))
        self.build_dir = os.path.abspath(opts.build_dir or self.DEFAULT_BUILDDIR)
        self.output_dir = os.path.abspath(opts.output_dir or self.DEFAULT_OUTPUTDIR)
        self.obj_dir = os.path.join(self.build_dir, 'objects')
        for x in (self.output_dir, self.obj_dir):
            os.makedirs(x, exist_ok=True)
        pyqt_extensions, extensions = [], []
        for ext in all_extensions:
            if opts.only != 'all' and opts.only != ext.name:
                continue
            if ext.error:
                if ext.optional:
                    self.warn(ext.error)
                    continue
                else:
                    raise Exception(ext.error)
            dest = self.dest(ext)
            os.makedirs(self.d(dest), exist_ok=True)
            (pyqt_extensions if ext.sip_files else extensions).append((ext, dest))

        jobs = []
        objects_map = {}
        self.info(f'Building {len(extensions)+len(pyqt_extensions)} extensions')
        ccdb = []
        for (ext, dest) in extensions:
            cmds, objects = self.get_compile_commands(ext, dest, ccdb)
            objects_map[id(ext)] = objects
            for cmd in cmds:
                jobs.append(create_job(cmd.cmd))
        self.dump_db('compile', ccdb)
        if jobs:
            self.info(f'Compiling {len(jobs)} files...')
            if not parallel_build(jobs, self.info):
                raise SystemExit(1)
        jobs, link_commands, lddb = [], [], []
        for (ext, dest) in extensions:
            objects = objects_map[id(ext)]
            cmd = self.get_link_command(ext, dest, objects, lddb)
            if cmd is not None:
                link_commands.append(cmd)
                jobs.append(create_job(cmd.cmd))
        self.dump_db('link', lddb)
        if jobs:
            self.info(f'Linking {len(jobs)} files...')
            if not parallel_build(jobs, self.info):
                raise SystemExit(1)
            for cmd in link_commands:
                self.post_link_cleanup(cmd)

        jobs = []
        sbf_map = {}
        for (ext, dest) in pyqt_extensions:
            cmd, sbf, cwd = self.get_sip_commands(ext)
            sbf_map[id(ext)] = sbf
            if cmd is not None:
                jobs.append(create_job(cmd, cwd=cwd))
        if jobs:
            self.info(f'SIPing {len(jobs)} files...')
            if not parallel_build(jobs, self.info):
                raise SystemExit(1)
        for (ext, dest) in pyqt_extensions:
            sbf = sbf_map[id(ext)]
            if not os.path.exists(sbf):
                self.build_pyqt_extension(ext, dest, sbf)

        if opts.only in {'all', 'headless'}:
            self.build_headless()

    def dest(self, ext):
        ex = '.pyd' if iswindows else '.so'
        return os.path.join(self.output_dir, getattr(ext, 'name', ext))+ex

    def inc_dirs_to_cflags(self, dirs):
        return ['-I'+x for x in dirs]

    def lib_dirs_to_ldflags(self, dirs):
        pref = '/LIBPATH:' if iswindows else '-L'
        return [pref+x for x in dirs if x]

    def libraries_to_ldflags(self, dirs):
        pref = '' if iswindows else '-l'
        suff = '.lib' if iswindows else ''
        return [pref+x+suff for x in dirs]

    def get_compile_commands(self, ext, dest, db):
        compiler = self.env.cxx if ext.needs_cxx else self.env.cc
        objects = []
        ans = []
        obj_dir = self.j(self.obj_dir, ext.name)
        einc = self.inc_dirs_to_cflags(ext.inc_dirs)
        os.makedirs(obj_dir, exist_ok=True)

        for src in ext.sources:
            obj = self.j(obj_dir, os.path.splitext(self.b(src))[0]+'.o')
            objects.append(obj)
            inf = '/Tp' if src.endswith('.cpp') or src.endswith('.cxx') else '/Tc'
            sinc = [inf+src] if iswindows else ['-c', src]
            oinc = ['/Fo'+obj] if iswindows else ['-o', obj]
            cmd = [compiler] + self.env.cflags + ext.cflags + einc + sinc + oinc
            db.append({'arguments': cmd, 'directory': os.getcwd(), 'file': os.path.relpath(src, os.getcwd()), 'output': os.path.relpath(obj, os.getcwd())})
            if self.newer(obj, [src]+ext.headers):
                ans.append(CompileCommand(cmd, src, obj))
        return ans, objects

    def get_link_command(self, ext, dest, objects, lddb):
        compiler = self.env.cxx if ext.needs_cxx else self.env.cc
        linker = self.env.linker if iswindows else compiler
        dest = self.dest(ext)
        elib = self.lib_dirs_to_ldflags(ext.lib_dirs)
        xlib = self.libraries_to_ldflags(ext.libraries)
        cmd = [linker]
        if iswindows:
            pre_ld_flags = []
            if ext.uses_icu:
                # windows has its own ICU libs that dont work
                pre_ld_flags = elib
            cmd += pre_ld_flags + self.env.ldflags + ext.ldflags + elib + xlib + \
                ['/EXPORT:' + init_symbol_name(ext.name)] + objects + ext.extra_objs + ['/OUT:'+dest]
        else:
            cmd += objects + ext.extra_objs + ['-o', dest] + self.env.ldflags + ext.ldflags + elib + xlib
        lddb.append({'arguments': cmd, 'directory': os.getcwd(), 'output': os.path.relpath(dest, os.getcwd())})

        if self.newer(dest, objects+ext.extra_objs):
            return LinkCommand(cmd, objects, dest)

    def post_link_cleanup(self, link_command):
        if iswindows:
            dest = link_command.dest
            for x in ('.exp', '.lib'):
                x = os.path.splitext(dest)[0]+x
                if os.path.exists(x):
                    os.remove(x)

    def check_call(self, *args, **kwargs):
        """print cmdline if an error occurred

        If something is missing (cmake e.g.) you get a non-informative error
         self.check_call(qmc + [ext.name+'.pro'])
         so you would have to look at the source to see the actual command.
        """
        try:
            subprocess.check_call(*args, **kwargs)
        except:
            cmdline = ' '.join(['"%s"' % (arg) if ' ' in arg else arg for arg in args[0]])
            print("Error while executing: %s\n" % (cmdline))
            raise

    def build_headless(self):
        from setup.parallel_build import cpu_count
        if iswindows or ishaiku:
            return  # Dont have headless operation on these platforms
        from setup.build_environment import CMAKE, sw
        self.info('\n####### Building headless QPA plugin', '#'*7)
        a = absolutize
        headers = a([
            'calibre/headless/headless_backingstore.h',
            'calibre/headless/headless_integration.h',
        ])
        sources = a([
            'calibre/headless/main.cpp',
            'calibre/headless/headless_backingstore.cpp',
            'calibre/headless/headless_integration.cpp',
        ])
        others = a(['calibre/headless/headless.json'])
        target = self.dest('headless')
        if not ismacos:
            target = target.replace('headless', 'libheadless')
        if not self.newer(target, headers + sources + others):
            return

        bdir = self.j(self.build_dir, 'headless')
        if os.path.exists(bdir):
            shutil.rmtree(bdir)
        cmd = [CMAKE]
        if is_macos_universal_build:
            cmd += ['-DCMAKE_OSX_ARCHITECTURES=x86_64;arm64']
        if sw and os.path.exists(os.path.join(sw, 'qt')):
            cmd += ['-DCMAKE_SYSTEM_PREFIX_PATH=' + os.path.join(sw, 'qt').replace(os.sep, '/')]
        os.makedirs(bdir)
        cwd = os.getcwd()
        os.chdir(bdir)
        try:
            self.check_call(cmd + ['-S', os.path.dirname(sources[0])])
            self.check_call([self.env.make] + ['-j%d'%(cpu_count or 1)])
        finally:
            os.chdir(cwd)
        os.rename(self.j(bdir, 'libheadless.so'), target)

    def create_sip_build_skeleton(self, src_dir, ext):
        from setup.build_environment import pyqt_sip_abi_version
        abi_version = ''
        if pyqt_sip_abi_version():
            abi_version = f'abi-version = "{pyqt_sip_abi_version()}"'
        sipf = ext.sip_files[0]
        needs_exceptions = 'true' if ext.needs_exceptions else 'false'
        with open(os.path.join(src_dir, 'pyproject.toml'), 'w') as f:
            f.write(f'''
[build-system]
requires = ["sip >=5.3", "PyQt-builder >=1"]
build-backend = "sipbuild.api"

[tool.sip.metadata]
name = "{ext.name}"
requires-dist = "PyQt6 (>=6.2.1)"

[tool.sip]
project-factory = "pyqtbuild:PyQtProject"

[tool.sip.project]
sip-files-dir = "."
{abi_version}

[tool.sip.bindings.{ext.name}]
headers = {ext.headers}
sources = {ext.sources}
exceptions = {needs_exceptions}
include-dirs = {ext.inc_dirs}
qmake-QT = ["{ext.qt_project_type}"]
sip-file = "{os.path.basename(sipf)}"
''')
        shutil.copy2(sipf, src_dir)

    def get_sip_commands(self, ext):
        from setup.build_environment import QMAKE
        pyqt_dir = self.j(self.build_dir, 'pyqt')
        src_dir = self.j(pyqt_dir, ext.name)
        # TODO: Handle building extensions with multiple SIP files.
        sipf = ext.sip_files[0]
        sbf = self.j(src_dir, self.b(sipf)+'.sbf')
        cmd = None
        cwd = None
        if self.newer(sbf, [sipf] + ext.headers + ext.sources):
            shutil.rmtree(src_dir, ignore_errors=True)
            os.makedirs(src_dir)
            self.create_sip_build_skeleton(src_dir, ext)
            cwd = src_dir
            cmd = [
                sys.executable, '-c',
                '''from sipbuild.tools.build import main; main();''',
                '--verbose', '--no-make', '--qmake', QMAKE
            ]
        return cmd, sbf, cwd

    def build_pyqt_extension(self, ext, dest, sbf):
        self.info(f'\n####### Building {ext.name} extension', '#'*7)
        src_dir = os.path.dirname(sbf)
        cwd = os.getcwd()
        try:
            os.chdir(os.path.join(src_dir, 'build'))
            self.check_call([self.env.make] + ([] if iswindows else ['-j%d'%(os.cpu_count() or 1)]))
            e = 'pyd' if iswindows else 'so'
            m = glob.glob(f'{ext.name}/{ext.name}.*{e}')
            if len(m) != 1:
                raise SystemExit(f'Found extra PyQt extension files: {m}')
            shutil.copy2(m[0], dest)
            with open(sbf, 'w') as f:
                f.write('done')
        finally:
            os.chdir(cwd)

    def clean(self):
        self.output_dir = self.DEFAULT_OUTPUTDIR
        extensions = map(parse_extension, filter(is_ext_allowed, read_extensions()))
        for ext in extensions:
            dest = self.dest(ext)
            for x in (dest, dest+'.manifest'):
                if os.path.exists(x):
                    os.remove(x)
        build_dir = self.DEFAULT_BUILDDIR
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
