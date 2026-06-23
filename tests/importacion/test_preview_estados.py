from __future__ import annotations

from app.services.importacion_certificados_service import ImportacionCertificadosService
from tests.fixtures.db_factory import insert_vehiculo
from tests.fixtures.excel_factory import build_certificados_excel


def test_preview_detecta_nuevo_igual_diferencia_error_color_y_lca(db):
    insert_vehiculo(
        db,
        suffix="IGUAL",
        marca="QA",
        modelo="IGUAL",
        numero_motor="MOTOR-IGUAL",
        numero_cuadro="CUADRO-IGUAL",
        nro_certificado="CERT-IGUAL",
        nro_dnrpa=None,
        lca="IF-IGUAL",
        color_id=1,
        precio_lista=1000,
    )
    insert_vehiculo(
        db,
        suffix="DIF",
        marca="QA",
        modelo="VIEJO",
        numero_motor="MOTOR-DIF",
        numero_cuadro="CUADRO-DIF",
        nro_certificado="CERT-DIF",
        lca="IF-VIEJO",
        color_id=1,
        precio_lista=1000,
    )
    excel = build_certificados_excel(
        [
            {
                "modelo": "NUEVO",
                "nro_certificado": "CERT-NUEVO",
                "nro_dnrpa": None,
                "numero_cuadro": "CUADRO-NUEVO",
                "numero_motor": "MOTOR-NUEVO",
                "lca": "IF-NUEVO",
                "anio": 2026,
                "color": "Azul",
                "precio_lista": "$1.388.290,85",
            },
            {
                "modelo": "IGUAL",
                "nro_certificado": "CERT-IGUAL",
                "nro_dnrpa": None,
                "numero_cuadro": "CUADRO-IGUAL",
                "numero_motor": "MOTOR-IGUAL",
                "lca": "IF-IGUAL",
                "anio": 2026,
                "color": "Negro",
                "precio_lista": 1000,
            },
            {
                "modelo": "NUEVO MODELO",
                "nro_certificado": "CERT-DIF",
                "nro_dnrpa": None,
                "numero_cuadro": "CUADRO-DIF",
                "numero_motor": "MOTOR-DIF",
                "lca": "IF-NUEVO-DIF",
                "anio": 2026,
                "color": "Negro",
                "precio_lista": 1200,
            },
            {
                "modelo": "ERROR SIN MOTOR",
                "nro_certificado": "CERT-ERROR",
                "numero_cuadro": "CUADRO-ERROR",
                "lca": "IF-ERROR",
                "anio": 2026,
                "color": "Azul",
                "precio_lista": 1000,
            },
            {
                "modelo": "COLOR NUEVO",
                "nro_certificado": "CERT-COLOR",
                "numero_cuadro": "CUADRO-COLOR",
                "numero_motor": "MOTOR-COLOR",
                "lca": "IF-COLOR",
                "anio": 2026,
                "color": "PLATA",
                "precio_lista": 1000,
            },
        ],
        sheet_name="QA",
    )

    preview = ImportacionCertificadosService().generar_preview(excel)
    rows = preview["rows"]
    estados = [row["estado"] for row in rows]

    assert preview["success"] is True
    assert "NUEVO" in estados
    assert "EXISTENTE_IGUAL" in estados
    assert "EXISTENTE_DIFERENCIAS" in estados
    assert "ERROR" in estados
    nuevo = next(row for row in rows if row["payload"].get("numero_motor") == "MOTOR-NUEVO")
    assert nuevo["payload"]["nro_dnrpa"] is None
    assert nuevo["payload"]["lca"] == "IF-NUEVO"
    color = next(row for row in rows if row["payload"].get("numero_motor") == "MOTOR-COLOR")
    assert color["estado"] == "NUEVO"
    assert color["diferencias"][0]["campo"] == "color_id"


def test_preview_detecta_ambiguos(db):
    insert_vehiculo(db, suffix="A", numero_motor="MOTOR-A", numero_cuadro="CUADRO-A", nro_certificado="CERT-A")
    insert_vehiculo(db, suffix="B", numero_motor="MOTOR-B", numero_cuadro="CUADRO-B", nro_certificado="CERT-B")
    excel = build_certificados_excel(
        [
            {
                "modelo": "AMBIGUO",
                "nro_certificado": "CERT-A",
                "numero_cuadro": "CUADRO-B",
                "numero_motor": "MOTOR-NO-EXISTE",
                "anio": 2026,
                "color": "Azul",
                "precio_lista": 1000,
            }
        ],
        sheet_name="QA",
    )

    preview = ImportacionCertificadosService().generar_preview(excel)

    assert preview["rows"][0]["estado"] == "DUPLICADO_AMBIGUO"
