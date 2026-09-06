; Inno Setup script for the Emcomm BBS Windows installer.
; Built by the release workflow:  iscc /DAppVersion=1.7.0 packaging\emcomm_bbs.iss
; Installs per-user (no admin prompt) into %LOCALAPPDATA%\Programs\Emcomm BBS.
; Settings and check-in data live in %LOCALAPPDATA%\Emcomm BBS and survive
; upgrades and uninstalls.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{3E7D2C1A-5B64-4F0E-9A21-EMCOMMBBS001}
AppName=Emcomm BBS
AppVersion={#AppVersion}
AppVerName=Emcomm BBS {#AppVersion}
AppPublisher=KK4ODA
AppPublisherURL=https://github.com/KK4ODA/emcomm-bbs
AppSupportURL=https://github.com/KK4ODA/emcomm-bbs/issues
AppUpdatesURL=https://github.com/KK4ODA/emcomm-bbs/releases
DefaultDirName={autopf}\Emcomm BBS
DefaultGroupName=Emcomm BBS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Emcomm-BBS-Setup-{#AppVersion}
SetupIconFile=emcomm_bbs.ico
UninstallDisplayIcon={app}\Emcomm BBS.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Emcomm BBS
LicenseFile=..\LICENSE
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start Emcomm BBS automatically when I log in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\Emcomm BBS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Emcomm BBS"; Filename: "{app}\Emcomm BBS.exe"; WorkingDir: "{app}"
Name: "{group}\Emcomm BBS User Guide"; Filename: "{app}\_internal\docs\Emcomm_BBS_User_Guide.txt"
Name: "{group}\Uninstall Emcomm BBS"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Emcomm BBS"; Filename: "{app}\Emcomm BBS.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\Emcomm BBS"; Filename: "{app}\Emcomm BBS.exe"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\Emcomm BBS.exe"; Description: "Start Emcomm BBS now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; %LOCALAPPDATA%\Emcomm BBS (config, check-in template, data\) is deliberately kept.
