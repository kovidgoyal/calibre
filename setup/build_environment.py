#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, subprocess, re, shutil
from functools import lru_cache

from setup import ismacos, iswindows, is64bit, islinux, ishaiku

NMAKE = RC = msvc = MT = win_inc = win_lib = win_cc = win_ld = None


@lru_cache(maxsize=2)
def pyqt_sip_abi_version():
    import PyQt6
    if getattr(PyQt6, '__file__', None):
        bindings_path = os.path.join(os.path.dirname(PyQt6.__file__), 'bindings', 'QtCore', 'QtCore.toml')
        if os.path.exists(bindings_path):
            with open(bindings_path) as f:
                raw = f.read()
                m = re.search(r'^sip-abi-version\s*=\s*"(.+?)"', raw, flags=re.MULTILINE)
                if m is not None:
                    return m.group(1)


def merge_paths(a, b):
    a = [os.path.normcase(os.path.normpath(x)) for x in a.split(os.pathsep)]
    for q in b.split(os.pathsep):
        q = os.path.normcase(os.path.normpath(q))
        if q not in a:
            a.append(q)
    return os.pathsep.join(a)


if iswindows:
    from setup.vcvars import query_vcvarsall
    env = query_vcvarsall(is64bit)
    win_path = env['PATH']
    os.environ['PATH'] = merge_paths(env['PATH'], os.environ['PATH'])
    NMAKE = 'nmake.exe'
    RC = 'rc.exe'
    MT = 'mt.exe'
    win_cc = 'cl.exe'
    win_ld = 'link.exe'
    win_inc = [x for x in env['INCLUDE'].split(os.pathsep) if x]
    win_lib = [x for x in env['LIB'].split(os.pathsep) if x]
    for key in env:
        if key != 'PATH':
            os.environ[key] = env[key]

QMAKE = 'qmake'
for x in ('qmake6', 'qmake-qt6', 'qt6-qmake', 'qmake'):
    q = shutil.which(x)
    if q:
        QMAKE = q
        break
QMAKE = os.environ.get('QMAKE', QMAKE)
if iswindows and not QMAKE.lower().endswith('.exe'):
    QMAKE += '.exe'
CMAKE = 'cmake'
CMAKE = os.environ.get('CMAKE', CMAKE)

PKGCONFIG = shutil.which('pkg-config')
PKGCONFIG = os.environ.get('PKG_CONFIG', PKGCONFIG)
if (islinux or ishaiku) and not PKGCONFIG:
    raise SystemExit('Failed to find pkg-config on your system. You can use the environment variable PKG_CONFIG to point to the pkg-config executable')


def run_pkgconfig(name, envvar, default, flag, prefix):
    ans = []
    if envvar:
        ev = os.environ.get(envvar, None)
        if ev:
            ans = [x.strip() for x in ev.split(os.pathsep)]
            ans = [x for x in ans if x and (prefix=='-l' or os.path.exists(x))]
    if not ans:
        try:
            raw = subprocess.Popen([PKGCONFIG, flag, name],
                stdout=subprocess.PIPE).stdout.read().decode('utf-8')
            ans = [x.strip() for x in raw.split(prefix)]
            ans = [x for x in ans if x and (prefix=='-l' or os.path.exists(x))]
        except:
            print('Failed to run pkg-config:', PKGCONFIG, 'for:', name)

    return ans or ([default] if default else [])


def pkgconfig_include_dirs(name, envvar, default):
    return run_pkgconfig(name, envvar, default, '--cflags-only-I', '-I')


def pkgconfig_lib_dirs(name, envvar, default):
    return run_pkgconfig(name, envvar, default,'--libs-only-L', '-L')


def pkgconfig_libs(name, envvar, default):
    return run_pkgconfig(name, envvar, default,'--libs-only-l', '-l')


def consolidate(envvar, default):
    val = os.environ.get(envvar, default)
    ans = [x.strip() for x in val.split(os.pathsep)]
    return [x for x in ans if x and os.path.exists(x)]


qraw = subprocess.check_output([QMAKE, '-query']).decode('utf-8')


def readvar(name):
    return re.search('^%s:(.+)$' % name, qraw, flags=re.M).group(1).strip()


qt = {x:readvar(y) for x, y in {'libs':'QT_INSTALL_LIBS', 'plugins':'QT_INSTALL_PLUGINS'}.items()}
qmakespec = readvar('QMAKE_SPEC') if iswindows else None
ft_lib_dirs = []
ft_libs = []
ft_inc_dirs = []
podofo_inc = '/usr/include/podofo'
podofo_lib = '/usr/lib'
chmlib_inc_dirs = chmlib_lib_dirs = []
sqlite_inc_dirs = []
icu_inc_dirs = []
icu_lib_dirs = []
zlib_inc_dirs = []
zlib_lib_dirs = []
hunspell_inc_dirs = []
hunspell_lib_dirs = []
hyphen_inc_dirs = []
hyphen_lib_dirs = []
openssl_inc_dirs, openssl_lib_dirs = [], []
ICU = sw = ''

if iswindows:
    prefix  = sw = os.environ.get('SW', r'C:\cygwin64\home\kovid\sw')
    sw_inc_dir  = os.path.join(prefix, 'include')
    sw_lib_dir  = os.path.join(prefix, 'lib')
    icu_inc_dirs = [sw_inc_dir]
    icu_lib_dirs = [sw_lib_dir]
    hyphen_inc_dirs = [sw_inc_dir]
    hyphen_lib_dirs = [sw_lib_dir]
    openssl_inc_dirs = [sw_inc_dir]
    openssl_lib_dirs = [sw_lib_dir]
    sqlite_inc_dirs = [sw_inc_dir]
    chmlib_inc_dirs = [sw_inc_dir]
    chmlib_lib_dirs = [sw_lib_dir]
    ft_lib_dirs = [sw_lib_dir]
    ft_libs = ['freetype']
    ft_inc_dirs = [os.path.join(sw_inc_dir, 'freetype2'), sw_inc_dir]
    hunspell_inc_dirs = [os.path.join(sw_inc_dir, 'hunspell')]
    hunspell_lib_dirs = [sw_lib_dir]
    zlib_inc_dirs = [sw_inc_dir]
    zlib_lib_dirs = [sw_lib_dir]
    podofo_inc = os.path.join(sw_inc_dir, 'podofo')
    podofo_lib = sw_lib_dir
elif ismacos:
    sw = os.environ.get('SW', os.path.expanduser('~/sw'))
    sw_inc_dir  = os.path.join(sw, 'include')
    sw_lib_dir  = os.path.join(sw, 'lib')
    sw_bin_dir  = os.path.join(sw, 'bin')
    podofo_inc = os.path.join(sw_inc_dir, 'podofo')
    hunspell_inc_dirs = [os.path.join(sw_inc_dir, 'hunspell')]
    podofo_lib = sw_lib_dir
    ft_libs = ['freetype']
    ft_inc_dirs = [sw + '/include/freetype2']
    SSL = os.environ.get('OPENSSL_DIR', os.path.join(sw, 'private', 'ssl'))
    openssl_inc_dirs = [os.path.join(SSL, 'include')]
    openssl_lib_dirs = [os.path.join(SSL, 'lib')]
    if os.path.exists(os.path.join(sw_bin_dir, 'cmake')):
        CMAKE = os.path.join(sw_bin_dir, 'cmake')
else:
    ft_inc_dirs = pkgconfig_include_dirs('freetype2', 'FT_INC_DIR',
            '/usr/include/freetype2')
    ft_lib_dirs = pkgconfig_lib_dirs('freetype2', 'FT_LIB_DIR', '/usr/lib')
    ft_libs = pkgconfig_libs('freetype2', '', '')
    hunspell_inc_dirs = pkgconfig_include_dirs('hunspell', 'HUNSPELL_INC_DIR', '/usr/include/hunspell')
    hunspell_lib_dirs = pkgconfig_lib_dirs('hunspell', 'HUNSPELL_LIB_DIR', '/usr/lib')
    sw = os.environ.get('SW', os.path.expanduser('~/sw'))
    podofo_inc = '/usr/include/podofo'
    podofo_lib = '/usr/lib'
    if not os.path.exists(podofo_inc + '/podofo.h'):
        podofo_inc = os.path.join(sw, 'include', 'podofo')
        podofo_lib = os.path.join(sw, 'lib')


podofo_lib = os.environ.get('PODOFO_LIB_DIR', podofo_lib)
podofo_inc = os.environ.get('PODOFO_INC_DIR', podofo_inc)
podofo_error = None if os.path.exists(os.path.join(podofo_inc, 'podofo.h')) else \
        ('PoDoFo not found on your system. Various PDF related',
    ' functionality will not work. Use the PODOFO_INC_DIR and',
    ' PODOFO_LIB_DIR environment variables.')
podofo_inc = [podofo_inc, os.path.dirname(podofo_inc)]
