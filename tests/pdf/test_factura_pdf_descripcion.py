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
    assert "NÚMERO MOTOR: M1" in desc
    assert "LCA: IF-2024-117060280-APN-SSAM#JGM" in desc
    assert desc.splitlines().index("NÚMERO MOTOR: M1") < desc.splitlines().index(
        "LCA: IF-2024-117060280-APN-SSAM#JGM"
    )


def test_descripcion_factura_no_muestra_lca_si_esta_vacio():
    svc = ComprobantesService()

    desc = svc._desc_like_original(
        {
            "descripcion": "QA FACTURA B HOMOLOGACION | Motor: M1 | Cuadro: C1",
            "lca": "",
        }
    )

    assert "LCA" not in desc


def test_descripcion_factura_usa_numero_motor_enriquecido_si_no_viene_en_descripcion():
    svc = ComprobantesService()

    desc = svc._desc_like_original(
        {
            "descripcion": "QA FACTURA B HOMOLOGACION | Cuadro: C1",
            "numero_motor": "MOTOR-DB",
        }
    )

    assert "NÚMERO MOTOR: MOTOR-DB" in desc
