from __future__ import annotations

from sqlalchemy import text

from app.services.importacion_certificados_service import ImportacionCertificadosService
from tests.fixtures.excel_factory import build_certificados_excel


def test_color_faltante_se_crea_y_lca_se_importa(db):
    excel = build_certificados_excel(
        [
            {
                "modelo": "COLOR FALTANTE",
                "nro_certificado": "CERT-PLATA",
                "numero_cuadro": "CUADRO-PLATA",
                "numero_motor": "MOTOR-PLATA",
                "lca": "216; IF-2024-117060280-APN-SSAM#JGM",
                "anio": 2026,
                "color": "PLATA",
                "precio_lista": 1000,
            }
        ],
        sheet_name="QA",
    )
    svc = ImportacionCertificadosService()
    rows = svc.generar_preview(excel)["rows"]

    result = svc.aplicar(rows)

    color_id = db.execute(text("SELECT id FROM colores WHERE nombre='PLATA'")).scalar()
    vehiculo = db.execute(text("SELECT color_id,lca FROM vehiculos WHERE numero_motor='MOTOR-PLATA'")).mappings().first()
    assert result["success"] is True
    assert color_id is not None
    assert vehiculo["color_id"] == color_id
    assert vehiculo["lca"] == "216; IF-2024-117060280-APN-SSAM#JGM"
