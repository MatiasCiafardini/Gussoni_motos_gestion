from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
import base64
import json
import os
from pathlib import Path
import sys
import app.ui.utils.paths as paths
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parents[1]  # app/



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
    nombre_fantasia: str = "GUSSONI AUTOMOTORES 2021 SAS"
    razon_social: str = "GUSSONI AUTOMOTORES 2021 SAS"
    domicilio: str = "Vieytes 664 - San Antonio De Areco, Buenos Aires"
    telefono: str = "Tel: 02326 497388"
    condicion_iva: str = "IVA Responsable Inscripto"
    cuit: str = "33717057479"
    iibb: str = "33-71705747-9"
    inicio_actividades: str = "01/07/2021"
    punto_venta_default: int = 3


class ComprobantesService:
    TOP_BAND_H = 10 * mm
    HEADER_H = 36 * mm
    CLIENTE_H = 22 * mm
    TABLE_H = 150 * mm
    RESUMEN_H = 22 * mm
    FOOTER_H = 24 * mm

    def __init__(self, *, empresa: Optional[EmpresaConfig] = None) -> None:
        self._svc = FacturasService()
        self._empresa = empresa or EmpresaConfig()

        self.LOGO_GUSSONI_PATH = paths.LOGO_GUSSONI
        self.LOGO_AFIP_PATH   = paths.LOGO_AFIP

    def generar_pdf(self, factura_id: int) -> str:
        fac = self._svc.get(int(factura_id))
        if not fac:
            raise ValueError(f"No se encontró la factura ID {factura_id}.")
        print("aca entra 3")
        items = self._svc.get_detalle(int(factura_id)) or []

        out_dir = Path.home() / "Downloads"
        out_dir.mkdir(parents=True, exist_ok=True)
        print("aca entra 4")
        tipo = (fac.get("tipo") or "").upper() or "FB"
        pv = self._to_int(fac.get("punto_venta") or fac.get("pto_vta") or self._empresa.punto_venta_default) or 0
        nro = self._to_int(fac.get("numero") or 0) or 0
        print("aca entra 5")
        filename = f"{tipo}_{str(pv).zfill(5)}-{str(nro).zfill(8)}.pdf"
        pdf_path = out_dir / filename
        print("aca entra 6")
        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        c.setTitle(filename)
        print("aca entra 7")
        estado_id = self._to_int(fac.get("estado_id"))
        cae = str(fac.get("cae") or "").strip()
        print("aca entra 8")
        try:
            est_aut = self._svc.ESTADO_AUTORIZADA
        except Exception:
            est_aut = None

        autorizado = bool(cae) and (est_aut is None or estado_id == est_aut)

        pages = self._paginate_items(items, per_page=18)
        total_pages = len(pages) if pages else 1

        letra = self._letra_from_tipo(tipo)
        cod_afip = self._cod_afip_from_tipo(tipo)
        print("aca entra 9")
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
            print("aca nuevamente llega")
            if i < total_pages:
                c.showPage()
        print("aca entra 10")
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
        print("header 1")
        # Banda ORIGINAL
        self._draw_top_band(c, M, y_top)
        y_top -= self.TOP_BAND_H
        print("header 2")
        # Header principal
        self._draw_header(c, fac, M, y_top, self.HEADER_H, page, total_pages, letra, cod_afip)
        y = y_top - self.HEADER_H

        print("cliente 1")
        self._draw_cliente(c, fac, M, y, self.CLIENTE_H)
        y -= self.CLIENTE_H
        print("tabla 1")
        self._draw_table(c, page_items, M, y, self.TABLE_H)
        y -= self.TABLE_H
        print("resumen 1")
        self._draw_resumen(c, fac, all_items, M, y, self.RESUMEN_H)
        y -= self.RESUMEN_H
        print("footer 1")
        self._draw_footer(c, fac, all_items, M, y, self.FOOTER_H, autorizado, page, total_pages)
        print("footer 2")


    def _draw_top_band(self, c: canvas.Canvas, M: float, y_top: float) -> None:
        W, _ = A4
        h = self.TOP_BAND_H

        # línea inferior de la banda
        c.setLineWidth(0.6)
        c.line(M, y_top - h, W - M, y_top - h)

        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(
            W / 2,
            y_top - h + 3.5 * mm,
            "ORIGINAL"
        )

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
    
        # ==================================================
        # CUADRADO LETRA
        # ==================================================
        sq = 16 * mm
        sq_x = x + w / 2 - sq / 2
        sq_y = y + h - sq
    
        c.rect(sq_x, sq_y, sq, sq, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(sq_x + sq / 2, sq_y + sq * 0.62, letra)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(sq_x + sq / 2, sq_y + sq * 0.22, f"COD. {cod_afip}")
    
        split_x = sq_x + sq / 2
    
        # ==================================================
        # IZQUIERDA
        # ==================================================
        lx = x + 3 * mm
        top_y = y + h - 6 * mm
    
        logo_w = 14 * mm
        logo_h = 10 * mm
    
        self._draw_logo_if_exists(
            c,
            self.LOGO_GUSSONI_PATH,
            lx,
            top_y - logo_h,
            logo_w,
            logo_h
        )
    
        c.setFont("Helvetica-Bold", 9)
        c.drawString(lx + logo_w + 3 * mm, top_y - 2 * mm, self._empresa.nombre_fantasia)
    
        info_y = top_y - logo_h - 4 * mm
    
        c.setFont("Helvetica-Bold", 7)
        lbl_rs = "Razón Social:"
        lbl_dom = "Domicilio Comercial:"
        lbl_iva = "Condición frente al IVA:"
    
        c.drawString(lx, info_y, lbl_rs)
        c.drawString(lx, info_y - 4 * mm, lbl_dom)
        c.drawString(lx, info_y - 8 * mm, lbl_iva)
    
        c.setFont("Helvetica", 7)
        c.drawString(lx + stringWidth(lbl_rs, "Helvetica-Bold", 7) + 1.5 * mm, info_y, self._empresa.razon_social)
        c.drawString(lx + stringWidth(lbl_dom, "Helvetica-Bold", 7) + 1.5 * mm, info_y - 4 * mm, self._empresa.domicilio)
        c.drawString(lx + stringWidth(lbl_iva, "Helvetica-Bold", 7) + 1.5 * mm, info_y - 8 * mm, self._empresa.condicion_iva)
    
        # ==================================================
        # DERECHA: FACTURA / NOTA DE CRÉDITO
        # ==================================================
        rx = split_x + 9 * mm   # <<< un poco más a la derecha

        tipo = (fac.get("tipo") or "").upper() or "FB"
        titulo = "NOTA DE CRÉDITO" if tipo.startswith("NC") else "FACTURA"

        pv = self._to_int(
            fac.get("punto_venta") or fac.get("pto_vta") or self._empresa.punto_venta_default
        ) or 0
        nro = self._to_int(fac.get("numero") or 0) or 0
        fecha = self._fmt_fecha(fac.get("fecha_emision") or fac.get("fecha"))

        # ==================================================
        # BLOQUE SUPERIOR (COMPROBANTE) — OK
        # ==================================================
        fy = sq_y + sq - 4 * mm

        c.setFont("Helvetica-Bold", 12)
        c.drawString(rx, fy, titulo)

        c.setFont("Helvetica", 8)
        c.drawRightString(
            x + w - 3 * mm,
            fy,
            f"Página {page} de {total_pages}"
        )

        fy -= 5 * mm
        c.setFont("Helvetica-Bold", 8)
        c.drawString(rx, fy, "Punto de Venta:")
        c.setFont("Helvetica", 8)
        c.drawString(rx + 32 * mm, fy, str(pv).zfill(5))

        c.setFont("Helvetica-Bold", 8)
        c.drawString(rx + 55 * mm, fy, "Comp. Nro:")
        c.setFont("Helvetica", 8)
        c.drawString(rx + 75 * mm, fy, str(nro).zfill(8))

        fy -= 4 * mm
        c.setFont("Helvetica-Bold", 8)
        c.drawString(rx, fy, "Fecha de Emisión:")
        c.setFont("Helvetica", 8)
        c.drawString(rx + 32 * mm, fy, fecha)

        # ==================================================
        # BLOQUE INFERIOR (FISCAL) — LABEL EN NEGRITA
        # ==================================================
        fy = y + 12 * mm
        
        # CUIT
        c.setFont("Helvetica-Bold", 8)
        c.drawString(rx, fy, "CUIT:")
        label_w = stringWidth("CUIT:", "Helvetica-Bold", 8)
        c.setFont("Helvetica", 8)
        c.drawString(rx + label_w + 1.5 * mm, fy, self._empresa.cuit)
        
        # Ingresos Brutos
        fy -= 4 * mm
        c.setFont("Helvetica-Bold", 8)
        c.drawString(rx, fy, "Ingresos Brutos:")
        label_w = stringWidth("Ingresos Brutos:", "Helvetica-Bold", 8)
        c.setFont("Helvetica", 8)
        c.drawString(rx + label_w + 1.5 * mm, fy, self._empresa.iibb)
        
        # Fecha Inicio Actividades
        fy -= 4 * mm
        c.setFont("Helvetica-Bold", 8)
        c.drawString(rx, fy, "Fecha de Inicio de Actividades:")
        label_w = stringWidth("Fecha de Inicio de Actividades:", "Helvetica-Bold", 8)
        c.setFont("Helvetica", 8)
        c.drawString(rx + label_w + 1.5 * mm, fy, self._empresa.inicio_actividades)
        

    
        # ==================================================
        # LÍNEA DIVISORIA
        # ==================================================
        c.line(split_x, y, split_x, sq_y)
    
    


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
    
        # Márgenes
        left_x = x + 3 * mm
        right_x = x + w * 0.52
    
        # Líneas (una sola grilla)
        l1 = y_top - 6 * mm
        l2 = y_top - 11 * mm
        l3 = y_top - 16 * mm
    
        # -------------------------
        # Datos
        # -------------------------
        cliente = (
            f"{(fac.get('cliente_nombre') or '').strip()} {(fac.get('cliente_apellido') or '').strip()}".strip()
            or str(fac.get("cliente") or "").strip()
        )
    
        domicilio = str(
            fac.get("cliente_direccion")
            or fac.get("direccion")
            or ""
        ).strip()
    
        condicion_iva = str(
            fac.get("cliente_condicion_iva")
            or fac.get("condicion_iva_cliente")
            or "Consumidor Final"
        ).strip()
    
        cuil = self._fmt_doc(
            str(fac.get("cliente_tipo_doc") or fac.get("tipo_doc") or ""),
            str(fac.get("cliente_nro_doc") or fac.get("nro_doc") or ""),
        )
    
        condicion_venta = (
            str(
                fac.get("forma_pago_texto")
                or fac.get("forma_pago_nombre")
                or fac.get("forma_pago")
                or fac.get("condicion_venta")
                or fac.get("forma_pago_descripcion")
                or ""
            ).strip()
        )

        telefono = str(
            fac.get("cliente_telefono")
            or fac.get("telefono")
            or ""
        ).strip()

    
        # -------------------------
        # Línea 1
        # -------------------------
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(left_x, l1, "CUIL:")
        c.drawString(right_x, l1, "Apellido y Nombre / Razón Social:")
    
        c.setFont("Helvetica", 7.2)
        c.drawString(left_x + 10 * mm, l1, cuil)
        c.drawString(right_x + 52 * mm, l1, cliente)
    
        # -------------------------
        # Línea 2
        # -------------------------
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(left_x, l2, "Condición frente al IVA:")
        c.drawString(right_x, l2, "Domicilio:")
    
        c.setFont("Helvetica", 7.2)
        c.drawString(left_x + 38 * mm, l2, condicion_iva)
        c.drawString(right_x + 20 * mm, l2, domicilio)
    
        # -------------------------
        # Línea 3
        # -------------------------
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(left_x, l3, "Condición de Venta:")
        c.drawString(right_x, l3, "Teléfono:")

        c.setFont("Helvetica", 7.2)
        c.drawString(left_x + 32 * mm, l3, condicion_venta)
        c.drawString(right_x + 20 * mm, l3, telefono)

    



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
        raw = str(it.get("descripcion") or "").strip()
        if not raw:
            return ""

        # Ejemplo:
        # Motomel C110DLX 2026 | Motor: XXXXX | Cuadro: YYYYY
        parts = [p.strip() for p in raw.split("|") if p.strip()]

        marca = ""
        modelo = ""
        anio = ""
        motor = ""
        chasis = ""

        if parts:
            tokens = parts[0].split()
            if len(tokens) >= 3:
                marca = tokens[0]
                modelo = " ".join(tokens[1:-1])
                anio = tokens[-1] if tokens[-1].isdigit() else ""

        for p in parts[1:]:
            low = p.lower()
            if "motor" in low:
                motor = p.split(":", 1)[-1].strip()
            if "cuadro" in low or "chasis" in low:
                chasis = p.split(":", 1)[-1].strip()

        lines = []

        if marca:
            lines.append(f"MOTOVEHÍCULO MARCA: {marca.upper()}")
        if modelo:
            lines.append(f"MODELO: {modelo}")
        if anio:
            lines.append(f"AÑO: {anio}")
        if marca:
            lines.append(f"MARCA CHASIS: {marca.upper()}")
        if chasis:
            lines.append(f"NÚMERO CHASIS: {chasis}")
        if marca:
            lines.append(f"MARCA MOTOR: {marca.upper()}")
        if motor:
            lines.append(f"NÚMERO MOTOR: {motor}")

        return "\n".join(lines)


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

        # ---- BLOQUE TOTALES A LA DERECHA ----
        bx = x + w - 80 * mm
        by = y + h - 6 * mm

        c.setFont("Helvetica", 7)
        c.drawRightString(bx + 76 * mm, by, f"Subtotal: $ {self._fmt_money(total)}")
        c.drawRightString(bx + 76 * mm, by - 4 * mm, "Importe Otros Tributos: $ 0,00")

        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(
            bx + 76 * mm,
            by - 9 * mm,
            f"Importe Total: $ {self._fmt_money(total)}"
        )

        # ---- IVA CONTENIDO ----
        c.setFont("Helvetica", 7)
        c.drawString(
            x + 3 * mm,
            y + 6 * mm,
            "Régimen de Transparencia Fiscal al Consumidor (Ley 27.743)"
        )
        c.drawString(
            x + 3 * mm,
            y + 2 * mm,
            f"IVA Contenido: $ {self._fmt_money(iva21)}"
        )

        

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

        # Totales (no rompen aunque falten items)
        neto, iva21, total = self._calc_totals_iva21(fac, items)

        # Datos fiscales (defensivo)
        cae = str(fac.get("cae") or "").strip()
        vto = self._fmt_fecha(fac.get("vto_cae") or "")

        # ----------------------------------
        # Lógica REAL de QR / autorización
        # ----------------------------------
        estado_id = self._to_int(fac.get("estado_id"))
        try:
            est_aut = self._svc.ESTADO_AUTORIZADA
        except Exception:
            est_aut = None

        estado_autorizado = (est_aut is None or estado_id == est_aut)
        tiene_cae = bool(cae)

        puede_mostrar_qr = estado_autorizado and tiene_cae

        # ----------------------------------
        # Posiciones base (SIEMPRE definidas)
        # ----------------------------------
        qr_size = 24 * mm
        qr_x = x + 4 * mm
        qr_y = y + 0 * mm

        ax = qr_x + qr_size + 6 * mm  # eje para logo + texto

        # ----------------------------------
        # QR o placeholder
        # ----------------------------------
        if puede_mostrar_qr:
            payload = self._build_qr_payload(fac)
            self._draw_qr(c, payload, qr_x, qr_y, qr_size)
        else:
            c.rect(
                qr_x + 1 * mm,
                qr_y + 1 * mm,
                18 * mm,
                18 * mm,
                stroke=1,
                fill=0,
            )

        # ----------------------------------
        # Logo AFIP / ARCA
        # ----------------------------------
        self._draw_logo_if_exists(
            c,
            self.LOGO_AFIP_PATH,
            ax,
            y + 14 * mm,
            18 * mm,
            9 * mm
        )

        # Texto debajo del logo
        text_x = ax
        text_y = y + 10 * mm

        c.setFont("Helvetica-Bold", 8)
        c.drawString(
            text_x,
            text_y,
            "Comprobante Autorizado" if puede_mostrar_qr else "Comprobante no autorizado"
        )

        c.setFont("Helvetica", 6.5)
        c.drawString(
            text_x,
            text_y - 4 * mm,
            "Esta agencia no se responsabiliza por los datos ingresados en el detalle de la operación"
        )

        # ----------------------------------
        # CAE y Vencimiento (defensivo)
        # ----------------------------------
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(
            x + w - 4 * mm,
            y + h - 6 * mm,
            f"CAE N°: {cae}" if cae else "CAE N°: —"
        )

        c.setFont("Helvetica", 7)
        c.drawRightString(
            x + w - 4 * mm,
            y + h - 11 * mm,
            f"Fecha de Vto. CAE: {vto}" if vto else "Fecha de Vto. CAE: —"
        )



        

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

        # Tipo doc receptor (ya viene como ID AFIP)
        tipo_doc_rec = self._to_int(
            fac.get("cliente_tipo_doc_id")
        ) or 0

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
