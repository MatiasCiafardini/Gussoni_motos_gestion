# app/ui/widgets/config_card.py
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal, QSize, QEvent, QPoint, Property
from PySide6.QtGui import QIcon, QEnterEvent, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QWidget, QHBoxLayout, QSizePolicy
)

class ConfigCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: Optional[QWidget] = None,
        icon: Optional[QIcon] = None,
        icon_size: QSize = QSize(28, 28),
    ):
        super().__init__(parent)
        self.setObjectName("ConfigCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._hover = False
        self._icon = icon
        self._icon_size = icon_size

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # Encabezado con icono opcional
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        if icon:
            self._icon_lbl = QLabel()
            self._icon_lbl.setFixedSize(icon_size)
            self._icon_lbl.setPixmap(icon.pixmap(icon_size))
            self._icon_lbl.setObjectName("CardIcon")
            

            header.addWidget(self._icon_lbl, 0, Qt.AlignTop)
        else:
            self._icon_lbl = None

        text_box = QWidget(self)
        tb = QVBoxLayout(text_box); tb.setContentsMargins(0, 0, 0, 0); tb.setSpacing(2)
        self._title = QLabel(title); self._title.setObjectName("CardTitle")
        self._subtitle = QLabel(subtitle); self._subtitle.setObjectName("CardSubtitle")
        self._subtitle.setWordWrap(True)
        tb.addWidget(self._title)
        tb.addWidget(self._subtitle)
        header.addWidget(text_box, 1)

        root.addLayout(header)
        root.addStretch(1)

        # Estilos (QSS local, no rompe tu theme global)
        self.setStyleSheet("""
        QFrame#ConfigCard {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 14px;
        }
        QFrame#ConfigCard:hover {
            /* el "elevate" real lo hacemos con paintEvent */
            border-color: #D1D5DB;
        }
        QLabel#CardTitle {
            color: #0F172A; font-weight: 700; font-size: 1.2em;
        }
        QLabel#CardSubtitle {
            color: #6B7280; font-size: 1em;
        }
        """)

        # Sombra/elevación por pintura custom
        self.installEventFilter(self)

    # -------- UX --------
    def eventFilter(self, obj, ev):
        if obj is self:
            if ev.type() == QEvent.Enter:
                self._hover = True
                self.update()
            elif ev.type() == QEvent.Leave:
                self._hover = False
                self.update()
        return super().eventFilter(obj, ev)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(e)

    def paintEvent(self, ev: QPaintEvent) -> None:
        super().paintEvent(ev)
        # “elevate” sutil con sombra pintada
        if self._hover:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setOpacity(0.08)
            r = self.rect().adjusted(3, 6, -3, -2)
            p.fillRect(r, Qt.black)
            p.end()
