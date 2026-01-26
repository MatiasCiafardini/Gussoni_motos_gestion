#define MyAppName "Gussoni App"
#define MyAppExeName "GussoniApp.exe"
#define MyAppVersion "1.0.5"
#define MyAppPublisher "Gussoni"
#define MyAppDir "GussoniApp"

[Setup]
AppId={{6A0C8C4F-3D52-4A71-B8C4-9A1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\{#MyAppDir}
DefaultGroupName={#MyAppName}

OutputDir=installer
OutputBaseFilename=GussoniApp_Setup_{#MyAppVersion}

Compression=lzma
SolidCompression=yes

PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

DisableDirPage=yes
WizardStyle=modern

SetupIconFile=app\assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Accesos directos"

[Files]
; ===== APP PRINCIPAL =====
Source: "dist\GussoniApp.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; ===== UPDATER =====
Source: "dist\updater.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; ===== ASSETS =====
Source: "app\assets\*"; \
    DestDir: "{app}\assets"; \
    Flags: recursesubdirs createallsubdirs


[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\GussoniApp.exe"; \
    Description: "Iniciar Gussoni App"; \
    Flags: nowait postinstall skipifsilent runasoriginaluser

