from __future__ import annotations

from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.data.database import SessionLocal
from app.repositories.usuarios_repository import UsuariosRepository
from app.core.security import verify_password


class AuthService:
    """Simple authentication facade for the desktop client."""

    def _repo(self, db: Optional[Session] = None) -> UsuariosRepository:
        return UsuariosRepository(db or SessionLocal())

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip()
        if not username or not password:
            return None

        db = SessionLocal()
        try:
            repo = self._repo(db)
            user = repo.get_by_username(username)
            if not user:
                return None

            stored = user.get("contrasenia_hash") or ""
            if not verify_password(password, stored):
                return None

            user.pop("contrasenia_hash", None)
            return user
        finally:
            db.close()
