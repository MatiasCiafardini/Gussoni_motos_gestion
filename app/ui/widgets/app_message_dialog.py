from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QWidget,
)


class AppMessageDialog(QDialog):
    """
    Diálogo genérico con estilo de tarjeta:
    - kind: 'info', 'warning', 'error', 'confirm'
    - Movible arrastrando con el mouse.
    """

    def __init__(
        self,
        title: str,
        text: str,
        *,
        kind: str = "info",
        primary_text: str = "Aceptar",
        secondary_text: Optional[str] = None,
        parent: Optional[Widget] = None,
    ) -> None:
        super().__init__(parent)

        self.setModal(True)
        self.setObjectName("AppMessageDialog")

        # Ventana sin marco + fondo transparente
        self.setWindowFlags(
            Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowTitleHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._drag_offset: Optional[QPoint] = None

        # ---- layout raíz (transparente) ----
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Usamos el mismo card que en el resto del sistema
        card = QFrame(self)
        card.setObjectName("Panel")          # <- MISMO estilo que tus tarjetas
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(24, 20, 24, 20)
        card_l.setSpacing(10)

        # ---- encabezado ----
        header = QHBoxLayout()
        header.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setObjectName("AppMessageIcon")

        if kind == "warning":
            icon_lbl.setText("⚠️")
        elif kind == "error":
            icon_lbl.setText("⛔")
        elif kind == "confirm":
            icon_lbl.setText("❓")
        else:
            icon_lbl.setText("ℹ️")

        icon_lbl.setFixedWidth(24)
        icon_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("AppMessageTitle")
        title_lbl.setWordWrap(True)

        header.addWidget(icon_lbl)
        header.addWidget(title_lbl, 1)

        card_l.addLayout(header)

        # ---- texto ----
        text_lbl = QLabel(text)
        text_lbl.setObjectName("AppMessageText")
        text_lbl.setWordWrap(True)
        card_l.addWidget(text_lbl)

        # ---- botones ----
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        # Botón principal con mismo estilo que el sistema
        btn_primary = QPushButton(primary_text)
        btn_primary.setObjectName("BtnPrimary")   # <- MISMO estilo que botones primarios
        btn_primary.clicked.connect(lambda: self.done(QDialog.Accepted))

        if secondary_text:
            btn_secondary = QPushButton(secondary_text)
            btn_secondary.setObjectName("BtnGhost")  # <- MISMO estilo que botón “fantasma”
            btn_secondary.clicked.connect(lambda: self.done(QDialog.Rejected))
            btn_row.addWidget(btn_secondary)

        btn_row.addWidget(btn_primary)

        card_l.addSpacing(6)
        card_l.addLayout(btn_row)

        root.addWidget(card)

        # Solo QSS mínimo para el fondo del diálogo
        self.setStyleSheet(
            """
            QDialog#AppMessageDialog {
                background: transparent;
            }
            QLabel#AppMessageTitle {
                font-size: 15px;
                font-weight: 600;
            }
            QLabel#AppMessageText {
                font-size: 13px;
            }
            """
        )

    # ---------------- Drag para mover ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ------------ helpers estáticos ---------
    @classmethod
    def info(cls, parent, title: str, text: str, button_text: str = "OK") -> None:
        dlg = cls(title, text, kind="info", primary_text=button_text, parent=parent)
        dlg.exec()

    @classmethod
    def warning(cls, parent, title: str, text: str, button_text: str = "OK") -> None:
        dlg = cls(title, text, kind="warning", primary_text=button_text, parent=parent)
        dlg.exec()

    @classmethod
    def error(cls, parent, title: str, text: str, button_text: str = "OK") -> None:
        dlg = cls(title, text, kind="error", primary_text=button_text, parent=parent)
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
