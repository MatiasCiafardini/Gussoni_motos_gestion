from __future__ import annotations
from typing import Dict, Tuple


def validar_usuario(
    data: Dict,
    *,
    modo: str = "alta",  # "alta" | "edicion"
) -> Tuple[bool, Dict[str, str]]:
    """
    Validaciones comunes de Usuarios.
    Devuelve (ok, errores_por_campo)
    """

    errs: Dict[str, str] = {}

    # -------- Nombre --------
    if not data.get("nombre"):
        errs["nombre"] = "El nombre es obligatorio."

    # -------- Usuario --------
    if not data.get("usuario"):
        errs["usuario"] = "El nombre de usuario es obligatorio."

    # -------- Rol --------
    if not data.get("rol_id") and not data.get("rol"):
        errs["rol"] = "Seleccioná un rol."

    # -------- Estado --------
    if "estado_id" in data:
        if data.get("estado_id") not in (0, 1):
            errs["estado_id"] = "Seleccioná el estado."
    elif "activo" in data:
        if data.get("activo") not in (0, 1):
            errs["activo"] = "Seleccioná el estado."

    # -------- Email --------
    email = data.get("email")
    if email:
        if "@" not in email or "." not in email.split("@")[-1]:
            errs["email"] = "Email inválido."

    # -------- Password (solo alta) --------
    if modo == "alta":
        pwd = data.get("password")
        pwd2 = data.get("password2")

        if not pwd or len(pwd) < 4:
            errs["password"] = "La contraseña debe tener al menos 4 caracteres."

        if pwd != pwd2:
            errs["password2"] = "Las contraseñas no coinciden."

    return (len(errs) == 0, errs)
