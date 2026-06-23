from __future__ import annotations

from app.services.comprobantes_service import ComprobantesService


def test_descripcion_factura_muestra_lca_si_existe():
    svc = ComprobantesService()

    desc = svc._desc_like_original(
        {
            "descripcion": "QA FACTURA B HOMOLOGACION | Motor: M1 | Cuadro: C1",
            "lca": "IF-2024-117060280-APN-SSAM#JGM",
        }
    )

    assert "MARCA MOTOR: QA" in desc
    assert "EXPEDIENTE / IF: IF-2024-117060280-APN-SSAM#JGM" in desc


def test_descripcion_factura_no_muestra_lca_si_esta_vacio():
    svc = ComprobantesService()

    desc = svc._desc_like_original(
        {
            "descripcion": "QA FACTURA B HOMOLOGACION | Motor: M1 | Cuadro: C1",
            "lca": "",
        }
    )

    assert "EXPEDIENTE / IF" not in desc
