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
AppCopyright=Copyright (c) 2026 Abdulrahman Aloqayli
DefaultDirName={autopf}\ZK Pull
DefaultGroupName=ZK Pull
DisableProgramGroupPage=yes
; Installs for the current user without admin rights; IT can still choose "all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Choose the mode afresh each time instead of reusing a previous install's: a silent update from an
; HR account must not pick "all users" because IT once installed it that way.
UsePreviousPrivileges=no
OutputDir=..\dist
OutputBaseFilename=ZK-Pull-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\ZK Pull.exe
; The updater closes the app itself; this covers the app being open when someone runs setup by hand.
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

; A new version may ship different Qt files, and leftovers from the old one can make Qt load
; mismatched plugins, so the old _internal folder must go. It is moved aside before the files are
; copied, with the exe that matches it (the exe holds the app's Python code), and deleted only once
; they all are ([Code]): [InstallDelete] would delete it for good, and an update aborted part-way (a
; locked file, a full disk) would leave an app that cannot start.

[Files]
Source: "..\dist\ZK Pull\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; Only there if deleting it after an update failed.
Type: filesandordirs; Name: "{app}\_internal.old"
Type: files; Name: "{app}\ZK Pull.exe.old"

[Icons]
Name: "{group}\ZK Pull"; Filename: "{app}\ZK Pull.exe"
Name: "{autodesktop}\ZK Pull"; Filename: "{app}\ZK Pull.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ZK Pull.exe"; Description: "{cm:LaunchProgram,ZK Pull}"; Flags: nowait postinstall skipifsilent
; The in-app updater runs this installer with /SILENT /ZKUPDATE=1; start the new version when it is
; done. Not after other silent installs: IT deploying for all users must not start it elevated.
Filename: "{app}\ZK Pull.exe"; Flags: nowait; Check: IsInAppUpdate

; The database and log in %LOCALAPPDATA%\ZK Pull are left in place on uninstall: they hold the
; pulled attendance and the names HR typed in.

[Code]
var
  OldMovedAside: Boolean;
  ExeMovedAside: Boolean;
  FilesCopied: Boolean;

function OldInternal: String;
begin
  Result := ExpandConstant('{app}\_internal.old');
end;

function OldExe: String;
begin
  Result := ExpandConstant('{app}\ZK Pull.exe.old');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    DelTree(OldInternal, True, True, True);  // left by an earlier run that could not finish
    DeleteFile(OldExe);
    if DirExists(ExpandConstant('{app}\_internal')) then
      OldMovedAside := RenameFile(ExpandConstant('{app}\_internal'), OldInternal);
    if OldMovedAside and FileExists(ExpandConstant('{app}\ZK Pull.exe')) then
      ExeMovedAside := RenameFile(ExpandConstant('{app}\ZK Pull.exe'), OldExe);
  end
  else if CurStep = ssPostInstall then
  begin
    FilesCopied := True;
    DelTree(OldInternal, True, True, True);
    DeleteFile(OldExe);
  end;
end;

procedure DeinitializeSetup;
begin
  // Aborted after the old files were moved: Setup has rolled back the new ones, so put them back.
  if OldMovedAside and not FilesCopied then
  begin
    DelTree(ExpandConstant('{app}\_internal'), True, True, True);
    RenameFile(OldInternal, ExpandConstant('{app}\_internal'));
    if ExeMovedAside then
    begin
      DeleteFile(ExpandConstant('{app}\ZK Pull.exe'));
      RenameFile(OldExe, ExpandConstant('{app}\ZK Pull.exe'));
    end;
  end;
end;

function IsInAppUpdate: Boolean;
begin
  // Updaters before 0.4.0 do not pass /ZKUPDATE; their silent per-user runs are updates too.
  Result := WizardSilent and ((ExpandConstant('{param:ZKUPDATE|0}') = '1') or not IsAdminInstallMode);
end;
