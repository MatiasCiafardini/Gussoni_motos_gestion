from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QMouseEvent, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget, QGridLayout,
    QGraphicsDropShadowEffect
)


class FacturaPreviewDialog(QDialog):

    def __init__(
        self,
        cabecera: dict,
        items: list,
        cliente: dict,
        tipo_nombre: str,
        condicion_iva: str,
        forma_pago: str,
        subtotal: float,
        iva: float,
        total: float,
        parent=None
    ):
        super().__init__(parent)

        # =============================
        # CONFIG VENTANA
        # =============================
        self.setModal(True)
        self.setObjectName("NiceDialog")
        self.setWindowFlags(
            Qt.Dialog |
            Qt.FramelessWindowHint |
            Qt.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(920, 650)

        # =============================
        # PANEL CON SOMBRA
        # =============================
        panel = QFrame(self)
        panel.setObjectName("DialogPanel")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 120))
        panel.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.addWidget(panel)

        main = QVBoxLayout(panel)
        main.setContentsMargins(36, 32, 36, 32)
        main.setSpacing(26)

        # =============================
        # HEADER SUPERIOR
        # =============================
        header = QHBoxLayout()

        lbl_tipo = QLabel(f"<span style='font-size:32px; font-weight:600;'>{tipo_nombre}</span>")

        pv = str(cabecera.get("pto_vta")).zfill(4)
        nro = str(cabecera.get("numero")).zfill(8)

        lbl_comp = QLabel(f"<b>{pv}-{nro}</b>")
        lbl_comp.setAlignment(Qt.AlignRight)
        lbl_comp.setStyleSheet("font-size: 18px;")

        header.addWidget(lbl_tipo)
        header.addStretch()
        header.addWidget(lbl_comp)

        main.addLayout(header)

        # =============================
        # GRID INFORMACIÓN
        # =============================
        grid = QGridLayout()
        grid.setHorizontalSpacing(70)
        grid.setVerticalSpacing(10)

        # ---- Columna izquierda (Factura)
        grid.addWidget(QLabel("<b>Fecha</b>"), 0, 0)
        grid.addWidget(QLabel(cabecera.get("fecha_emision")), 0, 1)

        grid.addWidget(QLabel("<b>Moneda</b>"), 1, 0)
        grid.addWidget(QLabel(cabecera.get("moneda")), 1, 1)

        grid.addWidget(QLabel("<b>Condición IVA</b>"), 2, 0)
        grid.addWidget(QLabel(condicion_iva), 2, 1)

        grid.addWidget(QLabel("<b>Forma de pago</b>"), 3, 0)
        grid.addWidget(QLabel(forma_pago), 3, 1)

        # ---- Columna derecha (Cliente simplificado)
        nombre = f"{cliente.get('nombre','')} {cliente.get('apellido','')}".strip()
        tipo_doc = cliente.get("tipo_doc", "")
        nro_doc = cliente.get("nro_doc", "")

        grid.addWidget(QLabel("<b>Cliente</b>"), 0, 2)
        grid.addWidget(QLabel(nombre), 0, 3)

        grid.addWidget(QLabel("<b>Documento</b>"), 1, 2)
        grid.addWidget(QLabel(f"{tipo_doc} {nro_doc}".strip()), 1, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        main.addLayout(grid)

        # =============================
        # SEPARADOR SUAVE
        # =============================
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.12);")
        main.addWidget(sep)

        # =============================
        # DETALLE
        # =============================
        main.addWidget(QLabel("<span style='font-size:18px; font-weight:600;'>Detalle</span>"))

        for it in items:
            box = QFrame()
            box.setObjectName("Panel")
            box.setStyleSheet("""
                QFrame#Panel {
                    border-radius: 10px;
                    padding: 12px;
                }
            """)

            box_l = QVBoxLayout(box)
            box_l.setSpacing(8)

            # Descripción principal
            desc_lbl = QLabel(f"<b>{it['descripcion']}</b>")
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("font-size: 15px;")

            box_l.addWidget(desc_lbl)

            # Importe alineado a la derecha
            importe_lbl = QLabel(self._fmt(it["importe_total"]))
            importe_lbl.setAlignment(Qt.AlignRight)
            importe_lbl.setStyleSheet("font-size: 16px; font-weight:600;")

            box_l.addWidget(importe_lbl)

            main.addWidget(box)

        # =============================
        # BLOQUE TOTALES
        # =============================
        totals_wrap = QFrame()
        totals_wrap.setObjectName("Panel")
        totals_wrap.setStyleSheet("""
            QFrame#Panel {
                border-radius: 12px;
                padding: 16px;
            }
        """)

        totals_layout = QVBoxLayout(totals_wrap)
        totals_layout.setAlignment(Qt.AlignRight)
        totals_layout.setSpacing(6)

        totals_layout.addWidget(QLabel(f"Subtotal: {self._fmt(subtotal)}"))
        totals_layout.addWidget(QLabel(f"IVA: {self._fmt(iva)}"))

        total_lbl = QLabel(self._fmt(total))
        total_lbl.setAlignment(Qt.AlignRight)
        total_lbl.setStyleSheet("font-size: 30px; font-weight: 700;")

        totals_layout.addSpacing(6)
        totals_layout.addWidget(total_lbl)

        main.addWidget(totals_wrap)

        # =============================
        # BOTONES
        # =============================
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("BtnGhost")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = QPushButton("Confirmar y Enviar")
        self.btn_ok.setObjectName("BtnPrimary")
        self.btn_ok.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)

        main.addLayout(btn_row)

        # =============================
        # DRAG PARA MOVER
        # =============================
        self._drag_pos = None
        panel.installEventFilter(self)

    # =============================
    # FORMATO MONEDA
    # =============================
    def _fmt(self, value):
        try:
            return f"$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return f"$ {value}"

    # =============================
    # CENTRAR SOBRE PADRE
    # =============================
    def showEvent(self, ev):
        super().showEvent(ev)
        if self.parent():
            pw = self.parent().window()
            if pw:
                cx = pw.x() + (pw.width() - self.width()) // 2
                cy = pw.y() + (pw.height() - self.height()) // 2
                self.move(max(cx, 0), max(cy, 0))

    # =============================
    # DRAG DEL PANEL
    # =============================
    def eventFilter(self, obj, event):
        if obj.objectName() == "DialogPanel":
            if event.type() == QEvent.MouseButtonPress and isinstance(event, QMouseEvent):
                if event.button() == Qt.LeftButton:
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif event.type() == QEvent.MouseMove and isinstance(event, QMouseEvent):
                if self._drag_pos:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                self._drag_pos = None
                return True
        return super().eventFilter(obj, event)
