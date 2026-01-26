from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session


class FacturasRepository:
    """Consultas a 'facturas' y catálogos auxiliares para facturación."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------- Lookups --------------------

    def list_tipos_comprobante(self) -> List[Dict[str, Any]]:
        """
        Tipos de comprobante (tabla opcional 'tipos_comprobante').
        Fallback a códigos comunes AR.
        """
        try:
            rows = self.db.execute(
                text("SELECT codigo, nombre FROM tipos_comprobante ORDER BY nombre ASC")
            ).mappings().all()
            out = [{"codigo": r["codigo"], "nombre": r["nombre"]} for r in rows]
            if out:
                return out
        except Exception:
            pass

        return [
            {"codigo": "FA", "nombre": "Factura A"},
            {"codigo": "FB", "nombre": "Factura B"},
            {"codigo": "FC", "nombre": "Factura C"},
            {"codigo": "NCA", "nombre": "Nota de crédito A"},
            {"codigo": "NCB", "nombre": "Nota de crédito B"},
            {"codigo": "NCC", "nombre": "Nota de crédito C"},
            {"codigo": "NDA", "nombre": "Nota de débito A"},
            {"codigo": "NDB", "nombre": "Nota de débito B"},
            {"codigo": "NDC", "nombre": "Nota de débito C"},
        ]

    def list_estados_facturas(self) -> List[Dict[str, Any]]:
        """
        Estados de facturas desde 'estados' (tipo='facturas'), si existe.
        Fallback vacío (UI mostrará "Todos").
        """
        try:
            rows = self.db.execute(
                text(
                    "SELECT id, nombre "
                    "FROM estados "
                    "WHERE tipo = 'facturas' "
                    "ORDER BY nombre ASC"
                )
            ).mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def list_puntos_venta(self) -> List[Dict[str, Any]]:
        """
        Devuelve los puntos de venta definidos en la tabla 'puntos_venta'.
        """
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT
                        idpunto_venta,
                        punto_venta
                    FROM puntos_venta
                    ORDER BY punto_venta
                    """
                )
            ).mappings().all()
        except Exception:
            rows = []

        out: List[Dict[str, Any]] = []
        for r in rows:
            raw_pv = r.get("punto_venta")
            try:
                pv_int = int(raw_pv)
            except (TypeError, ValueError):
                pv_int = raw_pv
            out.append(
                {
                    "id": r.get("idpunto_venta"),
                    "punto_venta": pv_int,
                }
            )
        return out

    def list_condiciones_iva_receptor(self) -> List[Dict[str, Any]]:
        """
        Condiciones frente al IVA del receptor, desde tabla 'condiciones_iva_receptor'.
        """
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT
                        id,
                        nombre,
                        codigo,
                        descripcion
                    FROM condiciones_iva_receptor
                    ORDER BY nombre ASC, id ASC
                    """
                )
            ).mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []
    def get_by_id_con_venta(self, factura_id: int) -> dict | None:
        row = self.db.execute(
            text("""
                SELECT
                    f.*,
    
                    -- Cliente
                    c.id        AS cliente_id,
                    c.nombre    AS cliente_nombre,
                    c.apellido  AS cliente_apellido,
                    c.tipo_doc  AS cliente_tipo_doc,
                    c.nro_doc   AS cliente_nro_doc,
                    c.email     AS cliente_email,
                    c.telefono  AS cliente_telefono,
                    c.direccion AS cliente_direccion,
    
                    -- Venta
                    v.precio_total,
                    v.forma_pago_id,
                    v.anticipo,
    
                    -- Plan de financiación (si existe)
                    pf.cantidad_cuotas,
                    pf.importe_cuota,
    
                    -- Forma de pago
                    fp.nombre AS forma_pago_nombre
    
                FROM facturas f
                LEFT JOIN clientes c ON c.id = f.cliente_id
                LEFT JOIN ventas v ON v.id = f.venta_id
                LEFT JOIN plan_financiacion pf ON pf.venta_id = v.id
                LEFT JOIN forma_pago fp ON fp.id = v.forma_pago_id
                WHERE f.id = :id
            """),
            {"id": factura_id}
        ).mappings().first()
    
        return dict(row) if row else None
    
    
    # -------------------- Alta / helpers de numeración --------------------

    def get_next_numero(self, tipo: str, punto_venta: int) -> int:
        """
        Devuelve el próximo número de comprobante para (tipo, punto_venta),
        a partir del MAX(numero) actual. Si no hay registros, devuelve 1.
        """
        pv = int(punto_venta) if punto_venta is not None else 0

        row = self.db.execute(
            text(
                """
                SELECT COALESCE(MAX(numero), 0) AS max_nro
                FROM facturas
                WHERE tipo = :tipo AND punto_venta = :pv
                """
            ),
            {"tipo": tipo, "pv": pv},
        ).mappings().first()

        max_nro = int(row["max_nro"]) if row and row.get("max_nro") is not None else 0
        return max_nro + 1

    def insert_factura(self, cabecera: Dict[str, Any]) -> int:
        """
        Inserta un registro en 'facturas' y devuelve el ID generado.

        Soporta:
        - condicion_iva_receptor_id (si existe)
        - cbte_asoc_tipo / cbte_asoc_pto_vta / cbte_asoc_numero (opcionales)
          -> intenta insertarlos y si la tabla no los tiene, reintenta sin ellos.
        """
        base_data: Dict[str, Any] = {
            "tipo": cabecera.get("tipo"),
            "numero": cabecera.get("numero"),
            "fecha_emision": cabecera.get("fecha_emision"),
            "punto_venta": cabecera.get("punto_venta"),
            "moneda": cabecera.get("moneda", "ARS"),
            "cotizacion": cabecera.get("cotizacion", 1.0),
            "cae": cabecera.get("cae"),
            "fecha_cae": cabecera.get("fecha_cae"),
            "vto_cae": cabecera.get("vto_cae"),
            "subtotal": cabecera.get("subtotal", 0.0),
            "iva": cabecera.get("iva", 0.0),
            "total": cabecera.get("total", 0.0),
            "observaciones": cabecera.get("observaciones"),
            "estado_id": cabecera.get("estado_id"),
            "cliente_id": cabecera.get("cliente_id"),
            "condicion_iva_receptor_id": cabecera.get("condicion_iva_receptor_id"),
            "venta_id": cabecera.get("venta_id"),
            "factura_origen_id": cabecera.get("factura_origen_id"),
        }

        # Opcionales (NC asociada)
        opt_data = {
            "cbte_asoc_tipo": cabecera.get("cbte_asoc_tipo"),
            "cbte_asoc_pto_vta": cabecera.get("cbte_asoc_pto_vta"),
            "cbte_asoc_numero": cabecera.get("cbte_asoc_numero"),
        }
        include_opt = any(v not in (None, "", 0, "0") for v in opt_data.values())

        # Intento 1: con opcionales (si vienen)
        if include_opt:
            data = {**base_data, **opt_data}
            try:
                result = self.db.execute(
                    text(
                        """
                        INSERT INTO facturas (
                            tipo,
                            numero,
                            fecha_emision,
                            punto_venta,
                            moneda,
                            cotizacion,
                            cae,
                            fecha_cae,
                            vto_cae,
                            subtotal,
                            iva,
                            total,
                            observaciones,
                            estado_id,
                            cliente_id,
                            condicion_iva_receptor_id,
                            factura_origen_id, 
                            cbte_asoc_tipo,
                            cbte_asoc_pto_vta,
                            cbte_asoc_numero,
                            venta_id
                        )
                        VALUES (
                            :tipo,
                            :numero,
                            :fecha_emision,
                            :punto_venta,
                            :moneda,
                            :cotizacion,
                            :cae,
                            :fecha_cae,
                            :vto_cae,
                            :subtotal,
                            :iva,
                            :total,
                            :observaciones,
                            :estado_id,
                            :cliente_id,
                            :condicion_iva_receptor_id,
                            :factura_origen_id,
                            :cbte_asoc_tipo,
                            :cbte_asoc_pto_vta,
                            :cbte_asoc_numero,
                            :venta_id
                        )
                        """
                    ),
                    data,
                )
                new_id = result.lastrowid
                return int(new_id) if new_id is not None else new_id
            except Exception:
                # Si la tabla no tiene esas columnas, reintentamos sin ellas
                pass

        # Intento 2: base (sin opcionales)
        result = self.db.execute(
            text(
                """
                INSERT INTO facturas (
                    tipo,
                    numero,
                    fecha_emision,
                    punto_venta,
                    moneda,
                    cotizacion,
                    cae,
                    fecha_cae,
                    vto_cae,
                    subtotal,
                    iva,
                    total,
                    observaciones,
                    estado_id,
                    cliente_id,
                    condicion_iva_receptor_id,
                    factura_origen_id
                )
                VALUES (
                    :tipo,
                    :numero,
                    :fecha_emision,
                    :punto_venta,
                    :moneda,
                    :cotizacion,
                    :cae,
                    :fecha_cae,
                    :vto_cae,
                    :subtotal,
                    :iva,
                    :total,
                    :observaciones,
                    :estado_id,
                    :cliente_id,
                    :condicion_iva_receptor_id,
                    :factura_origen_id
                )
                """
            ),
            base_data,
        )

        new_id = result.lastrowid
        return int(new_id) if new_id is not None else new_id

    def insert_detalle(self, factura_id: int, items: List[Dict[str, Any]]) -> None:
        """
        Inserta filas en 'facturas_detalle' para la factura dada.
        """
        if not items:
            return

        for it in items:
            cantidad = float(it.get("cantidad") or 0)
            precio_unit = float(it.get("precio_unitario") or 0)
            alic_iva = float(it.get("alicuota_iva") or 0)

            # Recalcular importes si no vienen
            importe_neto = it.get("importe_neto")
            if importe_neto is None:
                importe_neto = cantidad * precio_unit

            importe_iva = it.get("importe_iva")
            if importe_iva is None:
                importe_iva = float(importe_neto) * alic_iva / 100.0

            importe_total = it.get("importe_total")
            if importe_total is None:
                importe_total = float(importe_neto) + float(importe_iva)

            params = {
                "factura_id": factura_id,
                "item_tipo": it.get("item_tipo", "VEHICULO"),
                "vehiculo_id": it.get("vehiculo_id"),
                "descripcion": it.get("descripcion"),
                "cantidad": cantidad,
                "precio_unitario": precio_unit,
                "alicuota_iva": alic_iva,
                "importe_neto": importe_neto,
                "importe_iva": importe_iva,
                "importe_total": importe_total,
            }

            self.db.execute(
                text(
                    """
                    INSERT INTO facturas_detalle (
                        factura_id,
                        item_tipo,
                        vehiculo_id,
                        descripcion,
                        cantidad,
                        precio_unitario,
                        alicuota_iva,
                        importe_neto,
                        importe_iva,
                        importe_total
                    )
                    VALUES (
                        :factura_id,
                        :item_tipo,
                        :vehiculo_id,
                        :descripcion,
                        :cantidad,
                        :precio_unitario,
                        :alicuota_iva,
                        :importe_neto,
                        :importe_iva,
                        :importe_total
                    )
                    """
                ),
                params,
            )

    def actualizar_cae_y_estado(
        self,
        factura_id: int,
        cae: Optional[str],
        fecha_cae: Optional[str],
        vto_cae: Optional[str],
        estado_id: Optional[int],
    ) -> None:
        """
        Pensado para ARCA: actualiza CAE, fechas y estado_id.
        """
        self.db.execute(
            text(
                """
                UPDATE facturas
                SET
                    cae = :cae,
                    fecha_cae = :fecha_cae,
                    vto_cae = :vto_cae,
                    estado_id = :estado_id
                WHERE id = :id
                """
            ),
            {
                "id": factura_id,
                "cae": cae,
                "fecha_cae": fecha_cae,
                "vto_cae": vto_cae,
                "estado_id": estado_id,
            },
        )

    def actualizar_estado(self, factura_id: int, estado_id: int) -> None:
        """
        Actualiza solo el estado_id de una factura.
        """
        self.db.execute(
            text(
                """
                UPDATE facturas
                SET estado_id = :estado_id
                WHERE id = :id
                """
            ),
            {"id": factura_id, "estado_id": estado_id},
        )

    # -------------------- Búsqueda / Detalle --------------------

    def search(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filtros admitidos:
          - tipo, pto_vta, numero, cliente, cuit
          - estado_id
          - fecha_desde (YYYY-MM-DD), fecha_hasta (YYYY-MM-DD)
        """
        f: Dict[str, Any] = filters or {}
        where = ["(1=1)"]
        params: Dict[str, Any] = {}

        # sanitizar paginación
        try:
            page_i = int(page)
        except Exception:
            page_i = 1
        try:
            page_size_i = int(page_size)
        except Exception:
            page_size_i = 25

        page_i = max(page_i, 1)
        page_size_i = max(page_size_i, 1)
        offset = (page_i - 1) * page_size_i

        # tipo comprobante
        if f.get("tipo"):
            where.append("f.tipo = :tipo")
            params["tipo"] = f["tipo"]

        # punto de venta
        if f.get("pto_vta"):
            where.append("f.punto_venta = :pto_vta")
            try:
                params["pto_vta"] = int(f["pto_vta"])
            except Exception:
                params["pto_vta"] = f["pto_vta"]

        # número (like)
        if f.get("numero"):
            where.append("CAST(f.numero AS CHAR) LIKE :numero")
            params["numero"] = f"%{f['numero']}%"

        # cliente por nombre/apellido
        if f.get("cliente"):
            where.append("LOWER(CONCAT_WS(' ', c.nombre, c.apellido)) LIKE :cliente")
            params["cliente"] = f"%{str(f['cliente']).lower()}%"

        # CUIT/CUIL del filtro -> usamos nro_doc
        if f.get("cuit"):
            doc_digits = "".join(ch for ch in str(f["cuit"]) if ch.isdigit())
            if doc_digits:
                where.append("REPLACE(COALESCE(c.nro_doc, ''), '-', '') LIKE :doc")
                params["doc"] = f"%{doc_digits}%"

        # estado
        if f.get("estado_id") not in (None, "", "null"):
            where.append("f.estado_id = :estado_id")
            try:
                params["estado_id"] = int(f["estado_id"])
            except Exception:
                params["estado_id"] = f["estado_id"]

        # fechas
        # Nota: fecha_emision es datetime, así que fecha_hasta conviene llevarla a fin de día.
        if f.get("fecha_desde"):
            where.append("f.fecha_emision >= :fd")
            params["fd"] = f["fecha_desde"]

        if f.get("fecha_hasta"):
            fh_raw = str(f["fecha_hasta"]).strip()
            try:
                # si viene YYYY-MM-DD => 23:59:59 para incluir todo el día
                dt = datetime.strptime(fh_raw, "%Y-%m-%d")
                fh = dt.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                # si ya viene con hora, o viene algo raro, lo pasamos tal cual
                fh = fh_raw
            where.append("f.fecha_emision <= :fh")
            params["fh"] = fh

        where_sql = " AND ".join(where)

        sql_base = f"""
            FROM facturas f
            LEFT JOIN clientes c ON c.id = f.cliente_id
            LEFT JOIN estados  e ON e.id = f.estado_id
            WHERE {where_sql}
        """

        total = self.db.execute(text(f"SELECT COUNT(*) {sql_base}"), params).scalar_one()

        rows = self.db.execute(
            text(
                f"""
                SELECT
                    f.id,
                    f.fecha_emision AS fecha,
                    f.tipo,
                    f.punto_venta    AS pto_vta,
                    f.numero,
                    CONCAT_WS(' ', c.nombre, c.apellido) AS cliente,
                    TRIM(CONCAT(COALESCE(c.tipo_doc, ''),
                                CASE WHEN c.tipo_doc IS NULL OR c.tipo_doc = '' THEN '' ELSE ' ' END,
                                COALESCE(c.nro_doc, ''))) AS cuit,
                    f.total,
                    f.estado_id,
                    e.nombre AS estado,
                    f.cae,
                    f.vto_cae,
                    f.observaciones
                {sql_base}
                ORDER BY f.fecha_emision DESC, f.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": page_size_i, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], int(total)

    def get_by_id(self, factura_id: int) -> Optional[Dict[str, Any]]:
        """
        Devuelve la cabecera de factura con datos de cliente y estado.
        Incluye campos del cliente para la pantalla de consulta.
        """
        row = self.db.execute(
            text(
                """
                SELECT
                    f.*,
                    CONCAT_WS(' ', c.nombre, c.apellido) AS cliente,
                    TRIM(CONCAT(COALESCE(c.tipo_doc, ''),
                                CASE WHEN c.tipo_doc IS NULL OR c.tipo_doc = '' THEN '' ELSE ' ' END,
                                COALESCE(c.nro_doc, ''))) AS cuit,
                    c.nombre      AS cliente_nombre,
                    c.apellido    AS cliente_apellido,
                    c.tipo_doc    AS cliente_tipo_doc,
                    c.nro_doc     AS cliente_nro_doc,
                    c.email       AS cliente_email,
                    c.telefono    AS cliente_telefono,
                    c.direccion   AS cliente_direccion,
                    e.nombre      AS estado_nombre
                FROM facturas f
                LEFT JOIN clientes c ON c.id = f.cliente_id
                LEFT JOIN estados  e ON e.id = f.estado_id
                WHERE f.id = :id
                """
            ),
            {"id": factura_id},
        ).mappings().first()

        return dict(row) if row else None

    def get_detalle_by_factura(self, factura_id: int) -> List[Dict[str, Any]]:
        """
        Lee el detalle de la factura desde 'facturas_detalle'.
        """
        rows = self.db.execute(
            text(
                """
                SELECT
                    id,
                    factura_id,
                    item_tipo,
                    vehiculo_id,
                    descripcion,
                    cantidad,
                    precio_unitario,
                    alicuota_iva,
                    importe_neto,
                    importe_iva,
                    importe_total
                FROM facturas_detalle
                WHERE factura_id = :fid
                ORDER BY id ASC
                """
            ),
            {"fid": factura_id},
        ).mappings().all()

        return [dict(r) for r in rows]
