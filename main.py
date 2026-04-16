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
    style_dir = os.path.join(os.path.dirname(__file__), 'src', 'styles')
    style_files = [
        'base.qss',
        'window_buttons.qss',
        'auth.qss',
        'main.qss',
        'dialogs.qss',
        'account_settings.qss',
        'start_session.qss',
        'pitchers.qss',
        'users.qss',
    ]
    combined = ""
    for f in style_files:
        with open(os.path.join(style_dir, f), 'r', encoding='utf-8') as fp:
            combined += fp.read() + "\n"
    app.setStyleSheet(combined)

    # Initialize database
    init_db()

    # Show login window centered
    window = AuthWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
