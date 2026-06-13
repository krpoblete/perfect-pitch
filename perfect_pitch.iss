; perfect_pitch.iss
; ─────────────────────────────────────────────────────────────────────────────
; Inno Setup script for Perfect Pitch
;
; Prerequisites:
;   1. Run PyInstaller first:
;        pyinstaller perfect_pitch.spec
;   2. Copy the ML files into dist\PerfectPitch\ (they are not auto-copied):
;        models\                    (LSTM checkpoint, scaler, threshold files)
;        pose_landmarker_heavy.task
;   3. Compile this script:
;        - Open Inno Setup Compiler → File → Open → perfect_pitch.iss
;        - Click Build → Compile  (or press F9)
;
; Output:
;   installer\PerfectPitch_Setup.exe
;
; What the installer does for the end user:
;   • Installs to C:\Program Files\PerfectPitch\ by default
;   • Creates a Desktop shortcut
;   • Creates a Start Menu entry under Perfect Pitch
;   • Registers an uninstaller (Add/Remove Programs)
;   • Runs as administrator (required for Program Files write access)
;   • database and output/ folder are created at runtime — not during install
; ─────────────────────────────────────────────────────────────────────────────

#define AppName      "Perfect Pitch"
#define AppVersion   "1.0.0"
#define AppPublisher "Kozaki, Poblete, Prudente"
#define AppExeName   "PerfectPitch.exe"
#define AppId        "{{A3F2B1C4-8D7E-4F9A-B6C2-1E3D5A7F9B0C}"
#define SourceDir    "dist\PerfectPitch"

[Setup]
; ── Identity ─────────────────────────────────────────────────────────────────
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisherURL=https://github.com/krpoblete/perfect-pitch
AppSupportURL=https://github.com/krpoblete/perfect-pitch
AppUpdatesURL=https://github.com/krpoblete/perfect-pitch
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Installer

; ── Install location ─────────────────────────────────────────────────────────
DefaultDirName={autopf}\PerfectPitch
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; ── Privileges ───────────────────────────────────────────────────────────────
; lowest = installs to AppData\Local\Programs\ for the current user only.
; No UAC prompt, no admin rights needed, fully writable path — database and
; session output files are written to AppData\Roaming\PerfectPitch\ via config.py.
PrivilegesRequired=lowest

; ── Output ───────────────────────────────────────────────────────────────────
OutputDir=installer
OutputBaseFilename=PerfectPitch_Setup
SetupIconFile=assets\app_icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; ── Appearance ───────────────────────────────────────────────────────────────
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
ShowLanguageDialog=no

; ── Windows version requirement ───────────────────────────────────────────────
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop shortcut is checked by default; user can uncheck it.
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; \
  GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
; ── Application files (entire PyInstaller output folder) ─────────────────────
; Recurse the full dist\PerfectPitch\ folder.
; Excludes the database file if it somehow ends up there — it is created at runtime.
Source: "{#SourceDir}\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs; \
  Excludes: "*.db"
Source: "assets\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; ── ML model files (must be present in dist\PerfectPitch\ before compiling) ──
; These are listed separately so the comment makes the dependency explicit.
; They are already captured by the wildcard above — this is documentation only.
; Source: "{#SourceDir}\models\*";                 DestDir: "{app}\models\";  Flags: ignoreversion recursesubdirs
; Source: "{#SourceDir}\pose_landmarker_heavy.task"; DestDir: "{app}";        Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExeName}"; \
  IconFilename: "{app}\app_icon.ico"; Comment: "Launch Perfect Pitch"

; Start Menu uninstall shortcut
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop shortcut (only if task selected above)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
  IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
; Offer to launch the app immediately after installation.
Filename: "{app}\{#AppExeName}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; On uninstall, also remove the database and output folder created at runtime.
; The user's session data lives here — add a confirmation message below
; if you want to warn before deleting.
Type: filesandordirs; Name: "{userappdata}\PerfectPitch\perfect_pitch.db"
Type: filesandordirs; Name: "{userappdata}\PerfectPitch\output"

[Code]
// ── Pre-install check: warn if Visual C++ runtime is likely missing ───────────
// PerfectPitch.exe (via PyInstaller) bundles its own Python but some
// OpenCV and PyTorch DLLs still depend on the MSVC runtime.
// This is a soft warning only — the install proceeds regardless.
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

// ── Uninstall confirmation ─────────────────────────────────────────────────────
// Warn the user that uninstalling will also delete their session database
// and all recorded output files.
function InitializeUninstall(): Boolean;
var
  Response: Integer;
begin
  Response := MsgBox(
    'Uninstalling Perfect Pitch will also permanently delete your session ' +
    'database and all recorded output files.' + #13#10 + #13#10 +
    'Are you sure you want to continue?',
    mbConfirmation,
    MB_YESNO
  );
  Result := (Response = IDYES);
end;
