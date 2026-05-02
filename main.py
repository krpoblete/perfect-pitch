import sys
import os

# Windows: tell the taskbar this is its own app, not python.exe
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("perfectpitch.app")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from src.config import ASSETS_DIR
from src.db import init_db
from src.windows.auth_window import AuthWindow

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # App icon — applied globally to all windows
    app.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "app_icon.ico")))

    # Load stylesheets
    styles_dir = os.path.join(os.path.dirname(__file__), 'src', 'styles')
    styles_files = [
        'base.qss',
        'window_buttons.qss',
        'dialogs.qss',
        'auth.qss',
        'main.qss',
        'dashboard.qss',
        'users.qss',
        'pitchers.qss',
        'start_session.qss',
        'account_settings.qss',
    ]
    combined = ""
    for styles_file in styles_files:
        path =  os.path.join(styles_dir, styles_file)
        with open(path, 'r', encoding='utf-8') as f:
            combined += f.read() + "\n"
    app.setStyleSheet(combined)

    # Initialize database
    init_db()

    # Pre-load ML model once at startup so StartSession launches instantly.
    # load_model() returns (model, scaler, threshold, joint_thresholds).
    from src.analyze import load_model
    ml_bundle = load_model()
    print("ML model loaded.")

    # Show login window centered
    window = AuthWindow(ml_bundle=ml_bundle)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
