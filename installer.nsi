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
!define PRODUCT_VERSION "0.3.15"
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


