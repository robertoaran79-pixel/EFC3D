; EFC3D (Easy Flexy and Cuts 3D): instalador do Windows (Inno Setup 6).
;   iscc /DVersao=1.50 /DOrigem=dist\EFC3D empacotar\efc3d.iss
#ifndef Versao
  #define Versao "0.0"
#endif
#ifndef Origem
  #define Origem "dist\EFC3D"
#endif

[Setup]
AppId={{6C1E3D9A-4B2F-4E8B-9C3D-EFC3D0000150}
AppName=EFC3D
AppVerName=EFC3D {#Versao} (Easy Flexy and Cuts 3D)
AppVersion={#Versao}
AppPublisher=RLA LABS
AppPublisherURL=https://github.com/robertoaran79-pixel/EFC3D
DefaultDirName={localappdata}\Programs\EFC3D
DefaultGroupName=EFC3D
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=..\saida
OutputBaseFilename=EFC3D-{#Versao}-windows-instalador
SetupIconFile=..\app\windows\AppIcon.ico
UninstallDisplayIcon={app}\EFC3D.exe
UninstallDisplayName=EFC3D (Easy Flexy and Cuts 3D)
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\{#Origem}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\EFC3D"; Filename: "{app}\EFC3D.exe"; Comment: "Easy Flexy and Cuts 3D"
Name: "{autodesktop}\EFC3D"; Filename: "{app}\EFC3D.exe"; Comment: "Easy Flexy and Cuts 3D"; Tasks: desktopicon

[Run]
Filename: "{app}\EFC3D.exe"; Description: "{cm:LaunchProgram,EFC3D}"; Flags: nowait postinstall skipifsilent
