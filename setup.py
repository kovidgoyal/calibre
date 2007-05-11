##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#!/usr/bin/env python
import sys, re
sys.path.append('src')
from libprs500 import __version__ as VERSION

import ez_setup
ez_setup.use_setuptools()
from setuptools import setup, find_packages


################################# py2exe #######################################
py2exe_options = {}
if sys.argv[1] == 'py2exe':
    py2exe_dir = 'C:\libprs500'    
    try:
        import py2exe
        console = [
                    {'script' : 'src/libprs500/cli/main.py', 'dest_base':'prs500'},
                    {'script' : 'src/libprs500/lrf/html/convert_from.py', 'dest_base':'html2lrf'},
                    {'script' : 'src/libprs500/lrf/txt/convert_from.py', 'dest_base':'txt2lrf'},
                    {'script' : 'src/libprs500/lrf/meta.py', 'dest_base':'lrf-meta'},
                    {'script' : 'src/libprs500/metadata/rtf.py', 'dest_base':'rtf-meta'},
                  ]
        windows = [{'script' : 'src/libprs500/gui/main.py', 'dest_base':'prs500-gui',
                    'icon_resources':[(1,'icons/library.ico')]}]
        excludes = ["Tkconstants", "Tkinter", "tcl", "_imagingtk", 
                    "ImageTk", "FixTk"]
        options = { 'py2exe' : {'includes' : ['sip', 'pkg_resources'], 
                                'dist_dir' : py2exe_dir,
                                'packages' : ['PIL'],
                                'excludes' : excludes}}
        py2exe_options = {'console'  : console, 'windows' : windows, 
                          'options'  : options}
    except ImportError:
        print >>sys.stderr, 'Must be in Windows to run py2exe'
        sys.exit(1)
    installer = \
r'''
SetCompressor     lzma
ShowInstDetails   show
ShowUnInstDetails show

;------------------------------------------------------------------------------------------------------
;Include Modern UI
  !include "AddToPath.nsh"
  !include "XPUI.nsh"
  !define XPUI_SKIN "Windows XP"
  
;------------------------------------------------------------------------------------------------------
;Variables
Var STARTMENU_FOLDER
Var MUI_TEMP

!define PRODUCT_NAME "libprs500"
!define XPUI_BRANDINGTEXT "${PRODUCT_NAME} created by Kovid Goyal"
!define PRODUCT_VERSION "'''+VERSION+r'''"
!define WEBSITE "https://libprs500.kovidgoyal.net"
!define PY2EXE_DIR "C:\libprs500"
!define LIBUSB_DIR "C:\libusb-prs500"
!define LIBUNRAR_DIR "C:\Program Files\UnrarDLL"
!define QT_DIR     "C:\Qt\4.2.3\bin"

;------------------------------------------------------------------------------------------------------
;General

  ;Name and file
  Name "${PRODUCT_NAME}"
  OutFile "dist\${PRODUCT_NAME}-${PRODUCT_VERSION}.exe"

  ;Default installation folder
  InstallDir "$PROGRAMFILES\${PRODUCT_NAME}"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\${PRODUCT_NAME}" ""
  
  ;Vista redirects $SMPROGRAMS to all users without this
  RequestExecutionLevel admin
  
;------------------------------------------------------------------------------------------------------
;Interface Settings

  !define MUI_HEADERIMAGE
  !define MUI_HEADERIMAGE_BITMAP "icons\library.ico"
  !define MUI_ABORTWARNING

;------------------------------------------------------------------------------------------------------
;Pages

  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_LICENSE "LICENSE"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY
  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU" 
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\${PRODUCT_NAME}"
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
  
  !insertmacro MUI_PAGE_STARTMENU Application $STARTMENU_FOLDER
  !insertmacro MUI_PAGE_INSTFILES
  
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  !insertmacro MUI_UNPAGE_FINISH
;------------------------------------------------------------------------------------------------------
;Languages
 
  !insertmacro MUI_LANGUAGE "English"
;------------------------------------------------------------------------------------------------------
;Installer Sections

Function .onInit
    ; Prevent multiple instances of the installer from running
    System::Call 'kernel32::CreateMutexA(i 0, i 0, t "${PRODUCT_NAME}-setup") i .r1 ?e'
        Pop $R0
 
    StrCmp $R0 0 +3
        MessageBox MB_OK|MB_ICONEXCLAMATION "The installer is already running."
        Abort

FunctionEnd


Section "libprs500" Seclibprs500

  SetOutPath "$INSTDIR"
  
  ;ADD YOUR OWN FILES HERE...
  File /r "${PY2EXE_DIR}\*"
  ; The next line can be commented out once py2exe starts including QtSvg.dll
  File "${QT_DIR}\QtSvg4.dll"
  
  SetOutPath "$INSTDIR\driver"
  File "${LIBUSB_DIR}\*.dll"
  File "${LIBUSB_DIR}\*.sys"
  File "${LIBUSB_DIR}\*.cat"
  File "${LIBUSB_DIR}\*.inf"
  
  SetOutPath "$SYSDIR"
  File "${LIBUSB_DIR}\libusb0.dll"
  File "${LIBUNRAR_DIR}\unrar.dll"
  DetailPrint " "
  
  DetailPrint "Installing USB driver (this may take a few seconds) ..."
  ExecWait '"rundll32" libusb0.dll,usb_install_driver_np_rundll "$INSTDIR\driver\prs500.inf"' $0
  DetailPrint "rundll32 returned exit code $0"
  IfErrors 0 +2
           MessageBox MB_OK 'You may need to run the following at the console in order for the SONY Reader to be detected:\r\n"rundll32" libusb0.dll,usb_install_driver_np_rundll "$INSTDIR\driver\prs500.inf"'
  DetailPrint " "
  
  
  ;Store installation folder
  WriteRegStr HKCU "Software\${PRODUCT_NAME}" "" $INSTDIR
  
  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "DisplayName" "${PRODUCT_NAME} -- E-book management software"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "UninstallString" "$INSTDIR\Uninstall.exe"

  SetOutPath "$INSTDIR"
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    
    ;Create shortcuts
    WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${WEBSITE}"
    CreateDirectory "$SMPROGRAMS\$STARTMENU_FOLDER"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\libprs500.lnk" "$INSTDIR\prs500-gui.exe"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    CreateShortCut  "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\prs500-gui.exe"

  !insertmacro MUI_STARTMENU_WRITE_END
  
  ;Add the installation directory to PATH for the commandline tools
  Push "$INSTDIR"
  Call AddToPath
  
SectionEnd
;------------------------------------------------------------------------------------------------------
;Descriptions

  ;Language strings
  LangString DESC_Seclibprs500 ${LANG_ENGLISH} "The GUI and command-line tools for working with ebooks"

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${Seclibprs500} $(DESC_Seclibprs500)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END
;------------------------------------------------------------------------------------------------------
;Uninstaller Section

Section "Uninstall"
  ;ADD YOUR OWN FILES HERE...
  RMDir /r "$INSTDIR"
  !insertmacro MUI_STARTMENU_GETFOLDER Application $MUI_TEMP
  RMDir /r "$SMPROGRAMS\$MUI_TEMP"
  ;Delete empty start menu parent diretories
  StrCpy $MUI_TEMP "$SMPROGRAMS\$MUI_TEMP"

  startMenuDeleteLoop:
    ClearErrors
    RMDir $MUI_TEMP
    GetFullPathName $MUI_TEMP "$MUI_TEMP\.."

    IfErrors startMenuDeleteLoopDone

    StrCmp $MUI_TEMP $SMPROGRAMS startMenuDeleteLoopDone startMenuDeleteLoop
  startMenuDeleteLoopDone:
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"

  DeleteRegKey /ifempty HKCU "Software\${PRODUCT_NAME}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
  ; Remove installation directory from PATH
  Push "$INSTDIR"
  Call un.RemoveFromPath

SectionEnd
'''
    f = open('installer.nsi', 'w').write(installer)
    
################################################################################
    

if sys.hexversion < 0x2050000:
    print >> sys.stderr, "You must use python >= 2.5 Try invoking this script as python2.5 setup.py."
    print >> sys.stderr, "If you are using easy_install, try easy_install-2.5"
    sys.exit(1)
    
try:
  from PIL import Image
except ImportError:
  import Image
  print >>sys.stderr, "You do not have the Python Imaging Library correctly installed."
  sys.exit(1)

setup(
      name='libprs500', 
      packages = find_packages('src'), 
      package_dir = { '' : 'src' }, 
      version=VERSION, 
      author='Kovid Goyal', 
      author_email='kovid@kovidgoyal.net', 
      url = 'http://libprs500.kovidgoyal.net', 
      package_data = { \
                        'libprs500.gui' : ['*.ui'], \
                        'libprs500.lrf' : ['*.jar', '*.jpg'], \
                        'libprs500.metadata' : ['*.pl'] \
                     }, 
      entry_points = {
        'console_scripts': [ \
                             'prs500 = libprs500.cli.main:main', \
                             'lrf-meta = libprs500.lrf.meta:main', \
                             'rtf-meta = libprs500.metadata.rtf:main', \
                             'txt2lrf = libprs500.lrf.txt.convert_from:main', \
                             'html2lrf = libprs500.lrf.html.convert_from:main',\
                           ], 
        'gui_scripts'    : [ 'prs500-gui = libprs500.gui.main:main']
      }, 
      zip_safe = True,
      install_requires = ['sqlalchemy >= 0.3.7'],
      description = 
                  """
                  Library to interface with the Sony Portable Reader 500 
                  over USB. Also has a GUI with library management features.
                  """, 
      long_description = 
      """
      libprs500 is a ebook management application. It maintains an ebook library
      and allows for easy transfer of books from the library to an ebook reader.
      At the moment, it supports the `SONY Portable Reader`_.
      
      It can also convert various popular ebook formats into LRF, the native
      ebook format of the SONY Reader.
      
      For screenshots: https://libprs500.kovidgoyal.net/wiki/Screenshots
      
      For installation/usage instructions please see 
      https://libprs500.kovidgoyal.net/wiki/WikiStart#Installation
      
      For SVN access: svn co https://svn.kovidgoyal.net/code/libprs500
      
        .. _SONY Portable Reader: http://Sony.com/reader
        .. _USB: http://www.usb.org  
      """, 
      license = 'GPL', 
      classifiers = [
        'Development Status :: 3 - Alpha', 
        'Environment :: Console', 
        'Environment :: X11 Applications :: Qt', 
        'Intended Audience :: Developers', 
        'Intended Audience :: End Users/Desktop', 
        'License :: OSI Approved :: GNU General Public License (GPL)', 
        'Natural Language :: English', 
        'Operating System :: POSIX :: Linux', 
        'Programming Language :: Python', 
        'Topic :: Software Development :: Libraries :: Python Modules', 
        'Topic :: System :: Hardware :: Hardware Drivers'
        ],
        **py2exe_options   
     )

try:
  import PyQt4
except ImportError:
  print "You do not have PyQt4 installed. The GUI will not work.", \
        "You can obtain PyQt4 from http://www.riverbankcomputing.co.uk/pyqt/download.php"
else:
  import PyQt4.QtCore
  if PyQt4.QtCore.PYQT_VERSION < 0x40101:
    print "WARNING: The GUI needs PyQt >= 4.1.1"

import os
if os.access('/etc/udev/rules.d', os.W_OK):
  from subprocess import check_call
  print 'Trying to setup udev rules...',
  sys.stdout.flush()
  udev = open('/etc/udev/rules.d/95-libprs500.rules', 'w')
  udev.write('''# Sony Reader PRS-500\n'''
             '''BUS=="usb", SYSFS{idProduct}=="029b", SYSFS{idVendor}=="054c", MODE="660", GROUP="plugdev"\n'''
             )
  udev.close()
  check_call('udevstart', shell=True)
  print 'success'
