; Inno Setup script for the Funis installer.
; Compiled by packaging\build_windows.ps1 with /DAppVersion=<version> /DSourceDir=<repository root>.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir ".."
#endif

[Setup]
AppId={{47E80E71-742F-4625-B357-081B29D8B4EB}
AppName=Funis
AppVersion={#AppVersion}
AppVerName=Funis {#AppVersion}
AppPublisher=Funis
DefaultDirName={autopf}\Funis
DefaultGroupName=Funis
DisableProgramGroupPage=yes
OutputDir={#SourceDir}\dist
OutputBaseFilename=Funis-{#AppVersion}-Windows-Setup
SetupIconFile={#SourceDir}\funis\assets\icon.ico
UninstallDisplayIcon={app}\Funis.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\dist\Funis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Funis"; Filename: "{app}\Funis.exe"
Name: "{group}\Uninstall Funis"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Funis"; Filename: "{app}\Funis.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.funis"; ValueType: string; ValueName: ""; ValueData: "Funis.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Funis.Project"; ValueType: string; ValueName: ""; ValueData: "Funis project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Funis.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Funis.exe,0"
Root: HKA; Subkey: "Software\Classes\Funis.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Funis.exe"" ""%1"""

[Run]
Filename: "{app}\Funis.exe"; Description: "{cm:LaunchProgram,Funis}"; Flags: nowait postinstall skipifsilent
