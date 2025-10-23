from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QMouseEvent, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QWidget,
    QGraphicsDropShadowEffect
)


class ConfirmDialog(QDialog):
    """
    Diálogo de confirmación lindo, frameless (sin borde del SO).
    - Fondo translúcido + panel con bordes redondeados y sombra
    - Título, texto, texto secundario
    - Botones confirm/cancel con objectNames (#BtnPrimary / #BtnGhost)
    - Icono (emoji por simplicidad; podés cambiar a SVG)
    """

    def __init__(
        self,
        title: str,
        text: str,
        informative_text: Optional[str] = None,
        confirm_text: str = "Confirmar",
        cancel_text: str = "Cancelar",
        icon: str = "⚠️",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        # -------- Ventana sin marco + fondo translúcido --------
        self.setObjectName("NiceDialog")
        self.setModal(True)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowSystemMenuHint
            # | Qt.WindowStaysOnTopHint  # dejalo comentado si no querés "always on top"
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(420)

        # -------- Panel principal (tarjeta) --------
        panel = QFrame(self)
        panel.setObjectName("DialogPanel")

        # Sombra suave
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 110))
        panel.setGraphicsEffect(shadow)

        # Root con margen para ver el glow de la sombra
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.addWidget(panel)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(10)

        lbl_icon = QLabel(icon, panel)
        lbl_icon.setObjectName("DialogIcon")
        lbl_icon.setFixedWidth(28)

        lbl_title = QLabel(title, panel)
        lbl_title.setObjectName("DialogTitle")
        lbl_title.setWordWrap(True)

        header.addWidget(lbl_icon)
        header.addWidget(lbl_title, 1)

        # Texto
        lbl_text = QLabel(text, panel)
        lbl_text.setObjectName("DialogText")
        lbl_text.setWordWrap(True)

        lay.addLayout(header)
        lay.addWidget(lbl_text)

        if informative_text:
            lbl_info = QLabel(informative_text, panel)
            lbl_info.setObjectName("DialogInfo")
            lbl_info.setWordWrap(True)
            lay.addWidget(lbl_info)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton(cancel_text, panel)
        self.btn_cancel.setObjectName("BtnGhost")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = QPushButton(confirm_text, panel)
        self.btn_ok.setObjectName("BtnPrimary")
        self.btn_ok.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)
        lay.addLayout(btn_row)

        # Para arrastrar el popup con el mouse (drag del panel)
        self._drag_pos: Optional[QPoint] = None
        panel.installEventFilter(self)

    # ------- Helpers estáticos -------
    @staticmethod
    def ask_discard(parent: QWidget) -> bool:
        dlg = ConfirmDialog(
            title="Descartar cambios",
            text="Tenés cambios sin guardar.",
            informative_text="Si volvés ahora, los cambios no se guardarán. ¿Querés volver igual?",
            confirm_text="Volver y descartar",
            cancel_text="Seguir editando",
            icon="⚠️",
            parent=parent,
        )
        return dlg.exec() == QDialog.Accepted

    # ------- UX extra: centrar sobre el padre y Esc para cerrar -------
    def showEvent(self, ev):
        super().showEvent(ev)
        # Centrar sobre el parent si existe
        if self.parent() and isinstance(self.parent(), QWidget):
            pw = self.parent().window()
            if pw:
                cx = pw.x() + (pw.width() - self.width()) // 2
                cy = pw.y() + (pw.height() - self.height()) // 2
                self.move(max(cx, 0), max(cy, 0))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(ev)

    # ------- Drag para mover el diálogo -------
    def eventFilter(self, obj, event):
        if obj.objectName() == "DialogPanel":
            et = event.type()
            if et == QEvent.MouseButtonPress and isinstance(event, QMouseEvent):
                if event.button() == Qt.LeftButton:
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif et == QEvent.MouseMove and isinstance(event, QMouseEvent):
                if self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            elif et == QEvent.MouseButtonRelease and isinstance(event, QMouseEvent):
                self._drag_pos = None
                return True
        return super().eventFilter(obj, event)
