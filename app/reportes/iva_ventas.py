# reports/iva_ventas.py

import os
import smtplib
from email.message import EmailMessage
from typing import Optional

from db.connection import get_connection  # ajustá si tu import es distinto


# =========================
# Configuración general
# =========================

REPORTS_DIR = "reports_output"
ENCODING = "utf-8"

MAIL_CONFIG = {
    "host": "smtp.gmail.com",
    "port": 587,
    "user": "tu_mail@gmail.com",
    "password": "APP_PASSWORD",
    "from": "tu_mail@gmail.com",
    "to": ["contador@estudio.com"]
}


# =========================
# Query IVA Ventas (REAL)
# =========================

IVA_VENTAS_QUERY = """
SELECT
    DATE(f.fecha_emision) AS fecha,
    f.tipo               AS tipo_comprobante,
    f.punto_venta,
    f.numero,
    c.tipo_doc,
    c.nro_doc,
    CONCAT(
        TRIM(c.nombre),
        CASE WHEN c.apellido <> '' THEN CONCAT(' ', TRIM(c.apellido)) ELSE '' END
    ) AS razon_social,
    fd.alicuota_iva,
    SUM(fd.importe_neto)  AS neto,
    SUM(fd.importe_iva)   AS iva,
    SUM(fd.importe_total) AS total
FROM facturas f
JOIN facturas_detalle fd ON fd.factura_id = f.id
JOIN clientes c ON c.id = f.cliente_id
WHERE
    f.estado_id = 14                 -- Autorizadas
    AND MONTH(f.fecha_emision) = %s
    AND YEAR(f.fecha_emision) = %s
GROUP BY
    f.id,
    fd.alicuota_iva
ORDER BY
    f.fecha_emision,
    f.punto_venta,
    f.numero;
"""


# =========================
# Generar TXT
# =========================

def generar_txt_iva_ventas(mes: int, anio: int) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)

    filename = f"IVA_Ventas_{anio}_{mes:02}.txt"
    filepath = os.path.join(REPORTS_DIR, filename)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(IVA_VENTAS_QUERY, (mes, anio))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    if not rows:
        raise ValueError("No hay comprobantes autorizados para el período seleccionado.")

    with open(filepath, "w", encoding=ENCODING) as f:
        for r in rows:
            line = (
                f"{r['fecha']}|"
                f"{r['tipo_comprobante']}|"
                f"{int(r['punto_venta']):04d}|"
                f"{int(r['numero']):08d}|"
                f"{r['tipo_doc']}|"
                f"{r['nro_doc']}|"
                f"{r['razon_social']}|"
                f"{r['alicuota_iva']:.2f}|"
                f"{r['neto']:.2f}|"
                f"{r['iva']:.2f}|"
                f"{r['total']:.2f}"
            )
            f.write(line + "\n")

    return filepath


# =========================
# Envío por Email
# =========================

def enviar_iva_ventas_por_mail(
    mes: int,
    anio: int,
    destinatarios: Optional[list[str]] = None
) -> str:
    filepath = generar_txt_iva_ventas(mes, anio)

    msg = EmailMessage()
    msg["Subject"] = f"Libro IVA Ventas {mes:02}/{anio}"
    msg["From"] = MAIL_CONFIG["from"]
    msg["To"] = destinatarios or MAIL_CONFIG["to"]

    msg.set_content(
        f"""Hola,

Adjunto el archivo TXT correspondiente al Libro IVA Ventas del período {mes:02}/{anio}.

Archivo: {os.path.basename(filepath)}

Saludos.
"""
    )

    with open(filepath, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="text",
            subtype="plain",
            filename=os.path.basename(filepath)
        )

    with smtplib.SMTP(MAIL_CONFIG["host"], MAIL_CONFIG["port"]) as server:
        server.starttls()
        server.login(MAIL_CONFIG["user"], MAIL_CONFIG["password"])
        server.send_message(msg)

    return filepath
