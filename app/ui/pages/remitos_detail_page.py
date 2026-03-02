from __future__ import annotations
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QFrame, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QMainWindow, QTextEdit
)

from sqlalchemy import text as sql_text
from app.data.database import SessionLocal
from app.services.remitos_service import RemitosService
from app.services.clientes_service import ClientesService
from app.services.vehiculos_service import VehiculosService
import app.ui.app_message as popUp
from app.services.comprobantes_service import ComprobantesService
import os

def _vehiculo_label(v: Dict[str, Any]) -> str:
    desc = f"{v.get('marca', '')} {v.get('modelo', '')}".strip()
    anio = v.get("anio")
    if anio:
        desc += f" {anio}"
    nro_motor = v.get("numero_motor")
    if nro_motor:
        desc += f" | Motor: {nro_motor}"
    nro_cuadro = v.get("numero_cuadro")
    if nro_cuadro:
        desc += f" | Cuadro: {nro_cuadro}"
    return desc or "(sin descripción)"


class RemitosDetailPage(QWidget):

    go_back = Signal()

    COL_VEHICULO = 0
    COL_OBSERVACIONES = 1

    def __init__(
        self,
        remito_id: int,
        parent: Optional[QWidget] = None,
        main_window: Optional[QMainWindow] = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("RemitosDetailPage")

        self._remito_id = int(remito_id)
        self._main_window = main_window

        self._svc_remitos = RemitosService()
        self._svc_clientes = ClientesService()
        self._svc_vehiculos = VehiculosService()

        self._edit_mode = False
        self._estado_actual: Optional[str] = None

        self._build_ui()
        self._load_data()

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(8)

        title = QLabel("Detalle de remito")
        title.setStyleSheet("font-size: 1.4em; font-weight: 600;")
        main.addWidget(title)

        # ---------------- Cabecera ----------------

        sec1 = QFrame()
        sec1.setObjectName("Panel")
        sec1_l = QVBoxLayout(sec1)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        sec1_l.addLayout(grid)

        for col, stretch in enumerate((1, 3, 1, 3, 1,3)):
            grid.setColumnStretch(col, stretch)

        self.in_pv = QLineEdit()
        self.in_numero = QLineEdit()
        self.in_fecha = QLineEdit()
        self.in_estado = QLineEdit()

        for w in (self.in_pv, self.in_numero, self.in_fecha, self.in_estado):
            w.setReadOnly(True)

        row = 0
        grid.addWidget(QLabel("Pto Vta"), row, 0)
        grid.addWidget(self.in_pv, row, 1)
        grid.addWidget(QLabel("Número"), row, 2)
        grid.addWidget(self.in_numero, row, 3)

        row += 1
        grid.addWidget(QLabel("Fecha"), row, 0)
        grid.addWidget(self.in_fecha, row, 1)
        grid.addWidget(QLabel("Estado"), row, 2)
        grid.addWidget(self.in_estado, row, 3)

        row += 1
        self.in_observaciones = QTextEdit()
        self.in_observaciones.setReadOnly(True)
        self.in_observaciones.setFixedHeight(70)

        grid.addWidget(QLabel("Observaciones"), row, 0)
        grid.addWidget(self.in_observaciones, row, 1, 1, 3)

        main.addWidget(sec1)

        # ---------------- Cliente ----------------

        sec2 = QFrame()
        sec2.setObjectName("Panel")
        sec2_l = QVBoxLayout(sec2)

        grid2 = QGridLayout()
        sec2_l.addLayout(grid2)

        for col, stretch in enumerate((1, 3, 1, 3)):
            grid2.setColumnStretch(col, stretch)

        self.in_cliente = QLineEdit()
        self.in_doc = QLineEdit()
        self.in_tel = QLineEdit()
        self.in_dir = QLineEdit()

        for w in (self.in_cliente, self.in_doc, self.in_tel, self.in_dir):
            w.setReadOnly(True)

        r = 0
        grid2.addWidget(QLabel("Cliente"), r, 0)
        grid2.addWidget(self.in_cliente, r, 1, 1, 3)

        r += 1
        grid2.addWidget(QLabel("Documento"), r, 0)
        grid2.addWidget(self.in_doc, r, 1)
        grid2.addWidget(QLabel("Teléfono"), r, 2)
        grid2.addWidget(self.in_tel, r, 3)

        r += 1
        grid2.addWidget(QLabel("Dirección"), r, 0)
        grid2.addWidget(self.in_dir, r, 1, 1, 3)

        main.addWidget(sec2)

        # ---------------- Detalle ----------------

        sec3 = QFrame()
        sec3.setObjectName("Panel")
        sec3_l = QVBoxLayout(sec3)
        sec3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.tbl_detalle = QTableWidget(0, 2)
        self.tbl_detalle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.tbl_detalle.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_detalle.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_detalle.verticalHeader().setVisible(False)
        self.tbl_detalle.setAlternatingRowColors(True)
        self.tbl_detalle.setHorizontalHeaderLabels(["Vehículo"])
        header = self.tbl_detalle.horizontalHeader()
        header.setSectionResizeMode(self.COL_VEHICULO, QHeaderView.Stretch)

        sec3_l.addWidget(self.tbl_detalle)
        main.addWidget(sec3, 1)

        # ---------------- Botones ----------------

        btns = QHBoxLayout()

        self.btn_volver = QPushButton("Volver")
        self.btn_modificar = QPushButton("Modificar")
        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_entregado = QPushButton("Marcar como ENTREGADO")
        self.btn_anular = QPushButton("Anular")
        self.btn_pdf = QPushButton("Generar PDF")
        self.btn_pdf.setObjectName("BtnPrimary")
        self.btn_guardar.setObjectName("BtnPrimary")
        self.btn_entregado.setObjectName("BtnPrimary")

        btns.addStretch(1)
        btns.addWidget(self.btn_volver)
        btns.addWidget(self.btn_modificar)
        btns.addWidget(self.btn_guardar)
        btns.addWidget(self.btn_entregado)
        btns.addWidget(self.btn_anular)
        btns.addWidget(self.btn_pdf)
        btns.addStretch(1)

        main.addLayout(btns)
        main.addStretch()
        # conexiones
        self.btn_volver.clicked.connect(self.go_back.emit)
        self.btn_modificar.clicked.connect(self._on_modificar)
        self.btn_guardar.clicked.connect(self._on_guardar)
        self.btn_entregado.clicked.connect(self._on_entregado)
        self.btn_anular.clicked.connect(self._on_anular)
        self.btn_pdf.clicked.connect(self._on_generar_pdf)
        self._apply_edit_visibility()

    # =========================================================
    # CARGA
    # =========================================================

    def _load_data(self) -> None:
        db = SessionLocal()
        try:
            remito = self._svc_remitos.get(self._remito_id)
            if not remito:
                popUp.toast(self, "Remito no encontrado.", kind="error")
                return

            self._estado_actual = remito.get("estado")

            self.in_pv.setText(str(remito.get("punto_venta")))
            self.in_numero.setText(str(remito.get("numero")))
            fecha = remito.get("fecha_emision")
            if fecha:
                self.in_fecha.setText(str(fecha))
            else:
                self.in_fecha.clear()
            self.in_estado.setText(str(remito.get("estado")))
            self.in_observaciones.setPlainText(remito.get("observaciones") or "")

            # Cliente
            cliente = self._svc_clientes.get(remito.get("cliente_id"))
            if cliente:
                nombre = f"{cliente.get('nombre')} {cliente.get('apellido')}"
                self.in_cliente.setText(nombre.strip())
                self.in_doc.setText(cliente.get("nro_doc") or "")
                self.in_tel.setText(cliente.get("telefono") or "")
                self.in_dir.setText(cliente.get("direccion") or "")

            # Detalle
            rows = db.execute(
                sql_text("""
                    SELECT vehiculo_id, descripcion
                    FROM remitos_detalle
                    WHERE remito_id = :id
                    ORDER BY id
                """),
                {"id": self._remito_id},
            ).mappings().all()

            self.tbl_detalle.setRowCount(0)

            for r in rows:
                row = self.tbl_detalle.rowCount()
                self.tbl_detalle.insertRow(row)

                vehiculo = self._svc_vehiculos.get(r["vehiculo_id"])
                label = _vehiculo_label(vehiculo) if vehiculo else r["descripcion"]

                self.tbl_detalle.setItem(row, 0, QTableWidgetItem(label))
            self.tbl_detalle.resizeRowsToContents()
        finally:
            db.close()

        self._apply_edit_visibility()

    # =========================================================
    # ESTADO / EDICIÓN
    # =========================================================
    def _adjust_table_height(self):
        header_height = self.tbl_detalle.horizontalHeader().height()
        rows_height = sum(
            self.tbl_detalle.rowHeight(r)
            for r in range(self.tbl_detalle.rowCount())
        )
        frame = self.tbl_detalle.frameWidth() * 2
        total = header_height + rows_height + frame + 4

        self.tbl_detalle.setFixedHeight(total)
    def _apply_edit_visibility(self) -> None:
        puede_editar = self._estado_actual == "EMITIDO"

        self.btn_modificar.setVisible(puede_editar and not self._edit_mode)
        self.btn_guardar.setVisible(self._edit_mode)
        self.btn_entregado.setVisible(puede_editar)
        self.btn_anular.setVisible(puede_editar)

    def _on_modificar(self) -> None:
        if self._estado_actual != "":
            return
        self._edit_mode = True
        self.in_observaciones.setReadOnly(False)
        self._apply_edit_visibility()

    def _on_guardar(self) -> None:
        db = SessionLocal()
        try:
            db.execute(
                sql_text("""
                    UPDATE remitos
                    SET observaciones = :obs
                    WHERE id = :id
                """),
                {"obs": self.in_observaciones.toPlainText(), "id": self._remito_id},
            )
            db.commit()
        except Exception:
            db.rollback()
            popUp.toast(self, "Error al guardar cambios.", kind="error")
            return
        finally:
            db.close()

        popUp.toast(self, "Cambios guardados.", kind="success")
        self._edit_mode = False
        self._load_data()

    def _on_entregado(self) -> None:
        db = SessionLocal()
        try:
            db.execute(
                sql_text("UPDATE remitos SET estado = 'ENTREGADO' WHERE id = :id"),
                {"id": self._remito_id},
            )
            db.commit()
        finally:
            db.close()

        popUp.toast(self, "Remito marcado como ENTREGADO.", kind="success")
        self._load_data()

    def _on_anular(self) -> None:
        if self._estado_actual != "Emitido":
            popUp.toast(self, "Solo se puede anular un remito Emitido.", kind="warning")
            return

        if not popUp.confirm(
            self,
            "Anular remito",
            "¿Seguro que querés anular este remito?\n\nSe devolverá el stock de los vehículos."
        ):
            return

        try:
            self._svc_remitos.anular(self._remito_id)
        except Exception as e:
            popUp.toast(self, f"Error al anular: {e}", kind="error")
            return

        popUp.toast(self, "Remito anulado correctamente.", kind="success")
        self._load_data()
    def _on_generar_pdf(self) -> None:
        try:
            svc = ComprobantesService()
            pdf_path = svc.generar_pdf_remito(self._remito_id)

            popUp.toast(self, "PDF generado correctamente.", kind="success")

            # Abrir automáticamente el PDF
            if os.name == "nt":  # Windows
                os.startfile(pdf_path)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", pdf_path])

        except Exception as e:
            popUp.toast(self, f"Error al generar PDF: {e}", kind="error")