from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


class AuditLogService:
    """Registra auditoria si la tabla existe, sin romper el flujo si falta."""

    def __init__(self) -> None:
        self._table_available: Optional[bool] = None

    def _has_audit_log(self, db: Session) -> bool:
        if self._table_available is not None:
            return self._table_available

        exists = db.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = 'audit_log'
                LIMIT 1
                """
            ),
            {"schema": settings.DB_NAME},
        ).first()
        self._table_available = bool(exists)
        return self._table_available

    def registrar(
        self,
        db: Session,
        *,
        entidad: str,
        accion: str,
        entidad_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
        datos_previos: Any = None,
        datos_nuevos: Any = None,
        contexto: Any = None,
    ) -> bool:
        if not entidad or not accion:
            return False

        if not self._has_audit_log(db):
            logger.debug("Tabla audit_log no disponible; se omite auditoria.")
            return False

        db.execute(
            text(
                """
                INSERT INTO audit_log (
                    entidad,
                    entidad_id,
                    accion,
                    usuario_id,
                    datos_previos,
                    datos_nuevos,
                    contexto
                ) VALUES (
                    :entidad,
                    :entidad_id,
                    :accion,
                    :usuario_id,
                    :datos_previos,
                    :datos_nuevos,
                    :contexto
                )
                """
            ),
            {
                "entidad": entidad,
                "entidad_id": entidad_id,
                "accion": accion[:40],
                "usuario_id": usuario_id,
                "datos_previos": self._json_or_none(datos_previos),
                "datos_nuevos": self._json_or_none(datos_nuevos),
                "contexto": self._json_or_none(contexto),
            },
        )
        return True

    @staticmethod
    def _json_or_none(value: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, default=str, ensure_ascii=False)
