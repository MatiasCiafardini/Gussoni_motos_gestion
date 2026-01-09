from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QHBoxLayout,
)

from app.services.auth_service import AuthService


class LoginDialog(QDialog):
    """Simple login dialog that validates credentials against the database."""

    def __init__(self, parent=None, auth_service: Optional[AuthService] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Iniciar sesión")
        self.setModal(True)
        self.setObjectName("LoginDialog")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumSize(480, 520)

        self._auth_service = auth_service or AuthService()
        self._authenticated_user: Optional[Dict[str, Any]] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(60, 48, 60, 48)
        root.setSpacing(24)

        root.addStretch(1)
        card = QFrame(self)
        card.setObjectName("LoginCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(18)

        self.logo_label = QLabel(card)
        self.logo_label.setObjectName("LoginLogo")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFixedHeight(140)
        self._load_logo()
        card_layout.addWidget(self.logo_label)

        title = QLabel("Bienvenido", card)
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("LoginTitle")
        card_layout.addWidget(title)

        subtitle = QLabel("Ingresá tus credenciales para continuar", card)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("LoginSubtitle")
        card_layout.addWidget(subtitle)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        self.user_input = QLineEdit(card)
        self.user_input.setPlaceholderText("Usuario")
        self.user_input.setObjectName("LoginUserInput")
        self.user_input.returnPressed.connect(lambda: self.password_input.setFocus())
        form_layout.addWidget(self.user_input)
        self.user_input.setText("mati")

        self.password_input = QLineEdit(card)
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setObjectName("LoginPasswordInput")
        self.password_input.returnPressed.connect(self._attempt_login)
        form_layout.addWidget(self.password_input)
        self.password_input.setText("1234")

        self.error_label = QLabel("", card)
        self.error_label.setObjectName("LoginError")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        form_layout.addWidget(self.error_label)

        card_layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.login_button = QPushButton("Aceptar", card)
        self.login_button.setObjectName("Primary")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._attempt_login)
        button_row.addWidget(self.login_button)
        button_row.addStretch(1)
        card_layout.addLayout(button_row)

        root.addWidget(card, alignment=Qt.AlignCenter)
        root.addStretch(1)

        self.user_input.textChanged.connect(self._clear_error)
        self.password_input.textChanged.connect(self._clear_error)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def user(self) -> Optional[Dict[str, Any]]:
        return self._authenticated_user

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_logo(self) -> None:
        assets_dir = Path(__file__).resolve().parent.parent / "assets"
        candidates = ["logo.png", "logo.jpg", "logo.jpeg"]
        pixmap: Optional[QPixmap] = None
        for name in candidates:
            path = assets_dir / name
            if path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    break
        if pixmap and not pixmap.isNull():
            self.logo_label.setPixmap(pixmap)
        else:
            self.logo_label.setText("Tu logo aquí")
            self.logo_label.setStyleSheet("color: #6c757d; font-size: 16px; font-weight: 500;")

    def _clear_error(self) -> None:
        if self.error_label.isVisible():
            self.error_label.setVisible(False)
            self.error_label.clear()

    def _attempt_login(self) -> None:
        username = self.user_input.text().strip()
        password = self.password_input.text()

        self._clear_error()
        if not username or not password:
            self._show_error("Credenciales incorrectas.")
            return
        self.login_button.setEnabled(False)
        try:
            user = self._auth_service.authenticate(username, password)
        except Exception as exc:
            self._show_error(f"No se pudo iniciar sesión. {exc}")
            return
        finally:
            self.login_button.setEnabled(True)

        if not user:
            self._show_error("Credenciales incorrectas.")
            return

        self._authenticated_user = user
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.password_input.setFocus()
        self.password_input.selectAll()
