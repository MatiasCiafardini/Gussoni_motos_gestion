from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import QObject, Slot, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.data.database import SessionLocal
from app.services.dashboard_service import DashboardService, DashboardData
from loguru import logger

HTML_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MotoAgency · Dashboard</title>
  <!-- Bootstrap 5 -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <!-- Qt WebChannel -->
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <style>
    body { background: linear-gradient(180deg,#f7f8fb 0,#eef2ff 100%); }
    .card { border-radius: 16px; box-shadow: 0 10px 24px rgba(16,24,40,0.08); }
    .badge { font-weight: 600; }
    .kpi-value { font-size: 34px; font-weight: 800; }
    .chip { border-radius: 999px; }
    .section-title { color:#475569; font-weight:700; letter-spacing:.2px; }
  </style>
</head>
<body class="p-3 p-lg-4">
  <div class="container-fluid">
    <!-- KPIs -->
    <div class="row g-3 g-lg-4 mb-3" id="kpis">
      <div class="col-12 col-md-6 col-xl-3">
        <div class="card h-100 p-3">
          <div class="text-secondary">Ventas del mes</div>
          <div class="kpi-value" id="kpi_ventas">—</div>
        </div>
      </div>
      <div class="col-12 col-md-6 col-xl-3">
        <div class="card h-100 p-3">
          <div class="text-secondary">Importe del mes (ARS)</div>
          <div class="kpi-value" id="kpi_total">—</div>
        </div>
      </div>
      <div class="col-12 col-md-6 col-xl-3">
        <div class="card h-100 p-3">
          <div class="text-secondary">Stock total</div>
          <div class="kpi-value" id="kpi_stock">—</div>
        </div>
      </div>
      <div class="col-12 col-md-6 col-xl-3">
        <div class="card h-100 p-3">
          <div class="text-secondary">Stock disponible</div>
          <div class="kpi-value" id="kpi_disp">—</div>
        </div>
      </div>
    </div>

    <!-- Tres paneles -->
    <div class="row g-3 g-lg-4">
      <div class="col-12 col-xl-4">
        <div class="card p-3">
          <div class="section-title mb-2">📦 Stock por estado</div>
          <div id="stockEstados" class="d-flex flex-wrap gap-2"></div>
        </div>
      </div>
      <div class="col-12 col-xl-4">
        <div class="card p-3">
          <div class="section-title mb-2">🏷️ Top marcas en stock</div>
          <div id="topMarcas" class="d-flex flex-wrap gap-2"></div>
        </div>
      </div>
      <div class="col-12 col-xl-4">
        <div class="card p-3">
          <div class="section-title mb-2">🧾 Últimas ventas</div>
          <div id="ultimasVentas" class="d-flex flex-column gap-2"></div>
        </div>
      </div>
    </div>
  </div>

<script>
  function fmtNum(n) {
    try { return new Intl.NumberFormat('es-AR').format(n); } catch(e) { return n; }
  }
  function setData(payload) {
    const d = payload;
    // KPIs
    document.getElementById('kpi_ventas').innerText = fmtNum(d.ventas_mes_cantidad);
    document.getElementById('kpi_total').innerText  = fmtNum(d.ventas_mes_total.toFixed(2));
    document.getElementById('kpi_stock').innerText  = fmtNum(d.stock_total);
    document.getElementById('kpi_disp').innerText   = fmtNum(d.stock_disponible);

    // Stock por estado
    const se = document.getElementById('stockEstados'); se.innerHTML = "";
    d.stock_por_estado.forEach(it => {
      const b = document.createElement('span');
      b.className = "badge text-bg-primary-subtle border border-primary-subtle chip px-3 py-2";
      b.innerText = `${it.estado} · ${fmtNum(it.cantidad)}`;
      se.appendChild(b);
    });

    // Top marcas
    const tm = document.getElementById('topMarcas'); tm.innerHTML = "";
    d.top_marcas.forEach(it => {
      const b = document.createElement('span');
      b.className = "badge text-bg-success-subtle border border-success-subtle chip px-3 py-2";
      b.innerText = `${it.marca} · ${fmtNum(it.cantidad)}`;
      tm.appendChild(b);
    });

    // Últimas ventas
    const uv = document.getElementById('ultimasVentas'); uv.innerHTML = "";
    d.ultimas_ventas.forEach(v => {
      const row = document.createElement('div');
      row.className = "d-flex align-items-center justify-content-between border rounded-5 px-3 py-2";
      row.innerHTML = `
        <div class="small text-secondary">${v.fecha}</div>
        <div class="fw-semibold">${v.marca} ${v.modelo}</div>
        <div class="text-secondary">${v.cliente}</div>
        <div class="badge text-bg-warning-subtle border border-warning-subtle">$
          ${fmtNum(Math.round(v.precio_operacion))}
        </div>`;
      uv.appendChild(row);
    });
  }

  // Bridge con Python
  new QWebChannel(qt.webChannelTransport, function(channel) {
    window.bridge = channel.objects.bridge;
    // Python llamará a window.setData(...)
  });
  // Exponemos para que Python ejecute setData(...)
  window.setData = setData;
</script>
</body>
</html>
"""

class _Bridge(QObject):
    """Objeto puente para futuras acciones JS<-→Python si las necesitás."""
    @Slot(str)
    def log(self, msg: str):
        logger.info(f"[WEB] {msg}")

class DashboardWebPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QWebEngineView(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.view)

        # Cargar HTML generado en memoria
        self.view.setHtml(HTML_TEMPLATE, baseUrl=QUrl("about:blank"))

        # Canal web para comunicar
        self.channel = QWebChannel(self.view.page())
        self.bridge = _Bridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.load_data()

    def load_data(self):
        """Obtiene datos del servicio y se los pasa al HTML."""
        try:
            with SessionLocal() as db:
                service = DashboardService(db)
                d: DashboardData = service.load_dashboard()
                payload = {
                    "ventas_mes_cantidad": d.ventas_mes_cantidad,
                    "ventas_mes_total": d.ventas_mes_total,
                    "stock_total": d.stock_total,
                    "stock_disponible": d.stock_disponible,
                    "stock_por_estado": d.stock_por_estado,
                    "top_marcas": d.top_marcas,
                    "ultimas_ventas": d.ultimas_ventas,
                }
        except Exception as e:
            logger.exception("Dashboard web: error cargando datos: {}", e)
            payload = {
                "ventas_mes_cantidad": 0, "ventas_mes_total": 0.0,
                "stock_total": 0, "stock_disponible": 0,
                "stock_por_estado": [], "top_marcas": [],
                "ultimas_ventas": []
            }

        js = f"window.setData({json.dumps(payload)});"
        self.view.page().runJavaScript(js)
