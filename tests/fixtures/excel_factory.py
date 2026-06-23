from __future__ import annotations

from io import BytesIO
from typing import Iterable, Mapping

from openpyxl import Workbook


HEADERS = [
    "MODELO",
    "N° CERTIFICADO",
    "N° DNRPA",
    "N° CUADRO",
    "N° MOTOR",
    "LCA",
    "AÑO MODELO",
    "COLOR",
    "PRECIO TOTAL",
]


def build_certificados_excel(
    rows: Iterable[Mapping],
    *,
    sheet_name: str = "QA",
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(HEADERS)
    for row in rows:
        ws.append(
            [
                row.get("modelo"),
                row.get("nro_certificado"),
                row.get("nro_dnrpa"),
                row.get("numero_cuadro"),
                row.get("numero_motor"),
                row.get("lca"),
                row.get("anio"),
                row.get("color"),
                row.get("precio_lista"),
            ]
        )
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
