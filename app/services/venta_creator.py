from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.domain_constants import EstadoStock, FormaPago, TipoMovimientoStock
from app.services.stock_service import StockService
from app.services.ventas_service import VentasService


class VentaCreator:
    """Coordina venta y stock dentro de la transaccion de facturacion."""

    def __init__(
        self,
        *,
        ventas_service: Optional[VentasService] = None,
        stock_service: Optional[StockService] = None,
    ) -> None:
        self._ventas = ventas_service or VentasService()
        self._stock = stock_service or StockService()

    def crear_venta_base(
        self,
        *,
        db: Session,
        cabecera_db: Dict[str, Any],
        items: List[Dict[str, Any]],
    ) -> int:
        vehiculo_id = items[0]["vehiculo_id"] if items else None
        return self._ventas.crear_venta(
            db=db,
            cliente_id=cabecera_db.get("cliente_id"),
            vehiculo_id=vehiculo_id,
            fecha=cabecera_db.get("fecha_emision"),
        )

    def marcar_vehiculos_vendidos(
        self,
        *,
        db: Session,
        factura_id: int,
        items: Iterable[Dict[str, Any]],
    ) -> None:
        vehiculo_ids = {
            it.get("vehiculo_id")
            for it in items
            if it.get("vehiculo_id")
        }

        if not vehiculo_ids:
            return

        rows = db.execute(
            text(
                """
                SELECT id, estado_stock_id
                FROM vehiculos
                WHERE id IN :ids
                """
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": tuple(vehiculo_ids)},
        ).mappings().all()

        no_disponibles = [
            r["id"]
            for r in rows
            if int(r["estado_stock_id"] or 0) != EstadoStock.DISPONIBLE
        ]

        if no_disponibles:
            raise ValueError(
                f"Vehiculos no disponibles para facturar: {no_disponibles}"
            )

        for row in rows:
            self._stock.cambiar_estado(
                db,
                vehiculo_id=int(row["id"]),
                estado_nuevo_id=EstadoStock.VENDIDO,
                tipo_movimiento=TipoMovimientoStock.VENTA,
                origen_tipo="facturas",
                origen_id=factura_id,
                observaciones="Factura creada.",
            )

    def completar_venta_desde_factura(
        self,
        *,
        db: Session,
        venta_id: int,
        cabecera: Dict[str, Any],
        cabecera_db: Dict[str, Any],
    ) -> None:
        precio_real = float(cabecera.get("precio_real") or 0.0)
        forma_pago_id = cabecera.get("forma_pago_id")
        anticipo = float(cabecera.get("anticipo") or 0.0)
        cantidad_cuotas = int(cabecera.get("cantidad_cuotas") or 0)
        importe_cuota = float(cabecera.get("importe_cuota") or 0.0)

        if forma_pago_id != FormaPago.FINANCIACION:
            anticipo = 0.0
            cantidad_cuotas = 0
            importe_cuota = 0.0

        self._ventas.completar_venta(
            db=db,
            venta_id=venta_id,
            precio_total=precio_real,
            forma_pago_id=forma_pago_id,
            importe_cuota=importe_cuota,
            anticipo=anticipo,
            cantidad_cuotas=cantidad_cuotas,
            fecha_inicio=cabecera_db.get("fecha_emision"),
        )
