from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QWidget, QSizePolicy, QListView, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtGui import QColor
import app.ui.app_message as popUp
from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtCore import QLocale
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.services.catalogos_service import CatalogosService
from app.services.pagos_service import PagosService


class RegistrarPagoDialog(QDialog):
    def __init__(
        self,
        venta_id: int,
        cliente_id: int,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.venta_id = venta_id
        self.cliente_id = cliente_id

        self.catalogos_service = CatalogosService()
        self.pagos_service = PagosService()

        self.setWindowTitle("Registrar pago")
        self.setModal(True)
        self.setMinimumSize(800, 600)

        self._build_ui()
        self._load_data()

    # -----------------------------------------------------
    # UI
    # -----------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # =========================
        # CARD
        # =========================
        card = QWidget()
        card.setObjectName("Card")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(16)

        # =========================
        # TITLE
        # =========================
        title = QLabel("Registrar pago")
        title.setObjectName("SectionTitle")
        card_layout.addWidget(title)

        # =========================
        # DETALLE VENTA
        # =========================
        self.lbl_detalle_venta = QLabel()
        self.lbl_detalle_venta.setObjectName("TextMuted")
        self.lbl_detalle_venta.setWordWrap(True)
        card_layout.addWidget(self.lbl_detalle_venta)

        # =========================
        # MONTO + FORMA DE PAGO
        # =========================
        row_pago = QHBoxLayout()
        row_pago.setSpacing(12)

        col_monto = QVBoxLayout()
        lbl_monto = QLabel("Monto recibido")
        self.in_monto = MoneySpinBox()


        col_monto.addWidget(lbl_monto)
        col_monto.addWidget(self.in_monto)

        col_fp = QVBoxLayout()
        lbl_fp = QLabel("Forma de pago")
        self.cb_forma_pago = QComboBox()
        self._setup_combo(self.cb_forma_pago)
        col_fp.addWidget(lbl_fp)
        col_fp.addWidget(self.cb_forma_pago)

        row_pago.addLayout(col_monto, 2)
        row_pago.addLayout(col_fp, 1)

        card_layout.addLayout(row_pago)

        # =========================
        # PREVIEW
        # =========================
        self.lbl_preview = QLabel()
        self.lbl_preview.setObjectName("TextMuted")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.hide()
        card_layout.addWidget(self.lbl_preview)

        # =========================
        # OBSERVACIONES
        # =========================
        lbl_obs = QLabel("Observaciones")
        self.in_obs = QTextEdit()
        self.in_obs.setMinimumHeight(80)

        card_layout.addWidget(lbl_obs)
        card_layout.addWidget(self.in_obs)

        # =========================
        # TABLA CUOTAS
        # =========================
        lbl_cuotas = QLabel("Cuotas de la venta")
        lbl_cuotas.setObjectName("SectionSubtitle")
        card_layout.addWidget(lbl_cuotas)

        self.tbl_cuotas = QTableWidget(0, 6)
        self.tbl_cuotas.setHorizontalHeaderLabels([
            "Nº",
            "Vencimiento",
            "Monto",
            "Pagado",
            "Estado",
            "Fecha de pago"
        ])

        self.tbl_cuotas.verticalHeader().hide()
        self.tbl_cuotas.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_cuotas.setSelectionMode(QTableWidget.NoSelection)
        self.tbl_cuotas.horizontalHeader().setStretchLastSection(True)
        self.tbl_cuotas.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_cuotas.setMinimumHeight(220)


        card_layout.addWidget(self.tbl_cuotas)

        root.addWidget(card)

        # =========================
        # FOOTER
        # =========================
        footer = QHBoxLayout()
        footer.addStretch(1)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("BtnFlat")

        self.btn_confirm = QPushButton("Registrar pago")
        self.btn_confirm.setObjectName("BtnPrimary")

        footer.addWidget(self.btn_cancel)
        footer.addSpacing(8)
        footer.addWidget(self.btn_confirm)

        root.addLayout(footer)

        # =========================
        # SIGNALS
        # =========================
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_confirm.clicked.connect(self._on_confirm)
        self.in_monto.valueChanged.connect(self._update_preview)

    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        cb.setMinimumHeight(36)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lv = QListView()
        lv.setObjectName("ComboPopup")
        lv.setUniformItemSizes(True)
        lv.setSpacing(2)
        cb.setView(lv)

    # -----------------------------------------------------
    # DATA
    # -----------------------------------------------------
    def _load_data(self):
        self._load_detalle_venta()
        self._load_formas_pago()
        self._load_cuotas()

    def _load_detalle_venta(self):
        try:
            d = self.pagos_service.get_detalle_venta(self.venta_id)
        except Exception:
            self.lbl_detalle_venta.setText(f"<b>Venta #{self.venta_id}</b>")
            return

        self.lbl_detalle_venta.setText(
            f"<b>Venta #{d['venta_id']}</b><br>"
            f"Moto: {d['moto']}<br>"
            f"Precio total: $ {d['precio']:,.2f}<br>"
            f"Financiación: {d['financiacion']}"
        )



    def _load_formas_pago(self):
        self.cb_forma_pago.clear()
        for fp in self.catalogos_service.get_formas_pago():
            self.cb_forma_pago.addItem(fp["nombre"], fp["id"])

    def _load_cuotas(self):
        self.tbl_cuotas.setRowCount(0)

        try:
            cuotas = self.pagos_service.get_cuotas_venta(self.venta_id)
        except Exception:
            return

        for c in cuotas:
            row = self.tbl_cuotas.rowCount()
            self.tbl_cuotas.insertRow(row)

            # Color de fila según estado (suave)
            if c["estado"] == "PAGADA":
                bg_color = QColor(230, 245, 235)   # verde suave
            elif c["estado"] == "PARCIAL":
                bg_color = QColor(255, 245, 225)   # amarillo suave
            else:  # PENDIENTE
                bg_color = QColor(255, 235, 235)   # rojo suave

            items = [
                QTableWidgetItem(str(c["nro"])),                               # Nº
                QTableWidgetItem(c["vencimiento"]),                            # Vencimiento
                QTableWidgetItem(f"$ {c['importe']:,.2f}"),                    # Monto
                QTableWidgetItem(f"$ {c['pagado']:,.2f}"),                     # Pagado
                QTableWidgetItem(c["estado"]),                                  # Estado
                QTableWidgetItem(c["fecha_pago"] or "-"),                       # Fecha pago
            ]

            for col, item in enumerate(items):
                item.setBackground(bg_color)
                item.setTextAlignment(Qt.AlignCenter if col in (0, 4) else Qt.AlignVCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.tbl_cuotas.setItem(row, col, item)



        

    # -----------------------------------------------------
    # PREVIEW
    # -----------------------------------------------------
    def _update_preview(self):
        monto = float(self.in_monto.value())

        if monto <= 0:
            self.lbl_preview.hide()
            return

        try:
            r = self.pagos_service.simular_pago(self.venta_id, monto)
        except Exception as ex:
            self.lbl_preview.setText(str(ex))
            self.lbl_preview.show()
            return

        lines = []

        if r["cuotas_pagadas"] > 0:
            lines.append(f"• {r['cuotas_pagadas']} cuotas completas")

        if r["cuotas_parciales"] > 0:
            lines.append("• 1 cuota parcial")

        if r["monto_restante"] > 0:
            lines.append(
                f"• Saldo sin imputar: $ {r['monto_restante']:,.2f}"
            )

        self.lbl_preview.setText(
            "<b>Resumen del pago:</b><br>" + "<br>".join(lines)
        )
        self.lbl_preview.show()


    # -----------------------------------------------------
    # CONFIRM
    # -----------------------------------------------------
    def _on_confirm(self):
        monto = float(self.in_monto.value())
    
        if monto <= 0:
            popUp.warning(self, "Pagos", "El monto debe ser mayor a cero.")
            return
    
        if self.cb_forma_pago.currentIndex() < 0:
            popUp.warning(self, "Pagos", "Seleccioná una forma de pago.")
            return
    
        # -----------------------------------------
        # SIMULACIÓN (para resumen)
        # -----------------------------------------
        try:
            r = self.pagos_service.simular_pago(self.venta_id, monto)
        except Exception as ex:
            popUp.warning(self, "Pagos", str(ex))
            return
    
        # Armar resumen
        resumen = [
            f"Vas a registrar un pago de <b>$ {monto:,.2f}</b>.",
            "",
        ]
    
        if r["cuotas_pagadas"] > 0:
            resumen.append(f"• {r['cuotas_pagadas']} cuotas completas")
    
        if r["cuotas_parciales"] > 0:
            resumen.append("• 1 cuota parcial")
    
        if r["monto_restante"] > 0:
            resumen.append(
                f"• Saldo sin imputar: $ {r['monto_restante']:,.2f}"
            )
    
        resumen_html = "<br>".join(resumen)
    
        # -----------------------------------------
        # CONFIRMACIÓN
        # -----------------------------------------
        ok = popUp.confirm(
            self,
            "Confirmar registro de pago",
            resumen_html
        )
    
        if not ok:
            return
    
        # -----------------------------------------
        # REGISTRO REAL
        # -----------------------------------------
        try:
            self.pagos_service.registrar_pago(
                venta_id=self.venta_id,
                cliente_id=self.cliente_id,
                monto=monto,
                forma_pago_id=self.cb_forma_pago.currentData(),
                observaciones=self.in_obs.toPlainText().strip() or None
            )
        except Exception as ex:
            popUp.toast(self, "Pagos", str(ex))
            return
    
        self.accept()
    

