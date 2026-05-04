import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Root directory resolution
# ---------------------------------------------------------------------------
# When running from source:  ROOT_DIR = project root (two levels above config.py)
# When running as a PyInstaller .exe: ROOT_DIR = folder containing the .exe
#   - sys.frozen is set by PyInstaller
#   - sys.executable is the path to the .exe itself
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Folder containing the .exe — for external runtime files (models, DB, .task)
    EXE_DIR = Path(sys.executable).resolve().parent
    # PyInstaller's temp extraction folder — for files embedded inside the .exe
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    EXE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the .exe folder (optional — safe to omit, all values have defaults)
load_dotenv(EXE_DIR / ".env")

# Asset paths (embedded inside the .exe → use BUNDLE_DIR)
ASSETS_DIR = str(BUNDLE_DIR / "assets")
ICONS_DIR = str(BUNDLE_DIR / "assets" / "icons")
STYLES_DIR = str(BUNDLE_DIR / "src" / "styles")

# Model paths (external alongside the .exe → use EXE_DIR)
MODELS_DIR = str(EXE_DIR / "models")
POSE_MODEL_PATH = str(EXE_DIR / "pose_landmarker_heavy.task")

# Database (external alongside the .exe → use EXE_DIR)
DB_NAME = os.getenv("DB_NAME", "perfect_pitch.db")
DB_PATH = str(EXE_DIR / DB_NAME)

# App info
APP_NAME = os.getenv("APP_NAME", "Perfect Pitch")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
