# perfect_pitch.spec
# ─────────────────────────────────────────────────────────────────────────────
# PyInstaller spec file for Perfect Pitch
#
# Build command (run from project root with venv activated):
#   pyinstaller perfect_pitch.spec
#
# Output:
#   dist/PerfectPitch/PerfectPitch.exe   ← the executable
#   dist/PerfectPitch/                   ← ship this entire folder
#
# Bundled INSIDE the .exe:
#   assets/          (icons, sounds, skeleton PNGs)
#   src/styles/      (QSS stylesheets)
#
# Required files alongside the .exe (NOT bundled — kept external):
#   models/                      (download from Google Drive — developers only)
#   pose_landmarker_heavy.task   (download from Google Drive — developers only)
#
# The .env file is NOT required — all values have hardcoded fallbacks in config.py.
# Session artifacts (JSON logs, skeleton PNGs) are written to AppData\Roaming\PerfectPitch\
# at runtime by pitch_worker.py — not alongside the .exe.
# version_info.txt embeds Windows version metadata so Task Manager shows
# "Perfect Pitch" instead of "PerfectPitch.exe".
# ─────────────────────────────────────────────────────────────────────────────

from PyInstaller.utils.hooks import collect_all, collect_data_files
import os, sys
import PyQt6 as _pyqt6

# ── Collect packages that PyInstaller misses by default ──────────────────────
mediapipe_datas,    mediapipe_binaries,    mediapipe_hiddenimports    = collect_all("mediapipe")
torch_datas,        torch_binaries,        torch_hiddenimports        = collect_all("torch")
cv2_datas,          cv2_binaries,          cv2_hiddenimports          = collect_all("cv2")
sounddevice_datas,  sounddevice_binaries,  sounddevice_hiddenimports  = collect_all("sounddevice")
soundfile_datas,    soundfile_binaries,    soundfile_hiddenimports    = collect_all("soundfile")
sklearn_datas,      sklearn_binaries,      sklearn_hiddenimports      = collect_all("sklearn")
matplotlib_datas,   matplotlib_binaries,   matplotlib_hiddenimports   = collect_all("matplotlib")

# ── Qt plugin DLLs — targeted fix for QDateEdit calendar popup icon ──────────
# PyInstaller misses these because the calendar icon is rendered via Qt's SVG
# icon engine, which is loaded lazily at runtime and never seen by static
# analysis. Without qsvgicon.dll the calendar button appears blank.
_qt_plugins = os.path.join(os.path.dirname(_pyqt6.__file__), "Qt6", "plugins")
qt_plugin_binaries = [
    (os.path.join(_qt_plugins, "iconengines", "qsvgicon.dll"),
     "PyQt6/Qt6/plugins/iconengines"),
    (os.path.join(_qt_plugins, "imageformats", "qsvg.dll"),
     "PyQt6/Qt6/plugins/imageformats"),
    (os.path.join(_qt_plugins, "imageformats", "qico.dll"),
     "PyQt6/Qt6/plugins/imageformats"),
    (os.path.join(_qt_plugins, "styles", "qmodernwindowsstyle.dll"),
     "PyQt6/Qt6/plugins/styles"),
]

# ── Data files to bundle INSIDE the .exe ─────────────────────────────────────
# assets/ and src/styles/ are embedded so the zip needs no loose folders.
# models/ and pose_landmarker_heavy.task are intentionally kept OUTSIDE —
# they are loaded at runtime via file paths and cannot be embedded.
datas = (
    mediapipe_datas +
    torch_datas +
    cv2_datas +
    sounddevice_datas +
    soundfile_datas +
    matplotlib_datas +
    sklearn_datas +
    [
        ("assets",      "assets"),       # icons, sounds, skeleton PNGs
        ("src/styles",  "src/styles"),   # QSS stylesheets
    ]
)

binaries = (
    mediapipe_binaries +
    torch_binaries +
    cv2_binaries +
    sounddevice_binaries +
    soundfile_binaries +
    matplotlib_binaries +
    sklearn_binaries +
    qt_plugin_binaries
)

hiddenimports = (
    mediapipe_hiddenimports +
    torch_hiddenimports +
    cv2_hiddenimports +
    sounddevice_hiddenimports +
    soundfile_hiddenimports +
    matplotlib_hiddenimports +
    sklearn_hiddenimports +
    [
        "win32com",
        "win32com.client",
        "win32com.shell",
        "win32com.shell.shell",
        "pywintypes",
        "pkg_resources.py2_warn",
        "pygrabber",
        "pygrabber.dshow_graph",
        "sounddevice",
        "soundfile",
        "bcrypt",
        "dotenv",
        "pyqttoast",
        "qframelesswindow",
        "src.config",
        "src.db",
        "src.analyze",
        "src.live_capture",
        "src.pitch_worker",
        "src.pitch_summary",
        "src.utils.animations",
        "src.utils.icons",
        "src.utils.pitch_rules",
        "src.utils.toast",
        "src.utils.validators",
        "src.widgets.confirm_dialog",
        "src.widgets.hand_selector",
        "src.widgets.password_input",
        "src.widgets.tour_overlay",
        "src.widgets.trend_chart",
        "src.widgets.window_buttons",
        "src.pages.auth.auth_base",
        "src.pages.auth.login_page",
        "src.pages.auth.signup_page",
        "src.pages.auth.forgot_password_page",
        "src.pages.dashboard_page",
        "src.pages.start_session_page",
        "src.pages.camera_manager",
        "src.pages.session_summary",
        "src.pages.pitchers_page",
        "src.pages.users_page",
        "src.pages.account_settings_page",
        "src.windows.auth_window",
        "src.windows.main_window",
    ]
)

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "xmlrpc",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,       # Keep binaries external (one-dir mode)
    name="PerfectPitch",
    version="version_info.txt",  # Embeds FileDescription = "Perfect Pitch" for Task Manager
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                    # Compress binaries if UPX is installed
    console=False,
    disable_windowed_traceback=False,
    icon="assets/app_icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PerfectPitch",
)
