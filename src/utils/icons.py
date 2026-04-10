import os
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt
from PyQt6.QtSvg import QSvgRenderer
from src.config import ICONS_DIR

def get_icon(name: str, color: str = "#888888", size: int = 18) -> QIcon:
    """Load a Tabler SVG icon, recolor it, and return as QIcon."""
    path = os.path.join(str(ICONS_DIR), f"{name}.svg")

    # Read SVG and replace currentColor with the desired color
    with open(path, "r", encoding="utf-8") as f:
        svg_data = f.read()

    svg_data = svg_data.replace("currentColor", color)
    svg_bytes = svg_data.encode("utf-8")

    # Render SVG to QPixmap
    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)
