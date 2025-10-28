from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class ChangePasswordDialog(QDialog):
    """Diálogo para ingresar una nueva contraseña y confirmarla."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("NiceDialog")
        self.setModal(True)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(420)

        self._new_password: Optional[str] = None

        # Panel principal
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

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QLabel("Cambiar contraseña", panel)
        header.setObjectName("DialogTitle")
        layout.addWidget(header)

        instructions = QLabel(
            "Ingresá la nueva contraseña y repetila para confirmar.",
            panel,
        )
        instructions.setObjectName("DialogText")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.in_password1 = QLineEdit(panel)
        self.in_password1.setEchoMode(QLineEdit.Password)
        self.in_password1.setPlaceholderText("Nueva contraseña")
        self.in_password1.setMinimumHeight(36)

        self.in_password2 = QLineEdit(panel)
        self.in_password2.setEchoMode(QLineEdit.Password)
        self.in_password2.setPlaceholderText("Repetir contraseña")
        self.in_password2.setMinimumHeight(36)

        form.addWidget(QLabel("Contraseña"), 0, 0)
        form.addWidget(self.in_password1, 0, 1)
        form.addWidget(QLabel("Confirmación"), 1, 0)
        form.addWidget(self.in_password2, 1, 1)

        layout.addLayout(form)

        self.error_label = QLabel("", panel)
        self.error_label.setObjectName("DialogError")
        self.error_label.setStyleSheet("color: #d9534f;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        self.btn_cancel = QPushButton("Cancelar", panel)
        self.btn_cancel.setObjectName("BtnGhost")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_accept = QPushButton("Guardar", panel)
        self.btn_accept.setObjectName("BtnPrimary")
        self.btn_accept.clicked.connect(self._on_accept)

        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_accept)

        layout.addLayout(buttons)

        self.in_password1.returnPressed.connect(self._on_accept)
        self.in_password2.returnPressed.connect(self._on_accept)
        self.in_password1.textChanged.connect(self._clear_error)
        self.in_password2.textChanged.connect(self._clear_error)

    @property
    def password(self) -> Optional[str]:
        return self._new_password

    def _on_accept(self) -> None:
        pwd1 = (self.in_password1.text() or "").strip()
        pwd2 = (self.in_password2.text() or "").strip()

        if not pwd1 or not pwd2:
            self._show_error("Ingresá la contraseña en ambos campos.")
            return

        if pwd1 != pwd2:
            self._show_error("Las contraseñas no coinciden.")
            return

        if len(pwd1) < 6:
            self._show_error("La contraseña debe tener al menos 6 caracteres.")
            return

        self._new_password = pwd1
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        self.in_password1.selectAll()
        self.in_password1.setFocus()

    def _clear_error(self) -> None:
        if self.error_label.isHidden():
            return
        self.error_label.hide()
