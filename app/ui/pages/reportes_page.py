# pages/reportes_page.py

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QMessageBox,
)
from datetime import datetime

from app.reportes.iva_ventas import (
    generar_txt_iva_ventas,
    enviar_iva_ventas_por_mail,
)


class ReportesPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    # =====================
    # UI
    # =====================
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # ===== Título =====
        lbl_title = QLabel("📊 Reportes")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        main_layout.addWidget(lbl_title)

        # ===== Selector de período =====
        period_layout = QHBoxLayout()

        self.cmb_mes = QComboBox()
        self.cmb_anio = QComboBox()

        for m in range(1, 13):
            self.cmb_mes.addItem(f"{m:02}", m)

        current_year = datetime.now().year
        for y in range(current_year - 5, current_year + 1):
            self.cmb_anio.addItem(str(y), y)

        self.cmb_mes.setCurrentIndex(datetime.now().month - 1)
        self.cmb_anio.setCurrentText(str(current_year))

        period_layout.addWidget(QLabel("Mes:"))
        period_layout.addWidget(self.cmb_mes)
        period_layout.addSpacing(10)
        period_layout.addWidget(QLabel("Año:"))
        period_layout.addWidget(self.cmb_anio)
        period_layout.addStretch()

        main_layout.addLayout(period_layout)

        # ===== Sección IVA Ventas =====
        main_layout.addSpacing(20)

        lbl_iva = QLabel("📘 Libro IVA Ventas")
        lbl_iva.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(lbl_iva)

        btn_gen_txt = QPushButton("📄 Generar TXT")
        btn_send_mail = QPushButton("📧 Generar y Enviar al Contador")

        btn_gen_txt.clicked.connect(self.on_generar_txt)
        btn_send_mail.clicked.connect(self.on_enviar_mail)

        main_layout.addWidget(btn_gen_txt)
        main_layout.addWidget(btn_send_mail)

        main_layout.addStretch()

    # =====================
    # Acciones
    # =====================
    def _get_periodo(self):
        mes = self.cmb_mes.currentData()
        anio = self.cmb_anio.currentData()
        return mes, anio

    def on_generar_txt(self):
        mes, anio = self._get_periodo()

        try:
            path = generar_txt_iva_ventas(mes, anio)

            QMessageBox.information(
                self,
                "Reporte generado",
                f"El archivo fue generado correctamente:\n\n{path}",
            )

        except ValueError as e:
            QMessageBox.warning(
                self,
                "Sin datos",
                str(e),
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Ocurrió un error al generar el reporte:\n{e}",
            )

    def on_enviar_mail(self):
        mes, anio = self._get_periodo()

        confirm = QMessageBox.question(
            self,
            "Confirmar envío",
            f"¿Deseás generar y enviar el Libro IVA Ventas {mes:02}/{anio} al contador?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm != QMessageBox.Yes:
            return

        try:
            path = enviar_iva_ventas_por_mail(mes, anio)

            QMessageBox.information(
                self,
                "Reporte enviado",
                f"El reporte fue enviado correctamente.\n\nArchivo:\n{path}",
            )

        except ValueError as e:
            QMessageBox.warning(
                self,
                "Sin datos",
                str(e),
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Ocurrió un error al enviar el reporte:\n{e}",
            )
