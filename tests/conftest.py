from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.fixtures.arca_fakes import FakeWSAA, FakeWSFE
from tests.fixtures.db_factory import make_sqlite_sessionmaker, insert_cliente, insert_vehiculo


@pytest.fixture()
def test_sessionmaker(tmp_path, monkeypatch):
    SessionTesting = make_sqlite_sessionmaker(tmp_path)

    from app.core.catalog_cache import CatalogCache

    CatalogCache.get().invalidate()

    modules_to_patch = [
        "app.data.database",
        "app.services.facturas_service",
        "app.services.factura_numbering_service",
        "app.services.arca_authorization_service",
        "app.services.nota_credito_creator",
        "app.services.importacion_certificados_service",
        "app.services.importacion_datos_service",
        "app.services.comprobantes_service",
        "app.services.catalogos_service",
        "app.services.ventas_service",
        "app.services.pagos_service",
        "app.reportes.iva_ventas",
        "app.reportes.iva_ventas_datos",
    ]
    for module_name in modules_to_patch:
        try:
            module = __import__(module_name, fromlist=["SessionLocal"])
            monkeypatch.setattr(module, "SessionLocal", SessionTesting, raising=False)
        except Exception:
            pass

    from app.services.audit_log_service import AuditLogService
    from app.services.stock_service import StockService

    monkeypatch.setattr(AuditLogService, "_has_audit_log", lambda self, db: True)
    monkeypatch.setattr(StockService, "_has_stock_movimientos", lambda self, db: True)
    return SessionTesting


@pytest.fixture()
def db(test_sessionmaker):
    session = test_sessionmaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def cliente_id(db):
    return insert_cliente(db)


@pytest.fixture()
def vehiculo_id(db):
    return insert_vehiculo(db)


@pytest.fixture()
def make_vehiculo(db):
    def _make(**kwargs):
        return insert_vehiculo(db, **kwargs)

    return _make


@pytest.fixture()
def factura_service_factory(test_sessionmaker):
    from app.services.facturas_service import FacturasService

    def _make(*, wsfe: FakeWSFE | None = None):
        svc = FacturasService()
        fake_wsaa = FakeWSAA()
        fake_wsfe = wsfe or FakeWSFE(ultimo_autorizado=0, aprobada=True)
        svc._wsaa = fake_wsaa
        svc._wsfe = fake_wsfe
        svc._numbering._wsaa = fake_wsaa
        svc._numbering._wsfe = fake_wsfe
        svc._arca_authorization._wsaa = fake_wsaa
        svc._arca_authorization._wsfe = fake_wsfe
        svc._nota_credito_creator._wsaa = fake_wsaa
        svc._nota_credito_creator._wsfe = fake_wsfe
        return svc

    return _make


def build_factura_payload(cliente_id: int, vehiculo_id: int, *, pto_vta: int = 2, total: float = 1000.0):
    from datetime import datetime

    neto = round(total / 1.21, 2)
    iva = round(total - neto, 2)
    cabecera = {
        "tipo_comprobante_id": 2,
        "pto_vta": pto_vta,
        "numero": None,
        "fecha_emision": datetime.now(),
        "moneda": "ARS",
        "cotizacion": 1.0,
        "cliente_id": cliente_id,
        "condicion_iva_receptor_id": 5,
        "observaciones": "QA test",
        "precio_real": total,
        "forma_pago_id": 1,
        "anticipo": 0,
        "cantidad_cuotas": 0,
        "importe_cuota": 0,
    }
    items = [
        {
            "item_tipo": "VEHICULO",
            "vehiculo_id": vehiculo_id,
            "descripcion": "QA MOTO TEST | Motor: MOTOR | Cuadro: CUADRO",
            "cantidad": 1,
            "precio_unitario": total,
            "alicuota_iva": 21,
            "importe_neto": neto,
            "importe_iva": iva,
            "importe_total": total,
        }
    ]
    return cabecera, items
