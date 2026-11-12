; Inno Setup script: wraps the PyInstaller folder (dist\ZK Pull) in a Windows installer.
; Build: iscc /DAppVersion=0.1.0 packaging\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0E4F2A-6C1D-4E8B-9C57-2F4A9D3E1B70}
AppName=ZK Pull
AppVersion={#AppVersion}
AppPublisher=NSS
DefaultDirName={autopf}\ZK Pull
DefaultGroupName=ZK Pull
DisableProgramGroupPage=yes
; Installs for the current user without admin rights; IT can still choose "all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=ZK-Pull-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\ZK Pull.exe

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\ZK Pull\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ZK Pull"; Filename: "{app}\ZK Pull.exe"
Name: "{autodesktop}\ZK Pull"; Filename: "{app}\ZK Pull.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ZK Pull.exe"; Description: "{cm:LaunchProgram,ZK Pull}"; Flags: nowait postinstall skipifsilent

; The database and log in %LOCALAPPDATA%\ZK Pull are left in place on uninstall: they hold the
; pulled attendance and the names HR typed in.
