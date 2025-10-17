from __future__ import annotations
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QWidget

class NotifyPopup(QFrame):
    """
    Popup flotante (frameless) con fade-in/out.
    tipo: "info" | "success" | "warning" | "error"
    """
    def __init__(self, text: str, tipo: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._bg = {
            "info":    "#2563EB",
            "success": "#059669",
            "warning": "#F59E0B",
            "error":   "#EF4444",
        }.get(tipo, "#2563EB")

        wrap = QFrame(self)
        wrap.setObjectName("NotifyWrap")
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.addWidget(QLabel(text))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(wrap)

        self.setStyleSheet(f"""
        #NotifyWrap {{
            background: {self._bg};
            color: white;
            border-radius: 10px;
            font-weight: 600;
        }}
        """)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def show_centered(self, msec: int = 2200, pos: str = "bottom"):
        """
        pos: "bottom" (default), "middle", "top"
        """
        if self.parent() is None:
            # sin padre, no calculamos centro relativo
            self.show()
            self._timer.start(msec)
            return

        pw = self.parent().width()
        ph = self.parent().height()
        self.adjustSize()
        w = self.width()
        h = self.height()

        x = (pw - w) // 2
        if pos == "middle":
            y = (ph - h) // 2
        elif pos == "top":
            y = 28
        else:  # "bottom"
            y = ph - h - 28

        self.setGeometry(x, y, w, h)
        self.setWindowOpacity(0.0)
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(msec)

    def _fade_out(self):
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.close)
        self._anim.start()
