from __future__ import annotations
from typing import Optional, Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QComboBox, QPushButton,
    QHBoxLayout, QListView, QSizePolicy, QFrame, QMainWindow
)
import app.ui.app_message as popUp
from app.services.facturas_service import FacturasService
from app.ui.widgets.loading_overlay import LoadingOverlay
from app.ui.utils.loading_decorator import with_loading


class ConfiguracionArcaPage(QWidget):
    """
    Pantalla de configuración / prueba de ARCA / AFIP.

    Permite seleccionar:
      - Tipo de comprobante (FA, FB, FC, NCA, etc.)
      - Punto de venta

    Y consultar el PRÓXIMO NÚMERO a autorizar, usando el WS de AFIP/ARCA.
    """

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConfiguracionArcaPage")
        self.main_window = main_window

        self.service = FacturasService()

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)

        title = QLabel("Configuración ARCA / AFIP")
        title.setObjectName("CfgArcaH1")
        subtitle = QLabel(
            "Verificá la numeración real de AFIP/ARCA por tipo de comprobante y punto de venta.\n"
            "Usa el mismo servicio que la facturación electrónica, para asegurarte que siempre esté funcionando."
        )
        subtitle.setObjectName("CfgArcaMuted")

        root.addWidget(title)
        root.addWidget(subtitle)

        # --- Formulario principal ---
        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        # Combos
        self.cb_tipo = QComboBox()
        self._setup_combo(self.cb_tipo)
        self.cb_pto_vta = QComboBox()
        self._setup_combo(self.cb_pto_vta)

        self.cb_tipo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cb_pto_vta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        form.addWidget(QLabel("Tipo de comprobante"), 0, 0)
        form.addWidget(self.cb_tipo, 0, 1)

        form.addWidget(QLabel("Punto de venta"), 1, 0)
        form.addWidget(self.cb_pto_vta, 1, 1)

        root.addLayout(form)

        # Línea separadora
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # --- Botón de consulta + resultado ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_consultar = QPushButton("Consultar próximo número")
        self.btn_consultar.setObjectName("BtnPrimary")
        self.btn_consultar.setCursor(Qt.PointingHandCursor)

        btn_row.addWidget(self.btn_consultar)
        btn_row.addStretch(1)

        root.addLayout(btn_row)

        self.lbl_result = QLabel("")
        self.lbl_result.setObjectName("CfgArcaResult")
        self.lbl_result.setWordWrap(True)
        root.addWidget(self.lbl_result)

        root.addStretch(1)

        # Loading overlay
        self.loading_overlay = LoadingOverlay(self, text="")

        # Conexiones
        self.btn_consultar.clicked.connect(self.on_consultar_clicked)

        # Cargar datos
        self._load_tipos_comprobante()
        self._load_puntos_venta()

        # Estilos locales
        self.setStyleSheet("""
        QLabel#CfgArcaH1 {
            font-size: 20px;
            font-weight: 800;
            color: #0F172A;
            margin-bottom: 4px;
        }
        QLabel#CfgArcaMuted {
            color: #6B7280;
            margin-bottom: 12px;
        }
        QLabel#CfgArcaResult {
            margin-top: 8px;
            padding: 8px 10px;
            border-radius: 6px;
            background-color: #0f172a;
            color: #e5e7eb;
            font-size: 13px;
        }
        """)

    # ---------- Helpers UI ----------

    def _setup_combo(self, cb: QComboBox) -> None:
        cb.setObjectName("FilterCombo")
        lv = QListView()
        lv.setObjectName("ComboPopup")
        lv.setUniformItemSizes(True)
        lv.setSpacing(2)
        cb.setView(lv)

    def _load_tipos_comprobante(self) -> None:
        self.cb_tipo.clear()
        self.cb_tipo.addItem("Seleccionar...", None)

        try:
            tipos = self.service.get_tipos_comprobante()
        except Exception as e:
            popUp.critical(
                self,
                "Error",
                f"No pude cargar los tipos de comprobante.\n\n{e}",
            )
            return

        if not tipos:
            popUp.warning(
                self,
                "Atención",
                "No hay tipos de comprobante configurados. Revisá la tabla de tipos de comprobante.",
            )
            return

        for t in tipos:
            # Tratamos de ser defensivos con las claves
            codigo = (t.get("codigo") or t.get("tipo") or t.get("letra") or "").strip()
            if not codigo:
                # Si no tenemos código, usamos el ID como último recurso
                codigo = str(t.get("id") or t.get("id_tipo") or "")
            descripcion = (
                t.get("descripcion")
                or t.get("nombre")
                or ""
            )
            label = f"{codigo} – {descripcion}".strip(" –")
            self.cb_tipo.addItem(label, codigo)

    def _load_puntos_venta(self) -> None:
        self.cb_pto_vta.clear()
        self.cb_pto_vta.addItem("Seleccionar...", None)

        try:
            pvs = self.service.get_puntos_venta()
        except Exception as e:
            popUp.critical(
                self,
                "Error",
                f"No pude cargar los puntos de venta.\n\n{e}",
            )
            return

        if not pvs:
            popUp.warning(
                self,
                "Atención",
                "No hay puntos de venta configurados. Revisá la tabla 'puntos_venta'.",
            )
            return

        for pv in pvs:
            nro_raw = pv.get("punto_venta") or pv.get("punto") or pv.get("numero") or pv.get("pv")
            try:
                nro = int(nro_raw)
            except Exception:
                continue
            label = f"{nro:04d}"
            self.cb_pto_vta.addItem(label, nro)

    # ---------- Acción principal ----------

    @with_loading("Consultando próximo número en ARCA / AFIP...")
    def on_consultar_clicked(self) -> None:
        tipo_codigo = self.cb_tipo.currentData()
        pto_vta = self.cb_pto_vta.currentData()

        if not tipo_codigo:
            popUp.warning(self, "Faltan datos", "Seleccioná un tipo de comprobante.")
            return
        if not pto_vta:
            popUp.warning(self, "Faltan datos", "Seleccioná un punto de venta.")
            return

        try:
            diag = self.service.diagnosticar_proximo_numero(
                tipo=str(tipo_codigo),
                pto_vta=pto_vta,
            )
        except Exception as e:
            popUp.critical(
                self,
                "Error",
                f"Ocurrió un error al consultar el próximo número.\n\n{e}",
            )
            return

        proximo = diag.get("proximo")
        origen = diag.get("origen") or "desconocido"
        ultimo_afip = diag.get("ultimo_afip")
        proximo_local = diag.get("proximo_local")
        ws_ok = diag.get("ws_ok", False)
        errores: List[str] = diag.get("errores") or []
        mensaje = diag.get("mensaje") or ""

        lineas: List[str] = []
        lineas.append(
            f"Tipo: {diag.get('tipo')} | Punto de venta: {str(diag.get('pto_vta')).zfill(4)}"
        )
        lineas.append(f"Próximo número sugerido: {proximo}")

        if origen == "AFIP":
            lineas.append("Origen: ARCA / AFIP (FECompUltimoAutorizado).")
        elif origen == "BD":
            lineas.append("Origen: base de datos local (no se pudo usar ARCA / AFIP).")
        else:
            lineas.append(f"Origen: {origen}")

        if ultimo_afip is not None:
            lineas.append(f"Último autorizado en AFIP: {ultimo_afip}")
        if proximo_local is not None and origen == "AFIP":
            lineas.append(f"Referencia local (próximo en BD): {proximo_local}")

        if errores:
            lineas.append("")
            lineas.append("Errores / detalles:")
            for err in errores:
                lineas.append(f"• {err}")

        if mensaje and not errores:
            lineas.append("")
            lineas.append(mensaje)

        self.lbl_result.setText("\n".join(lineas))

        # Popup corto para confirmar
        if ws_ok:
            popUp.info(
                self,
                "Consulta realizada",
                f"Próximo número sugerido: {proximo}\n\nOrigen: {origen}",
            )
        else:
            popUp.warning(
                self,
                "Consulta parcial",
                "No se pudo usar correctamente el WS de ARCA / AFIP.\n"
                "Se mostró la mejor información disponible.\n\n"
                + (mensaje or ""),
            )
