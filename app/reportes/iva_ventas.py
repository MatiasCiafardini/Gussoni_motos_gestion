# app/reportes/iva_ventas.py

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict

from sqlalchemy import text
from app.data.database import SessionLocal


# =========================================================
# Helpers formato AFIP
# =========================================================

def fmt_fecha(d: date | None) -> str:
    return d.strftime("%Y%m%d") if d else "00000000"


def fmt_num(valor: float | int | None, largo: int) -> str:
    if valor is None:
        valor = 0
    return str(int(round(float(valor) * 100))).zfill(largo)


def fmt_int(valor: int | None, largo: int) -> str:
    return str(int(valor or 0)).zfill(largo)


def fmt_str(txt: str | None, largo: int) -> str:
    return (txt or "")[:largo].ljust(largo)


# =========================================================
# Códigos AFIP
# =========================================================

TIPO_COMPROBANTE = {
    "FA": "001",
    "FB": "006",
    "FC": "011",
    "NDB": "007",
    "NCB": "008",
}

TIPO_DOC = {
    "CUIT": "80",
    "DNI": "96",
}

ALICUOTA_IVA = {
    21.0: "0005",
    10.5: "0004",
    0.0: "0003",
}


# =========================================================
# Queries
# =========================================================

QUERY_CBTE = """
SELECT
    f.id,
    f.fecha_emision,
    f.tipo,
    f.punto_venta,
    f.numero,
    f.total,
    f.iva,
    f.moneda,
    f.cotizacion,
    f.vto_cae,
    c.tipo_doc,
    c.nro_doc,
    CONCAT(TRIM(c.apellido), ' ', TRIM(c.nombre)) AS razon_social
FROM facturas f
LEFT JOIN clientes c ON c.id = f.cliente_id
WHERE
    f.estado_id = 14
    AND MONTH(f.fecha_emision) = :mes
    AND YEAR(f.fecha_emision) = :anio
ORDER BY f.fecha_emision, f.punto_venta, f.numero
"""

QUERY_DETALLE = """
SELECT
    fd.factura_id,
    fd.alicuota_iva,
    SUM(fd.importe_neto) AS neto,
    SUM(fd.importe_iva) AS iva
FROM facturas_detalle fd
GROUP BY fd.factura_id, fd.alicuota_iva
"""


# =========================================================
# Generador principal
# =========================================================

def generar_txt_iva_ventas(
    mes: int,
    anio: int,
    path_override: str | None = None,
) -> Dict[str, str]:

    base = Path(path_override) if path_override else Path.home() / "Downloads"
    base.mkdir(parents=True, exist_ok=True)

    path_cbte = base / "LIBRO_IVA_DIGITAL_VENTAS_CBTE.txt"
    path_alic = base / "LIBRO_IVA_DIGITAL_VENTAS_ALICUOTAS.txt"

    session = SessionLocal()
    try:
        cbtes = session.execute(
            text(QUERY_CBTE),
            {"mes": mes, "anio": anio},
        ).mappings().all()

        if not cbtes:
            raise ValueError("No hay comprobantes autorizados para el período.")

        detalles = session.execute(
            text(QUERY_DETALLE)
        ).mappings().all()

    finally:
        session.close()

    # indexar detalle por factura
    detalle_por_factura: dict[int, list[dict]] = {}
    for d in detalles:
        detalle_por_factura.setdefault(d["factura_id"], []).append(d)

    # =====================================================
    # CBTE
    # =====================================================
    with open(path_cbte, "w", encoding="utf-8") as f:
        for r in cbtes:
            line = (
                fmt_fecha(r["fecha_emision"])
                + TIPO_COMPROBANTE.get(r["tipo"], "000")
                + fmt_int(r["punto_venta"], 5)
                + fmt_int(r["numero"], 20)
                + fmt_int(r["numero"], 20)
                + TIPO_DOC.get(r["tipo_doc"], "99")
                + fmt_str(r["nro_doc"], 20)
                + fmt_str(r["razon_social"], 30)
                + fmt_num(r["total"], 15)
                + fmt_num(0, 15) * 7
                + fmt_str(r["moneda"] or "ARS", 3)
                + fmt_int(int((r["cotizacion"] or 1) * 1_000_000), 10)
                + "1"
                + "0"
                + fmt_num(0, 15)
                + fmt_fecha(r["vto_cae"])
            )
            f.write(line + "\n")

    # =====================================================
    # ALICUOTAS (LÓGICA CORRECTA)
    # =====================================================
    with open(path_alic, "w", encoding="utf-8") as f:
        for r in cbtes:
            factura_id = r["id"]
            filas = detalle_por_factura.get(factura_id)

            if filas:
                # 1️⃣ Usar detalle real
                for d in filas:
                    alic = float(d["alicuota_iva"] or 0)
                    line = (
                        TIPO_COMPROBANTE.get(r["tipo"], "000")
                        + fmt_int(r["punto_venta"], 5)
                        + fmt_int(r["numero"], 20)
                        + fmt_num(d["neto"], 15)
                        + ALICUOTA_IVA.get(alic, "0003")
                        + fmt_num(d["iva"], 15)
                    )
                    f.write(line + "\n")

            elif r["iva"] is not None and float(r["iva"]) > 0:
                # 2️⃣ Usar IVA cargado en la factura
                iva = float(r["iva"])
                total = float(r["total"] or 0)
                neto = total - iva

                alic = round((iva / neto) * 100, 1) if neto else 0.0

                line = (
                    TIPO_COMPROBANTE.get(r["tipo"], "000")
                    + fmt_int(r["punto_venta"], 5)
                    + fmt_int(r["numero"], 20)
                    + fmt_num(neto, 15)
                    + ALICUOTA_IVA.get(alic, "0005")
                    + fmt_num(iva, 15)
                )
                f.write(line + "\n")

            else:
                # 3️⃣ Último recurso: reconstruir desde total
                total = float(r["total"] or 0)

                if r["tipo"] in ("FA", "FB", "NDB", "NCB"):
                    neto = total / 1.21
                    iva = total - neto
                    alic = 21.0
                else:
                    neto = total
                    iva = 0
                    alic = 0.0

                line = (
                    TIPO_COMPROBANTE.get(r["tipo"], "000")
                    + fmt_int(r["punto_venta"], 5)
                    + fmt_int(r["numero"], 20)
                    + fmt_num(neto, 15)
                    + ALICUOTA_IVA.get(alic, "0003")
                    + fmt_num(iva, 15)
                )
                f.write(line + "\n")

    return {
        "cbte": str(path_cbte),
        "alicuotas": str(path_alic),
    }
