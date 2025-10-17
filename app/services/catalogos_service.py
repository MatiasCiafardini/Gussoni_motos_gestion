from __future__ import annotations
from typing import Dict, Any
from sqlalchemy import text
from app.data.database import SessionLocal
from app.core.catalog_cache import CatalogCache

CAT_KEYS = ["colores", "estados_stock", "condiciones", "proveedores"]

class CatalogosService:
    """
    Lee catálogos desde DB y los guarda en CatalogCache.
    Usá warmup_all() antes de mostrar páginas que dependan de catálogos.
    """

    def warmup_all(self) -> Dict[str, list[dict]]:
        cache = CatalogCache.get()
        if cache.has_all(CAT_KEYS):
            # Ya está cargado
            return {k: cache.get_value(k) for k in CAT_KEYS}

        # Una sola sesión / conexión para reducir latencia
        with SessionLocal() as s:
            colores = s.execute(text("SELECT id, nombre FROM colores ORDER BY nombre")).mappings().all()
            estados_stock = s.execute(text("SELECT id, nombre FROM estados_stock ORDER BY nombre")).mappings().all()
            condiciones = s.execute(text("SELECT id, nombre FROM estados_moto ORDER BY nombre")).mappings().all()
            proveedores = s.execute(text("""
                SELECT id, razon_social as nombre
                FROM proveedores
                ORDER BY nombre
            """)).mappings().all()

        cache.set("colores", colores)
        cache.set("estados_stock", estados_stock)
        cache.set("condiciones", condiciones)
        cache.set("proveedores", proveedores)
        cache.mark_loaded()

        return {
            "colores": colores,
            "estados_stock": estados_stock,
            "condiciones": condiciones,
            "proveedores": proveedores,
        }

    # Getters que leen SIEMPRE del caché (y si falta, hacen warmup)
    def get_colores(self):        return CatalogCache.get().get_value("colores")        or self.warmup_all()["colores"]
    def get_estados_stock(self):  return CatalogCache.get().get_value("estados_stock")  or self.warmup_all()["estados_stock"]
    def get_condiciones(self):    return CatalogCache.get().get_value("condiciones")    or self.warmup_all()["condiciones"]
    def get_proveedores(self):    return CatalogCache.get().get_value("proveedores")    or self.warmup_all()["proveedores"]

    # Invalida si cambian tablas (ej: agregaste un color o proveedor)
    def invalidate(self, *keys: str):
        CatalogCache.get().invalidate(*keys if keys else [])
