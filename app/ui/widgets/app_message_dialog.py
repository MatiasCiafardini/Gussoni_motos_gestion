from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QMouseEvent, QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QWidget,
    QGraphicsDropShadowEffect,
)


class AppMessageDialog(QDialog):
    """
    Diálogo moderno unificado para mensajes:
    - kind: info | warning | error | confirm
    - Estilo tarjeta con sombra
    - Sin marco del SO
    - Draggable
    - Botones con estilos globales (BtnPrimary / BtnGhost)
    """

    ICONS = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "⛔",
        "confirm": "❓",
    }

    def __init__(
        self,
        title: str,
        text: str,
        *,
        kind: str = "info",
        primary_text: str = "Aceptar",
        secondary_text: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.setModal(True)
        self.setObjectName("NiceDialog")
        self.setMinimumWidth(420)

        # ---- ventana sin marco ----
        self.setWindowFlags(
            Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # ---- panel principal ----
        panel = QFrame(self)
        panel.setObjectName("DialogPanel")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 110))
        panel.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.addWidget(panel)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        # ---- header ----
        header = QHBoxLayout()
        header.setSpacing(10)

        icon_lbl = QLabel(self.ICONS.get(kind, "ℹ️"), panel)
        icon_lbl.setObjectName("DialogIcon")
        icon_lbl.setFixedWidth(28)
        icon_lbl.setAlignment(Qt.AlignTop)

        title_lbl = QLabel(title, panel)
        title_lbl.setObjectName("DialogTitle")
        title_lbl.setWordWrap(True)

        header.addWidget(icon_lbl)
        header.addWidget(title_lbl, 1)
        lay.addLayout(header)

        # ---- texto ----
        text_lbl = QLabel(text, panel)
        text_lbl.setObjectName("DialogText")
        text_lbl.setWordWrap(True)
        lay.addWidget(text_lbl)

        # ---- botones ----
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        if secondary_text:
            btn_secondary = QPushButton(secondary_text, panel)
            btn_secondary.setObjectName("BtnGhost")
            btn_secondary.clicked.connect(lambda: self.done(QDialog.Rejected))
            btn_row.addWidget(btn_secondary)

        btn_primary = QPushButton(primary_text, panel)
        btn_primary.setObjectName("BtnPrimary")
        btn_primary.clicked.connect(lambda: self.done(QDialog.Accepted))
        btn_row.addWidget(btn_primary)

        lay.addSpacing(6)
        lay.addLayout(btn_row)

        # ---- drag ----
        self._drag_pos: Optional[QPoint] = None
        panel.installEventFilter(self)

        # ---- QSS mínimo (el resto viene del global) ----
        self.setStyleSheet(
            """
            QDialog#NiceDialog {
                background: transparent;
            }
            QLabel#DialogTitle {
                font-size: 1.2em;
                font-weight: 600;
            }
            QLabel#DialogText {
                font-size: 1em;
            }
            QLabel#DialogIcon {
                font-size: 1.4em;
            }
            """
        )

    # ---------------- Drag ----------------
    def eventFilter(self, obj, event):
        if obj.objectName() == "DialogPanel":
            if event.type() == QEvent.MouseButtonPress and isinstance(event, QMouseEvent):
                if event.button() == Qt.LeftButton:
                    self._drag_pos = (
                        event.globalPosition().toPoint()
                        - self.frameGeometry().topLeft()
                    )
                    return True

            elif event.type() == QEvent.MouseMove and isinstance(event, QMouseEvent):
                if self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True

            elif event.type() == QEvent.MouseButtonRelease:
                self._drag_pos = None
                return True

        return super().eventFilter(obj, event)

    # ---------------- helpers estáticos ----------------
    @classmethod
    def info(cls, parent, title: str, text: str, button_text: str = "Aceptar") -> None:
        dlg = cls(
            title,
            text,
            kind="info",
            primary_text=button_text,
            parent=parent,
        )
        dlg.exec()

    @classmethod
    def warning(cls, parent, title: str, text: str, button_text: str = "Aceptar") -> None:
        dlg = cls(
            title,
            text,
            kind="warning",
            primary_text=button_text,
            parent=parent,
        )
        dlg.exec()

    @classmethod
    def error(cls, parent, title: str, text: str, button_text: str = "Aceptar") -> None:
        dlg = cls(
            title,
            text,
            kind="error",
            primary_text=button_text,
            parent=parent,
        )
        dlg.exec()

    @classmethod
    def confirm(
        cls,
        parent,
        title: str,
        text: str,
        *,
        ok_text: str = "Aceptar",
        cancel_text: str = "Cancelar",
    ) -> bool:
        dlg = cls(
            title,
            text,
            kind="confirm",
            primary_text=ok_text,
            secondary_text=cancel_text,
            parent=parent,
        )
        return dlg.exec() == QDialog.Accepted
