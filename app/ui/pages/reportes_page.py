# app/ui/pages/reportes_page.py

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QMessageBox,
    QFileDialog,
    QFrame,
)
from PySide6.QtCore import Qt
from datetime import datetime
from pathlib import Path
import calendar
import zipfile
from app.core.config import settings

from app.reportes.iva_ventas import generar_txt_iva_ventas
from app.reportes.iva_ventas_datos import generar_txt_iva_ventas_datos


class ReportesPage(QWidget):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self._build_ui()

    # =====================================================
    # UI
    # =====================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # ===== Título =====
        title = QLabel("📊 Reportes Contables")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        root.addWidget(title)

        subtitle = QLabel("Libro IVA Digital – AFIP")
        subtitle.setStyleSheet("color: #555;")
        root.addWidget(subtitle)

        # ===== Panel =====
        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(16)

        # ===== Selector de reporte =====
        row_reporte = QHBoxLayout()
        lbl_rep = QLabel("Reporte:")
        lbl_rep.setMinimumWidth(120)

        self.cmb_reporte = QComboBox()
        self.cmb_reporte.addItem("Libro IVA Ventas", "iva_ventas")

        row_reporte.addWidget(lbl_rep)
        row_reporte.addWidget(self.cmb_reporte, 1)
        panel_layout.addLayout(row_reporte)

        # ===== Selector de período (combo único MES/AÑO) =====
        row_periodo = QHBoxLayout()
        lbl_periodo = QLabel("Período:")
        lbl_periodo.setMinimumWidth(120)

        self.cmb_periodo = QComboBox()
        self._load_periodos()

        row_periodo.addWidget(lbl_periodo)
        row_periodo.addWidget(self.cmb_periodo, 1)
        panel_layout.addLayout(row_periodo)

        # ===== Acción =====
        btn_exportar = QPushButton("📦 Generar Libro IVA (ZIP)")
        btn_exportar.setMinimumHeight(44)
        btn_exportar.clicked.connect(self.on_exportar)

        panel_layout.addSpacing(10)
        panel_layout.addWidget(btn_exportar, alignment=Qt.AlignRight)

        root.addWidget(panel)
        root.addStretch()

    # =====================================================
    # Helpers
    # =====================================================
    def _load_periodos(self):
        """
        Carga períodos tipo:
        Enero 2026
        Diciembre 2025
        Noviembre 2025
        """
        hoy = datetime.now()
        anio = hoy.year
        mes = hoy.month

        for _ in range(18):
            nombre_mes = calendar.month_name[mes].capitalize()
            label = f"{nombre_mes} {anio}"
            self.cmb_periodo.addItem(label, (mes, anio))

            mes -= 1
            if mes == 0:
                mes = 12
                anio -= 1

    # =====================================================
    # Acción principal
    # =====================================================
    def on_exportar(self):
        tipo_reporte = self.cmb_reporte.currentData()
        if tipo_reporte != "iva_ventas":
            QMessageBox.warning(
                self,
                "Reporte no disponible",
                "El reporte seleccionado aún no está disponible.",
            )
            return

        mes, anio = self.cmb_periodo.currentData()

        # Elegir carpeta destino
        carpeta = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de destino",
            str(Path.home() / "Downloads"),
        )

        if not carpeta:
            return

        try:
            base = Path(carpeta)

            # 1️⃣ Generar CBTE + ALICUOTAS
            paths = generar_txt_iva_ventas(mes, anio, path_override=str(base))

            # 2️⃣ Generar DATOS (resumen)
            if settings.ARCA_ENV == "PRODUCCION":
                cuit = settings.ARCA_PROD_CUIT
            else:
                cuit = settings.ARCA_HOMO_CUIT

            if not cuit:
                raise RuntimeError("No está configurado el CUIT del contribuyente.")

            path_datos = generar_txt_iva_ventas_datos(
                mes=mes,
                anio=anio,
                cuit=str(cuit),
                path_override=str(base),
            )



            # 3️⃣ Crear ZIP final
            zip_name = f"Libro_IVA_Ventas_{anio}_{mes:02}.zip"
            zip_path = base / zip_name

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(paths["cbte"], Path(paths["cbte"]).name)
                z.write(paths["alicuotas"], Path(paths["alicuotas"]).name)
                z.write(path_datos, Path(path_datos).name)

            QMessageBox.information(
                self,
                "Reporte generado",
                "El Libro IVA Ventas fue generado correctamente.\n\n"
                f"Archivo:\n{zip_path}\n\n"
                "Incluye:\n"
                "- VENTAS_CBTE\n"
                "- VENTAS_ALICUOTAS\n"
                "- VENTAS_DATOS",
            )

        except ValueError as e:
            QMessageBox.warning(self, "Sin datos", str(e))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Ocurrió un error al generar el reporte:\n{e}",
            )
