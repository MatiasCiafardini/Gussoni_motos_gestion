from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QHBoxLayout,
    QWidget,
    QApplication,
    QGraphicsDropShadowEffect,
)


class NotifyPopup(QFrame):
    """
    Popup flotante (frameless) con fade-in/out.
    tipo: "info" | "success" | "warning" | "error"

    Diseño:
    - Colores suaves (no saturados)
    - Card flotante con sombra
    - Íconos discretos
    - No invade el layout
    """

    STYLES = {
        "info": {
            "bg": "#3B82F6",   # blue-500 suave
            "icon": "ℹ️",
        },
        "success": {
            "bg": "#22C55E",   # green-500 suave
            "icon": "",        # sin icono para success
        },
        "warning": {
            "bg": "#FBBF24",   # amber-400
            "icon": "⚠️",
        },
        "error": {
            "bg": "#F87171",   # red-400
            "icon": "⛔",
        },
    }

    def __init__(self, text: str, tipo: str = "info", parent: QWidget | None = None):
        super().__init__(parent)

        self.setFont(QApplication.font())

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        style = self.STYLES.get(tipo, self.STYLES["info"])

        # ---------------- Card ----------------
        card = QFrame(self)
        card.setObjectName("NotifyCard")

        # sombra suave
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)

        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 10, 16, 10)
        lay.setSpacing(10)

        # icono (solo si existe)
        if style["icon"]:
            icon_lbl = QLabel(style["icon"], card)
            icon_lbl.setObjectName("NotifyIcon")
            icon_lbl.setAlignment(Qt.AlignTop)
            lay.addWidget(icon_lbl)

        # texto
        text_lbl = QLabel(text, card)
        text_lbl.setObjectName("NotifyText")
        text_lbl.setWordWrap(True)
        lay.addWidget(text_lbl, 1)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(card)

        # ---------------- estilos ----------------
        self.setStyleSheet(f"""
        #NotifyCard {{
            background: {style["bg"]};
            color: white;
            border-radius: 12px;
        }}
        #NotifyIcon {{
            font-size: 1.15em;
        }}
        #NotifyText {{
            font-size: 0.9em;
            font-weight: 500;
        }}
        """)

        # ---------------- animaciones ----------------
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    # -------------------------------------------------

    def show_centered(self, msec: int = 2400, pos: str = "bottom"):
        """
        pos: "top" | "middle" | "bottom"
        """
        container = self.parent().window() if self.parent() else self

        self.adjustSize()
        w = self.width()
        h = self.height()

        pw = container.width()
        ph = container.height()

        x = (pw - w) // 2

        if pos == "top":
            y = 32
        elif pos == "middle":
            y = (ph - h) // 2
        else:  # bottom
            y = ph - h - 32

        global_pos = container.mapToGlobal(container.rect().topLeft())

        self.setGeometry(
            global_pos.x() + x,
            global_pos.y() + y,
            w,
            h,
        )

        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()

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
