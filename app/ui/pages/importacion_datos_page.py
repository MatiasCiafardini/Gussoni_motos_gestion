from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QHBoxLayout, QSizePolicy,
    QSpacerItem, QFileDialog, QListView
)

import app.ui.app_message as popUp
from app.services.importacion_datos_service import ImportacionDatosService


class ImportacionDatosPage(QWidget):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("ImportacionDatosPage")

        # ---------------- Layout base ----------------
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(14)

        title = QLabel("Importación de Datos")
        title.setObjectName("CfgH1")

        subtitle = QLabel(
            "Importá información al sistema usando plantillas de Excel (.xlsx) "
            "validadas para evitar errores en la carga."
        )
        subtitle.setObjectName("CfgMuted")

        root.addWidget(title)
        root.addWidget(subtitle)

        # ---------------- Selector de tabla ----------------
        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(12)

        lbl_tabla = QLabel("Tabla:")
        self.combo_tablas = QComboBox()
        self._setup_combo(self.combo_tablas)
        self.combo_tablas.setMinimumWidth(260)
        self.combo_tablas.setEnabled(False)

        selector_layout.addWidget(lbl_tabla)
        selector_layout.addWidget(self.combo_tablas)
        selector_layout.addStretch(1)

        root.addLayout(selector_layout)

        # ---------------- Botones de acción ----------------
        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.btn_descargar = QPushButton("Descargar plantilla Excel")
        self.btn_descargar.setEnabled(False)

        self.btn_importar = QPushButton("Importar archivo Excel")
        self.btn_importar.setEnabled(False)

        actions.addWidget(self.btn_descargar)
        actions.addWidget(self.btn_importar)
        actions.addStretch(1)

        root.addLayout(actions)

        root.addItem(QSpacerItem(0, 6, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # ---------------- Service ----------------
        self.service = ImportacionDatosService()

        # ---------------- Cargar tablas ----------------
        self._cargar_tablas()

        # ---------------- Signals ----------------
        self.combo_tablas.currentIndexChanged.connect(self._on_tabla_changed)
        self.btn_descargar.clicked.connect(self._descargar_plantilla)
        self.btn_importar.clicked.connect(self._importar_archivo)

        # ---------------- QSS local ----------------
        self.setStyleSheet("""
        QLabel#CfgH1 {
            font-size: 22px;
            font-weight: 800;
            color: #0F172A;
            margin-bottom: 2px;
        }
        QLabel#CfgMuted {
            color: #6B7280;
            margin-bottom: 8px;
        }
        """)

    # ==================================================
    # Internos
    # ==================================================

    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView()
        lv.setObjectName("ComboPopup")
        lv.setUniformItemSizes(True)
        lv.setSpacing(2)
        cb.setView(lv)

    def _cargar_tablas(self):
        try:
            tablas = self.service.listar_tablas()

            self.combo_tablas.clear()
            self.combo_tablas.addItem("Seleccionar tabla...")

            for t in tablas:
                self.combo_tablas.addItem(t["label"], t["key"])

            self.combo_tablas.setEnabled(True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            popUp.critical(
                self,
                f"No se pudieron cargar las tablas de importación.\n\n{e}"
            )

    def _on_tabla_changed(self, index: int):
        tabla = self.combo_tablas.currentData()
        enabled = bool(tabla)

        self.btn_descargar.setEnabled(enabled)
        self.btn_importar.setEnabled(enabled)

    # ==================================================
    # Acciones
    # ==================================================

    def _descargar_plantilla(self):
        tabla = self.combo_tablas.currentData()
        if not tabla:
            return

        try:
            data = self.service.generar_plantilla(tabla)
        except Exception as e:
            popUp.critical(self, str(e))
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar plantilla Excel",
            f"{tabla}_plantilla.xlsx",
            "Excel (*.xlsx)"
        )

        if not path:
            return

        try:
            with open(path, "wb") as f:
                f.write(data)

            # Toast de éxito (no molesta)
            popUp.critical(
                self,
                f"Plantilla Excel de '{tabla}' descargada correctamente."
            )

        except Exception as e:
            popUp.critical(
                self,
                f"No se pudo guardar el archivo.\n\n{e}"
            )

    def _importar_archivo(self):
        tabla = self.combo_tablas.currentData()
        if not tabla:
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo Excel",
            "",
            "Excel (*.xlsx)"
        )

        if not path:
            return

        try:
            with open(path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            popUp.critical(
                self,
                f"No se pudo leer el archivo.\n\n{e}"
            )
            return

        try:
            result = self.service.importar_xlsx(tabla, file_bytes)
        except Exception as e:
            popUp.critical(
                self,
                f"Ocurrió un error inesperado.\n\n{e}"
            )
            return

        # ---------------- Resultado ----------------
        if result.get("success"):
            # Éxito → toast corto
            popUp.critical(
                self,
                f"Importación exitosa.\nRegistros importados: {result.get('insertados', 0)}"
            )
        else:
            # Errores → modal estático
            errores = result.get("errores", [])
            msg = (
                "No se pudo completar la importación.\n\n"
                "Se encontraron los siguientes errores:\n\n"
                + "\n".join(errores[:20])
            )

            if len(errores) > 20:
                msg += f"\n\n... y {len(errores) - 20} errores más."

            popUp.info(
                self,
                "Errores de importación",
                msg
            )
