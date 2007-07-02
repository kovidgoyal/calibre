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
''' Create a windows installer '''
import sys, re, os, shutil, subprocess
from setup import VERSION, APPNAME, entry_points, scripts, basenames
sys.argv[1:2] = ['py2exe']
if '--verbose' not in ' '.join(sys.argv):
    sys.argv.append('--quiet') #py2exe produces too much output by default
from distutils.core import setup
from distutils.filelist import FileList
import py2exe, glob
from py2exe.build_exe import py2exe as build_exe
from libprs500 import __version__ as VERSION
from libprs500 import __appname__ as APPNAME

class NSISInstaller(object):
    TEMPLATE = r'''
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

!define PRODUCT_NAME "%(name)s"
!define XPUI_BRANDINGTEXT "${PRODUCT_NAME} created by Kovid Goyal"
!define PRODUCT_VERSION "%(version)s"
!define WEBSITE "https://libprs500.kovidgoyal.net"
!define DEVCON  "C:\devcon\i386\devcon.exe"
!define PY2EXE_DIR "%(py2exe_dir)s"
!define LIBUSB_DIR "C:\libusb-prs500"
!define LIBUNRAR_DIR "C:\Program Files\UnrarDLL"
!define CLIT         "C:\clit\clit.exe"
!define UNRTF        "C:\unrtf\unrtf.exe"

;------------------------------------------------------------------------------------------------------
;General

  ;Name and file
  Name "${PRODUCT_NAME}"
  OutFile "%(outpath)s\${PRODUCT_NAME}-${PRODUCT_VERSION}.exe"

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
  !insertmacro MUI_PAGE_LICENSE "${PY2EXE_DIR}\LICENSE"
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
  File "${CLIT}"
  File "${UNRTF}"
    
  SetOutPath "$INSTDIR\driver"
  File "${LIBUSB_DIR}\*.dll"
  File "${LIBUSB_DIR}\*.sys"
  File "${LIBUSB_DIR}\*.cat"
  File "${LIBUSB_DIR}\*.inf"
  File "${DEVCON}"
  
  SetOutPath "$SYSDIR"
  File "${LIBUSB_DIR}\libusb0.dll"
  File "${LIBUNRAR_DIR}\unrar.dll"
  DetailPrint " "
  
  DetailPrint "Installing USB driver for prs500..."
  ExecWait '"$INSTDIR\driver\devcon.exe" install "$INSTDIR\driver\prs500.inf" "USB\VID_054C&PID_029B"' $0
  DetailPrint "devcon returned exit code $0"
  IfErrors 0 +2
          MessageBox MB_OK "Failed to install USB driver. devcon exit code: $0"
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
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\libprs500.lnk" "$INSTDIR\${PRODUCT_NAME}.exe"
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
    def __init__(self, name, py2exe_dir, output_dir):
        self.installer = self.__class__.TEMPLATE % dict(name=name, py2exe_dir=py2exe_dir,
                                                   version=VERSION, 
                                                   outpath=os.path.abspath(output_dir))
        
    def build(self):        
        f = open('installer.nsi', 'w')
        path = f.name
        f.write(self.installer)
        f.close()
        try:
            subprocess.check_call('"C:\Program Files\NSIS\makensis.exe" /V2 ' + path, shell=True)
        except:
            print path 
        else:
            os.remove(path)


class BuildEXE(build_exe):
    manifest_resource_id = 0    
    MANIFEST_TEMPLATE = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"> 
  <assemblyIdentity version="%(version)s"
     processorArchitecture="x86"
     name="net.kovidgoyal.%(prog)s"
     type="win32"
     /> 
  <description>Ebook management application</description> 
  <!-- Identify the application security requirements. -->
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v2">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel
          level="asInvoker"
          uiAccess="false"/>
        </requestedPrivileges>
       </security>
  </trustInfo>
</assembly>
'''
    def run(self):
        build_exe.run(self)
        qtsvgdll = None
        for other in self.other_depends:
            if 'qtsvg4.dll' in other.lower():
                qtsvgdll = other
                break
        shutil.copyfile('LICENSE', os.path.join(self.dist_dir, 'LICENSE'))
        print
        if qtsvgdll:
            print 'Adding', qtsvgdll
            shutil.copyfile(qtsvgdll, os.path.join(self.dist_dir, os.path.basename(qtsvgdll)))
            qtxmldll = os.path.join(os.path.dirname(qtsvgdll), 'QtXml4.dll')
            print 'Adding', qtxmldll
            shutil.copyfile(qtxmldll, 
                            os.path.join(self.dist_dir, os.path.basename(qtxmldll)))
        
        print
        print 'Building Installer'
        installer = NSISInstaller(APPNAME, self.dist_dir, 'dist')
        installer.build()
        
    @classmethod
    def manifest(cls, prog):
        cls.manifest_resource_id += 1
        return (24, cls.manifest_resource_id, 
                cls.MANIFEST_TEMPLATE % dict(prog=prog, version=VERSION+'.0'))

console = [dict(dest_base=basenames['console'][i], script=scripts['console'][i]) 
           for i in range(len(scripts['console']))]

PY2EXE_DIR = os.path.join('build','py2exe')
if os.path.exists(PY2EXE_DIR):
    shutil.rmtree(PY2EXE_DIR)
setup(
      cmdclass = {'py2exe': BuildEXE},
      windows = [{'script'          : scripts['gui'][0], 
                  'dest_base'       : APPNAME,
                  'icon_resources'  : [(1, 'icons/library.ico')],
                  'other_resources' : [BuildEXE.manifest(APPNAME)],
                  },],
      console = console,
      options = { 'py2exe' : {'compressed': 1,
                              'optimize'  : 2,
                              'dist_dir'  : PY2EXE_DIR,
                              'includes'  : ['sip', 'pkg_resources', 'PyQt4.QtSvg'],                                
                              'packages'  : ['PIL'],
                              'excludes'  : ["Tkconstants", "Tkinter", "tcl", 
                                             "_imagingtk", "ImageTk", "FixTk", 
                                             'pydoc'],
                             },
                },
      
      )