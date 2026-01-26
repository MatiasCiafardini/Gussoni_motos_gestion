from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QHBoxLayout,
    QMessageBox, QSpinBox
)
from PySide6.QtCore import Qt
import sys
import os
from app.shared.config_loader import load_config, save_config
from app.core.db_connection import probar_conexion_db


class ConfigDialog(QDialog):
    """
    Diálogo de configuración inicial de la base de datos.
    Se muestra SOLO si la DB no está configurada.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración inicial")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._build_ui()
        self._load_existing_config()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(3306)

        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.db_input = QLineEdit()

        form.addRow("Host:", self.host_input)
        form.addRow("Puerto:", self.port_input)
        form.addRow("Usuario:", self.user_input)
        form.addRow("Contraseña:", self.pass_input)
        form.addRow("Base de datos:", self.db_input)

        layout.addLayout(form)

        # Botones
        btns = QHBoxLayout()

        self.test_btn = QPushButton("Probar conexión")
        self.save_btn = QPushButton("Guardar y continuar")
        self.save_btn.setEnabled(False)

        btns.addStretch(1)
        btns.addWidget(self.test_btn)
        btns.addWidget(self.save_btn)

        layout.addLayout(btns)

        # Señales
        self.test_btn.clicked.connect(self._on_test_connection)
        self.save_btn.clicked.connect(self._on_save)

    # -------------------------------------------------
    # Lógica
    # -------------------------------------------------
    def _load_existing_config(self):
        """
        Si existe config previa (raro, pero posible),
        la cargamos en los inputs.
        """
        cfg = load_config()
        db = cfg.get("db", {})

        self.host_input.setText(db.get("host", ""))
        self.port_input.setValue(int(db.get("port", 3306)))
        self.user_input.setText(db.get("user", ""))
        self.pass_input.setText(db.get("password", ""))
        self.db_input.setText(db.get("name", ""))

    def _collect_db_config(self) -> dict:
        return {
            "host": self.host_input.text().strip(),
            "port": int(self.port_input.value()),
            "user": self.user_input.text().strip(),
            "password": self.pass_input.text(),
            "name": self.db_input.text().strip(),
        }
    def restart_app():
        python = sys.executable
        os.execl(python, python, *sys.argv)
    def _on_test_connection(self):
        db_config = self._collect_db_config()

        ok, error = probar_conexion_db(db_config)

        if not ok:
            QMessageBox.toast(
                self,
                "Error de conexión",
                f"No se pudo conectar a la base de datos:\n\n{error}"
            )
            self.save_btn.setEnabled(False)
            return

        QMessageBox.information(
            self,
            "Conexión exitosa",
            "La conexión a la base de datos fue exitosa."
        )
        self.save_btn.setEnabled(True)

    def _on_save(self):
        cfg = load_config()
        cfg["db"] = self._collect_db_config()
        save_config(cfg)
        self.accept()
        self.restart_app()
