from __future__ import annotations

from sqlalchemy import text

from app.services.importacion_certificados_service import ImportacionCertificadosService
from tests.fixtures.db_factory import insert_vehiculo
from tests.fixtures.excel_factory import build_certificados_excel


def test_aplicar_crea_nuevos_actualiza_diferencias_y_omite(db):
    existing_id = insert_vehiculo(
        db,
        suffix="UPD",
        marca="QA",
        modelo="MODELO VIEJO",
        numero_motor="MOTOR-UPD",
        numero_cuadro="CUADRO-UPD",
        nro_certificado="CERT-UPD",
        color_id=1,
        precio_lista=1000,
        lca=None,
    )
    excel = build_certificados_excel(
        [
            {
                "modelo": "CREADO",
                "nro_certificado": "CERT-CREADO",
                "numero_cuadro": "CUADRO-CREADO",
                "numero_motor": "MOTOR-CREADO",
                "lca": "IF-CREADO",
                "anio": 2026,
                "color": "Azul",
                "precio_lista": 1500,
            },
            {
                "modelo": "MODELO NUEVO",
                "nro_certificado": "CERT-UPD",
                "numero_cuadro": "CUADRO-UPD",
                "numero_motor": "MOTOR-UPD",
                "lca": "IF-ACTUALIZADO",
                "anio": 2026,
                "color": "Negro",
                "precio_lista": 2000,
            },
        ],
        sheet_name="QA",
    )
    svc = ImportacionCertificadosService()
    rows = svc.generar_preview(excel)["rows"]

    result = svc.aplicar(rows)

    creado = db.execute(text("SELECT * FROM vehiculos WHERE numero_motor='MOTOR-CREADO'")).mappings().first()
    actualizado = db.execute(text("SELECT * FROM vehiculos WHERE id=:id"), {"id": existing_id}).mappings().first()
    assert result["success"] is True
    assert result["creados"] == 1
    assert result["actualizados"] == 1
    assert creado["lca"] == "IF-CREADO"
    assert actualizado["modelo"] == "MODELO NUEVO"
    assert actualizado["lca"] == "IF-ACTUALIZADO"


def test_aplicar_no_aplica_filas_con_error(db):
    excel = build_certificados_excel(
        [
            {
                "modelo": "ERROR",
                "nro_certificado": "CERT-ERROR",
                "numero_cuadro": "CUADRO-ERROR",
                "anio": 2026,
                "color": "Azul",
                "precio_lista": 1000,
            }
        ],
        sheet_name="QA",
    )
    svc = ImportacionCertificadosService()
    rows = svc.generar_preview(excel)["rows"]

    result = svc.aplicar(rows)

    assert result["success"] is True
    assert result["omitidos"] == 1
    assert db.execute(text("SELECT COUNT(*) FROM vehiculos WHERE nro_certificado='CERT-ERROR'")).scalar() == 0


def test_aplicar_completar_vacios_no_pisa_campos_existentes(db):
    existing_id = insert_vehiculo(
        db,
        suffix="EMPTY",
        marca="QA",
        modelo="MODELO EXISTENTE",
        numero_motor="MOTOR-EMPTY",
        numero_cuadro="CUADRO-EMPTY",
        nro_certificado="CERT-EMPTY",
        lca=None,
        color_id=1,
        precio_lista=1000,
    )
    excel = build_certificados_excel(
        [
            {
                "modelo": "MODELO EXCEL",
                "nro_certificado": "CERT-EMPTY",
                "numero_cuadro": "CUADRO-EMPTY",
                "numero_motor": "MOTOR-EMPTY",
                "lca": "IF-COMPLETADO",
                "anio": 2026,
                "color": "Negro",
                "precio_lista": 2000,
            }
        ],
        sheet_name="QA",
    )
    svc = ImportacionCertificadosService()
    rows = svc.generar_preview(excel)["rows"]
    rows[0]["accion"] = "COMPLETAR_VACIOS"

    result = svc.aplicar(rows)

    row = db.execute(text("SELECT modelo,lca,precio_lista FROM vehiculos WHERE id=:id"), {"id": existing_id}).mappings().first()
    assert result["success"] is True
    assert row["modelo"] == "MODELO EXISTENTE"
    assert row["lca"] == "IF-COMPLETADO"
    assert float(row["precio_lista"]) == 1000.0
