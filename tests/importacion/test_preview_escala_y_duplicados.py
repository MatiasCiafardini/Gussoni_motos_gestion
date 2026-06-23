from __future__ import annotations

from sqlalchemy import text

from app.services.importacion_certificados_service import ImportacionCertificadosService
from tests.fixtures.db_factory import insert_vehiculo
from tests.fixtures.excel_factory import build_certificados_excel


def test_preview_importacion_grande_no_pierde_conteos(db):
    insert_vehiculo(
        db,
        suffix="BASE",
        marca="QA",
        modelo="BASE",
        numero_motor="MOTOR-BASE",
        numero_cuadro="CUADRO-BASE",
        nro_certificado="CERT-BASE",
        color_id=1,
        precio_lista=1000,
    )
    rows_excel = []
    for idx in range(1, 121):
        rows_excel.append(
            {
                "modelo": f"LOTE {idx}",
                "nro_certificado": f"CERT-LOTE-{idx}",
                "nro_dnrpa": None,
                "numero_cuadro": f"CUADRO-LOTE-{idx}",
                "numero_motor": f"MOTOR-LOTE-{idx}",
                "lca": f"IF-LOTE-{idx}",
                "anio": 2026,
                "color": "Azul",
                "precio_lista": 1000 + idx,
            }
        )

    preview = ImportacionCertificadosService().generar_preview(build_certificados_excel(rows_excel, sheet_name="QA"))

    assert preview["success"] is True
    assert preview["summary"]["total"] == 120
    assert preview["summary"]["nuevos"] == 120
    assert preview["summary"]["errores"] == 0
    assert preview["summary"]["ambiguos"] == 0


def test_aplicar_no_duplica_motor_cuadro_o_certificado_existente(db):
    insert_vehiculo(
        db,
        suffix="DUP",
        marca="QA",
        modelo="DUP EXISTENTE",
        numero_motor="MOTOR-DUP",
        numero_cuadro="CUADRO-DUP",
        nro_certificado="CERT-DUP",
        precio_lista=1000,
    )
    excel = build_certificados_excel(
        [
            {
                "modelo": "DUP DESDE EXCEL",
                "nro_certificado": "CERT-DUP",
                "numero_cuadro": "CUADRO-DUP",
                "numero_motor": "MOTOR-DUP",
                "anio": 2026,
                "color": "Azul",
                "precio_lista": 1800,
            }
        ],
        sheet_name="QA",
    )

    svc = ImportacionCertificadosService()
    rows = svc.generar_preview(excel)["rows"]
    result = svc.aplicar(rows)

    assert result["success"] is True
    assert result["creados"] == 0
    assert db.execute(text("SELECT COUNT(*) FROM vehiculos WHERE numero_motor='MOTOR-DUP'")).scalar() == 1
