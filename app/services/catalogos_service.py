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

        # ---- catálogos lógicos ----

        tipos_comprobante = [
            {"codigo": "FA", "nombre": "Factura A"},
            {"codigo": "FB", "nombre": "Factura B"},
            {"codigo": "FC", "nombre": "Factura C"},
            {"codigo": "NCA", "nombre": "Nota de Crédito A"},
            {"codigo": "NCB", "nombre": "Nota de Crédito B"},
            {"codigo": "NCC", "nombre": "Nota de Crédito C"},
        ]

        condicion_iva_receptor = [
            {"id": 5, "codigo": "CF", "descripcion": "Consumidor Final"},
            {"id": 1, "codigo": "RI", "descripcion": "Responsable Inscripto"},
            {"id": 6, "codigo": "MT", "descripcion": "Monotributista"},
            {"id": 4, "codigo": "EX", "descripcion": "Exento"},
        ]

        puntos_venta = s.execute(
            text("""
                SELECT punto_venta
                FROM puntos_venta
                ORDER BY punto_venta
            """)
        ).mappings().all()



        # ---- cache ----
        cache.set("colores", colores)
        cache.set("estados_stock", estados_stock)
        cache.set("condiciones", condiciones)
        cache.set("proveedores", proveedores)
        cache.set("forma_pago", forma_pago)
        cache.set("tipos_comprobante", tipos_comprobante)
        cache.set("condicion_iva_receptor", condicion_iva_receptor)
        cache.set("puntos_venta", puntos_venta)

        cache.mark_loaded()


    # -------------------------------------------------
    # Getters (leen SIEMPRE del caché, con fallback)
    # -------------------------------------------------
    def get_colores(self):
        return CatalogCache.get().get_value("colores") or self.warmup_all()["colores"]

    def get_estados_stock(self):
        return CatalogCache.get().get_value("estados_stock") or self.warmup_all()["estados_stock"]

    def get_condiciones(self):
        return CatalogCache.get().get_value("condiciones") or self.warmup_all()["condiciones"]

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
