; ==========================================================
; Inno Setup Script - Oficina Eficiencia
; Genera el instalador a partir de la carpeta que compila Nuitka (build\nuitka\main_ui.dist)
; ==========================================================

#define MyAppName "Oficina Eficiencia"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Tu Empresa"
#define MyAppExeName "OficinaEficiencia_VMS.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-AB12-CD34EF567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\OficinaEficiencia
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=setup_oficina_eficiencia_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
SetupIconFile=
WizardStyle=modern

; Don't require admin for per-user install
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
; Carpeta completa compilada por Nuitka (ejecutable, DLL y models/)
Source: "build\nuitka\main_ui.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Avisos de licencia de terceros (los genera compilar_exe.bat)
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent
