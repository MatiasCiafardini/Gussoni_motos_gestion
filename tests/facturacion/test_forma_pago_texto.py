from __future__ import annotations

from app.services.facturas_service import FacturasService


def _build(row):
    service = FacturasService.__new__(FacturasService)
    return service._build_forma_pago_texto(row)


def test_financiacion_no_muestra_cantidad_ni_importe_de_cuotas():
    texto = _build(
        {
            "forma_pago_nombre": "Financiación",
            "cantidad_cuotas": 6,
            "importe_cuota": 145_000,
        }
    )

    assert texto == "Financiación"


def test_otra_forma_de_pago_conserva_su_nombre():
    assert _build({"forma_pago_nombre": "Transferencia"}) == "Transferencia"
