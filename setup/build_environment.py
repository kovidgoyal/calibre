#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, socket, struct, subprocess, sys, glob
from distutils.spawn import find_executable

from PyQt4 import pyqtconfig

from setup import isosx, iswindows, islinux

OSX_SDK = '/Developer/SDKs/MacOSX10.5.sdk'

os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.5'
is64bit = sys.maxsize > 2**32

NMAKE = RC = msvc = MT = win_inc = win_lib = win_ddk = win_ddk_lib_dirs = None
if iswindows:
    from distutils import msvc9compiler
    msvc = msvc9compiler.MSVCCompiler()
    msvc.initialize()
    NMAKE = msvc.find_exe('nmake.exe')
    RC = msvc.find_exe('rc.exe')
    SDK = os.environ.get('WINSDK', r'C:\Program Files\Microsoft SDKs\Windows\v6.0A')
    DDK = os.environ.get('WINDDK', r'Q:\WinDDK\7600.16385.0')
    win_ddk = [DDK+'\\inc\\'+x for x in ('atl71',)]
    win_ddk_lib_dirs = [DDK+'\\lib\\ATL\\i386']
    win_inc = os.environ['include'].split(';')
    win_lib = os.environ['lib'].split(';')
    for p in win_inc:
        if 'SDK' in p:
            MT = os.path.join(os.path.dirname(p), 'bin', 'mt.exe')
    MT = os.path.join(SDK, 'bin', 'mt.exe')
    os.environ['QMAKESPEC'] = 'win32-msvc'
    ICU = os.environ.get('ICU_DIR', r'Q:\icu')

QMAKE = '/Volumes/sw/qt/bin/qmake' if isosx else 'qmake'
if find_executable('qmake-qt4'):
    QMAKE = find_executable('qmake-qt4')
elif find_executable('qmake'):
    QMAKE = find_executable('qmake')
QMAKE = os.environ.get('QMAKE', QMAKE)

PKGCONFIG = find_executable('pkg-config')
PKGCONFIG = os.environ.get('PKG_CONFIG', PKGCONFIG)

def run_pkgconfig(name, envvar, default, flag, prefix):
    ans = []
    if envvar:
        ans = os.environ.get(envvar, default)
        ans = [x.strip() for x in ans.split(os.pathsep)]
        ans = [x for x in ans if x and (prefix=='-l' or os.path.exists(x))]
    if not ans:
        try:
            raw = subprocess.Popen([PKGCONFIG, flag, name],
                stdout=subprocess.PIPE).stdout.read()
            ans = [x.strip() for x in raw.split(prefix)]
            ans = [x for x in ans if x and (prefix=='-l' or os.path.exists(x))]
        except:
            print 'Failed to run pkg-config:', PKGCONFIG, 'for:', name

    return ans

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

pyqt = pyqtconfig.Configuration()

qt_inc = pyqt.qt_inc_dir
qt_lib = pyqt.qt_lib_dir
ft_lib_dirs = []
ft_libs = []
ft_inc_dirs = []
jpg_libs = []
jpg_lib_dirs = []
podofo_inc = '/usr/include/podofo'
podofo_lib = '/usr/lib'
chmlib_inc_dirs = chmlib_lib_dirs = []
sqlite_inc_dirs = []
icu_inc_dirs = []
icu_lib_dirs = []
zlib_inc_dirs = []
zlib_lib_dirs = []
zlib_libs = ['z']

if iswindows:
    prefix  = r'C:\cygwin\home\kovid\sw'
    sw_inc_dir  = os.path.join(prefix, 'include')
    sw_lib_dir  = os.path.join(prefix, 'lib')
    icu_inc_dirs = [os.path.join(ICU, 'source', 'common'), os.path.join(ICU,
        'source', 'i18n')]
    icu_lib_dirs = [os.path.join(ICU, 'source', 'lib')]
    sqlite_inc_dirs = [sw_inc_dir]
    chmlib_inc_dirs = consolidate('CHMLIB_INC_DIR', os.path.join(prefix,
        'build', 'chmlib-0.40', 'src'))
    chmlib_lib_dirs = consolidate('CHMLIB_LIB_DIR', os.path.join(prefix,
        'build', 'chmlib-0.40', 'src', 'Release'))
    png_inc_dirs = [sw_inc_dir]
    png_lib_dirs = [sw_lib_dir]
    png_libs = ['png12']
    jpg_lib_dirs = [sw_lib_dir]
    jpg_libs = ['jpeg']
    ft_lib_dirs = [sw_lib_dir]
    ft_libs = ['freetype']
    ft_inc_dirs = [sw_inc_dir]
    zlib_inc_dirs = [sw_inc_dir]
    zlib_lib_dirs = [sw_lib_dir]
    zlib_libs = ['zlib']

    md = glob.glob(os.path.join(prefix, 'build', 'ImageMagick-*'))[-1]
    magick_inc_dirs = [md]
    magick_lib_dirs = [os.path.join(magick_inc_dirs[0], 'VisualMagick', 'lib')]
    magick_libs = ['CORE_RL_wand_', 'CORE_RL_magick_']
    podofo_inc = os.path.join(sw_inc_dir, 'podofo')
    podofo_lib = sw_lib_dir
elif isosx:
    podofo_inc = '/sw/podofo'
    podofo_lib = '/sw/lib'
    magick_inc_dirs = consolidate('MAGICK_INC',
        '/sw/include/ImageMagick')
    magick_lib_dirs = consolidate('MAGICK_LIB',
        '/sw/lib')
    magick_libs = ['MagickWand', 'MagickCore']
    png_inc_dirs = consolidate('PNG_INC_DIR', '/sw/include')
    png_lib_dirs = consolidate('PNG_LIB_DIR', '/sw/lib')
    png_libs = ['png12']
    ft_libs = ['freetype']
    ft_inc_dirs = ['/sw/include/freetype2']
else:
    # Include directories
    png_inc_dirs = pkgconfig_include_dirs('libpng', 'PNG_INC_DIR',
        '/usr/include')
    magick_inc_dirs = pkgconfig_include_dirs('MagickWand', 'MAGICK_INC', '/usr/include/ImageMagick')

    # Library directories
    png_lib_dirs = pkgconfig_lib_dirs('libpng', 'PNG_LIB_DIR', '/usr/lib')
    magick_lib_dirs = pkgconfig_lib_dirs('MagickWand', 'MAGICK_LIB', '/usr/lib')

    # Libraries
    magick_libs = pkgconfig_libs('MagickWand', '', '')
    if not magick_libs:
        magick_libs = ['MagickWand', 'MagickCore']
    png_libs = ['png']
    ft_inc_dirs = pkgconfig_include_dirs('freetype2', 'FT_INC_DIR',
            '/usr/include/freetype2')
    ft_lib_dirs = pkgconfig_lib_dirs('freetype2', 'FT_LIB_DIR', '/usr/lib')
    ft_libs = pkgconfig_libs('freetype2', '', '')


magick_error = None
if not magick_inc_dirs or not os.path.exists(os.path.join(magick_inc_dirs[0],
    'wand')):
    magick_error = ('ImageMagick not found on your system. '
            'Try setting the environment variables MAGICK_INC '
            'and MAGICK_LIB to help calibre locate the include and library '
            'files.')

podofo_lib = os.environ.get('PODOFO_LIB_DIR', podofo_lib)
podofo_inc = os.environ.get('PODOFO_INC_DIR', podofo_inc)
podofo_error = None if os.path.exists(os.path.join(podofo_inc, 'podofo.h')) else \
        ('PoDoFo not found on your system. Various PDF related',
    ' functionality will not work. Use the PODOFO_INC_DIR and',
    ' PODOFO_LIB_DIR environment variables.')

def get_ip_address(ifname):
    import fcntl
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

try:
    if islinux:
        HOST=get_ip_address('eth0')
    else:
        HOST='192.168.1.2'
except:
    try:
        HOST=get_ip_address('wlan0')
    except:
        try:
            HOST=get_ip_address('ppp0')
        except:
            HOST='192.168.1.2'

PROJECT=os.path.basename(os.path.abspath('.'))


