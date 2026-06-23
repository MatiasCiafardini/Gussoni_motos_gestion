from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.audit_log_service import AuditLogService


class StockService:
    """Registra historial de stock sin reemplazar el estado actual del vehiculo."""

    def __init__(self) -> None:
        self._table_available: Optional[bool] = None
        self._audit = AuditLogService()

    def _has_stock_movimientos(self, db: Session) -> bool:
        if self._table_available is not None:
            return self._table_available

        exists = db.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = 'stock_movimientos'
                LIMIT 1
                """
            ),
            {"schema": settings.DB_NAME},
        ).first()
        self._table_available = bool(exists)
        return self._table_available

    def registrar_movimiento(
        self,
        db: Session,
        *,
        vehiculo_id: int,
        tipo_movimiento: str,
        estado_anterior_id: Optional[int] = None,
        estado_nuevo_id: Optional[int] = None,
        origen_tipo: Optional[str] = None,
        origen_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
        observaciones: Optional[str] = None,
    ) -> bool:
        if not vehiculo_id:
            return False

        if not self._has_stock_movimientos(db):
            logger.debug("Tabla stock_movimientos no disponible; se omite historial de stock.")
            return False

        db.execute(
            text(
                """
                INSERT INTO stock_movimientos (
                    vehiculo_id,
                    estado_stock_anterior_id,
                    estado_stock_nuevo_id,
                    tipo_movimiento,
                    origen_tipo,
                    origen_id,
                    usuario_id,
                    observaciones
                ) VALUES (
                    :vehiculo_id,
                    :estado_anterior_id,
                    :estado_nuevo_id,
                    :tipo_movimiento,
                    :origen_tipo,
                    :origen_id,
                    :usuario_id,
                    :observaciones
                )
                """
            ),
            {
                "vehiculo_id": int(vehiculo_id),
                "estado_anterior_id": estado_anterior_id,
                "estado_nuevo_id": estado_nuevo_id,
                "tipo_movimiento": tipo_movimiento,
                "origen_tipo": origen_tipo,
                "origen_id": origen_id,
                "usuario_id": usuario_id,
                "observaciones": observaciones,
            },
        )
        self._audit.registrar(
            db,
            entidad="vehiculos",
            entidad_id=int(vehiculo_id),
            accion="STOCK_MOVIMIENTO",
            usuario_id=usuario_id,
            datos_previos={"estado_stock_id": estado_anterior_id},
            datos_nuevos={"estado_stock_id": estado_nuevo_id},
            contexto={
                "tipo_movimiento": tipo_movimiento,
                "origen_tipo": origen_tipo,
                "origen_id": origen_id,
                "observaciones": observaciones,
            },
        )
        return True

    def cambiar_estado(
        self,
        db: Session,
        *,
        vehiculo_id: int,
        estado_nuevo_id: int,
        tipo_movimiento: str,
        origen_tipo: Optional[str] = None,
        origen_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
        observaciones: Optional[str] = None,
        estado_requerido_id: Optional[int] = None,
    ) -> bool:
        row = db.execute(
            text(
                """
                SELECT id, estado_stock_id
                FROM vehiculos
                WHERE id = :vehiculo_id
                LIMIT 1
                """
            ),
            {"vehiculo_id": vehiculo_id},
        ).mappings().first()

        if not row:
            raise ValueError("El vehiculo no existe.")

        estado_anterior_id = row.get("estado_stock_id")
        if (
            estado_requerido_id is not None
            and int(estado_anterior_id or 0) != int(estado_requerido_id)
        ):
            raise ValueError("El vehiculo no esta en el estado requerido.")

        db.execute(
            text(
                """
                UPDATE vehiculos
                SET estado_stock_id = :estado_nuevo_id
                WHERE id = :vehiculo_id
                """
            ),
            {
                "estado_nuevo_id": estado_nuevo_id,
                "vehiculo_id": vehiculo_id,
            },
        )

        return self.registrar_movimiento(
            db,
            vehiculo_id=vehiculo_id,
            tipo_movimiento=tipo_movimiento,
            estado_anterior_id=estado_anterior_id,
            estado_nuevo_id=estado_nuevo_id,
            origen_tipo=origen_tipo,
            origen_id=origen_id,
            usuario_id=usuario_id,
            observaciones=observaciones,
        )
