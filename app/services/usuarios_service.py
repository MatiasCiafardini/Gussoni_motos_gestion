# app/services/usuarios_service.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.data.database import SessionLocal
from app.repositories.usuarios_repository import UsuariosRepository
from app.core.security import hash_password


def _coerce_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("id")
    try:
        return int(v)
    except Exception:
        return None


def _hash_password(pwd: Optional[str]) -> Optional[str]:
    """Wrapper to keep backwards compatibility with existing imports."""
    if not pwd:
        return None
    return hash_password(pwd)


def _rol_texto_from_id(rol_id: Optional[int]) -> Optional[str]:
    if rol_id is None:
        return None
    return "admin" if rol_id == 1 else "vendedor"


class UsuariosService:
    """Orquesta casos de uso de Usuarios."""

    # -------------------- Infra --------------------
    def _repo(self, db: Optional[Session] = None) -> UsuariosRepository:
        return UsuariosRepository(db or SessionLocal())

    # -------------------- Catálogos --------------------
    def get_roles(self) -> List[Dict[str, Any]]:
        """
        Devuelve lista de roles para combos.
        Delegado al repositorio para mantener una sola fuente.
        """
        db = SessionLocal()
        try:
            return self._repo(db).get_roles()
        finally:
            db.close()

    def get_estados(self) -> List[Dict[str, Any]]:
        """
        Devuelve estados (Activo/Inactivo) para combos.
        """
        db = SessionLocal()
        try:
            return self._repo(db).get_estados()
        finally:
            db.close()

    # -------------------- Search / CRUD --------------------
    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Recibe un dict de filtros (nombre, username, email, rol_id, estado_id, etc.)
        y delega al repositorio.

        Importante: Pasamos el dict completo como primer argumento para aprovechar
        la compatibilidad del repositorio (detecta dict y mapea automáticamente),
        evitando olvidar campos nuevos en el futuro.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            rows, total = repo.search(filtros, page=page, page_size=page_size)
            return rows, total
        finally:
            db.close()

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            return self._repo(db).get_by_id(user_id)
        finally:
            db.close()

    def update(self, user_id: int, data: Dict[str, Any]) -> int:
        """
        Actualiza un usuario. `data` debe usar nombres de columna de DB
        (ej.: nombre, usuario, email, rol, activo, contrasenia_hash).
        """
        db = SessionLocal()
        try:
            rc = self._repo(db).update(user_id, data)
            db.commit()
            return rc
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def change_password(self, user_id: int, new_password: str) -> None:
        """Actualiza la contraseña del usuario aplicando el hash configurado."""
        if not new_password or not new_password.strip():
            raise ValueError("La contraseña no puede estar vacía.")

        hashed = _hash_password(new_password)
        if not hashed:
            raise ValueError("No fue posible generar el hash de la contraseña.")

        db = SessionLocal()
        try:
            repo = self._repo(db)
            repo.update(user_id, {"contrasenia_hash": hashed})
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_usuario(self, data: Dict[str, Any]) -> int:
        """
        Crea un usuario y devuelve el ID insertado.
        Se adapta al nombre del método que tenga el repositorio:
        - create_usuario / create / add_usuario / add / insert_usuario / insert
        Fallback: usa SELECT LAST_INSERT_ID() si el repo no devuelve el ID.

        Campos esperados desde la UI (flexible):
        - nombre, usuario, email (opcional)
        - rol_id (1=admin, 2=vendedor) o rol (texto)
        - estado_id (1=activo, 0=inactivo) o activo (0/1)
        - password (opcional) → se convierte en contrasenia_hash
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)

            # ------- Normalizaciones mínimas -------
            payload = dict(data)

            # Mapear rol/estado si vienen como *_id desde la UI
            if "rol" not in payload:
                payload["rol"] = _rol_texto_from_id(_coerce_int(payload.get("rol_id")))
            if "activo" not in payload and "estado_id" in payload:
                eid = _coerce_int(payload.get("estado_id"))
                payload["activo"] = 1 if eid == 1 else 0 if eid is not None else None

            # Generar hash si viene password
            pwd = payload.pop("password", None) or payload.pop("contrasenia", None)
            if "contrasenia_hash" not in payload:
                ch = _hash_password(pwd)
                if ch:
                    payload["contrasenia_hash"] = ch

            # Evitar strings vacíos para campos claves
            for k in ("nombre", "usuario", "rol", "email"):
                if payload.get(k) == "":
                    payload[k] = None
            if payload.get("activo") in ("", " "):
                payload["activo"] = None

            # ------- Resolución de método en el repo -------
            method_names = [
                "create_usuario", "create",
                "add_usuario", "add",
                "insert_usuario", "insert",
            ]
            fn = None
            for name in method_names:
                cand = getattr(repo, name, None)
                if callable(cand):
                    fn = cand
                    break

            if fn is None:
                raise AttributeError(
                    "UsuariosRepository no implementa un método de creación compatible "
                    "(esperado: create_usuario/create/add_usuario/add/insert_usuario/insert)"
                )

            result = fn(payload)

            # Intentamos deducir el ID devuelto
            new_id: Optional[int] = None
            if isinstance(result, int):
                new_id = result
            elif isinstance(result, dict) and "id" in result:
                try:
                    new_id = int(result["id"])
                except Exception:
                    new_id = None

            # Fallback: obtener LAST_INSERT_ID() en esta misma sesión
            if not new_id:
                try:
                    new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
                    if new_id is not None:
                        new_id = int(new_id)
                except Exception:
                    new_id = None

            if not new_id:
                raise RuntimeError("No se pudo determinar el ID del nuevo usuario insertado.")

            db.commit()
            return int(new_id)

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
