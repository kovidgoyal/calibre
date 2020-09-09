#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, subprocess, re, sys, sysconfig
from distutils.spawn import find_executable

from setup import isfreebsd, ismacos, iswindows, is64bit, islinux, ishaiku
is64bit

NMAKE = RC = msvc = MT = win_inc = win_lib = None
if iswindows:
    from distutils import msvc9compiler
    msvc = msvc9compiler.MSVCCompiler()
    msvc.initialize()
    NMAKE = msvc.find_exe('nmake.exe')
    RC = msvc.find_exe('rc.exe')
    MT = msvc.find_exe('mt.exe')
    win_inc = [x for x in os.environ['include'].split(';') if x]
    win_lib = [x for x in os.environ['lib'].split(';') if x]

QMAKE = 'qmake'
for x in ('qmake-qt5', 'qt5-qmake', 'qmake'):
    q = find_executable(x)
    if q:
        QMAKE = q
        break
QMAKE = os.environ.get('QMAKE', QMAKE)

PKGCONFIG = find_executable('pkg-config')
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


pyqt = {x:readvar(y) for x, y in (
    ('inc', 'QT_INSTALL_HEADERS'), ('lib', 'QT_INSTALL_LIBS')
)}
qt = {x:readvar(y) for x, y in {'libs':'QT_INSTALL_LIBS', 'plugins':'QT_INSTALL_PLUGINS'}.items()}
qmakespec = readvar('QMAKE_SPEC') if iswindows else None

pyqt['sip_bin'] = os.environ.get('SIP_BIN', 'sip')

import PyQt5
from PyQt5.QtCore import PYQT_CONFIGURATION
pyqt['sip_flags'] = PYQT_CONFIGURATION['sip_flags']


def get_sip_dir():
    q = None
    if getattr(PyQt5, '__file__', None):
        q = os.path.join(os.path.dirname(PyQt5.__file__), 'bindings')
        if not os.path.exists(q):
            q = None
    if q is None:
        if iswindows:
            q = os.path.join(sys.prefix, 'share', 'sip')
        elif isfreebsd:
            q = os.path.join(sys.prefix, 'share', 'py-sip')
        else:
            q = os.path.join(os.path.dirname(PyQt5.__file__), 'bindings')
            if not os.path.exists(q):
                q = os.path.join(sys.prefix, 'share', 'sip')
    q = os.environ.get('SIP_DIR', q)
    for x in ('', 'Py2-PyQt5', 'PyQt5', 'sip/PyQt5'):
        base = os.path.join(q, x)
        if os.path.exists(os.path.join(base, 'QtWidgets')):
            return base
    raise EnvironmentError('Failed to find the location of the PyQt5 .sip files')


pyqt['pyqt_sip_dir'] = get_sip_dir()
pyqt['sip_inc_dir'] = os.environ.get('SIP_INC_DIR', sysconfig.get_path('include'))

qt_inc = pyqt['inc']
qt_lib = pyqt['lib']
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
    podofo_inc = os.path.join(sw_inc_dir, 'podofo')
    hunspell_inc_dirs = [os.path.join(sw_inc_dir, 'hunspell')]
    podofo_lib = sw_lib_dir
    ft_libs = ['freetype']
    ft_inc_dirs = [sw + '/include/freetype2']
    SSL = os.environ.get('OPENSSL_DIR', os.path.join(sw, 'private', 'ssl'))
    openssl_inc_dirs = [os.path.join(SSL, 'include')]
    openssl_lib_dirs = [os.path.join(SSL, 'lib')]
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
