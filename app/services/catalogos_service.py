from __future__ import annotations
from typing import Dict, Any
from sqlalchemy import text

from app.data.database import SessionLocal
from app.core.catalog_cache import CatalogCache
# 👉 Agregamos forma_pago al listado oficial de catálogos
CAT_KEYS = [
    "colores",
    "estados_stock",
    "condiciones",
    "proveedores",
    "forma_pago",
    "tipos_comprobante",
    "condicion_iva_receptor",
    "puntos_venta",
    "condicion_iva_receptor",
    "estados_factura",
    "estados_clientes",  
    "tipos_documento",
]


class CatalogosService:
    """
    Lee catálogos desde DB y los guarda en CatalogCache.
    Usá warmup_all() antes de mostrar páginas que dependan de catálogos.
    """

    def warmup_all(self):
        cache = CatalogCache.get()
        if cache.has_all(CAT_KEYS):
            return {k: cache.get_value(k) for k in CAT_KEYS}

        with SessionLocal() as s:
            colores = s.execute(
                text("SELECT id, nombre FROM colores ORDER BY nombre")
            ).mappings().all()

            estados_stock = s.execute(
                text("SELECT id, nombre FROM estados_stock ORDER BY nombre")
            ).mappings().all()

            condiciones = s.execute(
                text("""
                    SELECT id, nombre
                    FROM estados
                    WHERE tipo = 'vehiculos'
                    ORDER BY nombre
                """)
            ).mappings().all()
            estados_factura = s.execute(
                text("""
                    SELECT id, nombre
                    FROM estados
                    WHERE tipo = 'facturas'
                    ORDER BY nombre
                """)
            ).mappings().all()
            estados_clientes = s.execute(
                text("""
                    SELECT id, nombre
                    FROM estados
                    WHERE tipo = 'clientes'
                    ORDER BY nombre
                """)
            ).mappings().all()

            tipos_documento = s.execute(
                text("""
                    SELECT id, codigo, descripcion
                    FROM tipos_documento
                    WHERE activo = 1
                    ORDER BY descripcion
                """)
            ).mappings().all()

            proveedores = s.execute(
                text("""
                    SELECT id, razon_social AS nombre
                    FROM proveedores
                    ORDER BY nombre
                """)
            ).mappings().all()

            forma_pago = s.execute(
                text("SELECT id, nombre FROM forma_pago ORDER BY nombre")
            ).mappings().all()
            puntos_venta = s.execute(
                text("""
                    SELECT punto_venta
                    FROM puntos_venta
                    ORDER BY punto_venta
                """)
            ).mappings().all()

        # ---- catálogos lógicos ----

        tipos_comprobante = s.execute(
            text("""
                SELECT
                    id,
                    codigo,
                    nombre,
                    letra,
                    es_nota_credito,
                    es_nota_debito,
                    activo
                FROM tipos_comprobante
                WHERE activo = 1
                ORDER BY nombre
            """)
        ).mappings().all()


        condicion_iva_receptor = [
            {"id": 5, "codigo": "CF", "descripcion": "Consumidor Final"},
            {"id": 1, "codigo": "RI", "descripcion": "Responsable Inscripto"},
            {"id": 6, "codigo": "MT", "descripcion": "Monotributista"},
            {"id": 4, "codigo": "EX", "descripcion": "Exento"},
        ]

        


        # ---- cache ----
        cache.set("colores", colores)
        cache.set("estados_stock", estados_stock)
        cache.set("condiciones", condiciones)
        cache.set("proveedores", proveedores)
        cache.set("forma_pago", forma_pago)
        cache.set("tipos_comprobante", tipos_comprobante)
        cache.set("condicion_iva_receptor", condicion_iva_receptor)
        cache.set("puntos_venta", puntos_venta)
        cache.set("estados_factura", estados_factura)
        cache.set("tipos_documento", tipos_documento)
        cache.set("estados_clientes", estados_clientes)
        


        cache.mark_loaded()

        return {k: cache.get_value(k) for k in CAT_KEYS}



    # -------------------------------------------------
    # Getters (leen SIEMPRE del caché, con fallback)
    # -------------------------------------------------
    def get_colores(self):
        return CatalogCache.get().get_value("colores") or self.warmup_all()["colores"]
    def get_estados_clientes(self):
        return (
            CatalogCache.get().get_value("estados_clientes")
            or self.warmup_all()["estados_clientes"]
        )
    def get_estados_stock(self):
        return CatalogCache.get().get_value("estados_stock") or self.warmup_all()["estados_stock"]

    def get_condiciones(self):
        return CatalogCache.get().get_value("condiciones") or self.warmup_all()["condiciones"]
    def get_tipos_documento(self):
        return (
            CatalogCache.get().get_value("tipos_documento")
            or self.warmup_all()["tipos_documento"]
        )
    def get_tipo_doc_by_id(self, tipo_doc_id: int) -> Dict[str, Any] | None:
        tipos = self.get_tipos_documento()
        for t in tipos:
            if t["id"] == tipo_doc_id:
                return t
        return None
    def get_tipo_doc_by_codigo(self, codigo: str) -> Dict[str, Any] | None:
        if not codigo:
            return None
        codigo = codigo.strip().upper()
        for t in self.get_tipos_documento():
            if t["codigo"].upper() == codigo:
                return t
        return None
    def require_tipo_doc(self, codigo: str) -> Dict[str, Any]:
        tipo = self.get_tipo_doc_by_codigo(codigo)
        if not tipo:
            raise ValueError(f"Tipo de documento inválido: {codigo}")
        return tipo
    def es_cuit(self, tipo_doc_id: int) -> bool:
        tipo = self.get_tipo_doc_by_id(tipo_doc_id)
        return bool(tipo and tipo["codigo"] == "CUIT")

    def es_cuil(self, tipo_doc_id: int) -> bool:
        tipo = self.get_tipo_doc_by_id(tipo_doc_id)
        return bool(tipo and tipo["codigo"] == "CUIL")

    def es_dni(self, tipo_doc_id: int) -> bool:
        tipo = self.get_tipo_doc_by_id(tipo_doc_id)
        return bool(tipo and tipo["codigo"] == "DNI")

    def es_consumidor_final(self, tipo_doc_id: int) -> bool:
        tipo = self.get_tipo_doc_by_id(tipo_doc_id)
        return bool(tipo and tipo["codigo"] == "CF")
    def get_tipo_comprobante_by_id(self, tipo_id: int) -> Dict[str, Any] | None:
        """
        Devuelve un tipo de comprobante por ID desde el caché.
        """
        if not tipo_id:
            return None

        tipos = self.get_tipos_comprobante()
        for t in tipos:
            if t.get("id") == tipo_id:
                return t

        return None

    def get_proveedores(self):
        return CatalogCache.get().get_value("proveedores") or self.warmup_all()["proveedores"]

    # ✅ NUEVO getter oficial
    def get_formas_pago(self):
        return CatalogCache.get().get_value("forma_pago") or self.warmup_all()["forma_pago"]
    
    def get_tipos_comprobante(self):
        return CatalogCache.get().get_value("tipos_comprobante") or self.warmup_all()["tipos_comprobante"]

    def get_condicion_iva_receptor(self):
        return CatalogCache.get().get_value("condicion_iva_receptor") or self.warmup_all()["condicion_iva_receptor"]

    def get_puntos_venta(self):
        return CatalogCache.get().get_value("puntos_venta") or self.warmup_all()["puntos_venta"]
    # -------------------------------------------------
    # Invalidate (si cambian tablas)
    # -------------------------------------------------
    def invalidate(self, *keys: str):
        CatalogCache.get().invalidate(*keys if keys else [])
    def get_estados_factura(self):
        return (
            CatalogCache.get().get_value("estados_factura")
            or self.warmup_all()["estados_factura"]
        )
