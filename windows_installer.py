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
from distutils.core import setup
from distutils.filelist import FileList
import py2exe, glob
from py2exe.build_exe import py2exe as build_exe
from libprs500 import __version__ as VERSION
from libprs500 import __appname__ as APPNAME

PY2EXE_DIR = os.path.join('build','py2exe')
if os.path.exists(PY2EXE_DIR):
    shutil.rmtree(PY2EXE_DIR)


class NSISInstaller(object):
    TEMPLATE = r'''
; Do a Cyclic Redundancy Check to make sure the installer
; was not corrupted by the download.  
CRCCheck on

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
!define LIBUSB_DIR "C:\libusb"
!define LIBUNRAR_DIR "C:\Program Files\UnrarDLL"
!define CLIT         "C:\clit\clit.exe"
!define PDFTOHTML    "C:\pdftohtml\pdftohtml.exe"
!define IMAGEMAGICK  "C:\ImageMagick"

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
  
  ; Finish page with option to run program
  ; Disabled as GUI requires PATH and working directory to be set correctly
  ;!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_NAME}.exe"
  ;!define MUI_FINISHPAGE_NOAUTOCLOSE
  ;!insertmacro MUI_PAGE_FINISH
  
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


Section "Main" "secmain"

  SetOutPath "$INSTDIR"
  
  ;ADD YOUR OWN FILES HERE...
  File /r "${PY2EXE_DIR}\*"
  File "${CLIT}"
  File "${PDFTOHTML}"
  
  SetOutPath "$INSTDIR\ImageMagick"
  File /r "${IMAGEMAGICK}\*"
  
    
  SetOutPath "$SYSDIR"
  File "${LIBUNRAR_DIR}\unrar.dll"
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
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\lrfviewer.lnk" "$INSTDIR\lrfviewer.exe"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    CreateShortCut  "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\libprs500.exe"

  !insertmacro MUI_STARTMENU_WRITE_END
  
  ;Add the installation directory to PATH for the commandline tools
  Push "$INSTDIR"
  Call AddToPath
  
SectionEnd

Section /o "Device Drivers (only needed for PRS500)" "secdd"
  SetOutPath "$INSTDIR\driver"
  File "${LIBUSB_DIR}\*.dll"
  File "${LIBUSB_DIR}\*.sys"
  File "${LIBUSB_DIR}\*.cat"
  File "${LIBUSB_DIR}\*.inf"
  File "${LIBUSB_DIR}\testlibusb-win.exe"
  File "${DEVCON}"

  SetOutPath "$SYSDIR"
  File "${LIBUSB_DIR}\libusb0.dll"
  File "${LIBUSB_DIR}\libusb0.sys"
  ;File "${LIBUSB_DIR}\libusb0_x64.dll"
  ;File "${LIBUSB_DIR}\libusb0_x64.sys"
    
  ; Uninstall USB drivers
  DetailPrint "Uninstalling any existing device drivers"
  ExecWait '"$INSTDIR\driver\devcon.exe" remove "USB\VID_054C&PID_029B"' $0
  DetailPrint "devcon returned exit code $0"
  
  
  DetailPrint "Installing USB driver for prs500..."
  ExecWait '"$INSTDIR\driver\devcon.exe" install "$INSTDIR\driver\prs500.inf" "USB\VID_054C&PID_029B"' $0
  DetailPrint "devcon returned exit code $0"
  IfErrors 0 +3
          MessageBox MB_OK|MB_ICONINFORMATION|MB_TOPMOST "Failed to install USB driver. devcon exit code: $0"
          Goto +2
  MessageBox MB_OK '1. If you have the SONY Connect Reader software installed: $\nGoto Add Remove Programs and uninstall the entry "Windows Driver Package - Sony Corporation (PRSUSB)". $\n$\n2. If your reader is connected to the computer, disconnect and reconnect it now.'
  DetailPrint " "
  
  
  
  
SectionEnd

;------------------------------------------------------------------------------------------------------
;Descriptions

  ;Language strings
  LangString DESC_secmain ${LANG_ENGLISH} "The GUI and command-line tools for working with ebooks."
  LangString DESC_secdd   ${LANG_ENGLISH} "The device drivers to talk to the Sony PRS500. You only need this if you plan to transfer books to the Sony PRS500 with ${PRODUCT_NAME}. It is not required for the PRS 505."

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${secmain} $(DESC_secmain)
    !insertmacro MUI_DESCRIPTION_TEXT ${secdd} $(DESC_secdd)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END
;------------------------------------------------------------------------------------------------------
;Uninstaller Section

Section "un.DeviceDrivers"
  ; Uninstall USB drivers
  ExecWait '"$INSTDIR\driver\devcon.exe" remove "USB\VID_054C&PID_029B"' $0
  DetailPrint "devcon returned exit code $0"
SectionEnd

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

class WixInstaller(object):
    '''
    Make a .msi installer. Can't get the driver installation to play well with
    an existing installation of the connect USB driver. Pick this up again when
    libusb1.dll is released based on winusb.
    '''
    TEMPLATE=\
r'''<?xml version='1.0' encoding='windows-1252'?>
<Wix xmlns='http://schemas.microsoft.com/wix/2003/01/wi'>

  <Product Name='%(appname)s' Id='955DF7A2-8861-46A9-8710-56A4BDEA8E29'
    Language='1033' Codepage='1252' Version='%(version)s' Manufacturer='Kovid Goyal'>

    <Package Id='????????-????-????-????-????????????' Keywords='Installer'
      Description="Ebook management software"
      Manufacturer='Kovid Goyal'
      InstallerVersion='100' Languages='1033' Compressed='yes' SummaryCodepage='1252' />
    <Icon Id="appicon.ico" SourceFile="icons\library.ico" />
    <Binary Id="devcon" SourceFile="C:\devcon\i386\devcon.exe" />
    <Condition Message="You need to be an administrator to install this product.">
      Privileged
    </Condition>
    <Property Id='ARPNOMODIFY'>1</Property>
    <Property Id='ARPURLINFOABOUT'>http://libprs500.kovidgoyal.net</Property>
    <Property Id='ARPPRODUCTICON'>appicon.ico</Property>
    <Media Id='1' Cabinet='%(appname)s.cab' EmbedCab='yes' />
    <Directory Id='TARGETDIR' Name='SourceDir'>
      <Directory Id='ProgramFilesFolder' Name='PFiles'>
        <Directory Id='INSTALLDIR' Name='libprs' LongName='%(appname)s'>
          %(py2exefiles)s
            <Directory Id='driver' Name='driver' FileSource="C:\libusb-prs500">
              <Component Id="usbdriver" DriverSequence="0" Guid="1169D502-DE59-4153-BC0D-712894C37FEF">
                <File Id='libusb0.dll' Name='libusb0.dll' Vital='yes' Compressed='yes' DiskId="1" />
                <File Id='libusb0.sys' Name='libusb0.sys' Vital='yes' Compressed='yes' DiskId="1" />
                <File Id='libusb0_x64.dll' Name='a' LongName='libusb0_x64.dll' Vital='yes' Compressed='yes' DiskId="1" />
                <File Id='libusb0_x64.sys' Name='b' LongName='libusb0_x64.sys' Vital='yes' Compressed='yes' DiskId="1" />
                <File Id='prs500.inf' Name='prs500.inf' Vital='yes' Compressed='yes' DiskId="1" />
              </Component>
            </Directory>
        </Directory>
      </Directory>
      <Component Id='misc' Guid=''>
        <Environment Id='UpdatePath' Name='PATH' Action='create' System='yes' 
                 Part='last' Value='[INSTALLDIR]' Permanent="no"/>
      </Component>
    </Directory>
    
    <Feature Id='Complete' Title="%(appname)s" Description="The complete package">
      <ComponentRef Id='py2exe' />
      <ComponentRef Id='usbdriver' />
      <ComponentRef Id='misc' />
    </Feature>
  </Product>
   
</Wix>
    '''
    CANDLE=r'C:\wix\candle.exe '
    LIGHT=r'C:\wix\light.exe -out %s -loc C:\wix\WixUI_en-us.wxl %s c:\wix\wixui.wixlib "C:\Program Files\Driver Installation Tools 2.01\DIFxApp\English-US\WiXLib\x86\DIFxApp.wixlib"'
    
    def __init__(self, py2exe_dir, dest_dir='dist'):
        self.py2exe_dir = py2exe_dir
        self.dest_dir = dest_dir
        filelist = []
        print self.py2exe_dir
        for root, dirs, files in os.walk(self.py2exe_dir):
            for name in files:
                path = os.path.abspath(os.path.join(root, name))
                filelist.append(path)
        component = "<Component Id='py2exe' DiskId='1' Guid='0248CACF-FDF5-4E68-B898-227C16F1C7B8'>\n"
        counter = 0
        for path in filelist:
            entry = '<File Id="file%d" Name="fn%d" Compressed="yes" Vital="yes" Source="%s" LongName="%s" />'%\
                    (counter, counter, path, os.path.basename(path))
            component += entry + "\n"
            counter += 1
        component += '</Component>'
        self.installer = self.TEMPLATE%dict(appname=APPNAME, version=VERSION, 
                                            py2exefiles=component)
        
    def build(self):
        f = open('installer.wxs', 'w')
        f.write(self.installer)
        f.close()
        subprocess.check_call(self.CANDLE + ' ' + f.name, shell=True)
        subprocess.check_call(self.LIGHT%(os.path.join(self.dest_dir, APPNAME + '-' + VERSION + '.msi'),
                                          ' installer.wixobj'), shell=True)
        
        os.remove('installer.wxs')
        os.remove('installer.wixobj')    
        

class BuildEXE(build_exe):
    manifest_resource_id = 0
    QT_PREFIX = r'C:\\Qt\\4.3.3' 
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
        print 'Adding plugins...',
        qt_prefix = self.QT_PREFIX
        if qtsvgdll:
            qt_prefix = os.path.dirname(os.path.dirname(qtsvgdll))
        plugdir = os.path.join(qt_prefix, 'plugins')
        for d in ('imageformats', 'codecs', 'iconengines'):
            print d,
            imfd = os.path.join(plugdir, d)
            tg = os.path.join(self.dist_dir, d)        
            if os.path.exists(tg):
                shutil.rmtree(tg)
            shutil.copytree(imfd, tg)
        
        print
        print
        print 'Building Installer'
        installer = NSISInstaller(APPNAME, self.dist_dir, 'dist')
        installer.build()
        
    @classmethod
    def manifest(cls, prog):
        cls.manifest_resource_id += 1
        return (24, cls.manifest_resource_id, 
                cls.MANIFEST_TEMPLATE % dict(prog=prog, version=VERSION+'.0'))


    
def main():
    auto = '--auto' in sys.argv
    if auto:
        sys.argv.remove('--auto')
    sys.argv[1:2] = ['py2exe']
    if '--verbose' not in sys.argv:
        sys.argv.append('--quiet') #py2exe produces too much output by default
    if auto and not os.path.exists('dist\\auto'):
        print os.path.abspath('dist\\auto'), 'does not exist'
        return 1
    console = [dict(dest_base=basenames['console'][i], script=scripts['console'][i]) 
               for i in range(len(scripts['console']))]
    
    setup(
          cmdclass = {'py2exe': BuildEXE},
          windows = [
                     {'script'          : scripts['gui'][0], 
                      'dest_base'       : APPNAME,
                      'icon_resources'  : [(1, 'icons/library.ico')],
                      'other_resources' : [BuildEXE.manifest(APPNAME)],
                      },
                      {'script'         : scripts['gui'][1], 
                      'dest_base'       : 'lrfviewer',
                      'icon_resources'  : [(1, 'icons/viewer.ico')],
                      'other_resources' : [BuildEXE.manifest('lrfviewer')],
                      },
                      ],
          console = console,
          options = { 'py2exe' : {'compressed': 1,
                                  'optimize'  : 2,
                                  'dist_dir'  : PY2EXE_DIR,
                                  'includes'  : ['sip', 'pkg_resources', 'PyQt4.QtSvg', 
                                                 'mechanize', 'ClientForm', 'wmi', 
                                                 'win32file', 'pythoncom', 'rtf2xml', 
                                                 'lxml', 'lxml._elementpath'],                                
                                  'packages'  : ['PIL'],
                                  'excludes'  : ["Tkconstants", "Tkinter", "tcl", 
                                                 "_imagingtk", "ImageTk", "FixTk", 
                                                 'pydoc'],
                                  'dll_excludes' : ['mswsock.dll'],
                                 },
                    },
          
          )
    if auto:
        subprocess.call(('shutdown', '-s', '-f', '-t', '01')) 
    return 0

if __name__ == '__main__':
    sys.exit(main())
