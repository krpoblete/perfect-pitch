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
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root (optional — safe to omit, all values have defaults)
load_dotenv(ROOT_DIR / ".env")

# Asset paths
ASSETS_DIR = str(ROOT_DIR / "assets")
ICONS_DIR = str(ROOT_DIR / "assets" / "icons")
STYLES_DIR = str(ROOT_DIR / "src" / "styles")

# Model paths
MODELS_DIR = str(ROOT_DIR / "models")
POSE_MODEL_PATH = str(ROOT_DIR / "pose_landmarker_heavy.task")

# Database
DB_NAME = os.getenv("DB_NAME", "perfect_pitch.db")
DB_PATH = str(ROOT_DIR / DB_NAME)

# App info
APP_NAME = os.getenv("APP_NAME", "Perfect Pitch")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
