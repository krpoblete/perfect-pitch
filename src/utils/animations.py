from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

def fade_in(widget, duration: int = 600, on_finish=None):
    """Fade a widget from 0 to 1 opacity."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    effect.setOpacity(0)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    if on_finish:
        anim.finished.connect(on_finish)

    # Keep reference so GC doesn't kill it
    widget._fade_anim = anim
    anim.start()

def fade_out(widget, duration: int = 150, on_finish=None):
    """Fade a widget from 1 to 0 opacity, then call on_finish."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    effect.setOpacity(1)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    if on_finish:
        anim.finished.connect(on_finish)

    widget._fade_anim = anim
    anim.start()
