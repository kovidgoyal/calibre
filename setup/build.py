#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import errno
import glob
import json
import os
import shlex
import shutil
import subprocess
import sys
import sysconfig
import textwrap
from functools import partial
from typing import List, NamedTuple

from setup import SRC, Command, isbsd, isfreebsd, ishaiku, islinux, ismacos, iswindows

isunix = islinux or ismacos or isbsd or ishaiku

py_lib = os.path.join(sys.prefix, 'libs', 'python%d%d.lib' % sys.version_info[:2])

class CompileCommand(NamedTuple):
    cmd: List[str]
    src: str
    dest: str


class LinkCommand(NamedTuple):
    cmd: List[str]
    objects: List[str]
    dest: str


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
        self.qt_modules = d['qt_modules'] = kwargs.get('qt_modules', ["widgets"])
        self.inc_dirs = d['inc_dirs'] = absolutize(kwargs.get('inc_dirs', []))
        self.lib_dirs = d['lib_dirs'] = absolutize(kwargs.get('lib_dirs', []))
        self.extra_objs = d['extra_objs'] = absolutize(kwargs.get('extra_objs', []))
        self.error = d['error'] = kwargs.get('error', None)
        self.libraries = d['libraries'] = kwargs.get('libraries', [])
        self.cflags = d['cflags'] = kwargs.get('cflags', [])
        self.uses_icu = 'icuuc' in self.libraries
        self.ldflags = d['ldflags'] = kwargs.get('ldflags', [])
        self.optional = d['options'] = kwargs.get('optional', False)
        self.needs_cxx_std = kwargs.get('needs_c++')
        self.needs_c_std = kwargs.get('needs_c')
        self.only_build_for = kwargs.get('only', '')


def lazy_load(name):
    if name.startswith('!'):
        name = name[1:]
    from setup import build_environment
    try:
        return getattr(build_environment, name)
    except AttributeError:
        raise ImportError('The setup.build_environment module has no symbol named: %s' % name)


def expand_file_list(items, is_paths=True, cross_compile_for='native'):
    if not items:
        return []
    ans = []
    for item in items:
        if item.startswith('!'):
            if cross_compile_for == 'native' or not item.endswith('_dirs'):
                item = lazy_load(item)
                if hasattr(item, 'rjust'):
                    item = [item]
                items = expand_file_list(item, is_paths=is_paths, cross_compile_for=cross_compile_for)
            else:
                pkg, category = item[1:].split('_')[:2]
                if category == 'inc':
                    category = 'include'
                items = [f'bypy/b/windows/64/{pkg}/{category}']
                items = expand_file_list(item, is_paths=is_paths, cross_compile_for=cross_compile_for)
            ans.extend(items)
        else:
            if '*' in item:
                ans.extend(expand_file_list(sorted(glob.glob(os.path.join(SRC, item))), is_paths=is_paths, cross_compile_for=cross_compile_for))
            else:
                item = [item]
                if is_paths:
                    item = absolutize(item)
                ans.extend(item)
    return ans


def is_ext_allowed(cross_compile_for: str, ext: Extension) -> bool:
    only = ext.only_build_for
    if only:
        if islinux and only == cross_compile_for:
            return True
        only = set(only.split())
        q = set(filter(lambda x: globals()["is" + x], ["bsd", "freebsd", "haiku", "linux", "macos", "windows"]))
        return len(q.intersection(only)) > 0
    return True


def parse_extension(ext, compiling_for='native'):
    ext = ext.copy()
    only = ext.pop('only', None)
    kw = {}
    name = ext.pop('name')
    get_key = 'linux_'
    if iswindows:
        get_key = 'windows_'
    elif ismacos:
        get_key = 'macos_'
    elif isbsd:
        get_key = 'bsd_'
    elif isfreebsd:
        get_key = 'freebsd_'
    elif ishaiku:
        get_key = 'haiku_'
    if compiling_for == 'windows':
        get_key = 'windows_'


    def get(k, default=''):
        ans = ext.pop(k, default)
        ans = ext.pop(get_key + k, ans)
        return ans
    for k in 'libraries qt_private ldflags cflags error'.split():
        kw[k] = expand_file_list(get(k).split(), is_paths=False)
    defines = get('defines')
    if defines:
        if 'cflags' not in kw:
            kw['cflags'] = []
        cflags = kw['cflags']
        prefix = '/D' if get_key == 'windows_' else '-D'
        cflags.extend(prefix + x for x in defines.split())
    for k in 'inc_dirs lib_dirs sources headers sip_files'.split():
        v = get(k)
        if v:
            kw[k] = expand_file_list(v.split())
    kw.update(ext)
    kw['only'] = only
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


def basic_windows_flags(debug=False):
    cflags = '/c /nologo /W3 /EHsc /O2 /utf-8'.split()
    cflags.append('/Zi' if debug else '/DNDEBUG')
    suffix = ('d' if debug else '')
    cflags.append('/MD' + suffix)
    ldflags = f'/DLL /nologo /INCREMENTAL:NO /NODEFAULTLIB:libcmt{suffix}.lib'.split()
    if debug:
        ldflags.append('/DEBUG')
    # cflags = '/c /nologo /Ox /MD /W3 /EHsc /Zi'.split()
    # ldflags = '/DLL /nologo /INCREMENTAL:NO /DEBUG'.split()
    cflags.append('/GS-')
    return cflags, ldflags


class Environment(NamedTuple):
    cc: str
    cxx: str
    linker: str
    base_cflags: List[str]
    base_cxxflags: List[str]
    base_ldflags: List[str]
    cflags: List[str]
    ldflags: List[str]
    make: str
    internal_inc_prefix: str
    external_inc_prefix: str
    libdir_prefix: str
    lib_prefix: str
    lib_suffix: str
    obj_suffix: str
    cc_input_c_flag: str
    cc_input_cpp_flag: str
    cc_output_flag: str
    platform_name: str
    dest_ext: str
    std_prefix: str

    def inc_dirs_to_cflags(self, dirs) -> List[str]:
        return [self.external_inc_prefix+x for x in dirs]

    def lib_dirs_to_ldflags(self, dirs) -> List[str]:
        return [self.libdir_prefix+x for x in dirs if x]

    def libraries_to_ldflags(self, libs):
        def map_name(x):
            if '/' in x:
                return x
            return self.lib_prefix+x+self.lib_suffix
        return list(map(map_name, libs))



def init_env(debug=False, sanitize=False, compiling_for='native'):
    from setup.build_environment import NMAKE, win_cc, win_inc, win_ld, win_lib
    linker = None
    internal_inc_prefix = external_inc_prefix = '-I'
    libdir_prefix = '-L'
    lib_prefix = '-l'
    lib_suffix = ''
    std_prefix = '-std='
    obj_suffix = '.o'
    cc_input_c_flag = cc_input_cpp_flag = '-c'
    cc_output_flag = '-o'
    platform_name = 'linux'
    dest_ext = '.so'
    if isunix:
        cc = os.environ.get('CC', 'gcc')
        cxx = os.environ.get('CXX', 'g++')
        debug = '-ggdb' if debug else ''
        cflags = os.environ.get('OVERRIDE_CFLAGS',
            f'-Wall -DNDEBUG {debug} -fno-strict-aliasing -pipe -O3')
        cflags = shlex.split(cflags) + ['-fPIC']
        ldflags = os.environ.get('OVERRIDE_LDFLAGS', '-Wall')
        ldflags = shlex.split(ldflags)
        base_cflags = shlex.split(os.environ.get('CFLAGS', ''))
        base_cxxflags = shlex.split(os.environ.get('CXXFLAGS', ''))
        base_ldflags = shlex.split(os.environ.get('LDFLAGS', ''))
        cflags += base_cflags
        ldflags += base_ldflags
        cflags += ['-fvisibility=hidden']
        if sanitize:
            cflags.append('-fsanitize=address')

    if islinux:
        cflags.append('-pthread')
        if sys.stdout.isatty():
            base_cflags.append('-fdiagnostics-color=always')
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
        platform_name = 'macos'
        if is_macos_universal_build:
            cflags.extend(['-arch', 'x86_64', '-arch', 'arm64'])
            ldflags.extend(['-arch', 'x86_64', '-arch', 'arm64'])
        cflags.append('-D_OSX')
        ldflags.extend('-bundle -undefined dynamic_lookup'.split())
        cflags.extend(['-fno-common', '-dynamic'])
        cflags.extend('-I' + x for x in get_python_include_paths())

    if iswindows or compiling_for == 'windows':
        platform_name = 'windows'
        std_prefix = '/std:'
        cc = cxx = win_cc
        linker = win_ld
        cflags, ldflags = basic_windows_flags(debug)
        base_cflags, base_cxxflags, base_ldflags = [], [], []
        if compiling_for == 'windows':
            cc = cxx = 'clang-cl'
            linker = 'lld-link'
            splat = '.build-cache/xwin/root'
            cflags.append('-fcolor-diagnostics')
            cflags.append('-fansi-escape-codes')
            for I in 'sdk/include/um sdk/include/cppwinrt sdk/include/shared sdk/include/ucrt crt/include'.split():
                cflags.append('/external:I')
                cflags.append(f'{splat}/{I}')
            for L in 'sdk/lib/um crt/lib sdk/lib/ucrt'.split():
                ldflags.append(f'/libpath:{splat}/{L}')
        else:
            for p in win_inc:
                cflags.append('-I'+p)
            for p in win_lib:
                if p:
                    ldflags.append('/LIBPATH:'+p)
        internal_inc_prefix = external_inc_prefix = '/I'
        libdir_prefix = '/libpath:'
        lib_prefix = ''
        lib_suffix = '.lib'
        cc_input_c_flag = '/Tc'
        cc_input_cpp_flag = '/Tp'
        cc_output_flag = '/Fo'
        obj_suffix = '.obj'
        dest_ext = '.pyd'
        if compiling_for == 'windows':
            external_inc_prefix = '/external:I'
            dest_ext = '.cross-windows-x64' + dest_ext
            obj_suffix = '.cross-windows-x64' + obj_suffix
            cflags.append('/external:I')
            cflags.append('bypy/b/windows/64/pkg/python/private/python/include')
            ldflags.append('/libpath:' + 'bypy/b/windows/64/pkg/python/private/python/libs')
        else:
            cflags.extend('-I' + x for x in get_python_include_paths())
            ldflags.append('/LIBPATH:'+os.path.join(sysconfig.get_config_var('prefix'), 'libs'))
    return Environment(
        platform_name=platform_name, dest_ext=dest_ext, std_prefix=std_prefix,
        base_cflags=base_cflags, base_cxxflags=base_cxxflags, base_ldflags=base_ldflags,
        cc=cc, cxx=cxx, cflags=cflags, ldflags=ldflags, linker=linker, make=NMAKE if iswindows else 'make', lib_prefix=lib_prefix,
        obj_suffix=obj_suffix, cc_input_c_flag=cc_input_c_flag, cc_input_cpp_flag=cc_input_cpp_flag, cc_output_flag=cc_output_flag,
        internal_inc_prefix=internal_inc_prefix, external_inc_prefix=external_inc_prefix, libdir_prefix=libdir_prefix, lib_suffix=lib_suffix)


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
        choices = [e['name'] for e in read_extensions()]+['all', 'headless']
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
        parser.add_option('--cross-compile-extensions', choices='windows disabled'.split(), default='disabled',
            help=('Cross compile extensions for other platforms. Useful for development.'
                ' Currently supports of windows extensions on Linux. Remember to run ./setup.py xwin first to install the Windows SDK locally. '))

    def dump_db(self, name, db):
        os.makedirs('build', exist_ok=True)
        existing = []
        try:
            with open(f'build/{name}_commands.json', 'rb') as f:
                existing = json.load(f)
        except FileNotFoundError:
            pass
        combined = {x['output']: x for x in existing}
        for x in db:
            combined[x['output']] = x
        try:
            with open(f'build/{name}_commands.json', 'w') as f:
                json.dump(tuple(combined.values()), f, indent=2)
        except OSError as err:
            if err.errno != errno.EROFS:
                raise

    def run(self, opts):
        from setup.parallel_build import create_job, parallel_build
        if opts.no_compile:
            self.info('--no-compile specified, skipping compilation')
            return
        self.compiling_for = 'native'
        if islinux and opts.cross_compile_extensions == 'windows':
            self.compiling_for = 'windows'
            if not os.path.exists('.build-cache/xwin/root'):
                subprocess.check_call([sys.executable, 'setup.py', 'xwin'])
        self.env = init_env(debug=opts.debug)
        self.windows_cross_env = init_env(debug=opts.debug, compiling_for='windows')
        all_extensions = tuple(map(partial(parse_extension, compiling_for=self.compiling_for), read_extensions()))
        self.build_dir = os.path.abspath(opts.build_dir or self.DEFAULT_BUILDDIR)
        self.output_dir = os.path.abspath(opts.output_dir or self.DEFAULT_OUTPUTDIR)
        self.obj_dir = os.path.join(self.build_dir, 'objects')
        for x in (self.output_dir, self.obj_dir):
            os.makedirs(x, exist_ok=True)
        pyqt_extensions, extensions = [], []
        for ext in all_extensions:
            if opts.only != 'all' and opts.only != ext.name:
                continue
            if not is_ext_allowed(self.compiling_for, ext):
                continue
            if ext.error:
                if ext.optional:
                    self.warn(ext.error)
                    continue
                else:
                    raise Exception(ext.error)
            (pyqt_extensions if ext.sip_files else extensions).append(ext)

        jobs = []
        objects_map = {}
        self.info(f'Building {len(extensions)+len(pyqt_extensions)} extensions')
        ccdb = []
        for ext in all_extensions:
            if ext in pyqt_extensions:
                continue
            cmds, objects = self.get_compile_commands(ext, ccdb)
            objects_map[id(ext)] = objects
            if ext in extensions:
                for cmd in cmds:
                    jobs.append(create_job(cmd.cmd))
        self.dump_db('compile', ccdb)
        if jobs:
            self.info(f'Compiling {len(jobs)} files...')
            if not parallel_build(jobs, self.info):
                raise SystemExit(1)
        jobs, link_commands, lddb = [], [], []
        for ext in all_extensions:
            if ext in pyqt_extensions:
                continue
            objects = objects_map[id(ext)]
            cmd = self.get_link_command(ext, objects, lddb)
            if ext in extensions and cmd is not None:
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
        for ext in pyqt_extensions:
            cmd, sbf, cwd = self.get_sip_commands(ext)
            sbf_map[id(ext)] = sbf
            if cmd is not None:
                jobs.append(create_job(cmd, cwd=cwd))
        if jobs:
            self.info(f'SIPing {len(jobs)} files...')
            if not parallel_build(jobs, self.info):
                raise SystemExit(1)
        for ext in pyqt_extensions:
            sbf = sbf_map[id(ext)]
            if not os.path.exists(sbf):
                self.build_pyqt_extension(ext, sbf)

        if opts.only in {'all', 'headless'}:
            self.build_headless()

    def dest(self, ext, env):
        return os.path.join(self.output_dir, getattr(ext, 'name', ext))+env.dest_ext

    def env_for_compilation_db(self, ext):
        if is_ext_allowed('native', ext):
            return self.env
        if ext.only_build_for == 'windows':
            return self.windows_cross_env

    def get_compile_commands(self, ext, db):
        obj_dir = self.j(self.obj_dir, ext.name)

        def get(src: str, env: Environment, for_tooling: bool = False) -> CompileCommand:
            compiler = env.cxx if ext.needs_cxx else env.cc
            obj = self.j(obj_dir, os.path.splitext(self.b(src))[0]+env.obj_suffix)
            inf = env.cc_input_cpp_flag if src.endswith('.cpp') or src.endswith('.cxx') else env.cc_input_c_flag
            sinc = [inf, src]
            if env.cc_output_flag.startswith('/'):
                if for_tooling:  # clangd gets confused by cl.exe style source and output flags
                    oinc = ['-o', obj]
                else:
                    oinc = [env.cc_output_flag + obj]
                    sinc = [inf + src]
            else:
                oinc = [env.cc_output_flag, obj]
            einc = env.inc_dirs_to_cflags(ext.inc_dirs)
            if env.cc_output_flag.startswith('/'):
                cflags = ['/DCALIBRE_MODINIT_FUNC=PyMODINIT_FUNC']
            else:
                return_type = 'PyObject*'
                extern_decl = 'extern "C"' if ext.needs_cxx else ''
                cflags = [
                    '-DCALIBRE_MODINIT_FUNC='
                    '{} __attribute__ ((visibility ("default"))) {}'.format(extern_decl, return_type)]
            if ext.needs_cxx and ext.needs_cxx_std:
                if env.cc_output_flag.startswith('/') and ext.needs_cxx == "11":
                    ext.needs_cxx = "14"
                cflags.append(env.std_prefix + 'c++' + ext.needs_cxx_std)

            if ext.needs_c_std and not env.std_prefix.startswith('/'):
                cflags.append(env.std_prefix + 'c' + ext.needs_c_std)

            cmd = [compiler] + env.cflags + cflags + ext.cflags + einc + sinc + oinc
            return CompileCommand(cmd, src, obj)

        objects = []
        ans = []
        os.makedirs(obj_dir, exist_ok=True)

        for src in ext.sources:
            cc = get(src, self.windows_cross_env if self.compiling_for == 'windows' else self.env)
            objects.append(cc.dest)
            if self.newer(cc.dest, [src]+ext.headers):
                ans.append(cc)
            env = self.env_for_compilation_db(ext)
            if env is not None:
                cc = get(src, env, for_tooling=True)
                db.append({
                    'arguments': cc.cmd, 'directory': os.getcwd(), 'file': os.path.relpath(src, os.getcwd()),
                    'output': os.path.relpath(cc.dest, os.getcwd())})
        return ans, objects

    def get_link_command(self, ext, objects, lddb):

        def get(env: Environment) -> LinkCommand:
            dest = self.dest(ext, env)
            compiler = env.cxx if ext.needs_cxx else env.cc
            linker = env.linker or compiler
            cmd = [linker]
            elib = env.lib_dirs_to_ldflags(ext.lib_dirs)
            xlib = env.libraries_to_ldflags(ext.libraries)
            if iswindows or env is self.windows_cross_env:
                pre_ld_flags = []
                if ext.uses_icu:
                    # windows has its own ICU libs that dont work
                    pre_ld_flags = elib
                cmd += pre_ld_flags + env.ldflags + ext.ldflags + elib + xlib + \
                    ['/EXPORT:' + init_symbol_name(ext.name)] + objects + ext.extra_objs + ['/OUT:'+dest]
            else:
                cmd += objects + ext.extra_objs + ['-o', dest] + env.ldflags + ext.ldflags + elib + xlib
            return LinkCommand(cmd, objects, dest)

        env = self.env_for_compilation_db(ext)
        if env is not None:
            ld = get(env)
            lddb.append({'arguments': ld.cmd, 'directory': os.getcwd(), 'output': os.path.relpath(ld.dest, os.getcwd())})

        env = self.windows_cross_env if self.compiling_for == 'windows' else self.env
        lc = get(env)
        if self.newer(lc.dest, objects+ext.extra_objs):
            return lc

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
        target = self.dest('headless', self.env)
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

[tool.sip]
project-factory = "pyqtbuild:PyQtProject"

[tool.sip.project]
sip-files-dir = "."
{abi_version}

[project]
name = "{ext.name}"

[tool.sip.builder]
qmake-settings = [
    """QMAKE_CC = {self.env.cc}""",
    """QMAKE_CXX = {self.env.cxx}""",
    """QMAKE_LINK = {self.env.linker or self.env.cxx}""",
    """QMAKE_CFLAGS += {shlex.join(self.env.base_cflags)}""",
    """QMAKE_CXXFLAGS += {shlex.join(self.env.base_cxxflags)}""",
    """QMAKE_LFLAGS += {shlex.join(self.env.base_ldflags)}""",
]

[tool.sip.bindings.{ext.name}]
headers = {ext.headers}
sources = {ext.sources}
exceptions = {needs_exceptions}
include-dirs = {ext.inc_dirs}
qmake-QT = {ext.qt_modules}
sip-file = {os.path.basename(sipf)!r}
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
                sys.executable, '-m', 'sipbuild.tools.build',
                '--verbose', '--no-make', '--qmake', QMAKE
            ]
        return cmd, sbf, cwd

    def build_pyqt_extension(self, ext, sbf):
        self.info(f'\n####### Building {ext.name} extension', '#'*7)
        src_dir = os.path.dirname(sbf)
        cwd = os.getcwd()
        try:
            os.chdir(os.path.join(src_dir, 'build'))
            env = os.environ.copy()
            if is_macos_universal_build:
                env['ARCHS'] = 'x86_64 arm64'
            self.check_call([self.env.make] + ([] if iswindows else ['-j%d'%(os.cpu_count() or 1)]), env=env)
            e = 'pyd' if iswindows else 'so'
            m = glob.glob(f'{ext.name}/{ext.name}.*{e}')
            if not m:
                raise SystemExit(f'No built PyQt extension file in {os.path.join(os.getcwd(), ext.name)}')
            if len(m) != 1:
                raise SystemExit(f'Found extra PyQt extension files: {m}')
            shutil.copy2(m[0], self.dest(ext, self.env))
            with open(sbf, 'w') as f:
                f.write('done')
        finally:
            os.chdir(cwd)

    def clean(self):
        self.output_dir = self.DEFAULT_OUTPUTDIR
        extensions = map(parse_extension, read_extensions())
        env = init_env()
        for ext in extensions:
            dest = self.dest(ext, env)
            b, d = os.path.basename(dest), os.path.dirname(dest)
            b = b.split('.')[0] + '.*'
            for x in glob.glob(os.path.join(d, b)):
                if os.path.exists(x):
                    os.remove(x)
        build_dir = self.DEFAULT_BUILDDIR
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
