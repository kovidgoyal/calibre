__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Create a windows installer '''
import sys, re, os, shutil, subprocess, zipfile
from setup import VERSION, APPNAME, entry_points, scripts, basenames
from distutils.core import setup
from distutils.filelist import FileList
import py2exe, glob
from py2exe.build_exe import py2exe as build_exe
from calibre import __version__ as VERSION
from calibre import __appname__ as APPNAME

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
  !include "MUI2.nsh"
  !include "WinMessages.nsh"
  
;------------------------------------------------------------------------------------------------------
;Variables
Var STARTMENU_FOLDER
Var MUI_TEMP

!define PRODUCT_NAME "%(name)s"
BrandingText "${PRODUCT_NAME} created by Kovid Goyal"
!define PRODUCT_VERSION "%(version)s"
!define WEBSITE "https://calibre.kovidgoyal.net"
!define DEVCON  "C:\devcon\i386\devcon.exe"
!define PY2EXE_DIR "%(py2exe_dir)s"
!define LIBUSB_DIR "C:\libusb"
!define LIBUNRAR_DIR "C:\Program Files\UnrarDLL"
!define CLIT         "C:\clit\clit.exe"
!define PDFTOHTML    "C:\pdftohtml\pdftohtml.exe"
!define IMAGEMAGICK  "C:\ImageMagick"
!DEFINE FONTCONFIG   "C:\fontconfig"


; ---------------PATH manipulation -----------------------------------------------------------------
; Registry key for changing the environment variables for all users on both XP and Vista
!define WriteEnvStr_RegKey 'HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"'

Function Trim ; Added by Pelaca
        Exch $R1
        Push $R2
Loop:
        StrCpy $R2 "$R1" 1 -1
        StrCmp "$R2" " " RTrim
        StrCmp "$R2" "$\n" RTrim
        StrCmp "$R2" "$\r" RTrim
        StrCmp "$R2" ";" RTrim
        GoTo Done
RTrim:  
        StrCpy $R1 "$R1" -1
        Goto Loop
Done:
        Pop $R2
        Exch $R1
FunctionEnd

; input, top of stack = string to search for
;        top of stack-1 = string to search in
; output, top of stack (replaces with the portion of the string remaining)
; modifies no other variables.
;
; Usage:
;   Push "this is a long ass string"
;   Push "ass"
;   Call StrStr
;   Pop $R0
;  ($R0 at this point is "ass string")
 
!macro StrStr un
Function ${un}StrStr
Exch $R1 ; st=haystack,old$R1, $R1=needle
  Exch    ; st=old$R1,haystack
  Exch $R2 ; st=old$R1,old$R2, $R2=haystack
  Push $R3
  Push $R4
  Push $R5
  StrLen $R3 $R1
  StrCpy $R4 0
  ; $R1=needle
  ; $R2=haystack
  ; $R3=len(needle)
  ; $R4=cnt
  ; $R5=tmp
  loop:
    StrCpy $R5 $R2 $R3 $R4
    StrCmp $R5 $R1 done
    StrCmp $R5 "" done
    IntOp $R4 $R4 + 1
    Goto loop
done:
  StrCpy $R1 $R2 "" $R4
  Pop $R5
  Pop $R4
  Pop $R3
  Pop $R2
  Exch $R1
FunctionEnd
!macroend
!insertmacro StrStr ""
!insertmacro StrStr "un."

Function AddToPath
  Exch $0
  Push $1
  Push $2
  Push $3
  ; don't add if the path doesn't exist
  IfFileExists "$0\*.*" "" AddToPath_done
  
  ReadEnvStr $1 PATH
  Push "$1;"
  Push "$0;"
  Call StrStr
  Pop $2
  StrCmp $2 "" "" AddToPath_done
  Push "$1;"
  Push "$0\;"
  Call StrStr
  Pop $2
  StrCmp $2 "" "" AddToPath_done
  GetFullPathName /SHORT $3 $0
  Push "$1;"
  Push "$3;"
  Call StrStr
  Pop $2
  StrCmp $2 "" "" AddToPath_done
  Push "$1;"
  Push "$3\;"
  Call StrStr
  Pop $2
  StrCmp $2 "" "" AddToPath_done
  
  ReadRegStr $1 ${WriteEnvStr_RegKey} "PATH"
    StrCmp $1 "" AddToPath_NTdoIt
      Push $1
      Call Trim
      Pop $1
      StrCpy $0 "$1;$0"
    AddToPath_NTdoIt:
      WriteRegExpandStr ${WriteEnvStr_RegKey} "PATH" $0
      SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
      
  AddToPath_done:
    Pop $3
    Pop $2
    Pop $1
    Pop $0
FunctionEnd

Function un.RemoveFromPath
  Exch $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6
 
  IntFmt $6 "%%c" 26 # DOS EOF
  
  ReadRegStr $1 ${WriteEnvStr_RegKey} "PATH"
    StrCpy $5 $1 1 -1 # copy last char
    StrCmp $5 ";" +2 # if last char != ;
      StrCpy $1 "$1;" # append ;
    Push $1
    Push "$0;"
    Call un.StrStr ; Find `$0;` in $1
    Pop $2 ; pos of our dir
    StrCmp $2 "" unRemoveFromPath_done
      ; else, it is in path
      # $0 - path to add
      # $1 - path var
      StrLen $3 "$0;"
      StrLen $4 $2
      StrCpy $5 $1 -$4 # $5 is now the part before the path to remove
      StrCpy $6 $2 "" $3 # $6 is now the part after the path to remove
      StrCpy $3 $5$6
 
      StrCpy $5 $3 1 -1 # copy last char
      StrCmp $5 ";" 0 +2 # if last char == ;
        StrCpy $3 $3 -1 # remove last char
 
      WriteRegExpandStr ${WriteEnvStr_RegKey} "PATH" $3
      SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
 
  unRemoveFromPath_done:
    Pop $6
    Pop $5
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Pop $0
FunctionEnd

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
  File /r "${FONTCONFIG}\*"
  
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
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\calibre.lnk" "$INSTDIR\${PRODUCT_NAME}.exe"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\lrfviewer.lnk" "$INSTDIR\lrfviewer.exe"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
    CreateShortCut  "$SMPROGRAMS\$STARTMENU_FOLDER\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    CreateShortCut  "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\calibre.exe"

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


class BuildEXE(build_exe):
    manifest_resource_id = 0
    QT_PREFIX = r'C:\\Qt\\4.4.0' 
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
    def build_plugins(self):
        cwd = os.getcwd()
        dd = os.path.join(cwd, self.dist_dir)
        try:
            os.chdir(os.path.join('src', 'calibre', 'gui2', 'pictureflow'))
            if os.path.exists('.build'):
                shutil.rmtree('.build')
            os.mkdir('.build')
            os.chdir('.build')
            subprocess.check_call(['qmake', '../pictureflow.pro'])
            subprocess.check_call(['mingw32-make', '-f', 'Makefile.Release'])
            shutil.copyfile('release\\pictureflow0.dll', os.path.join(dd, 'pictureflow0.dll'))
            os.chdir('..\\PyQt')
            if not os.path.exists('.build'):
                os.mkdir('.build')
            os.chdir('.build')
            subprocess.check_call(['python', '..\\configure.py'])
            subprocess.check_call(['mingw32-make', '-f', 'Makefile'])
            shutil.copyfile('pictureflow.pyd', os.path.join(dd, 'pictureflow.pyd'))
            os.chdir('..')
            shutil.rmtree('.build', True)
            os.chdir('..')
            shutil.rmtree('.build', True)
        finally:
            os.chdir(cwd)
    
    def run(self):
        if not os.path.exists(self.dist_dir):
            os.makedirs(self.dist_dir)
        print 'Building custom plugins...'
        self.build_plugins()
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
        print 'Adding GUI main.py'
        f = zipfile.ZipFile(os.path.join('build', 'py2exe', 'library.zip'), 'a', zipfile.ZIP_DEFLATED)
        f.write('src\\calibre\\gui2\\main.py', 'calibre\\gui2\\main.py')
        f.close()
        
        print 
        print 'Doing DLL redirection' # See http://msdn.microsoft.com/en-us/library/ms682600(VS.85).aspx
        for f in glob.glob(os.path.join('build', 'py2exe', '*.exe')):
            open(f + '.local', 'wb').write('\n')
        
        
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
    sys.argv[1:2] = ['py2exe']
    
    console = [dict(dest_base=basenames['console'][i], script=scripts['console'][i]) 
               for i in range(len(scripts['console']))]
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
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
                                  'includes'  : [
                                             'sip', 'pkg_resources', 'PyQt4.QtSvg', 
                                             'mechanize', 'ClientForm', 'wmi', 
                                             'win32file', 'pythoncom', 'rtf2xml', 
                                             'lxml', 'lxml._elementpath', 'genshi',
                                             'path', 'pydoc', 'IPython.Extensions.*',
                                             'calibre.web.feeds.recipes.*', 'PyQt4.QtWebKit',
                                             ],                                
                                  'packages'  : ['PIL'],
                                  'excludes'  : ["Tkconstants", "Tkinter", "tcl", 
                                                 "_imagingtk", "ImageTk", "FixTk"
                                                ],
                                  'dll_excludes' : ['mswsock.dll'],
                                 },
                    },
          
          )
    return 0

if __name__ == '__main__':
    sys.exit(main())
