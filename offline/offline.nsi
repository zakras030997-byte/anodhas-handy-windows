Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
Name "ANODHAS Handy — Offline"
OutFile "ANODHAS-Handy-0.9.8-Windows-x64-Offline-Setup.exe"
InstallDir "$LOCALAPPDATA\ANODHAS Handy"
RequestExecutionLevel user
SetCompressor zlib
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "Russian"
Function .onInit
  InitPluginsDir
FunctionEnd
Section
  SetShellVarContext current
  SetOutPath "$PLUGINSDIR"
  File /oname=app-setup.exe "payload\app-setup.exe"
  File /oname=WebView2.exe "payload\WebView2.exe"
  File "configure.ps1"
  ReadRegStr $1 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${If} $1 == ""
    ReadRegStr $1 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
  ${If} $1 == ""
    ReadRegStr $1 HKCU "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
  ${If} $1 == ""
  ${OrIf} $1 == "0.0.0.0"
    DetailPrint "Установка Microsoft WebView2…"
    ExecWait '"$PLUGINSDIR\WebView2.exe" /silent /install' $0
    ${If} $0 != 0
    ${AndIf} $0 != 3010
      MessageBox MB_ICONSTOP "Не удалось установить WebView2 (код $0)." /SD IDOK
      SetErrorLevel 10
      Abort
    ${EndIf}
  ${EndIf}
  DetailPrint "Установка ANODHAS Handy…"
  ExecWait '"$PLUGINSDIR\app-setup.exe" /S /D=$INSTDIR' $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "Не удалось установить приложение (код $0)." /SD IDOK
    SetErrorLevel 20
    Abort
  ${EndIf}
  SetOutPath "$APPDATA\ai.anodhas.handy\models"
  File "payload\parakeet-tdt-0.6b-v3-Q4_K_M.gguf"
  SetOutPath "$INSTDIR"
  File "MODEL-NOTICE.txt"
  DetailPrint "Проверка и выбор модели распознавания…"
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\configure.ps1"'
  Pop $0
  Pop $1
  FileOpen $2 "$TEMP\ANODHAS-configure.log" w
  FileWrite $2 $1
  FileClose $2
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "Настройка модели не завершена (код $0)." /SD IDOK
    SetErrorLevel 30
    Abort
  ${EndIf}
SectionEnd
