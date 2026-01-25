[Setup]
AppName=Gussoni App
AppVersion=1.0.3
DefaultDirName={pf}\GussoniApp
DefaultGroupName=Gussoni App
OutputBaseFilename=GussoniApp_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
DisableDirPage=yes


[Files]
Source: "dist\GussoniApp.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\updater.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Gussoni App"; Filename: "{app}\GussoniApp.exe"
Name: "{commondesktop}\Gussoni App"; Filename: "{app}\GussoniApp.exe"

[Run]
Filename: "{app}\GussoniApp.exe"; Description: "Iniciar Gussoni App"; Flags: nowait postinstall skipifsilent
