#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, subprocess, re, sys, sysconfig
from distutils.spawn import find_executable

from setup import isosx, iswindows, is64bit, islinux, ishaiku
is64bit

NMAKE = RC = msvc = MT = win_inc = win_lib = None
if iswindows:
    from distutils import msvc9compiler
    msvc = msvc9compiler.MSVCCompiler()
    msvc.initialize()
    NMAKE = msvc.find_exe('nmake.exe')
    RC = msvc.find_exe('rc.exe')
    MT = msvc.find_exe('mt.exe')
    win_inc = os.environ['include'].split(';')
    win_lib = os.environ['lib'].split(';')

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
                stdout=subprocess.PIPE).stdout.read()
            ans = [x.strip() for x in raw.split(prefix)]
            ans = [x for x in ans if x and (prefix=='-l' or os.path.exists(x))]
        except:
            print 'Failed to run pkg-config:', PKGCONFIG, 'for:', name

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
qt = {x:readvar(y) for x, y in {'libs':'QT_INSTALL_LIBS', 'plugins':'QT_INSTALL_PLUGINS'}.iteritems()}
qmakespec = readvar('QMAKE_SPEC') if iswindows else None

pyqt['sip_bin'] = os.environ.get('SIP_BIN', 'sip')

from PyQt5.QtCore import PYQT_CONFIGURATION
pyqt['sip_flags'] = PYQT_CONFIGURATION['sip_flags']
def get_sip_dir():
    q = os.environ.get('SIP_DIR', sys.prefix if iswindows else os.path.join(sys.prefix, 'share', 'sip'))
    for x in ('', 'Py2-PyQt5', 'PyQt5', 'sip/PyQt5'):
        base = os.path.join(q, x)
        if os.path.exists(os.path.join(base, 'QtWidgets')):
            return base
    raise EnvironmentError('Failed to find the location of the PyQt5 .sip files')
pyqt['pyqt_sip_dir'] = get_sip_dir()
pyqt['sip_inc_dir'] = os.environ.get('SIP_INC_DIR', sysconfig.get_path('include'))

glib_flags = subprocess.check_output([PKGCONFIG, '--libs', 'glib-2.0']).strip() if islinux or ishaiku else ''
fontconfig_flags = subprocess.check_output([PKGCONFIG, '--libs', 'fontconfig']).strip() if islinux or ishaiku else ''
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
openssl_inc_dirs, openssl_lib_dirs = [], []
icu_libs = ['icudata', 'icui18n', 'icuuc', 'icuio']
ICU = sw = ''

QT_DLLS = ['Qt5' + x for x in (
'Core', 'Gui',  'OpenGL', 'Network', 'PrintSupport', 'Positioning', 'Sensors', 'Sql', 'Svg',
'WebKit', 'WebKitWidgets', 'Widgets',  'Multimedia', 'MultimediaWidgets', 'Xml',  # 'XmlPatterns',
)]
QT_PLUGINS = ('imageformats', 'audio', 'iconengines', 'mediaservice', 'platforms', 'playlistformats', 'printsupport', 'sqldrivers')
if islinux or ishaiku:
    # platformthemes cause crashes in Ubuntu
    QT_PLUGINS += ('platforminputcontexts', 'generic',)

PYQT_MODULES = ('Qt', 'QtCore', 'QtGui', 'QtNetwork',  # 'QtMultimedia', 'QtMultimediaWidgets',
                'QtPrintSupport', 'QtSensors', 'QtSvg', 'QtWebKit', 'QtWebKitWidgets', 'QtWidgets')
QT_FRAMEWORKS = []


if iswindows:
    icu_libs = ['icudt', 'icuin', 'icuuc', 'icuio']
    QT_DLLS += ['Qt5WinExtras']
    QT_DLLS = {x + '.dll' for x in QT_DLLS}
    PYQT_MODULES += ('QtWinExtras',)
    PYQT_MODULES = {x + '.pyd' for x in PYQT_MODULES}
    prefix  = sw = os.environ.get('SW', r'C:\cygwin64\home\kovid\sw')
    sw_inc_dir  = os.path.join(prefix, 'include')
    sw_lib_dir  = os.path.join(prefix, 'lib')
    icu_inc_dirs = [sw_inc_dir]
    icu_lib_dirs = [sw_lib_dir]
    openssl_inc_dirs = [sw_inc_dir]
    openssl_lib_dirs = [sw_lib_dir]
    sqlite_inc_dirs = [sw_inc_dir]
    chmlib_inc_dirs = [sw_inc_dir]
    chmlib_lib_dirs = [sw_lib_dir]
    ft_lib_dirs = [sw_lib_dir]
    ft_libs = ['freetype']
    ft_inc_dirs = [os.path.join(sw_inc_dir, 'freetype2'), sw_inc_dir]
    zlib_inc_dirs = [sw_inc_dir]
    zlib_lib_dirs = [sw_lib_dir]
    podofo_inc = os.path.join(sw_inc_dir, 'podofo')
    podofo_lib = sw_lib_dir
elif isosx:
    QT_DLLS += ['Qt5DBus', 'Qt5MacExtras']
    PYQT_MODULES += ('QtMacExtras',)
    QT_FRAMEWORKS = [x.replace('5', '') for x in QT_DLLS]
    sw = os.environ.get('SW', os.path.expanduser('~/sw'))
    podofo_inc = os.path.join(sw, 'include', 'podofo')
    podofo_lib = os.path.join(sw, 'lib')
    ft_libs = ['freetype']
    ft_inc_dirs = [sw + '/include/freetype2']
    icu_inc_dirs = [sw + '/include']
    icu_lib_dirs = [sw + '/lib']
    SSL = os.environ.get('OPENSSL_DIR', os.path.join(sw, 'private', 'ssl'))
    openssl_inc_dirs = [os.path.join(SSL, 'include')]
    openssl_lib_dirs = [os.path.join(SSL, 'lib')]
else:
    QT_DLLS += ['Qt5DBus', 'Qt5XcbQpa', 'Qt5X11Extras']
    PYQT_MODULES += ('QtX11Extras',)
    ft_inc_dirs = pkgconfig_include_dirs('freetype2', 'FT_INC_DIR',
            '/usr/include/freetype2')
    ft_lib_dirs = pkgconfig_lib_dirs('freetype2', 'FT_LIB_DIR', '/usr/lib')
    ft_libs = pkgconfig_libs('freetype2', '', '')
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

BUILD_HOST='192.168.81.1'
PROJECT=os.path.basename(os.path.abspath('.'))


