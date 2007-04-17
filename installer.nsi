;------------------------------------------------------------------------------------------------------
;Include Modern UI

  !include "MUI.nsh"

;------------------------------------------------------------------------------------------------------
;General

  ;Name and file
  Name "libprs500"
  OutFile "Basic.exe"

  ;Default installation folder
  InstallDir "$PROGRAMFILES\libprs500"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\libprs500" ""
  
;------------------------------------------------------------------------------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;------------------------------------------------------------------------------------------------------