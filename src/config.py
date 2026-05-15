import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    # Folder containing the .exe
    EXE_DIR = Path(sys.executable).resolve().parent
    # PyInstaller's temp extraction folder
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    EXE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the .exe folder
load_dotenv(EXE_DIR / ".env")

# Asset paths
ASSETS_DIR = str(BUNDLE_DIR / "assets")
ICONS_DIR = str(BUNDLE_DIR / "assets" / "icons")
STYLES_DIR = str(BUNDLE_DIR / "src" / "styles")

# Model paths
MODELS_DIR = str(EXE_DIR / "models")
POSE_MODEL_PATH = str(EXE_DIR / "pose_landmarker_heavy.task")

# Database
DB_NAME = os.getenv("DB_NAME", "perfect_pitch.db")
DB_PATH = str(EXE_DIR / DB_NAME)

# App info
APP_NAME = os.getenv("APP_NAME", "Perfect Pitch")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
