; Instalador de Windows (Inno Setup 6) del Sistema Inteligente de Alquiler de Equipos.
; Lo construye GitHub Actions:  iscc /DVersion=0.1.0 instalador\AlquilerEquipos.iss
; Resultado: dist\AlquilerEquipos-Windows-Instalador.exe  (un solo archivo para descargar)

#ifndef Version
  #define Version "0.1.0"
#endif

[Setup]
AppId={{6B0F1C2E-3D7A-4E59-9B1E-AE21C0A7E5D4}
AppName=Alquiler de Equipos
AppVersion={#Version}
AppPublisher=moreno-stack
AppPublisherURL=https://github.com/moreno-stack/AlquilerEquipos
DefaultDirName={localappdata}\Programs\AlquilerEquipos
DefaultGroupName=Alquiler de Equipos
; Sin permisos de administrador: se instala para el usuario actual y la carpeta queda
; escribible (ahí va alquiler.env con la clave de Groq).
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AlquilerEquipos-Windows-Instalador
SetupIconFile=..\build\iconos\AlquilerEquipos.ico
UninstallDisplayIcon={app}\AlquilerEquipos.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\AlquilerEquipos\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Alquiler de Equipos"; Filename: "{app}\AlquilerEquipos.exe"
Name: "{userdesktop}\Alquiler de Equipos"; Filename: "{app}\AlquilerEquipos.exe"; Tasks: escritorio

[Run]
Filename: "{app}\AlquilerEquipos.exe"; Description: "Abrir Alquiler de Equipos"; Flags: nowait postinstall skipifsilent
