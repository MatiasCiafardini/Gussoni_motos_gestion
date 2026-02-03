# app/reportes/iva_ventas_datos.py

from __future__ import annotations

from pathlib import Path
from typing import Optional
from sqlalchemy import text

from app.data.database import SessionLocal


# =========================================================
# Helpers AFIP
# =========================================================

def fmt_num(valor: float | int | None, largo: int) -> str:
    if valor is None:
        valor = 0
    return str(int(round(float(valor) * 100))).zfill(largo)


def fmt_int(valor: int | None, largo: int) -> str:
    return str(int(valor or 0)).zfill(largo)


# =========================================================
# Query resumen
# =========================================================

QUERY_RESUMEN = """
SELECT
    COUNT(*) AS cant_cbtes,
    COALESCE(SUM(f.total - f.iva), 0) AS neto,
    COALESCE(SUM(f.iva), 0) AS iva,
    COALESCE(SUM(f.total), 0) AS total
FROM facturas f
WHERE
    f.estado_id = 14
    AND MONTH(f.fecha_emision) = :mes
    AND YEAR(f.fecha_emision) = :anio
"""


# =========================================================
# Generador
# =========================================================

def generar_txt_iva_ventas_datos(
    *,
    mes: int,
    anio: int,
    cuit: str,
    path_override: Optional[str] = None,
) -> str:
    """
    Genera LIBRO_IVA_DIGITAL_VENTAS_DATOS.txt
    """

    base = Path(path_override) if path_override else Path.home() / "Downloads"
    base.mkdir(parents=True, exist_ok=True)

    path = base / "LIBRO_IVA_DIGITAL_VENTAS_DATOS.txt"

    periodo = f"{anio}{mes:02d}"

    session = SessionLocal()
    try:
        row = session.execute(
            text(QUERY_RESUMEN),
            {"mes": mes, "anio": anio},
        ).mappings().first()
    finally:
        session.close()

    if not row or row["cant_cbtes"] == 0:
        raise ValueError("No hay comprobantes para generar el resumen del período.")

    line = (
        fmt_int(cuit, 11)              # CUIT
        + periodo                     # AAAAMM
        + "VENTAS"                    # Tipo libro
        + fmt_int(row["cant_cbtes"], 6)
        + fmt_num(row["neto"], 15)
        + fmt_num(row["iva"], 15)
        + fmt_num(row["total"], 15)
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(line + "\n")

    return str(path)
