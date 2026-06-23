from __future__ import annotations

from typing import Mapping, Optional

from app.core.domain_constants import RolUsuario


PERM_VER_USUARIOS = "usuarios.ver"
PERM_VER_CONFIGURACION = "configuracion.ver"
PERM_VER_REPORTES = "reportes.ver"
PERM_VER_FACTURACION = "facturacion.ver"
PERM_VER_STOCK = "stock.ver"

ALL_PERMISSIONS = frozenset(
    {
        PERM_VER_USUARIOS,
        PERM_VER_CONFIGURACION,
        PERM_VER_REPORTES,
        PERM_VER_FACTURACION,
        PERM_VER_STOCK,
    }
)

# Etapa 1: el cliente no usa permisos granulares todavia.
# Vendedor conserva acceso completo para no cambiar el flujo operativo actual.
ROLE_PERMISSIONS = {
    RolUsuario.ADMIN: ALL_PERMISSIONS,
    RolUsuario.VENDEDOR: ALL_PERMISSIONS,
}


def normalize_role(role: Optional[str]) -> str:
    return (role or "").strip().lower()


def user_has_permission(user: Optional[Mapping], permission: str) -> bool:
    if not user:
        return False

    role = normalize_role(str(user.get("rol") or ""))
    permissions = ROLE_PERMISSIONS.get(role, ALL_PERMISSIONS)
    return permission in permissions
