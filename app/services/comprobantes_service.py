from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
import base64
import json
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

from app.services.facturas_service import FacturasService


@dataclass(frozen=True)
class EmpresaConfig:
    nombre_fantasia: str = "GUSSONI MOTORS"
    razon_social: str = "MACHADO MOTOVEHICULOS S.A."
    domicilio: str = "Av. Smith 238"
    localidad: str = "(2760) San Antonio de Areco. Provincia de Buenos Aires"
    telefono: str = "Tel: 02326 497388"
    condicion_iva: str = "IVA Responsable Inscripto"
    cuit: str = "30-71532774-7"
    iibb: str = "30-71532774-7"
    inicio_actividades: str = "27/05/2016"
    punto_venta_default: int = 2


class ComprobantesService:
    HEADER_H = 36 * mm
    CLIENTE_H = 22 * mm
    TABLE_H = 150 * mm
    RESUMEN_H = 14 * mm
    FOOTER_H = 24 * mm

    def __init__(self, *, empresa: Optional[EmpresaConfig] = None) -> None:
        self._svc = FacturasService()
        self._empresa = empresa or EmpresaConfig()

        self.LOGO_GUSSONI_PATH = os.getenv("GUSSONI_LOGO_PATH", "").strip() or None
        self.LOGO_AFIP_PATH = os.getenv("AFIP_LOGO_PATH", "").strip() or None

    def generar_pdf(self, factura_id: int) -> str:
        fac = self._svc.get(int(factura_id))
        if not fac:
            raise ValueError(f"No se encontró la factura ID {factura_id}.")

        items = self._svc.get_detalle(int(factura_id)) or []

        out_dir = Path.home() / "Documents" / "Gussoni" / "Comprobantes"
        out_dir.mkdir(parents=True, exist_ok=True)

        tipo = (fac.get("tipo") or "").upper() or "FB"
        pv = self._to_int(fac.get("punto_venta") or fac.get("pto_vta") or self._empresa.punto_venta_default) or 0
        nro = self._to_int(fac.get("numero") or 0) or 0

        filename = f"{tipo}_{str(pv).zfill(5)}-{str(nro).zfill(8)}.pdf"
        pdf_path = out_dir / filename

        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        c.setTitle(filename)

        estado_id = self._to_int(fac.get("estado_id"))
        cae = str(fac.get("cae") or "").strip()

        try:
            est_aut = self._svc.ESTADO_AUTORIZADA
        except Exception:
            est_aut = None

        autorizado = bool(cae) and (est_aut is None or estado_id == est_aut)

        pages = self._paginate_items(items, per_page=18)
        total_pages = len(pages) if pages else 1

        letra = self._letra_from_tipo(tipo)
        cod_afip = self._cod_afip_from_tipo(tipo)

        for i, page_items in enumerate(pages or [[]], start=1):
            self._draw_page(
                c=c,
                fac=fac,
                page_items=page_items,
                all_items=items,
                page=i,
                total_pages=total_pages,
                autorizado=autorizado,
                letra=letra,
                cod_afip=cod_afip,
            )
            if i < total_pages:
                c.showPage()

        c.save()
        return str(pdf_path)

    def _draw_page(
        self,
        *,
        c: canvas.Canvas,
        fac: Dict[str, Any],
        page_items: List[Dict[str, Any]],
        all_items: List[Dict[str, Any]],
        page: int,
        total_pages: int,
        autorizado: bool,
        letra: str,
        cod_afip: str,
    ) -> None:
        W, H = A4
        M = 8 * mm

        c.setLineWidth(0.8)
        c.rect(M, M, W - 2 * M, H - 2 * M, stroke=1, fill=0)

        y_top = H - M

        self._draw_header(c, fac, M, y_top, self.HEADER_H, page, total_pages, letra, cod_afip)
        y = y_top - self.HEADER_H

        self._draw_cliente(c, fac, M, y, self.CLIENTE_H)
        y -= self.CLIENTE_H

        self._draw_table(c, page_items, M, y, self.TABLE_H)
        y -= self.TABLE_H

        self._draw_resumen(c, fac, all_items, M, y, self.RESUMEN_H)
        y -= self.RESUMEN_H

        self._draw_footer(c, fac, all_items, M, y, self.FOOTER_H, autorizado, page, total_pages)

    # =========================
    # HEADER: B pegada arriba + línea no pisa N°
    # =========================
    def _draw_header(
        self,
        c: canvas.Canvas,
        fac: Dict[str, Any],
        M: float,
        y_top: float,
        h: float,
        page: int,
        total_pages: int,
        letra: str,
        cod_afip: str,
    ) -> None:
        W, _H = A4
        x = M
        y = y_top - h
        w = W - 2 * M

        c.setLineWidth(0.6)
        c.rect(x, y, w, h, stroke=1, fill=0)

        # cuadrado B (PEGADO AL BORDE SUPERIOR del header)
        sq = 16 * mm
        sq_x = x + w / 2 - sq / 2
        sq_y = y + h - sq  # <-- pegado arriba (antes -1.5mm)

        c.rect(sq_x, sq_y, sq, sq, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(sq_x + sq / 2, sq_y + sq * 0.62, letra)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(sq_x + sq / 2, sq_y + sq * 0.22, f"COD. {cod_afip}")

        split_x = sq_x + sq / 2

        # IZQ: empresa
        lx = x + 3 * mm
        ly = y + h - 4.0 * mm

        self._draw_logo_if_exists(c, self.LOGO_GUSSONI_PATH, lx, ly - 10 * mm, 28 * mm, 10 * mm)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(lx, ly, self._empresa.nombre_fantasia)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(lx, ly - 4 * mm, self._empresa.razon_social)

        c.setFont("Helvetica", 7.2)
        c.drawString(lx, ly - 8 * mm, self._empresa.domicilio)
        c.drawString(lx, ly - 12 * mm, self._empresa.localidad)
        c.drawString(lx, ly - 16 * mm, self._empresa.telefono)
        c.drawString(lx, ly - 20 * mm, self._empresa.condicion_iva)

        # DER: factura (arranca debajo del cuadrado)
        rx = split_x + 3 * mm
        right_w = (x + w) - rx - 3 * mm

        tipo = (fac.get("tipo") or "").upper() or "FB"
        titulo = "Factura" if not tipo.startswith("NC") else "Nota de crédito"

        pv = self._to_int(fac.get("punto_venta") or fac.get("pto_vta") or self._empresa.punto_venta_default) or 0
        nro = self._to_int(fac.get("numero") or 0) or 0
        fecha = self._fmt_fecha(fac.get("fecha_emision") or fac.get("fecha"))

        top_line_y = y + h - 5.0 * mm

        c.setFont("Helvetica", 8)
        c.drawCentredString(rx + right_w / 2, top_line_y, titulo)
        c.drawRightString(x + w - 3 * mm, top_line_y, f"Original      Página {page} de {total_pages}")

        # bajamos un poco el N° para que no choque visualmente con la línea/box
        nro_y = sq_y - 3.5 * mm
        fecha_y = nro_y - 5.0 * mm

        c.setFont("Helvetica-Bold", 10)
        c.drawString(rx, nro_y, f"N°:  {str(pv).zfill(5)}-{str(nro).zfill(8)}")

        c.setFont("Helvetica", 8)
        c.drawString(rx, fecha_y, f"Fecha:  {fecha}" if fecha else "Fecha:")

        # Línea vertical: baja desde el cuadrado, pero NO pasa por el renglón del N°
        # Cortamos la línea justo por debajo del N°.
        # (dejamos 2mm de margen)
        # Línea vertical continua (sin hueco)
        c.line(split_x, y, split_x, sq_y)


        # Datos fiscales abajo
        c.setFont("Helvetica", 7.2)
        if self._empresa.cuit:
            c.drawString(rx, y + 7 * mm, f"CUIT: {self._empresa.cuit}")
        if self._empresa.iibb:
            c.drawString(rx + 55 * mm, y + 7 * mm, f"I. Brutos: {self._empresa.iibb}")
        if self._empresa.inicio_actividades:
            c.drawString(rx, y + 3 * mm, f"Inicio de Actividades: {self._empresa.inicio_actividades}")

    # =========================
    # CLIENTE
    # =========================
    def _draw_cliente(self, c: canvas.Canvas, fac: Dict[str, Any], M: float, y_top: float, h: float) -> None:
        W, _H = A4
        x = M
        y = y_top - h
        w = W - 2 * M

        c.setLineWidth(0.6)
        c.rect(x, y, w, h, stroke=1, fill=0)

        left_x = x + 3 * mm
        mid_x = x + w * 0.52
        right_x = x + w * 0.74

        line1_y = y_top - 6 * mm
        line2_y = y_top - 11 * mm
        line3_y = y_top - 16 * mm

        # Forma de pago más abajo (así no se “pega” con Localidad)
        bottom_y = y + 2.0 * mm

        cliente = (
            f"{(fac.get('cliente_nombre') or '').strip()} {(fac.get('cliente_apellido') or '').strip()}".strip()
            or (fac.get("cliente") or "").strip()
            or ""
        )
        cli_dir = str(fac.get("cliente_direccion") or fac.get("direccion") or "").strip() or ""
        provincia = "BUENOS AIRES"

        pedido = str(fac.get("pedido") or "").strip()
        remito = str(fac.get("remito") or "").strip()

        cuit_cli = self._fmt_doc(
            str(fac.get("cliente_tipo_doc") or fac.get("tipo_doc") or ""),
            str(fac.get("cliente_nro_doc") or fac.get("nro_doc") or ""),
        ).strip()

        c.setFont("Helvetica", 7.2)

        c.drawString(left_x, line1_y, "Sr.(s):")
        if cliente:
            c.setFont("Helvetica-Bold", 7.2)
            c.drawString(left_x + 17 * mm, line1_y, cliente)
            c.setFont("Helvetica", 7.2)

        c.drawString(left_x, line2_y, "Dirección:")
        if cli_dir:
            c.drawString(left_x + 17 * mm, line2_y, cli_dir)

        c.drawString(left_x, line3_y, "Localidad:")

        c.drawString(mid_x, line1_y, "Pedido:")
        if pedido:
            c.drawString(mid_x + 15 * mm, line1_y, pedido)

        c.drawString(mid_x, line2_y, "Fecha de Vencimiento de Pago:")
        c.drawString(mid_x, line3_y, "Provincia:")
        c.drawString(mid_x + 18 * mm, line3_y, provincia)

        c.drawString(right_x, line1_y, "CUIL:")
        if cuit_cli:
            c.drawString(right_x + 12 * mm, line1_y, cuit_cli)

        c.drawString(right_x, line2_y, "Remito N°:")
        if remito:
            c.drawString(right_x + 18 * mm, line2_y, remito)

        c.drawString(left_x, bottom_y, "Forma de Pago:")

    # ====== lo demás igual (tabla/resumen/footer/helpers) ======
    def _draw_table(self, c: canvas.Canvas, items: List[Dict[str, Any]], M: float, y_top: float, h: float) -> None:
        W, _H = A4
        x = M
        y = y_top - h
        w = W - 2 * M

        c.setLineWidth(0.6)
        c.rect(x, y, w, h, stroke=1, fill=0)

        th = 7 * mm
        c.line(x, y_top - th, x + w, y_top - th)

        cols = self._cols_table_like_photo(w)

        xcur = x
        for _name, cw in cols[:-1]:
            xcur += cw
            c.line(xcur, y, xcur, y_top)

        c.setFont("Helvetica", 7)
        header_y = y_top - 5 * mm
        xcur = x + 1.5 * mm
        for name, cw in cols:
            c.drawString(xcur, header_y, name)
            xcur += cw

        row_top = y_top - th
        row_h = 28 * mm

        rows = items or []
        max_rows = int((h - th) // row_h)
        rows = rows[:max_rows]

        yrow = row_top
        for idx, it in enumerate(rows):
            yrow -= row_h
            if len(rows) > 1:
                c.line(x, yrow, x + w, yrow)

            values = self._build_table_values(it)

            xcur = x
            for ((colname, cw), val) in zip(cols, values):
                tx = xcur + 1.5 * mm
                ty = yrow + row_h - 5 * mm

                if colname == "Descripción":
                    self._draw_multiline(
                        c, val, tx, ty,
                        max_w=cw - 3 * mm,
                        line_h=4 * mm,
                        max_lines=7,
                        font="Helvetica",
                        size=7,
                    )
                else:
                    if colname in ("Cantidad", "Precio", "IVA", "Importe"):
                        c.drawRightString(xcur + cw - 1.5 * mm, ty, str(val))
                    else:
                        c.drawString(tx, ty, str(val))
                xcur += cw

    def _build_table_values(self, it: Dict[str, Any]) -> List[str]:
        articulo = ""
        unid = "u"
        desc = self._desc_like_original(it)
        cant = self._fmt_qty(self._to_float(it.get("cantidad")))
        precio = self._fmt_money(self._to_float(it.get("precio_unitario")))
        iva = "21%"
        importe = self._fmt_money(self._to_float(it.get("importe_total")))
        return [articulo, unid, desc, cant, precio, iva, importe]

    def _cols_table_like_photo(self, total_w: float) -> List[Tuple[str, float]]:
        parts_mm = [
            ("Artículo", 18),
            ("Unid.", 10),
            ("Descripción", 95),
            ("Cantidad", 18),
            ("Precio", 22),
            ("IVA", 14),
            ("Importe", 25),
        ]
        cols = [(n, w * mm) for n, w in parts_mm]
        scale = total_w / sum(w for _, w in cols)
        return [(n, w * scale) for n, w in cols]

    def _desc_like_original(self, it: Dict[str, Any]) -> str:
        raw_desc = str(it.get("descripcion") or "").strip()

        nombre = raw_desc
        motor = ""
        chasis = ""
        anio = ""
        modelo = ""
        nro_int = ""

        if "|" in raw_desc:
            parts = [p.strip() for p in raw_desc.split("|") if p.strip()]
            if parts:
                nombre = parts[0]
            for p in parts[1:]:
                low = p.lower()
                if "motor" in low:
                    motor = p.split(":", 1)[-1].strip() if ":" in p else p.strip()
                if "cuadro" in low or "chasis" in low:
                    chasis = p.split(":", 1)[-1].strip() if ":" in p else p.strip()

        tokens = (nombre or "").split()
        if tokens and tokens[-1].isdigit() and len(tokens[-1]) == 4:
            anio = tokens[-1]
            nombre = " ".join(tokens[:-1]).strip()

        modelo = str(it.get("modelo") or "").strip()
        anio = str(it.get("anio") or anio or "").strip()

        nro_int = str(it.get("nro_interno") or it.get("numero_interno") or "").strip()
        if not nro_int and it.get("vehiculo_id") is not None:
            nro_int = str(it.get("vehiculo_id"))

        lines: List[str] = []
        if nombre:
            lines.append(nombre)
        if modelo:
            lines.append(f"Modelo: {modelo}")
        if anio:
            lines.append(f"Año: {anio}")
        if motor:
            lines.append(f"Nro. de Motor: {motor}")
        if chasis:
            lines.append(f"Nro. de Chasis: {chasis}")
        if nro_int:
            lines.append(f"Nro. Int: {nro_int}")

        return "\n".join(lines[:7])

    def _draw_resumen(self, c: canvas.Canvas, fac: Dict[str, Any], items: List[Dict[str, Any]], M: float, y_top: float, h: float) -> None:
        W, _H = A4
        x = M
        y = y_top - h
        w = W - 2 * M

        c.setLineWidth(0.6)
        c.rect(x, y, w, h, stroke=1, fill=0)

        neto, iva21, total = self._calc_totals_iva21(fac, items)

        c.setFont("Helvetica", 7)
        base_y = y + h - 6 * mm

        c.drawString(x + 3 * mm, base_y, "Descuentos:")
        c.drawString(x + 25 * mm, base_y, "0")

        c.drawString(x + 40 * mm, base_y, "No Gravado")
        c.drawRightString(x + 65 * mm, base_y, "0,01")

        c.drawString(x + 75 * mm, base_y, "Exento")
        c.drawRightString(x + 95 * mm, base_y, "0,00")

        c.drawString(x + 110 * mm, base_y, "Neto")
        c.drawRightString(x + 140 * mm, base_y, self._fmt_money(neto))

        c.drawString(x + 150 * mm, base_y, "Subtotal:")
        c.drawRightString(x + w - 3 * mm, base_y, self._fmt_money(neto))

    def _draw_footer(
        self,
        c: canvas.Canvas,
        fac: Dict[str, Any],
        items: List[Dict[str, Any]],
        M: float,
        y_top: float,
        h: float,
        autorizado: bool,
        page: int,
        total_pages: int,
    ) -> None:
        W, _H = A4
        x = M
        y = y_top - h
        w = W - 2 * M

        c.setLineWidth(0.6)
        c.rect(x, y, w, h, stroke=1, fill=0)

        neto, iva21, total = self._calc_totals_iva21(fac, items)

        cae = str(fac.get("cae") or "").strip()
        vto = self._fmt_fecha(fac.get("vto_cae") or "")

        if autorizado:
            payload = self._build_qr_payload(fac)
            self._draw_qr(c, payload, x + 3 * mm, y + 3 * mm, 18 * mm)
        else:
            c.rect(x + 3 * mm, y + 3 * mm, 18 * mm, 18 * mm, stroke=1, fill=0)

        ax = x + 25 * mm
        self._draw_logo_if_exists(c, self.LOGO_AFIP_PATH, ax, y + 7 * mm, 22 * mm, 10 * mm)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(ax, y + 11 * mm, "AFIP")

        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 75 * mm, y + 15 * mm, f"C.A.E. N°: {cae}" if cae else "C.A.E. N°:")

        c.setFont("Helvetica", 7)
        c.drawString(x + 75 * mm, y + 9 * mm, f"Fecha Vto. CAE: {vto}" if vto else "Fecha Vto. CAE:")

        c.setFont("Helvetica", 7)
        c.drawString(x + w - 60 * mm, y + 13 * mm, "IVA 21%")
        c.drawRightString(x + w - 3 * mm, y + 13 * mm, self._fmt_money(iva21))

        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + w - 60 * mm, y + 6 * mm, "Total:")
        box_w = 35 * mm
        box_h = 8 * mm
        c.rect(x + w - 3 * mm - box_w, y + 3 * mm, box_w, box_h, stroke=1, fill=0)
        c.drawRightString(x + w - 5 * mm, y + 5.5 * mm, self._fmt_money(total))

    def _draw_logo_if_exists(self, c: canvas.Canvas, path: Optional[str], x: float, y: float, w: float, h: float) -> None:
        if not path:
            return
        try:
            p = Path(path)
            if not p.exists():
                return
            c.drawImage(str(p), x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")
        except Exception:
            return

    def _draw_qr(self, c: canvas.Canvas, payload: str, x: float, y: float, size: float) -> None:
        widget = qr.QrCodeWidget(payload)
        bounds = widget.getBounds()
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        d = Drawing(size, size)
        d.add(widget)
        d.scale(size / w, size / h)
        renderPDF.draw(d, c, x, y)

    def _build_qr_payload(self, fac: Dict[str, Any]) -> str:
        tipo = (fac.get("tipo") or "").upper()
        pv = self._to_int(fac.get("punto_venta") or fac.get("pto_vta") or self._empresa.punto_venta_default) or 0
        nro = self._to_int(fac.get("numero") or 0) or 0
        fecha = self._fmt_fecha_iso(fac.get("fecha_emision") or fac.get("fecha"))
        total = float(self._to_float(fac.get("total")))

        cbte_tipo_map = {"FA": 1, "FB": 6, "FC": 11, "NCA": 3, "NCB": 8, "NCC": 13}
        cbte_tipo = int(cbte_tipo_map.get(tipo, 0))

        cli_tipo_doc = str(fac.get("cliente_tipo_doc") or fac.get("tipo_doc") or "").strip().upper()
        tipo_doc_map = {"CUIT": 80, "CUIL": 86, "CDI": 87, "DNI": 96}
        tipo_doc_rec = int(tipo_doc_map.get(cli_tipo_doc, 0))
        nro_doc_rec = int(self._digits(fac.get("cliente_nro_doc") or fac.get("nro_doc") or "0") or 0)

        payload = {
            "ver": 1,
            "fecha": fecha,
            "cuit": int(self._digits(self._empresa.cuit) or 0),
            "ptoVta": int(pv),
            "tipoCmp": cbte_tipo,
            "nroCmp": int(nro),
            "importe": round(total, 2),
            "moneda": "PES",
            "ctz": 1.0,
            "tipoDocRec": tipo_doc_rec,
            "nroDocRec": nro_doc_rec,
            "tipoCodAut": "E",
            "codAut": str(fac.get("cae") or ""),
        }

        js = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        b64 = base64.b64encode(js).decode("ascii")
        return f"https://www.afip.gob.ar/fe/qr/?p={b64}"

    def _calc_totals_iva21(self, fac: Dict[str, Any], items: List[Dict[str, Any]]) -> Tuple[float, float, float]:
        neto = 0.0
        iva21 = 0.0
        total = 0.0
        for it in items or []:
            neto += self._to_float(it.get("importe_neto"))
            total += self._to_float(it.get("importe_total"))
            rate = self._to_float(it.get("alicuota_iva"))
            if abs(rate - 21.0) < 0.0001:
                iva21 += self._to_float(it.get("importe_iva"))

        if fac.get("subtotal") is not None and abs(neto) < 0.0000001:
            neto = self._to_float(fac.get("subtotal"))
        if fac.get("iva") is not None and abs(iva21) < 0.0000001:
            iva21 = self._to_float(fac.get("iva"))
        if fac.get("total") is not None and abs(total) < 0.0000001:
            total = self._to_float(fac.get("total"))
        return neto, iva21, total

    def _draw_multiline(
        self,
        c: canvas.Canvas,
        text: str,
        x: float,
        y_top: float,
        *,
        max_w: float,
        line_h: float,
        max_lines: int,
        font: str,
        size: float,
    ) -> None:
        c.setFont(font, size)
        lines: List[str] = []
        for raw in str(text or "").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            cur = ""
            for word in raw.split():
                cand = (cur + " " + word).strip()
                if stringWidth(cand, font, size) <= max_w:
                    cur = cand
                else:
                    if cur:
                        lines.append(cur)
                    cur = word
            if cur:
                lines.append(cur)
        lines = lines[:max_lines]
        yy = y_top
        for ln in lines:
            c.drawString(x, yy, ln)
            yy -= line_h

    def _letra_from_tipo(self, tipo: str) -> str:
        t = (tipo or "").upper()
        if t.endswith("A"):
            return "A"
        if t.endswith("B"):
            return "B"
        if t.endswith("C"):
            return "C"
        return "X"

    def _cod_afip_from_tipo(self, tipo: str) -> str:
        t = (tipo or "").upper()
        mapping = {"FA": "01", "FB": "06", "FC": "11", "NCA": "03", "NCB": "08", "NCC": "13"}
        return mapping.get(t, "01")

    def _fmt_doc(self, tipo_doc: str, nro_doc: str) -> str:
        digits = self._digits(nro_doc)
        if tipo_doc.upper() in ("CUIT", "CUIL", "CDI") and len(digits) == 11:
            return f"{digits[0:2]}-{digits[2:10]}-{digits[10]}"
        return f"{tipo_doc} {nro_doc}".strip()

    def _fmt_fecha(self, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (datetime, date)):
            return v.strftime("%d/%m/%Y")
        s = str(v).strip()
        if not s:
            return ""
        try:
            dt = datetime.fromisoformat(s.replace("Z", ""))
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return s

    def _fmt_fecha_iso(self, v: Any) -> str:
        if v is None:
            return datetime.now().strftime("%Y-%m-%d")
        if isinstance(v, (datetime, date)):
            return v.strftime("%Y-%m-%d")
        s = str(v).strip()
        if not s:
            return datetime.now().strftime("%Y-%m-%d")
        if "/" in s and len(s.split("/")) == 3:
            dd, mm_, yy = s.split("/")
            dd = dd.zfill(2)
            mm_ = mm_.zfill(2)
            if len(yy) == 2:
                yy = "20" + yy
            return f"{yy}-{mm_}-{dd}"
        try:
            dt = datetime.fromisoformat(s.replace("Z", ""))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return s[:10]

    def _fmt_money(self, value: float) -> str:
        try:
            s = f"{float(value):,.2f}"
            return s.replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "0,00"

    def _fmt_qty(self, value: float) -> str:
        try:
            if float(value).is_integer():
                return str(int(value))
            return self._fmt_money(value)
        except Exception:
            return "0"

    def _paginate_items(self, items: List[Dict[str, Any]], *, per_page: int) -> List[List[Dict[str, Any]]]:
        if not items:
            return [[]]
        return [items[i:i + per_page] for i in range(0, len(items), per_page)]

    def _to_int(self, v: Any) -> Optional[int]:
        try:
            if v is None or v == "":
                return None
            return int(v)
        except Exception:
            return None

    def _to_float(self, v: Any) -> float:
        try:
            if v is None or v == "":
                return 0.0
            return float(v)
        except Exception:
            return 0.0

    def _digits(self, s: Any) -> str:
        return "".join(ch for ch in str(s or "") if ch.isdigit())
