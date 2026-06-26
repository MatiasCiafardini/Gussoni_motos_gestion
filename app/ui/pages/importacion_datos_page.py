from __future__ import annotations
from typing import Any, Dict, List, Optional

from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QStandardPaths, QItemSelectionModel, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QHBoxLayout, QSizePolicy,
    QSpacerItem, QFileDialog, QListView, QDialog,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QApplication, QFrame, QSplitter,
    QScrollArea, QListWidget, QListWidgetItem, QProgressBar
)

import app.ui.app_message as popUp
from app.services.importacion_certificados_service import ImportacionCertificadosService
from app.services.importacion_datos_service import ImportacionDatosService
from app.ui.widgets.money_spinbox import MoneySpinBox


ACTION_LABELS = {
    "OMITIR": "Omitir",
    "CREAR": "Crear",
    "COMPLETAR_VACIOS": "Completar vacios",
    "ACTUALIZAR_DIFERENCIAS": "Actualizar diferencias",
}

ACTION_TOOLTIPS = {
    "OMITIR": "No hacer nada con esta fila.",
    "CREAR": "Crear un vehiculo nuevo con los datos del Excel.",
    "COMPLETAR_VACIOS": "Completar solo campos vacios del sistema con datos del Excel.",
    "ACTUALIZAR_DIFERENCIAS": "Actualizar los campos diferentes usando los datos del Excel.",
}


class ImportacionDatosPage(QWidget):
    SETTINGS_ADVANCED_DIR = "ImportacionDatosPage/advanced_last_dir"

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("ImportacionDatosPage")
        self.settings = QSettings("Gussoni", "SistemaFacturacion")

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

        self.btn_avanzada = QPushButton("Carga avanzada masiva")
        self.btn_avanzada.setObjectName("BtnPrimary")

        actions.addWidget(self.btn_descargar)
        actions.addWidget(self.btn_importar)
        actions.addWidget(self.btn_avanzada)
        actions.addStretch(1)

        root.addLayout(actions)

        root.addItem(QSpacerItem(0, 6, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # ---------------- Service ----------------
        self.service = ImportacionDatosService()
        self.certificados_service = ImportacionCertificadosService()

        # ---------------- Cargar tablas ----------------
        self._cargar_tablas()

        # ---------------- Signals ----------------
        self.combo_tablas.currentIndexChanged.connect(self._on_tabla_changed)
        self.btn_descargar.clicked.connect(self._descargar_plantilla)
        self.btn_importar.clicked.connect(self._importar_archivo)
        self.btn_avanzada.clicked.connect(self._carga_avanzada_masiva)

        # ---------------- QSS local ----------------
        self.setStyleSheet("""
        QLabel#CfgH1 {
            font-size: 1.8em;
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
            popUp.toast(
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
            popUp.toast(self, str(e))
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
            popUp.toast(
                self,
                f"Plantilla Excel de '{tabla}' descargada correctamente."
            )

        except Exception as e:
            popUp.toast(
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
            popUp.toast(
                self,
                f"No se pudo leer el archivo.\n\n{e}"
            )
            return

        try:
            result = self.service.importar_xlsx(tabla, file_bytes)
        except Exception as e:
            popUp.toast(
                self,
                f"Ocurrió un error inesperado.\n\n{e}"
            )
            return

        # ---------------- Resultado ----------------
        if result.get("success"):
            # Éxito -> toast corto
            popUp.toast(
                self,
                f"Importación exitosa.\nRegistros importados: {result.get('insertados', 0)}"
            )
        else:
            # Errores -> modal estático
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

    def _carga_avanzada_masiva(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Excel de certificados / stock",
            self._advanced_initial_dir(),
            "Excel (*.xlsx)"
        )

        if not path:
            return

        self.settings.setValue(self.SETTINGS_ADVANCED_DIR, str(Path(path).parent))

        try:
            with open(path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            popUp.error(self, "Carga avanzada", f"No se pudo leer el archivo.\n\n{e}")
            return

        loading = _LoadingDialog("Analizando Excel...", self)
        loading.show()
        QApplication.processEvents()
        try:
            preview = self.certificados_service.generar_preview(file_bytes)
        except Exception as e:
            loading.close()
            popUp.error(self, "Carga avanzada", f"No se pudo analizar el Excel.\n\n{e}")
            return
        finally:
            loading.close()

        dlg = ImportacionCertificadosPreviewDialog(
            file_bytes,
            preview.get("rows", []),
            preview.get("summary", {}),
            preview.get("errores", []),
            self.certificados_service,
            self,
        )
        dlg.exec()

    def _advanced_initial_dir(self) -> str:
        saved = self.settings.value(self.SETTINGS_ADVANCED_DIR, "")
        if saved and Path(str(saved)).exists():
            return str(saved)

        downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if downloads and Path(downloads).exists():
            return downloads

        return str(Path.home())


class _LoadingDialog(QDialog):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Procesando")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setFixedSize(430, 160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        self.title = QLabel(text)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.detail = QLabel("Esto puede tardar unos segundos si el archivo tiene muchas hojas.")
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setObjectName("CfgMuted")
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(True)

        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        layout.addWidget(self.progress)
        layout.addStretch(1)

    def set_progress(self, current: int, total: int, detail: str = "") -> None:
        total = max(int(total or 0), 0)
        current = max(0, min(int(current or 0), total if total else current))
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            self.progress.setFormat(f"{current}/{total}")
        else:
            self.progress.setRange(0, 0)
        if detail:
            self.detail.setText(detail)
        QApplication.processEvents()


class ImportacionCertificadosPreviewDialog(QDialog):
    def __init__(
        self,
        file_bytes: bytes,
        rows: List[Dict[str, Any]],
        summary: Dict[str, Any],
        errores: List[str],
        service: ImportacionCertificadosService,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Preview de carga avanzada masiva")
        self.resize(1360, 780)
        self.setMinimumSize(1050, 620)
        QTimer.singleShot(0, self._fit_to_screen_with_margins)
        self.file_bytes = file_bytes
        self.rows = rows
        self.visible_rows = rows
        self._estado_filter: Optional[str] = None
        self.service = service
        self._action_combos: Dict[int, QComboBox] = {}
        self._table_row_to_data_index: Dict[int, int] = {}
        self._current_review_row: Optional[int] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        lbl_title = QLabel("Carga avanzada masiva")
        lbl_title.setObjectName("CfgH1")
        lbl_subtitle = QLabel("Revisa coincidencias, diferencias y acciones antes de aplicar la importacion.")
        lbl_subtitle.setObjectName("CfgMuted")
        title_wrap.addWidget(lbl_title)
        title_wrap.addWidget(lbl_subtitle)
        header.addLayout(title_wrap)
        header.addStretch(1)
        root.addLayout(header)

        self.summary = summary
        self.errores = errores

        summary_panel = QFrame(self)
        summary_panel.setObjectName("ImportSummaryPanel")
        summary_layout = QVBoxLayout(summary_panel)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(8)

        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)
        self._filter_buttons: Dict[str, QPushButton] = {}
        for estado, label, key in (
            ("NUEVO", "Nuevos", "nuevos"),
            ("EXISTENTE_IGUAL", "Iguales", "existentes_iguales"),
            ("EXISTENTE_DIFERENCIAS", "Diferencias", "existentes_diferencias"),
            ("DUPLICADO_AMBIGUO", "Ambiguos", "ambiguos"),
            ("ERROR", "Errores", "errores"),
        ):
            btn = self._summary_button(estado, label, summary.get(key, 0))
            btn.clicked.connect(lambda _=False, e=estado: self._set_estado_filter(e))
            filter_bar.addWidget(btn)
            self._filter_buttons[estado] = btn

        self.btn_limpiar_filtro = QPushButton("Limpiar filtro")
        self.btn_limpiar_filtro.setObjectName("BtnGhost")
        self.btn_limpiar_filtro.clicked.connect(lambda: self._set_estado_filter(None))
        self.btn_limpiar_filtro.setEnabled(False)
        filter_bar.addWidget(self.btn_limpiar_filtro)
        filter_bar.addStretch(1)
        summary_layout.addLayout(filter_bar)

        self.progress_bar = QFrame(self)
        self.progress_bar.setObjectName("ImportProgressBar")
        self.progress_layout = QHBoxLayout(self.progress_bar)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(2)
        summary_layout.addWidget(self.progress_bar)

        self.lbl_summary = QLabel(self._summary_text(summary, errores))
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setObjectName("CfgMuted")
        summary_layout.addWidget(self.lbl_summary)
        root.addWidget(summary_panel)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        btn_select_visible = QPushButton("[ ] Seleccionar visibles")
        btn_select_visible.setObjectName("BtnGhost")
        btn_select_visible.setCursor(Qt.PointingHandCursor)
        btn_select_visible.clicked.connect(self._select_visible_rows)
        toolbar.addWidget(btn_select_visible)
        toolbar.addWidget(self._toolbar_button("↻ Actualizar diferencias", "ACTUALIZAR_DIFERENCIAS"))
        toolbar.addWidget(self._toolbar_button("+ Completar vacios", "COMPLETAR_VACIOS"))
        toolbar.addWidget(self._toolbar_button("- Omitir cambios", "OMITIR"))
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        table_panel = QFrame(self)
        table_panel.setObjectName("ReviewTablePanel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self.table = QTableWidget(0, 13, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels([
            "Hoja", "Fila", "Estado", "Coincidencia", "Marca", "Modelo",
            "Motor", "Cuadro", "DNRPA", "Certificado", "LCA",
            "Accion", "Diferencias",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setStretchLastSection(False)
        header_view.setMinimumSectionSize(56)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setColumnWidth(0, 78)
        self.table.setColumnWidth(1, 50)
        self.table.setColumnWidth(2, 126)
        self.table.setColumnWidth(3, 72)
        self.table.setColumnWidth(4, 92)
        self.table.setColumnWidth(5, 185)
        self.table.setColumnWidth(6, 170)
        self.table.setColumnWidth(7, 155)
        self.table.setColumnWidth(8, 138)
        self.table.setColumnWidth(9, 154)
        self.table.setColumnWidth(10, 150)
        self.table.setColumnWidth(11, 215)
        self.table.setColumnWidth(12, 210)
        header_view.setSectionResizeMode(11, QHeaderView.Fixed)
        header_view.setSectionResizeMode(12, QHeaderView.Stretch)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setMouseTracking(True)
        table_layout.addWidget(self.table)
        splitter.addWidget(table_panel)

        detail_panel = QFrame(self)
        detail_panel.setObjectName("ReviewSidePanel")
        detail_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(10)

        self.side_scroll = QScrollArea(self)
        self.side_scroll.setObjectName("RightPanelScroll")
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.NoFrame)
        self.side_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.side_scroll_content = QWidget(self.side_scroll)
        side_content_layout = QVBoxLayout(self.side_scroll_content)
        side_content_layout.setContentsMargins(0, 0, 0, 0)
        side_content_layout.setSpacing(10)

        self.lbl_detail_title = QLabel("Selecciona una fila para ver el detalle")
        self.lbl_detail_title.setStyleSheet("font-size: 17px; font-weight: 800;")
        self.lbl_detail_brand = QLabel("")
        self.lbl_detail_brand.setObjectName("CfgMuted")
        self.lbl_detail_hint = QLabel(
            "Aca se comparan los datos actuales del sistema contra lo que trae el Excel."
        )
        self.lbl_detail_hint.setObjectName("CfgMuted")
        self.lbl_detail_hint.setWordWrap(True)

        side_content_layout.addWidget(self.lbl_detail_title)
        side_content_layout.addWidget(self.lbl_detail_brand)
        side_content_layout.addWidget(self.lbl_detail_hint)

        self.side_meta = QLabel("")
        self.side_meta.setObjectName("ImportMeta")
        self.side_meta.setWordWrap(True)
        side_content_layout.addWidget(self.side_meta)

        self.side_diff_header = QLabel("Diferencias detectadas")
        self.side_diff_header.setObjectName("SideSectionTitle")
        side_content_layout.addWidget(self.side_diff_header)

        self.side_diff_content = QWidget(self.side_scroll_content)
        self.side_diff_layout = QVBoxLayout(self.side_diff_content)
        self.side_diff_layout.setContentsMargins(0, 0, 0, 0)
        self.side_diff_layout.setSpacing(8)
        side_content_layout.addWidget(self.side_diff_content)
        self.side_scroll.setWidget(self.side_scroll_content)
        detail_layout.addWidget(self.side_scroll, 1)

        self.side_action_label = QLabel("Accion para esta fila")
        self.side_action_label.setObjectName("CfgMuted")
        self.side_action_combo = QComboBox(self)
        self.side_action_combo.setMinimumHeight(34)
        self.side_action_combo.currentIndexChanged.connect(self._on_side_action_changed)
        side_content_layout.addWidget(self.side_action_label)
        side_content_layout.addWidget(self.side_action_combo)
        side_content_layout.addStretch(1)

        splitter.addWidget(detail_panel)
        splitter.setSizes([875, 485])
        root.addWidget(splitter, 1)

        btns = QHBoxLayout()
        self.btn_colores = QPushButton("Agregar colores faltantes")
        self.btn_colores.setObjectName("BtnGhost")
        self.btn_aplicar = QPushButton("Aplicar importacion")
        self.btn_aplicar.setObjectName("BtnPrimary")
        self.lbl_apply_hint = QLabel("")
        self.lbl_apply_hint.setObjectName("CfgMuted")
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setObjectName("BtnGhost")
        btns.addWidget(self.btn_colores)
        btns.addStretch(1)
        btns.addWidget(self.lbl_apply_hint)
        btns.addWidget(self.btn_aplicar)
        btns.addWidget(self.btn_cerrar)
        btns.setContentsMargins(0, 4, 0, 0)
        root.addLayout(btns)

        self.table.currentCellChanged.connect(self._on_current_row_changed)
        self.btn_colores.clicked.connect(self._agregar_colores_faltantes)
        self.btn_aplicar.clicked.connect(self._aplicar)
        self.btn_cerrar.clicked.connect(self.reject)

        self._populate()
        self._update_color_button()
        self._refresh_progress()
        self._refresh_apply_hint()
        self._apply_dialog_styles()
        if self.rows:
            self.table.setCurrentCell(0, 0)

    def _fit_to_screen_with_margins(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            return

        margin = 18
        available = screen.availableGeometry()
        target = available.adjusted(margin, margin, -margin, -margin)

        frame_extra_w = max(0, self.frameGeometry().width() - self.geometry().width())
        frame_extra_h = max(0, self.frameGeometry().height() - self.geometry().height())

        fit_min_width = max(900, min(self.minimumWidth(), target.width() - frame_extra_w))
        fit_min_height = max(540, min(self.minimumHeight(), target.height() - frame_extra_h))
        self.setMinimumSize(fit_min_width, fit_min_height)

        width = max(fit_min_width, target.width() - frame_extra_w)
        height = max(fit_min_height, target.height() - frame_extra_h)
        width = min(width, target.width())
        height = min(height, target.height())

        self.setWindowState(Qt.WindowNoState)
        self.resize(width, height)

        frame = self.frameGeometry()
        self.move(self.pos() + (target.topLeft() - frame.topLeft()))

    def _summary_button(self, estado: str, label: str, count: int) -> QPushButton:
        btn = QPushButton(f"{label}  {count}")
        btn.setProperty("estado", estado)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(f"{label}: {count}")
        btn.setMinimumHeight(54)
        btn.setMinimumWidth(142)
        return btn

    def _toolbar_button(self, text: str, action: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("BtnGhost")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(36)
        btn.clicked.connect(lambda _=False, a=action: self._bulk_set_action(a))
        return btn

    def _bulk_set_action(self, action: str) -> None:
        for table_row in range(self.table.rowCount()):
            if self.table.isRowHidden(table_row):
                continue
            combo = self._action_combos.get(table_row)
            if not combo:
                continue
            idx = combo.findData(action)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._refresh_apply_hint()
        current = self.table.currentRow()
        if current >= 0:
            self._show_detail(current)

    def _select_visible_rows(self) -> None:
        self.table.clearSelection()
        first = self._first_visible_row()
        if first is not None:
            self.table.setCurrentCell(first, 0)
        selection_model = self.table.selectionModel()
        for table_row in range(self.table.rowCount()):
            if self.table.isRowHidden(table_row):
                continue
            index = self.table.model().index(table_row, 0)
            selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def _refresh_progress(self) -> None:
        while self.progress_layout.count():
            item = self.progress_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        segments = [
            ("NUEVO", "Nuevos", self.summary.get("nuevos", 0)),
            ("EXISTENTE_IGUAL", "Iguales", self.summary.get("existentes_iguales", 0)),
            ("EXISTENTE_DIFERENCIAS", "Diferencias", self.summary.get("existentes_diferencias", 0)),
            ("ERROR", "Errores", self.summary.get("errores", 0)),
        ]
        for estado, label, count in segments:
            if count <= 0:
                continue
            seg = QFrame(self.progress_bar)
            seg.setProperty("estado", estado)
            seg.setToolTip(f"{label}: {count}")
            seg.setFixedHeight(8)
            self.progress_layout.addWidget(seg, int(count))

    def _refresh_apply_hint(self) -> None:
        counts = self._action_counts()
        self.lbl_apply_hint.setTextFormat(Qt.RichText)
        self.lbl_apply_hint.setText(
            f"<span style='background-color:#F0FDF4; color:#166534; font-weight:700;'>&nbsp;{counts.get('CREAR', 0)} nuevos&nbsp;</span>"
            f"&nbsp;&nbsp;<span style='background-color:#FFF7ED; color:#9A3412; font-weight:700;'>&nbsp;{counts.get('ACTUALIZAR_DIFERENCIAS', 0)} actualizaciones&nbsp;</span>"
            f"&nbsp;&nbsp;<span style='background-color:#F0F9FF; color:#075985; font-weight:700;'>&nbsp;{counts.get('COMPLETAR_VACIOS', 0)} completar vacios&nbsp;</span>"
            f"&nbsp;&nbsp;<span style='background-color:#FEF2F2; color:#991B1B; font-weight:700;'>&nbsp;{self.summary.get('errores', 0)} errores&nbsp;</span>"
        )

    def _clear_side_diffs(self) -> None:
        while self.side_diff_layout.count():
            item = self.side_diff_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _diff_card(self, label: str, before: str, after: str) -> QWidget:
        card = QFrame(self.side_diff_content)
        card.setObjectName("DiffCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel(label)
        title.setObjectName("DiffTitle")
        before_lbl = QLabel(f"<b>Sistema actual</b><br>{self._html(before)}")
        before_lbl.setObjectName("DiffBefore")
        before_lbl.setWordWrap(True)
        before_lbl.setTextFormat(Qt.RichText)
        arrow = QLabel("↓")
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setObjectName("DiffArrow")
        after_lbl = QLabel(f"<b>Excel</b><br>{self._html(after)}")
        after_lbl.setObjectName("DiffAfter")
        after_lbl.setWordWrap(True)
        after_lbl.setTextFormat(Qt.RichText)

        layout.addWidget(title)
        layout.addWidget(before_lbl)
        layout.addWidget(arrow)
        layout.addWidget(after_lbl)
        return card

    def _empty_detail_card(self, text: str) -> QWidget:
        card = QFrame(self.side_diff_content)
        card.setObjectName("EmptyDetailCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        lbl = QLabel(text)
        lbl.setObjectName("CfgMuted")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        return card

    def _missing_price_card(self, table_row: int, row_data: Dict[str, Any]) -> QWidget:
        card = QFrame(self.side_diff_content)
        card.setObjectName("DiffCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("Completar precio lista")
        title.setObjectName("DiffTitle")
        hint = QLabel("Esta moto puede crearse cuando cargues el precio que corresponde.")
        hint.setObjectName("CfgMuted")
        hint.setWordWrap(True)

        price = MoneySpinBox(card)
        price.setMinimumHeight(36)
        price.setValue(float((row_data.get("payload") or {}).get("precio_lista") or 0))

        btn = QPushButton("Usar este precio")
        btn.setObjectName("BtnPrimary")
        btn.clicked.connect(lambda _=False, r=table_row, w=price: self._apply_missing_price(r, w.value()))

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(price)
        layout.addWidget(btn)
        return card

    def _missing_color_card(self, table_row: int, row_data: Dict[str, Any]) -> QWidget:
        card = QFrame(self.side_diff_content)
        card.setObjectName("DiffCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("Completar color")
        title.setObjectName("DiffTitle")
        hint = QLabel("Elegí el color correcto para que la moto pueda crearse.")
        hint.setObjectName("CfgMuted")
        hint.setWordWrap(True)

        color_list = QListWidget(card)
        color_list.setObjectName("ImportColorList")
        color_list.setMaximumHeight(170)
        color_list.setMinimumHeight(118)
        for color in self.service._catalogos.get_colores():
            item = QListWidgetItem(str(color.get("nombre") or ""))
            item.setData(Qt.UserRole, color.get("id"))
            color_list.addItem(item)
        if color_list.count():
            color_list.setCurrentRow(0)

        btn = QPushButton("Usar este color")
        btn.setObjectName("BtnPrimary")
        btn.clicked.connect(
            lambda _=False, r=table_row, w=color_list: self._apply_missing_color_from_list(r, w)
        )

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(color_list)
        layout.addWidget(btn)
        return card

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SideSectionTitle")
        return lbl

    def _html(self, value: Any) -> str:
        return escape(str(value or ""), quote=True)

    def _can_fix_missing_price(self, row_data: Dict[str, Any]) -> bool:
        payload = row_data.get("payload") or {}
        message = str(row_data.get("mensaje") or "")
        return (
            row_data.get("estado") == "ERROR"
            and self._empty_label(payload.get("precio_lista")) == "(vacio)"
            and "Precio lista" in message
        )

    def _can_fix_missing_color(self, row_data: Dict[str, Any]) -> bool:
        payload = row_data.get("payload") or {}
        message = str(row_data.get("mensaje") or "")
        excel_color = (row_data.get("excel") or {}).get("color_nombre")
        return (
            row_data.get("estado") == "ERROR"
            and self._empty_label(payload.get("color_id")) == "(vacio)"
            and "Color" in message
            and not excel_color
        )

    def _apply_missing_price(self, table_row: int, value: float) -> None:
        if value <= 0:
            popUp.warning(self, "Precio lista", "El precio lista debe ser mayor a 0.")
            return

        data_index = self._table_row_to_data_index.get(table_row)
        if data_index is None or data_index >= len(self.rows):
            return

        row_data = self.rows[data_index]
        payload = row_data.get("payload") or {}
        excel = row_data.get("excel") or {}
        payload["precio_lista"] = float(value)
        excel["precio_lista"] = float(value)
        row_data["payload"] = payload
        row_data["excel"] = excel

        self._refresh_row_after_manual_fix(table_row, row_data)

    def _apply_missing_color(self, table_row: int, color_id: Any) -> None:
        if not color_id:
            popUp.warning(self, "Color", "Elegí un color para continuar.")
            return

        data_index = self._table_row_to_data_index.get(table_row)
        if data_index is None or data_index >= len(self.rows):
            return

        row_data = self.rows[data_index]
        payload = row_data.get("payload") or {}
        excel = row_data.get("excel") or {}
        payload["color_id"] = int(color_id)
        excel["color_id"] = int(color_id)

        color_name = ""
        for color in self.service._catalogos.get_colores():
            if int(color.get("id") or 0) == int(color_id):
                color_name = str(color.get("nombre") or "")
                break
        if color_name:
            excel["color_nombre"] = color_name

        row_data["payload"] = payload
        row_data["excel"] = excel
        self._refresh_row_after_manual_fix(table_row, row_data)

    def _apply_missing_color_from_list(self, table_row: int, color_list: QListWidget) -> None:
        item = color_list.currentItem()
        color_id = item.data(Qt.UserRole) if item else None
        self._apply_missing_color(table_row, color_id)

    def _refresh_row_after_manual_fix(self, table_row: int, row_data: Dict[str, Any]) -> None:
        payload = row_data.get("payload") or {}
        remaining = self.service._create_payload_errors(payload, row_data)
        if remaining:
            row_data.update({
                "estado": "ERROR",
                "accion_sugerida": "OMITIR",
                "accion": "OMITIR",
                "mensaje": "; ".join(remaining),
            })
        else:
            row_data.update({
                "estado": "NUEVO",
                "accion_sugerida": "CREAR",
                "accion": "CREAR",
                "mensaje": "Precio lista completado en preview.",
                "diferencias": [],
            })

        self._recalculate_summary()
        self._refresh_filter_buttons()
        self._refresh_progress()
        self._populate()

        next_row = min(table_row, max(0, self.table.rowCount() - 1))
        if self._estado_filter:
            next_row = self._first_visible_row() if self._first_visible_row() is not None else -1
        if next_row >= 0:
            self.table.setCurrentCell(next_row, 0)
            self._show_detail(next_row)
        self._refresh_apply_hint()

    def _recalculate_summary(self) -> None:
        self.summary = {
            "total": len(self.rows),
            "nuevos": sum(1 for r in self.rows if r.get("estado") == "NUEVO"),
            "existentes_iguales": sum(1 for r in self.rows if r.get("estado") == "EXISTENTE_IGUAL"),
            "existentes_diferencias": sum(1 for r in self.rows if r.get("estado") == "EXISTENTE_DIFERENCIAS"),
            "ambiguos": sum(1 for r in self.rows if r.get("estado") == "DUPLICADO_AMBIGUO"),
            "errores": sum(1 for r in self.rows if r.get("estado") == "ERROR"),
        }
        self.lbl_summary.setText(self._summary_text(self.summary, self.errores))

    def _status_badge(self, estado: Optional[str]) -> str:
        return {
            "NUEVO": "Nuevo",
            "EXISTENTE_IGUAL": "Igual",
            "EXISTENTE_DIFERENCIAS": "Diferencias",
            "DUPLICADO_AMBIGUO": "Ambiguo",
            "ERROR": "Error",
        }.get(str(estado or ""), str(estado or ""))

    def _row_tint(self, estado: Optional[str]) -> QColor:
        return {
            "NUEVO": QColor("#F0FDF4"),
            "EXISTENTE_IGUAL": QColor("#F8FAFC"),
            "EXISTENTE_DIFERENCIAS": QColor("#FFF7ED"),
            "DUPLICADO_AMBIGUO": QColor("#F5F3FF"),
            "ERROR": QColor("#FEF2F2"),
        }.get(str(estado or ""), QColor("#FFFFFF"))

    def _status_color(self, estado: Optional[str]) -> QColor:
        return {
            "NUEVO": QColor("#166534"),
            "EXISTENTE_IGUAL": QColor("#334155"),
            "EXISTENTE_DIFERENCIAS": QColor("#9A3412"),
            "DUPLICADO_AMBIGUO": QColor("#5B21B6"),
            "ERROR": QColor("#991B1B"),
        }.get(str(estado or ""), QColor("#111827"))

    def _decorate_table_item(self, item: QTableWidgetItem, row_data: Dict[str, Any], col: int) -> None:
        estado = row_data.get("estado")
        item.setBackground(self._row_tint(estado))
        if col == 2:
            item.setForeground(self._status_color(estado))
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        elif col == 12 and (row_data.get("diferencias") or estado == "ERROR"):
            item.setForeground(self._status_color(estado))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

    def _populate_side_action(self, table_row: int) -> None:
        combo = self._action_combos.get(table_row)
        self.side_action_combo.blockSignals(True)
        self.side_action_combo.clear()
        if combo:
            for idx in range(combo.count()):
                self.side_action_combo.addItem(combo.itemText(idx), combo.itemData(idx))
            self.side_action_combo.setCurrentIndex(combo.currentIndex())
            self.side_action_combo.setEnabled(True)
            self.side_action_combo.setToolTip(ACTION_TOOLTIPS.get(combo.currentData(), ""))
            self.side_action_combo.setProperty("accion", combo.currentData())
        else:
            self.side_action_combo.setEnabled(False)
            self.side_action_combo.setProperty("accion", "OMITIR")
        self.side_action_combo.style().unpolish(self.side_action_combo)
        self.side_action_combo.style().polish(self.side_action_combo)
        self.side_action_combo.blockSignals(False)

    def _sync_side_action(self, action: str) -> None:
        self.side_action_combo.blockSignals(True)
        idx = self.side_action_combo.findData(action)
        if idx >= 0:
            self.side_action_combo.setCurrentIndex(idx)
        self.side_action_combo.setToolTip(ACTION_TOOLTIPS.get(action, ""))
        self.side_action_combo.setProperty("accion", action)
        self.side_action_combo.style().unpolish(self.side_action_combo)
        self.side_action_combo.style().polish(self.side_action_combo)
        self.side_action_combo.blockSignals(False)

    def _on_side_action_changed(self, _idx: int) -> None:
        table_row = self.table.currentRow()
        combo = self._action_combos.get(table_row)
        if not combo:
            return
        action = self.side_action_combo.currentData()
        idx = combo.findData(action)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _apply_dialog_styles(self) -> None:
        self.setStyleSheet(
            self.styleSheet()
            + """
            QFrame#ImportSummaryPanel,
            QFrame#ReviewSidePanel,
            QFrame#ReviewTablePanel {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background: #FFFFFF;
            }
            QTableWidget#DataTable {
                gridline-color: #E5E7EB;
                alternate-background-color: #F8FAFC;
                selection-background-color: #EAF2FF;
                selection-color: #0F172A;
                border: 0;
                font-size: 12px;
            }
            QTableWidget#DataTable::item {
                padding: 8px 10px;
                border: 0;
            }
            QTableWidget#DataTable::item:hover {
                background: #EEF2FF;
            }
            QScrollArea#RightPanelScroll {
                border: 0;
                background: transparent;
            }
            QScrollArea#RightPanelScroll QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: #F8FAFC;
                width: 10px;
                margin: 2px 2px 2px 2px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                min-height: 34px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                border: 0;
                background: transparent;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: #F8FAFC;
                height: 10px;
                margin: 2px 2px 2px 2px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #CBD5E1;
                min-width: 34px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
                border: 0;
                background: transparent;
            }
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            QListWidget#ImportColorList {
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                background: #FFFFFF;
                padding: 4px;
                outline: 0;
            }
            QListWidget#ImportColorList::item {
                min-height: 30px;
                padding: 6px 10px;
                border-radius: 6px;
                color: #0F172A;
            }
            QListWidget#ImportColorList::item:hover {
                background: #F1F5F9;
            }
            QListWidget#ImportColorList::item:selected {
                background: #EEF2FF;
                color: #3730A3;
                font-weight: 700;
            }
            QHeaderView::section {
                background: #181827;
                color: #FFFFFF;
                border: 0;
                border-right: 1px solid #2A2A3A;
                padding: 9px 10px;
                font-weight: 700;
            }
            QComboBox#ImportActionCombo,
            QFrame#ReviewSidePanel QComboBox {
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                background: #FFFFFF;
                padding: 6px 30px 6px 10px;
                color: #0F172A;
                font-weight: 600;
            }
            QComboBox#ImportActionCombo::drop-down,
            QFrame#ReviewSidePanel QComboBox::drop-down {
                width: 26px;
                border: 0;
            }
            QPushButton#BtnGhost {
                min-height: 34px;
            }
            QComboBox[accion="CREAR"] {
                border-color: #86EFAC;
                background: #F0FDF4;
                color: #166534;
            }
            QComboBox[accion="COMPLETAR_VACIOS"] {
                border-color: #BAE6FD;
                background: #F0F9FF;
                color: #075985;
            }
            QComboBox[accion="ACTUALIZAR_DIFERENCIAS"] {
                border-color: #FDBA74;
                background: #FFF7ED;
                color: #9A3412;
            }
            QComboBox[accion="OMITIR"] {
                border-color: #CBD5E1;
                background: #F8FAFC;
                color: #475569;
            }
            QPushButton[estado="NUEVO"] {
                border: 1px solid #B7E4C7;
                background: #F0FDF4;
                color: #166534;
                border-radius: 8px;
                text-align: left;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton[estado="EXISTENTE_IGUAL"] {
                border: 1px solid #CBD5E1;
                background: #F8FAFC;
                color: #334155;
                border-radius: 8px;
                text-align: left;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton[estado="EXISTENTE_DIFERENCIAS"] {
                border: 1px solid #FED7AA;
                background: #FFF7ED;
                color: #9A3412;
                border-radius: 8px;
                text-align: left;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton[estado="DUPLICADO_AMBIGUO"] {
                border: 1px solid #DDD6FE;
                background: #F5F3FF;
                color: #5B21B6;
                border-radius: 8px;
                text-align: left;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton[estado="ERROR"] {
                border: 1px solid #FECACA;
                background: #FEF2F2;
                color: #991B1B;
                border-radius: 8px;
                text-align: left;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 13px;
            }
            QFrame#ImportProgressBar {
                border: 0;
                background: transparent;
                min-height: 8px;
                max-height: 8px;
            }
            QFrame#ImportProgressBar QFrame {
                border-radius: 4px;
            }
            QFrame#ImportProgressBar QFrame[estado="NUEVO"] { background: #22C55E; }
            QFrame#ImportProgressBar QFrame[estado="EXISTENTE_IGUAL"] { background: #94A3B8; }
            QFrame#ImportProgressBar QFrame[estado="EXISTENTE_DIFERENCIAS"] { background: #F97316; }
            QFrame#ImportProgressBar QFrame[estado="ERROR"] { background: #EF4444; }
            QFrame#DiffCard {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background: #FFFFFF;
            }
            QLabel#DiffTitle {
                color: #0F172A;
                font-size: 13px;
                font-weight: 800;
            }
            QLabel#SideSectionTitle {
                color: #0F172A;
                font-size: 13px;
                font-weight: 800;
                padding: 6px 0 2px 0;
            }
            QLabel#DiffArrow {
                color: #94A3B8;
                font-weight: 700;
            }
            QLabel#DiffBefore {
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background: #F8FAFC;
                padding: 8px;
                color: #475569;
            }
            QLabel#DiffAfter {
                border: 1px solid #FED7AA;
                border-radius: 6px;
                background: #FFF7ED;
                padding: 8px;
                color: #9A3412;
                font-weight: 600;
            }
            QFrame#EmptyDetailCard {
                border: 1px dashed #CBD5E1;
                border-radius: 8px;
                background: #F8FAFC;
            }
            QLabel#ImportMeta {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background: #F8FAFC;
                padding: 8px;
                color: #334155;
            }
            """
        )

    def _populate(self) -> None:
        self.table.setRowCount(0)
        self._action_combos.clear()
        self._table_row_to_data_index.clear()
        self.visible_rows = self.rows

        for data_index, row_data in enumerate(self.rows):
            payload = row_data.get("payload") or {}
            existing = row_data.get("existing") or {}

            row = self.table.rowCount()
            self.table.insertRow(row)

            values = [
                row_data.get("hoja", ""),
                row_data.get("fila", ""),
                self._status_badge(row_data.get("estado")),
                existing.get("id", ""),
                payload.get("marca", ""),
                payload.get("modelo", ""),
                payload.get("numero_motor", ""),
                payload.get("numero_cuadro", ""),
                payload.get("nro_dnrpa", ""),
                payload.get("nro_certificado", ""),
                payload.get("lca", ""),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.UserRole, str(value or ""))
                if col in (1, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                self._decorate_table_item(item, row_data, col)
                self.table.setItem(row, col, item)

            combo = QComboBox(self)
            combo.setObjectName("ImportActionCombo")
            combo.setMinimumWidth(200)
            combo.setMinimumHeight(34)
            combo.addItem(ACTION_LABELS["OMITIR"], "OMITIR")
            if row_data.get("estado") == "NUEVO" or not row_data.get("existing"):
                combo.addItem(ACTION_LABELS["CREAR"], "CREAR")
            if row_data.get("existing"):
                combo.addItem(ACTION_LABELS["COMPLETAR_VACIOS"], "COMPLETAR_VACIOS")
                combo.addItem(ACTION_LABELS["ACTUALIZAR_DIFERENCIAS"], "ACTUALIZAR_DIFERENCIAS")

            suggested = row_data.get("accion_sugerida") or "OMITIR"
            combo_idx = combo.findData(suggested)
            combo.setCurrentIndex(combo_idx if combo_idx >= 0 else 0)
            combo.setToolTip(ACTION_TOOLTIPS.get(combo.currentData(), ""))
            combo.currentIndexChanged.connect(lambda _i, r=row: self._sync_action(r))
            self.table.setCellWidget(row, 11, combo)
            self._action_combos[row] = combo
            self._table_row_to_data_index[row] = data_index
            self._sync_action(row)

            diff_item = QTableWidgetItem(self._diff_summary(row_data))
            self._decorate_table_item(diff_item, row_data, 12)
            diff_item.setToolTip(self._diff_tooltip(row_data))
            self.table.setItem(row, 12, diff_item)

        self._apply_estado_filter()
        self._update_color_button()

    def _on_current_row_changed(self, row: int, *_args) -> None:
        self._highlight_selected_row(row)
        self._show_detail(row)

    def _highlight_selected_row(self, row: int) -> None:
        previous = self._current_review_row
        self._current_review_row = row if row >= 0 else None
        for table_row in {previous, self._current_review_row}:
            if table_row is None or table_row < 0 or table_row >= self.table.rowCount():
                continue
            data_index = self._table_row_to_data_index.get(table_row)
            row_data = self.rows[data_index] if data_index is not None and data_index < len(self.rows) else {}
            for col in range(self.table.columnCount()):
                item = self.table.item(table_row, col)
                if not item:
                    continue
                base_text = item.data(Qt.UserRole)
                if base_text is not None:
                    item.setText(str(base_text))
                item.setBackground(self._row_tint(row_data.get("estado")))
                if col in (2, 12):
                    item.setForeground(self._status_color(row_data.get("estado")))
                else:
                    item.setForeground(QColor("#0F172A"))
        if row < 0 or row >= self.table.rowCount():
            return
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if not item:
                continue
            item.setBackground(QColor("#EAF2FF"))
        first = self.table.item(row, 0)
        if first:
            base_text = first.data(Qt.UserRole) or first.text()
            first.setText(f"| {base_text}")
            first.setForeground(QColor("#2563EB"))

    def _sync_action(self, row: int) -> None:
        combo = self._action_combos.get(row)
        data_index = self._table_row_to_data_index.get(row)
        if not combo or data_index is None or data_index >= len(self.rows):
            return
        self.rows[data_index]["accion"] = combo.currentData()
        combo.setToolTip(ACTION_TOOLTIPS.get(combo.currentData(), ""))
        combo.setProperty("accion", combo.currentData())
        combo.style().unpolish(combo)
        combo.style().polish(combo)
        if self.table.currentRow() == row:
            self._sync_side_action(combo.currentData())
        self._refresh_apply_hint()

    def _show_detail(self, row: int) -> None:
        data_index = self._table_row_to_data_index.get(row)
        if row < 0 or data_index is None or data_index >= len(self.rows) or self.table.isRowHidden(row):
            self.lbl_detail_title.setText("Selecciona una fila para ver el detalle")
            self.lbl_detail_brand.setText("")
            self.lbl_detail_hint.setText("Aca se comparan los datos actuales del sistema contra lo que trae el Excel.")
            self.side_meta.setText("")
            self.side_diff_header.setText("Diferencias detectadas")
            self._clear_side_diffs()
            self.side_action_combo.blockSignals(True)
            self.side_action_combo.clear()
            self.side_action_combo.blockSignals(False)
            return

        data = self.rows[data_index]
        diffs = data.get("diferencias") or []
        payload = data.get("payload") or {}
        self.lbl_detail_title.setText(
            f"{payload.get('modelo') or 'Sin modelo'}"
        )
        self.lbl_detail_brand.setText(
            f"{payload.get('marca') or 'Sin marca'} - Hoja {data.get('hoja')} - fila {data.get('fila')}"
        )
        self.side_meta.setTextFormat(Qt.RichText)
        self.side_meta.setText(
            "<table width='100%' cellspacing='0' cellpadding='3'>"
            f"<tr><td><b>Estado</b></td><td>{self._html(self._estado_label(data.get('estado')))}</td></tr>"
            f"<tr><td><b>Motor</b></td><td>{self._html(payload.get('numero_motor') or '(vacio)')}</td></tr>"
            f"<tr><td><b>Cuadro</b></td><td>{self._html(payload.get('numero_cuadro') or '(vacio)')}</td></tr>"
            f"<tr><td><b>Certificado</b></td><td>{self._html(payload.get('nro_certificado') or '(vacio)')}</td></tr>"
            f"<tr><td><b>DNRPA</b></td><td>{self._html(payload.get('nro_dnrpa') or '(vacio)')}</td></tr>"
            "</table>"
        )

        self._clear_side_diffs()
        if data.get("estado") == "ERROR":
            message = data.get("mensaje") or "Esta fila no puede importarse hasta corregir el dato indicado."
            self.lbl_detail_hint.setText("Error de validacion. Esta fila queda separada de las diferencias.")
            self.side_diff_header.setText("Error detectado")
            self.side_diff_layout.addWidget(self._empty_detail_card(message))
            if self._can_fix_missing_price(data):
                self.side_diff_layout.addWidget(self._missing_price_card(row, data))
            if self._can_fix_missing_color(data):
                self.side_diff_layout.addWidget(self._missing_color_card(row, data))
        elif diffs:
            self.lbl_detail_hint.setText(
                f"{len(diffs)} diferencia(s) detectada(s). Revisa antes y despues, y ajusta la accion si hace falta."
            )
            self.side_diff_header.setText(f"Diferencias detectadas ({len(diffs)})")
            for diff in diffs:
                sistema, excel = self._display_diff_values(data, diff)
                self.side_diff_layout.addWidget(
                    self._diff_card(diff.get("label") or diff.get("campo") or "", sistema, excel)
                )
        else:
            if data.get("estado") == "EXISTENTE_DIFERENCIAS":
                message = "Esta fila figura con diferencias pero no se recibieron datos de comparacion."
            else:
                message = data.get("mensaje") or "No se detectaron diferencias para esta fila."
            self.lbl_detail_hint.setText(message)
            self.side_diff_header.setText("Diferencias detectadas (0)")
            self.side_diff_layout.addWidget(self._empty_detail_card(message))

        self._populate_side_action(row)

    def _display_diff_values(self, row_data: Dict[str, Any], diff: Dict[str, Any]) -> tuple[str, str]:
        field = diff.get("campo")
        if field == "color_id":
            existing = row_data.get("existing") or {}
            excel = row_data.get("excel") or {}
            return (
                self._empty_label(existing.get("color_nombre") or diff.get("sistema")),
                self._empty_label(excel.get("color_nombre") or diff.get("excel")),
            )
        return (
            self._empty_label(diff.get("sistema")),
            self._empty_label(diff.get("excel")),
        )

    def _empty_label(self, value: Any) -> str:
        text = str(value or "").strip()
        return text if text else "(vacio)"

    def _set_estado_filter(self, estado: Optional[str]) -> None:
        self._estado_filter = estado
        self.btn_limpiar_filtro.setEnabled(estado is not None)
        self._apply_estado_filter()
        self.lbl_summary.setText(self._summary_text(self.summary, self.errores))
        first = self._first_visible_row()
        if first is not None:
            self.table.setCurrentCell(first, 0)
            self._show_detail(first)
        else:
            self.lbl_detail_title.setText("Sin filas para este filtro")
            self.lbl_detail_brand.setText("")
            self.lbl_detail_hint.setText("Usa Limpiar filtro para volver a ver todas las filas.")
            self.side_meta.setText("")
            self.side_diff_header.setText("Diferencias detectadas")
            self._clear_side_diffs()

    def _apply_estado_filter(self) -> None:
        visible = []
        self.table.setUpdatesEnabled(False)
        try:
            for table_row in range(self.table.rowCount()):
                data_index = self._table_row_to_data_index.get(table_row)
                row_data = self.rows[data_index] if data_index is not None and data_index < len(self.rows) else {}
                hidden = self._estado_filter is not None and row_data.get("estado") != self._estado_filter
                self.table.setRowHidden(table_row, hidden)
                if not hidden:
                    visible.append(row_data)
        finally:
            self.table.setUpdatesEnabled(True)
        self.visible_rows = visible

    def _first_visible_row(self) -> Optional[int]:
        for table_row in range(self.table.rowCount()):
            if not self.table.isRowHidden(table_row):
                return table_row
        return None

    def _update_color_button(self) -> None:
        missing = self.service.colores_faltantes(self.rows)
        self.btn_colores.setEnabled(bool(missing))
        self.btn_colores.setToolTip(", ".join(missing[:10]) if missing else "")

    def _agregar_colores_faltantes(self) -> None:
        missing = self.service.colores_faltantes(self.rows)
        if not missing:
            popUp.info(self, "Colores", "No hay colores faltantes para agregar.")
            return

        preview = ", ".join(missing[:12])
        if len(missing) > 12:
            preview += f" y {len(missing) - 12} mas"

        if not popUp.confirm(
            self,
            "Agregar colores faltantes",
            f"Se agregaran estos colores al catalogo:\n\n{preview}",
            ok_text="Agregar",
            cancel_text="Cancelar",
        ):
            return

        loading = _LoadingDialog("Actualizando catalogo y recalculando preview...", self)
        loading.show()
        QApplication.processEvents()
        try:
            result = self.service.crear_colores_faltantes(missing)
            refreshed = self.service.generar_preview(self.file_bytes)
        except Exception as e:
            loading.close()
            popUp.error(self, "Colores", f"No se pudieron agregar los colores.\n\n{e}")
            return
        finally:
            loading.close()

        self.rows = refreshed.get("rows", [])
        self.visible_rows = self.rows
        self._estado_filter = None
        self.summary = refreshed.get("summary", {})
        self.errores = refreshed.get("errores", [])
        self.lbl_summary.setText(
            self._summary_text(self.summary, self.errores)
        )
        self._refresh_filter_buttons()
        self._populate()
        if self.rows:
            self.table.setCurrentCell(0, 0)

        popUp.info(
            self,
            "Colores",
            f"Colores creados: {len(result.get('creados', []))}\n"
            f"Ya existentes: {len(result.get('existentes', []))}\n\n"
            "La preview fue recalculada.",
        )

    def _aplicar(self) -> None:
        selected = [row for row in self.rows if row.get("accion") and row.get("accion") != "OMITIR"]
        if not selected:
            popUp.warning(self, "Carga avanzada", "No hay acciones para aplicar.")
            return

        missing_colors = self.service.colores_faltantes(selected)
        action_counts = self._action_counts()
        action_detail = (
            f"\n\nDetalle de acciones:\n"
            f"- Crear nuevos: {action_counts.get('CREAR', 0)}\n"
            f"- Completar campos vacios: {action_counts.get('COMPLETAR_VACIOS', 0)}\n"
            f"- Actualizar diferencias: {action_counts.get('ACTUALIZAR_DIFERENCIAS', 0)}\n"
            f"- Omitir: {action_counts.get('OMITIR', 0)}"
        )
        extra = ""
        if missing_colors:
            preview = ", ".join(missing_colors[:12])
            if len(missing_colors) > 12:
                preview += f" y {len(missing_colors) - 12} mas"
            extra = (
                "\n\nTambien se agregaran al catalogo estos colores faltantes:\n"
                f"{preview}"
            )

        if not popUp.confirm(
            self,
            "Aplicar carga avanzada",
            f"Se aplicaran {len(selected)} accion(es). No se borrara ningun dato."
            f"{action_detail}{extra}",
            ok_text="Aplicar",
            cancel_text="Revisar",
        ):
            return

        loading = _LoadingDialog("Aplicando importacion...", self)
        loading.show()
        self.btn_aplicar.setEnabled(False)
        self.btn_cerrar.setEnabled(False)
        QApplication.processEvents()
        try:
            selected_total = len([row for row in self.rows if row.get("accion") and row.get("accion") != "OMITIR"])
            processed_selected = {"count": 0}

            def on_progress(current: int, total: int, row: Dict[str, Any]) -> None:
                action = row.get("accion") or "OMITIR"
                if action == "OMITIR":
                    return
                processed_selected["count"] += 1
                label = ACTION_LABELS.get(action, action)
                detail = f"Hoja {row.get('hoja')} - fila {row.get('fila')} | {label}"
                loading.set_progress(processed_selected["count"], selected_total, detail)

            loading.set_progress(0, selected_total, "Preparando importacion...")
            result = self.service.aplicar(self.rows, progress_callback=on_progress)
        except Exception as e:
            popUp.error(self, "Carga avanzada", f"No se pudo aplicar la importacion.\n\n{e}")
            return
        finally:
            self.btn_aplicar.setEnabled(True)
            self.btn_cerrar.setEnabled(True)
            loading.close()

        if result.get("success"):
            popUp.info(
                self,
                "Carga avanzada",
                "Proceso finalizado.\n\n"
                f"Creados: {result.get('creados', 0)}\n"
                f"Actualizados: {result.get('actualizados', 0)}\n"
                f"Omitidos: {result.get('omitidos', 0)}",
            )
            self.accept()
        else:
            errores = result.get("errores", [])
            popUp.error(
                self,
                "Carga avanzada",
                "No se aplicaron cambios. Se encontraron errores:\n\n" + "\n".join(errores[:20]),
            )

    def _action_counts(self) -> Dict[str, int]:
        counts = {
            "CREAR": 0,
            "COMPLETAR_VACIOS": 0,
            "ACTUALIZAR_DIFERENCIAS": 0,
            "OMITIR": 0,
        }
        for row in self.rows:
            action = row.get("accion") or "OMITIR"
            if action not in counts:
                action = "OMITIR"
            counts[action] += 1
        return counts

    def _summary_text(self, summary: Dict[str, Any], errores: List[str]) -> str:
        text = f"Filas detectadas: {summary.get('total', 0)}"
        if self._estado_filter:
            text += f" | Filtro activo: {self._estado_label(self._estado_filter)} ({len(self.visible_rows)} filas)"
        if errores:
            text += "\nAvisos: " + " | ".join(errores[:3])
        return text

    def _refresh_filter_buttons(self) -> None:
        mapping = {
            "NUEVO": ("Nuevos", "nuevos"),
            "EXISTENTE_IGUAL": ("Iguales", "existentes_iguales"),
            "EXISTENTE_DIFERENCIAS": ("Diferencias", "existentes_diferencias"),
            "DUPLICADO_AMBIGUO": ("Ambiguos", "ambiguos"),
            "ERROR": ("Errores", "errores"),
        }
        for estado, btn in self._filter_buttons.items():
            label, key = mapping[estado]
            btn.setText(f"{label}  {self.summary.get(key, 0)}")
            btn.setToolTip(f"{label}: {self.summary.get(key, 0)}")
        self.btn_limpiar_filtro.setEnabled(self._estado_filter is not None)

    def _diff_summary(self, row_data: Dict[str, Any]) -> str:
        diffs = row_data.get("diferencias") or []
        if not diffs:
            if row_data.get("estado") == "ERROR":
                return row_data.get("mensaje") or "Ver error"
            return "Sin diferencias"
        if len(diffs) == 1:
            label = diffs[0].get("label") or diffs[0].get("campo") or "Diferencia"
            return f"1 dif.: {label}"
        labels = []
        for diff in diffs[:2]:
            label = diff.get("label") or diff.get("campo") or ""
            if label:
                labels.append(str(label))
        if labels and len(diffs) <= 2:
            return ", ".join(labels)
        return f"{len(diffs)} diferencias"

    def _diff_tooltip(self, row_data: Dict[str, Any]) -> str:
        diffs = row_data.get("diferencias") or []
        if not diffs:
            return row_data.get("mensaje") or "Sin diferencias detectadas."
        lines = []
        for diff in diffs:
            sistema, excel = self._display_diff_values(row_data, diff)
            label = diff.get("label") or diff.get("campo") or "Campo"
            lines.append(f"{label}: sistema='{sistema}' | excel='{excel}'")
        return "\n".join(lines)


    def _estado_label(self, estado: Optional[str]) -> str:
        return {
            "NUEVO": "Nuevo",
            "EXISTENTE_IGUAL": "Existente igual",
            "EXISTENTE_DIFERENCIAS": "Con diferencias",
            "DUPLICADO_AMBIGUO": "Duplicado ambiguo",
            "ERROR": "Error",
        }.get(str(estado or ""), str(estado or ""))
