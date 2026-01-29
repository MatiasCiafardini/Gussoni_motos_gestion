from datetime import date
import os

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.units import mm
from reportlab.lib import colors

import app.ui.utils.paths as paths


def generar_nota_no_rodamiento_pdf(cliente: dict, veh: dict) -> str:
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    filename = f"nota_no_rodamiento_{cliente['id']}_{veh['id']}.pdf"
    path = os.path.join(downloads_dir, filename)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 12
    styles["Normal"].leading = 15

    styles.add(ParagraphStyle("HeaderLeft", fontSize=11, alignment=TA_LEFT))
    styles.add(ParagraphStyle("HeaderRight", fontSize=11, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(
        "NotaTitle",
        fontSize=15,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        spaceAfter=18,
    ))
    styles.add(ParagraphStyle(
        "SectionTitle",
        fontName="Helvetica-Bold",
        fontSize=12.5,
        spaceBefore=14,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "Justified",
        parent=styles["Normal"],
        alignment=TA_JUSTIFY,
    ))

    story = []

    fecha = date.today().strftime("%d/%m/%Y")

    logo = Image(paths.LOGO_GUSSONI)
    max_height = 35 * mm
    ratio = logo.imageWidth / logo.imageHeight
    logo.drawHeight = max_height
    logo.drawWidth = max_height * ratio

    header_left = Paragraph(
        """<b>GUSSONI MULTIMARCAS S.A.S</b><br/>
        AV VIEYTES 664<br/>
        SAN ANTONIO DE ARECO (BS. AS.)<br/>
        2325-650604""",
        styles["HeaderLeft"],
    )

    header_right = Paragraph(
        f"""<b>Concesionario Oficial</b><br/>
        Multimarcas - 0km y Usados<br/>
        Compra - Venta - Consignación<br/><br/>
        <b>San Antonio de Areco {fecha}</b>""",
        styles["HeaderRight"],
    )

    header_table = Table(
        [[header_left, logo, header_right]],
        colWidths=[60 * mm, None, 60 * mm],
        rowHeights=[45 * mm],
    )

    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 2))
    story.append(Table(
        [[""]],
        colWidths=[doc.width],
        rowHeights=[1],
        style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.black)])
    ))
    story.append(Spacer(1, 22))

    story.append(Paragraph("<u>NOTA NO RODAMIENTO</u>", styles["NotaTitle"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "Por medio de la presente, se deja constancia que la siguiente unidad:",
        styles["Normal"]
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<u>DATOS DEL MOTOVEHÍCULO:</u>", styles["SectionTitle"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph(f"Marca: {veh.get('marca','')}", styles["Normal"]))
    story.append(Paragraph(f"Modelo: {veh.get('modelo','')}", styles["Normal"]))
    story.append(Paragraph(f"Chasis N°: {veh.get('numero_cuadro','')}", styles["Normal"]))
    story.append(Paragraph(f"Motor N°: {veh.get('numero_motor','')}", styles["Normal"]))
    story.append(Paragraph("Dominio: a designar", styles["Normal"]))
    story.append(Paragraph(f"Color: {veh.get('color','')}", styles["Normal"]))
    story.append(Paragraph(f"Año/Modelo: {veh.get('anio','')}", styles["Normal"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<u>DATOS DEL COMPRADOR:</u>", styles["SectionTitle"]))
    story.append(Spacer(1, 6))

    nombre = f"{cliente.get('nombre','')} {cliente.get('apellido','')}".strip()
    docu = f"{cliente.get('tipo_doc','')} {cliente.get('nro_doc','')}"

    story.append(Paragraph(f"Nombre: {nombre}", styles["Normal"]))
    story.append(Paragraph(f"DNI/CUIT/CUIL: {docu}", styles["Normal"]))
    story.append(Paragraph(f"Domicilio: {cliente.get('direccion','')}", styles["Normal"]))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Se encuentra en perfectas condiciones y sin rodar en nuestra concesionaria, "
        "siendo retirada por el titular en el día de la fecha.",
        styles["Justified"]
    ))

    doc.build(story)
    return path
