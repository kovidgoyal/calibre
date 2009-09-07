#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from distutils.spawn import find_executable

from PyQt4 import pyqtconfig

from setup import isosx, iswindows

OSX_SDK = '/Developer/SDKs/MacOSX10.5.sdk'
if not os.path.exists(OSX_SDK):
    OSX_SDK = '/Developer/SDKs/MacOSX10.4u.sdk'
leopard_build = '10.5' in OSX_SDK

os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.5' if leopard_build else '10.4'

NMAKE = RC = msvc = MT = win_inc = win_lib = None
if iswindows:
    from distutils import msvc9compiler
    msvc = msvc9compiler.MSVCCompiler()
    msvc.initialize()
    NMAKE = msvc.find_exe('nmake.exe')
    RC = msvc.find_exe('rc.exe')
    SDK = os.environ.get('WINSDK', r'C:\Program Files\Microsoft SDKs\Windows\v6.0A')
    win_inc = os.environ['include'].split(';')
    win_lib = os.environ['lib'].split(';')
    for p in win_inc:
        if 'SDK' in p:
            MT = os.path.join(os.path.dirname(p), 'bin', 'mt.exe')
    MT = os.path.join(SDK, 'bin', 'mt.exe')

QMAKE = '/Volumes/sw/qt/bin/qmake' if isosx else 'qmake'
if find_executable('qmake-qt4'):
    QMAKE = find_executable('qmake-qt4')
elif find_executable('qmake'):
    QMAKE = find_executable('qmake')
QMAKE = os.environ.get('QMAKE', QMAKE)


pyqt = pyqtconfig.Configuration()

qt_inc = pyqt.qt_inc_dir
qt_lib = pyqt.qt_lib_dir

fc_inc = '/usr/include/fontconfig'
fc_lib = '/usr/lib'
poppler_inc = '/usr/include/poppler/qt4'
poppler_lib = '/usr/lib'
poppler_libs = []
podofo_inc = '/usr/include/podofo'
podofo_lib = '/usr/lib'

if iswindows:
    fc_inc = r'C:\cygwin\home\kovid\fontconfig\include\fontconfig'
    fc_lib = r'C:\cygwin\home\kovid\fontconfig\lib'
    poppler_inc = r'C:\cygwin\home\kovid\poppler\include\poppler\qt4'
    poppler_lib = r'C:\cygwin\home\kovid\poppler\lib'
    poppler_libs = ['QtCore4', 'QtGui4']
    podofo_inc = 'C:\\podofo\\include\\podofo'
    podofo_lib = r'C:\podofo'

if isosx:
    fc_inc = '/Users/kovid/fontconfig/include/fontconfig'
    fc_lib = '/Users/kovid/fontconfig/lib'
    poppler_inc = '/Volumes/sw/build/poppler-0.10.7/qt4/src'
    poppler_lib = '/Users/kovid/poppler/lib'
    podofo_inc = '/usr/local/include/podofo'
    podofo_lib = '/usr/local/lib'


fc_inc = os.environ.get('FC_INC_DIR', fc_inc)
fc_lib = os.environ.get('FC_LIB_DIR', fc_lib)
fc_error = None if os.path.exists(os.path.join(fc_inc, 'fontconfig.h')) else \
    ('fontconfig header files not found on your system. '
            'Try setting the FC_INC_DIR and FC_LIB_DIR environment '
            'variables.')


poppler_inc = os.environ.get('POPPLER_INC_DIR', poppler_inc)
poppler_lib = os.environ.get('POPPLER_LIB_DIR', poppler_lib)
poppler_error = None if os.path.exists(os.path.join(poppler_inc,
    'poppler-qt4.h'))  else \
    ('Poppler not found on your system. Various PDF related',
    ' functionality will not work. Use the POPPLER_INC_DIR and',
    ' POPPLER_LIB_DIR environment variables.')


podofo_lib = os.environ.get('PODOFO_LIB_DIR', podofo_lib)
podofo_inc = os.environ.get('PODOFO_INC_DIR', podofo_inc)
podofo_error = None if os.path.exists(os.path.join(podofo_inc, 'podofo.h')) else \
        ('PoDoFo not found on your system. Various PDF related',
    ' functionality will not work. Use the PODOFO_INC_DIR and',
    ' PODOFO_LIB_DIR environment variables.')


