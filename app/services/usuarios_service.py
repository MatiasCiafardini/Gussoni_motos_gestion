from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

# Asumiendo que SessionLocal está disponible
from app.data.database import SessionLocal 
from app.repositories.usuarios_repository import UsuariosRepository
#from app.utils.security import hash_password, verify_password # << Hashing externo Stefano

class UsuariosService:
    """Orquesta casos de uso de Usuarios, incluyendo hashing de contraseñas."""

    def _repo(self, db: Optional[Session] = None) -> UsuariosRepository:
        """Devuelve una instancia del repositorio de usuarios."""
        return UsuariosRepository(db or SessionLocal()) [9]

    # -------------------- Creación de Usuario --------------------
    def create_user(self, data: Dict[str, Any]) -> int:
        """
        Crea un usuario, hasheando la contraseña antes de persistir.
        """
        db = SessionLocal()
        try:
            payload = dict(data)
            
            # 1. Aplicar Hashing
            password_plana = payload.pop("contraseña", None)
            if not password_plana:
                raise ValueError("La contraseña es obligatoria.")
                
            payload["contraseña_hash"] = ""#hash_password(password_plana) # Lógica de Hashing (Paso 1)

            # 2. Normalizaciones y valores por defecto
            payload["email"] = str(payload.get("email", "")).strip().lower() or None
            
            # Asegurar que 'activo' sea un booleano/entero
            if payload.get("activo") is None:
                payload["activo"] = 1 # Por defecto activo
                
            # Asignar fecha de creación (si la DB no lo hace automáticamente)
            # Aunque MySQL lo suele hacer, podemos forzarlo en Python si es necesario.
            # Aquí lo omitimos, esperando que la base de datos lo maneje o se agregue al payload.
            
            new_id = self._repo(db).create_user(payload)
            db.commit() [10]
            return new_id
        except Exception:
            db.rollback() [10]
            raise
        finally:
            db.close()

    # -------------------- Autenticación (Login) --------------------
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Busca al usuario y verifica la contraseña hasheada.
        """
        db = SessionLocal()
        try:
            user = self._repo(db).get_by_username(username)
            
            if user: #and verify_password(password, user.get("contraseña_hash", "")): Stefano
                # Retornar el usuario sin el hash de la contraseña por seguridad
                user.pop("contraseña_hash", None)
                return user
            
            return None
        finally:
            db.close()
            
    # -------------------- Modificación de Usuario --------------------
    def update_user(self, user_id: int, data: Dict[str, Any]) -> int:
        """
        Actualiza los datos del usuario. Hashea la contraseña si se está modificando.
        """
        db = SessionLocal()
        try:
            payload = dict(data)
            
            # Si se proporciona una nueva contraseña, la hasheamos
            password_plana = payload.pop("contraseña", None)
            if password_plana:
                payload["contraseña_hash"] = ""#hash_password(password_plana)Stefano
            
            # Normalizaciones
            if "email" in payload:
                payload["email"] = str(payload["email"]).strip().lower() or None
            
            rc = self._repo(db).update(user_id, payload)
            db.commit() [10]
            return rc
        except Exception:
            db.rollback() [10]
            raise
        finally:
            db.close()
            
    # -------------------- Búsqueda y Listado --------------------
    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Delega la búsqueda al repositorio."""
        db = SessionLocal() [11]
        try:
            repo = self._repo(db)
            rows, total = repo.search(**filtros, page=page, page_size=page_size)
            
            # Limpiar hashes de contraseña de los resultados antes de devolver
            for row in rows:
                row.pop("contraseña_hash", None)
                
            return rows, total
        finally:
            db.close() [11]

    def get_estados_stock(self) -> List[Dict[str, Any]]:
        return self._catalogos.get_estados_stock()
