from __future__ import annotations

from typing import Optional, Dict, Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.data.database import SessionLocal
from app.repositories.usuarios_repository import UsuariosRepository
from app.core.security import verify_password


class AuthServiceDatabaseError(RuntimeError):
    """Raised when credentials cannot be checked because the database failed."""


class AuthService:
    """Simple authentication facade for the desktop client."""

    def _repo(self, db: Optional[Session] = None) -> UsuariosRepository:
        return UsuariosRepository(db or SessionLocal())

    @staticmethod
    def _is_active_user(user: Dict[str, Any]) -> bool:
        raw = user.get("activo")
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, int):
            return raw == 1
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "activo", "active", "si"}
        return False

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip()
        if not username or not password:
            return None

        db: Optional[Session] = None
        try:
            db = SessionLocal()
            repo = self._repo(db)
            user = repo.get_by_username(username)
            if not user:
                return None

            stored = user.get("contrasenia_hash") or ""
            if not verify_password(password, stored):
                return None

            if not self._is_active_user(user):
                return None

            user.pop("contrasenia_hash", None)
            return user
        except SQLAlchemyError as exc:
            raise AuthServiceDatabaseError(
                "No se pudo validar el usuario contra la base de datos."
            ) from exc
        finally:
            if db is not None:
                db.close()
