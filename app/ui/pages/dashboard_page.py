from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFont
import pandas as pd
from datetime import datetime

# Matplotlib (opcional)
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


UPCOMING_DAYS = 7  # ventana de "próximos a vencer"


class DashboardPage(QWidget):
    """
    Dashboard enfocado en cobranza:
      - KPIs de pendientes, próximos, vencidas, vendidas, ingresos y ganancia.
      - Gráfico: ingresos cobrados últimos 6 meses.
      - Listas: próximos a vencer (7 días) y vencidas (top 5).
    Lectura desde Excel: clientes.xlsx, vehiculos.xlsx, facturas.xlsx (y cuotas.xlsx si existe).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardPage")

        # 🔧 Forzar textos sin fondo (evita gris heredado del tema)
        self.setStyleSheet("""
            QLabel { background: transparent; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Inicio")
        title.setStyleSheet("font-size:20px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch(1)
        self.lbl_last_update = QLabel("")
        self.btn_refresh = QPushButton("Refrescar")
        self.btn_refresh.setObjectName("Primary")
        hdr.addWidget(self.lbl_last_update)
        hdr.addWidget(self.btn_refresh)
        root.addLayout(hdr)

        # KPIs (7 tarjetas)
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setHorizontalSpacing(12)
        self.kpi_grid.setVerticalSpacing(12)
        root.addLayout(self.kpi_grid)

        self.card_pend_cnt = self._make_kpi_card("Facturas pendientes", "—")
        self.card_pend_amt = self._make_kpi_card("Pendiente (€)", "—")
        self.card_upcoming = self._make_kpi_card(f"Próx. {UPCOMING_DAYS} días", "—")
        self.card_overdue = self._make_kpi_card("Vencidas", "—")
        self.card_vendidas = self._make_kpi_card("Unidades vendidas", "—")
        self.card_ingresos = self._make_kpi_card("Ingresos cobrados", "—")
        self.card_ganancia = self._make_kpi_card("Ganancia estimada", "—")

        cards = [
            self.card_pend_cnt, self.card_pend_amt, self.card_upcoming,
            self.card_overdue, self.card_vendidas, self.card_ingresos,
            self.card_ganancia
        ]
        for i, c in enumerate(cards):
            r = i // 3
            col = i % 3
            self.kpi_grid.addWidget(c, r, col)

        # Zona de contenido (gráfico + listados)
        content = QHBoxLayout()
        content.setSpacing(12)
        root.addLayout(content, 1)

        # Gráfico ingresos
        self.chart_ingresos = self._make_chart_card("Ingresos cobrados (últimos 6 meses)")
        content.addWidget(self.chart_ingresos, 2)

        # Listas: próximos y vencidas
        lists_col = QVBoxLayout()
        lists_col.setSpacing(12)
        content.addLayout(lists_col, 1)

        self.list_upcoming = self._make_list_card(f"Próximos a vencer (≤ {UPCOMING_DAYS} días)")
        self.list_overdue = self._make_list_card("Vencidas (impagas)")
        lists_col.addWidget(self.list_upcoming)
        lists_col.addWidget(self.list_overdue)

        # Aviso matplotlib faltante (texto ya transparente)
        if not _HAS_MPL:
            warn = QLabel("Para ver el gráfico instalá matplotlib:  pip install matplotlib")
            warn.setStyleSheet("color:#b45309; border:1px solid #fde68a; padding:6px 10px; border-radius:8px;")
            root.addWidget(warn)

        # Eventos
        self.btn_refresh.clicked.connect(self.reload)

        # Primera carga
        self.reload()

    # ---------- UI helpers ----------
    def _make_kpi_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFrameShape(QFrame.StyledPanel)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color:#6c757d; font-size:12px;")
        lbl_value = QLabel(value)
        f = QFont(); f.setPointSize(18); f.setWeight(QFont.Weight.DemiBold)
        lbl_value.setFont(f); lbl_value.setObjectName("KpiValue")

        card._lbl_value = lbl_value
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_value)
        lay.addStretch(1)

        # Card blanca, textos transparentes por la regla global
        card.setStyleSheet("""
            QFrame#Card { background:#ffffff; border:1px solid #e9ecef; border-radius:12px; }
            QLabel#KpiValue { color:#212529; }
        """)
        return card

    def _make_chart_card(self, title: str) -> QFrame:
        wrapper = QFrame(); wrapper.setObjectName("Card"); wrapper.setFrameShape(QFrame.StyledPanel)
        wrapper.setStyleSheet("QFrame#Card { background:#ffffff; border:1px solid #e9ecef; border-radius:12px; }")
        lay = QVBoxLayout(wrapper); lay.setContentsMargins(14,12,14,12); lay.setSpacing(8)
        lbl = QLabel(title); lbl.setStyleSheet("color:#6c757d; font-size:12px;")
        lay.addWidget(lbl)
        if _HAS_MPL:
            fig = Figure(figsize=(4,3), tight_layout=True)
            canvas = FigureCanvas(fig)
            wrapper._fig = fig; wrapper._canvas = canvas
            lay.addWidget(canvas, 1)
        else:
            ph = QLabel("Gráfico no disponible (falta matplotlib)")
            ph.setAlignment(Qt.AlignCenter); ph.setStyleSheet("color:#6b7280; padding:20px;")
            lay.addWidget(ph, 1)
        return wrapper

    def _make_list_card(self, title: str) -> QFrame:
        card = QFrame(); card.setObjectName("Card"); card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("QFrame#Card { background:#ffffff; border:1px solid #e9ecef; border-radius:12px; }")
        lay = QVBoxLayout(card); lay.setContentsMargins(14,12,14,12); lay.setSpacing(8)
        lbl = QLabel(title); lbl.setStyleSheet("color:#6c757d; font-size:12px;")
        lay.addWidget(lbl)
        body = QVBoxLayout(); body.setSpacing(6); body.setContentsMargins(0,0,0,0)
        card._body = body
        lay.addLayout(body)
        return card

    def _add_list_row(self, container_layout: QVBoxLayout, left: str, right: str, subtle: bool = False):
        row = QHBoxLayout(); row.setSpacing(6)
        l = QLabel(left); r = QLabel(right)
        l.setStyleSheet("font-size:13px;" + ("color:#6c757d;" if subtle else ""))
        r.setStyleSheet("font-size:13px;")
        row.addWidget(l); row.addStretch(1); row.addWidget(r)
        container_layout.addLayout(row)

    # ---------- Carga de datos ----------
    def reload(self):
       """ # Datos base
        df_cli = ux.load_clientes({})
        df_veh = ux.load_vehiculos({})

        df_fac = self._load_facturas()
        df_cuo = self._load_cuotas()

        hoy = pd.Timestamp(datetime.now().date())

        # KPIs de cobranza
        if not df_cuo.empty:
            cuo_pend = df_cuo[df_cuo["estado"].isin(["Pendiente","Abierta","Impaga"])]
            cuo_pend["vencimiento"] = pd.to_datetime(cuo_pend["vencimiento"], errors="coerce")
            cuo_over = cuo_pend[cuo_pend["vencimiento"] < hoy]
            cuo_next = cuo_pend[(cuo_pend["vencimiento"] >= hoy) & (cuo_pend["vencimiento"] <= hoy + pd.Timedelta(days=UPCOMING_DAYS))]
            pend_cnt = len(cuo_pend)
            pend_amt = float(cuo_pend["monto"].fillna(0).astype(float).sum())
            overdue_cnt = len(cuo_over)
            upcoming_cnt = len(cuo_next)

            df_fac_idx = df_fac.set_index("id") if "id" in df_fac.columns else pd.DataFrame()
            def _cuo_row_display(row):
                cli = "—"; fecha = "—"
                if "factura_id" in row and not df_fac_idx.empty and row["factura_id"] in df_fac_idx.index:
                    cid = df_fac_idx.loc[row["factura_id"]].get("cliente_id", None)
                    if cid is not None:
                        cli = self._cliente_nombre(df_cli, cid)
                if pd.notna(row.get("vencimiento")):
                    fecha = pd.to_datetime(row["vencimiento"]).strftime("%d/%m")
                monto = self._format_currency(row.get("monto", 0) or 0)
                return cli, f"{fecha} · {monto}"
            upcoming_items = [ _cuo_row_display(r) for _, r in cuo_next.sort_values("vencimiento").head(5).iterrows() ]
            overdue_items  = [ _cuo_row_display(r) for _, r in cuo_over.sort_values("vencimiento").head(5).iterrows() ]
        else:
            if not df_fac.empty:
                if "vencimiento" not in df_fac.columns:
                    df_fac["vencimiento"] = pd.to_datetime(df_fac["fecha"], errors="coerce") + pd.Timedelta(days=30)
                else:
                    df_fac["vencimiento"] = pd.to_datetime(df_fac["vencimiento"], errors="coerce")
                pend_fac = df_fac[df_fac["estado"].isin(["Abierta","Pendiente","Impaga"])]
                pend_fac["total_calc"] = pend_fac.apply(lambda r: _calc_total_row(r), axis=1)
                fac_over = pend_fac[pend_fac["vencimiento"] < hoy]
                fac_next = pend_fac[(pend_fac["vencimiento"] >= hoy) & (pend_fac["vencimiento"] <= hoy + pd.Timedelta(days=UPCOMING_DAYS))]
                pend_cnt = len(pend_fac)
                pend_amt = float(pend_fac["total_calc"].fillna(0).astype(float).sum())
                overdue_cnt = len(fac_over)
                upcoming_cnt = len(fac_next)
                def _fac_row_display(row):
                    cli = self._cliente_nombre(df_cli, row.get("cliente_id", None))
                    fecha = row.get("vencimiento", None)
                    fecha = pd.to_datetime(fecha).strftime("%d/%m") if pd.notna(fecha) else "—"
                    monto = self._format_currency(row.get("total_calc", 0) or 0)
                    return cli, f"{fecha} · {monto}"
                upcoming_items = [ _fac_row_display(r) for _, r in fac_next.sort_values("vencimiento").head(5).iterrows() ]
                overdue_items  = [ _fac_row_display(r) for _, r in fac_over.sort_values("vencimiento").head(5).iterrows() ]
            else:
                pend_cnt = 0; pend_amt = 0.0; overdue_cnt = 0; upcoming_cnt = 0
                upcoming_items = []; overdue_items = []

        # Unidades vendidas
        vendidas = len(df_veh[df_veh["id_estado"] == "3"])

        # Ingresos cobrados + ganancia
        ingresos_cobrados = 0.0
        ganancia = None
        if not df_fac.empty:
            pagadas = df_fac[df_fac["estado"].isin(["Pagada","Cobrada","Pagado"])]
            if not pagadas.empty:
                pagadas["total_calc"] = pagadas.apply(lambda r: _calc_total_row(r), axis=1)
                ingresos_cobrados = float(pagadas["total_calc"].fillna(0).astype(float).sum())

                if "vehiculo_id" in pagadas.columns and "costo" in df_veh.columns:
                    veh_cost = df_veh.set_index("id")["costo"].to_dict()
                    costos = 0.0
                    for _, row in pagadas.iterrows():
                        vid = row.get("vehiculo_id", None)
                        if pd.notna(vid) and vid in veh_cost:
                            try:
                                costos += float(veh_cost[vid] or 0)
                            except Exception:
                                pass
                    ganancia = max(0.0, ingresos_cobrados - costos)

        # KPIs
        self.card_pend_cnt._lbl_value.setText(f"{pend_cnt:,}".replace(",", "."))
        self.card_pend_amt._lbl_value.setText(self._format_currency(pend_amt))
        self.card_upcoming._lbl_value.setText(f"{upcoming_cnt:,}".replace(",", "."))
        self.card_overdue._lbl_value.setText(f"{overdue_cnt:,}".replace(",", "."))
        self.card_vendidas._lbl_value.setText(f"{vendidas:,}".replace(",", "."))
        self.card_ingresos._lbl_value.setText(self._format_currency(ingresos_cobrados))
        if ganancia is None:
            self.card_ganancia._lbl_value.setText("—")
            self.card_ganancia._lbl_value.setToolTip("Agregá columna 'costo' en vehiculos.xlsx para calcular ganancia.")
        else:
            self.card_ganancia._lbl_value.setText(self._format_currency(ganancia))
            self.card_ganancia._lbl_value.setToolTip("Ganancia = Ingresos cobrados - Coste de unidades vendidas.")

        # Gráfico ingresos por mes
        if _HAS_MPL:
            self._plot_ingresos_mensuales(self.chart_ingresos, df_fac)

        # Listas
        self._render_list(self.list_upcoming._body, upcoming_items, "Sin próximos vencimientos")
        self._render_list(self.list_overdue._body, overdue_items, "Sin vencidas")

        # Timestamp
        now = QDateTime.currentDateTime()
        self.lbl_last_update.setText(f"Actualizado: {now.toString('dd/MM/yyyy HH:mm')}")"""

    # ---------- Render helpers ----------
    def _render_list(self, layout: QVBoxLayout, items: list[tuple[str, str]], placeholder: str):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w: w.setParent(None)
        if not items:
            ph = QLabel(placeholder); ph.setStyleSheet("color:#6b7280;")
            layout.addWidget(ph); return
        for left, right in items:
            self._add_list_row(layout, left, right, subtle=False)

    def _plot_ingresos_mensuales(self, card: QFrame, df_fac: pd.DataFrame):
        fig = card._fig; fig.clear()
        ax = fig.add_subplot(111)
        if df_fac.empty:
            ax.text(0.5, 0.5, "Sin datos de facturas", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off"); card._canvas.draw_idle(); return
        df = df_fac[df_fac["estado"].isin(["Pagada","Cobrada","Pagado"])].copy()
        if df.empty:
            ax.text(0.5, 0.5, "No hay facturas cobradas", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off"); card._canvas.draw_idle(); return
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["total_calc"] = df.apply(lambda r: _calc_total_row(r), axis=1)
        df = df.dropna(subset=["fecha"])
        today = pd.Timestamp(datetime.now().date())
        months = [ (today.to_period("M") - i).to_timestamp() for i in range(5, -1, -1) ]
        labels = [ m.strftime("%b %Y") for m in months ]
        sums = []
        for m in months:
            m_end = (m + pd.offsets.MonthEnd(0))
            mask = (df["fecha"] >= m) & (df["fecha"] <= m_end)
            sums.append(float(df.loc[mask, "total_calc"].sum()))
        ax.bar(labels, sums)
        ax.set_ylabel("€")
        ax.set_title("Ingresos cobrados")
        ax.tick_params(axis="x", rotation=20)
        self._polish_axes(ax)
        card._canvas.draw_idle()

    def _add_list_row(self, container_layout: QVBoxLayout, left: str, right: str, subtle: bool = False):
        row = QHBoxLayout(); row.setSpacing(6)
        l = QLabel(left); r = QLabel(right)
        l.setStyleSheet("font-size:13px;" + ("color:#6c757d;" if subtle else ""))
        r.setStyleSheet("font-size:13px;")
        row.addWidget(l); row.addStretch(1); row.addWidget(r)
        container_layout.addLayout(row)

    def _polish_axes(self, ax):
        ax.grid(axis="y", linestyle=":", alpha=0.4)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    def _format_currency(self, value: float) -> str:
        try:
            entero, dec = f"{float(value):,.2f}".split(".")
            entero = entero.replace(",", ".")
            return f"€ {entero},{dec}"
        except Exception:
            return f"€ {value}"

    def _load_facturas(self) -> pd.DataFrame:
      """  path = DATA_DIR / "facturas.xlsx"
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_excel(path)
            for c in ["id","cliente_id","vehiculo_id","estado","total","subtotal","impuestos","fecha","vencimiento"]:
                if c not in df.columns:
                    df[c] = None
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df["vencimiento"] = pd.to_datetime(df["vencimiento"], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()"""

    def _load_cuotas(self) -> pd.DataFrame:
      """  path = DATA_DIR / "cuotas.xlsx"
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_excel(path)
            for c in ["id","factura_id","numero","vencimiento","monto","estado"]:
                if c not in df.columns:
                    df[c] = None
            df["vencimiento"] = pd.to_datetime(df["vencimiento"], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()"""


def _calc_total_row(row: pd.Series) -> float:
    try:
        t = row.get("total", None)
        if pd.notna(t):
            return float(t)
    except Exception:
        pass
    try:
        sub = float(row.get("subtotal", 0) or 0)
        imp = float(row.get("impuestos", 0) or 0)
        return sub + imp
    except Exception:
        return 0.0
