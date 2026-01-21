from __future__ import annotations

from datetime import datetime
from dateutil.relativedelta import relativedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QSizePolicy, QFrame
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.data.database import SessionLocal
from sqlalchemy import text


# ------------------------------------------------------------
# Helper visual: Card ejecutiva
# ------------------------------------------------------------
class Card(QFrame):
    def __init__(self, titulo: str, valor: str):
        super().__init__()

        self.setObjectName("Card")
        self.setFixedHeight(100)
        self.setStyleSheet("""
            QFrame#Card {
                background: #ffffff;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("color:#6b7280; font-size:11px;")
        lbl_titulo.setAlignment(Qt.AlignLeft)

        lbl_valor = QLabel(valor)
        lbl_valor.setStyleSheet("font-size:22px; font-weight:600;")
        lbl_valor.setAlignment(Qt.AlignCenter)

        layout.addWidget(lbl_titulo)
        layout.addStretch()
        layout.addWidget(lbl_valor)
        layout.addStretch()


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------
class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        self._build_ui()
        self.reload()

    # --------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(18)

        # Header
        header = QHBoxLayout()
        self.lbl_update = QLabel("")
        self.lbl_update.setStyleSheet("color:#6b7280;")
        btn_refresh = QPushButton("Refrescar")
        btn_refresh.clicked.connect(self.reload)

        header.addStretch()
        header.addWidget(self.lbl_update)
        header.addSpacing(12)
        header.addWidget(btn_refresh)

        root.addLayout(header)

        # KPIs
        self.card_fact_pend = Card("Facturas pendientes (mes)", "0")
        self.card_deuda = Card("Deuda vencida", "$ 0,00")
        self.card_cuotas_v = Card("Cuotas vencidas", "0")
        self.card_prox = Card("Próx. a vencer", "0")

        kpi_layout = QGridLayout()
        kpi_layout.setSpacing(16)
        kpi_layout.addWidget(self.card_fact_pend, 0, 0)
        kpi_layout.addWidget(self.card_deuda, 0, 1)
        kpi_layout.addWidget(self.card_cuotas_v, 0, 2)
        kpi_layout.addWidget(self.card_prox, 0, 3)

        root.addLayout(kpi_layout)

        # Contenido inferior
        bottom = QHBoxLayout()
        bottom.setSpacing(18)

        # -------- Gráfico --------
        chart_card = QFrame()
        chart_card.setStyleSheet("""
            QFrame {
                background:#ffffff;
                border-radius:10px;
            }
        """)
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(14, 14, 14, 14)

        lbl_chart = QLabel("Unidades vendidas (últimos meses)")
        lbl_chart.setStyleSheet("color:#6b7280; font-size:12px;")

        self.fig = Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)

        chart_layout.addWidget(lbl_chart)
        chart_layout.addWidget(self.canvas)

        bottom.addWidget(chart_card, 3)

        # -------- Columna derecha --------
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        right_col.addWidget(self._small_card("Próximos vencimientos"))
        right_col.addWidget(self._small_card("Vencidas"))
        right_col.addStretch()

        bottom.addLayout(right_col, 1)

        root.addLayout(bottom)

    # --------------------------------------------------------
    def _small_card(self, titulo: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(120)
        card.setStyleSheet("""
            QFrame {
                background:#ffffff;
                border-radius:10px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)

        lbl_t = QLabel(titulo)
        lbl_t.setStyleSheet("color:#6b7280; font-size:12px;")

        lbl_empty = QLabel("Sin datos")
        lbl_empty.setStyleSheet("color:#9ca3af;")
        lbl_empty.setAlignment(Qt.AlignCenter)

        layout.addWidget(lbl_t)
        layout.addStretch()
        layout.addWidget(lbl_empty)
        layout.addStretch()

        return card

    # --------------------------------------------------------
    def reload(self):
        self.lbl_update.setText(
            f"Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

        with SessionLocal() as db:
            # Facturas pendientes del mes
            row = db.execute(text("""
                SELECT COUNT(*)
                FROM facturas
                WHERE estado_id = 12
                  AND MONTH(fecha_emision) = MONTH(CURDATE())
                  AND YEAR(fecha_emision) = YEAR(CURDATE())
            """)).scalar()
            self.card_fact_pend.layout().itemAt(2).widget().setText(str(row or 0))

            # Cuotas vencidas
            cuotas_v = db.execute(text("""
                SELECT COUNT(*)
                FROM cuotas
                WHERE estado != 'PAGADA'
                  AND fecha_vencimiento < CURDATE()
            """)).scalar()
            self.card_cuotas_v.layout().itemAt(2).widget().setText(str(cuotas_v or 0))

        self._draw_chart()

    # --------------------------------------------------------
    def _draw_chart(self):
        self.ax.clear()

        labels = []
        valores = []

        hoy = datetime.now().replace(day=1)
        for i in range(3, -1, -1):
            mes = hoy - relativedelta(months=i)
            labels.append(mes.strftime("%m/%Y"))
            valores.append(self._ventas_mes(mes))

        if all(v == 0 for v in valores):
            self.ax.set_ylim(0, 1)
            self.ax.text(
                0.5, 0.5, "Sin ventas en el período",
                ha="center", va="center",
                transform=self.ax.transAxes,
                color="#9ca3af"
            )
        else:
            self.ax.bar(labels, valores)

        self.ax.set_ylabel("Unidades")
        self.ax.set_xlabel("Mes")
        self.ax.grid(axis="y", linestyle="--", alpha=0.3)

        self.canvas.draw_idle()

    # --------------------------------------------------------
    def _ventas_mes(self, mes: datetime) -> int:
        with SessionLocal() as db:
            return db.execute(text("""
                SELECT COUNT(*)
                FROM ventas
                WHERE MONTH(fecha) = :m
                  AND YEAR(fecha) = :y
            """), {
                "m": mes.month,
                "y": mes.year
            }).scalar() or 0
